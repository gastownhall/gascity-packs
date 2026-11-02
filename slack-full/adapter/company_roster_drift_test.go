package main

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// company_roster_drift_test.go — live-membership eligibility overlay coverage.
// A stale directory roster that would terminalize a native mention as
// mentioned_no_eligible still wakes a mentioned directory agent whose bot is a
// GENUINE live channel member. The overlay only ADDS availability: a non-member,
// a membership-probe failure, and every ambient path are unaffected. It resolves
// the session via an existing room binding first and dm_bindings otherwise,
// increments company_roster_drift_wakes, and honors a 5-minute per-channel
// membership cache (one Slack call per channel per TTL under a mention burst).

// countingMembersProbe returns a channelMembersProbe that hands back a fixed live
// member set (or a failure) and counts its invocations, so a test can assert both
// the eligibility outcome and the cache behavior.
func countingMembersProbe(members map[string]bool, ok bool, calls *int32) func(string) (map[string]bool, bool) {
	return func(string) (map[string]bool, bool) {
		atomic.AddInt32(calls, 1)
		if !ok {
			return nil, false
		}
		return members, true
	}
}

func driftMention(botUserID string) string {
	return "<@" + botUserID + "> please take a look"
}

// TestRosterDriftOverlayWakesViaRoomBinding — a member excluded only by a stale
// mention_wake, mentioned and live, wakes via its EXISTING room binding (room
// bindings win over dm_bindings).
func TestRosterDriftOverlayWakesViaRoomBinding(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Rooms[0].MentionWake = []string{"ollie"} // riley is a member but NOT mention-eligible
	bf := baseBindingsFile()                    // riley-main room binding present
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{botRiley: true}, true, &calls)
	h.openBarrier()

	ts := "1700000000.020010"
	if _, handled := h.admitViaHandler(t, humanMessage(ts, driftMention(botRiley)), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	r, _ := h.gw.store().Get(roomOrigin(ts))
	if r.Status != ingressStatusDelivered {
		t.Fatalf("status = %q, want delivered (live member admitted)", r.Status)
	}
	sc := gc.sessionCalls()
	if len(sc) != 1 || !strings.Contains(sc[0].path, "/session/riley-main/") {
		t.Fatalf("session calls = %+v, want one to riley-main (existing room binding wins)", sc)
	}
	if ptr := readPointer(t, h, "riley-main"); ptr.RosterDriftOverlay {
		t.Error("pointer roster_drift_overlay = true, want false (room binding, ordinary turn)")
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 1 {
		t.Errorf("company_roster_drift_wakes = %d, want 1", got)
	}
	if n := atomic.LoadInt32(&calls); n != 1 {
		t.Errorf("membership probes = %d, want 1", n)
	}
}

// TestRosterDriftOverlayWakesViaDMBindingFallback — a directory agent that is NOT
// a room member (the workspace-admin-invited-a-new-app case), mentioned and live,
// with no room binding, wakes via its canonical dm_bindings session.
func TestRosterDriftOverlayWakesViaDMBindingFallback(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Agents = append(df.Agents, CompanyAgent{Name: "quinn", AppID: "A0AAAAAA3", BotUserID: "U0AAAAAA3"})
	bf := baseBindingsFile() // no room binding for quinn
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	h.gw.dmBindStore = loadDMBindingsStore(t, h, dmBindingsFile{
		SchemaVersion: 1,
		DMBindings:    []DMBinding{{Agent: "quinn", Session: "quinn-dm"}},
	})
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{"U0AAAAAA3": true}, true, &calls)
	h.openBarrier()

	ts := "1700000000.020020"
	if _, handled := h.admitViaHandler(t, humanMessage(ts, driftMention("U0AAAAAA3")), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	r, _ := h.gw.store().Get(roomOrigin(ts))
	if r.Status != ingressStatusDelivered {
		t.Fatalf("status = %q, want delivered (dm-binding session)", r.Status)
	}
	sc := gc.sessionCalls()
	if len(sc) != 1 || !strings.Contains(sc[0].path, "/session/quinn-dm/") {
		t.Fatalf("session calls = %+v, want one to quinn-dm (dm_bindings fallback)", sc)
	}
	// The pointer and the immutable record both carry the overlay mark, so the
	// reply verb accepts quinn-dm for this turn instead of refusing it.
	ptr := readPointer(t, h, "quinn-dm")
	if !ptr.RosterDriftOverlay || ptr.Kind != wakeKindTargeted || ptr.Agent != "quinn" {
		t.Fatalf("pointer = %+v, want a targeted quinn turn with roster_drift_overlay", ptr)
	}
	rec, err := os.ReadFile(filepath.Join(h.turnsDir, "by-ref", ptr.TurnRef+".json"))
	if err != nil {
		t.Fatalf("immutable turn record: %v", err)
	}
	if !strings.Contains(string(rec), `"roster_drift_overlay": true`) {
		t.Errorf("immutable turn record lacks roster_drift_overlay:\n%s", rec)
	}
	for _, td := range r.Targets {
		if td.Session == "quinn-dm" && !td.RosterDriftOverlay {
			t.Errorf("receipt target %+v lacks roster_drift_overlay", td)
		}
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 1 {
		t.Errorf("company_roster_drift_wakes = %d, want 1", got)
	}
}

// TestRosterDriftOverlayUnboundStaysFailedDMUnbound — an overlay-admitted agent
// with neither a room binding nor a dm binding fails failed_dm_unbound
// (redrive-recoverable), never a silent drop; the admission is still counted.
func TestRosterDriftOverlayUnboundStaysFailedDMUnbound(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Agents = append(df.Agents, CompanyAgent{Name: "quinn", AppID: "A0AAAAAA3", BotUserID: "U0AAAAAA3"})
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{"U0AAAAAA3": true}, true, &calls)
	h.openBarrier()

	ts := "1700000000.020025"
	if _, handled := h.admitViaHandler(t, humanMessage(ts, driftMention("U0AAAAAA3")), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	r, _ := h.gw.store().Get(roomOrigin(ts))
	if r.Status != ingressStatusFailed {
		t.Fatalf("status = %q, want failed (overlay-admitted but unbound)", r.Status)
	}
	if n := len(gc.sessionCalls()); n != 0 {
		t.Fatalf("delivered %d sessions, want 0 (no binding anywhere)", n)
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 1 {
		t.Errorf("company_roster_drift_wakes = %d, want 1 (drift is real even when unbound)", got)
	}
	if len(r.Targets) != 1 {
		t.Fatalf("targets = %d, want 1", len(r.Targets))
	}
	for _, td := range r.Targets {
		if td.Detail != companyReasonFailedDMUnbound {
			t.Errorf("target detail = %q, want %q", td.Detail, companyReasonFailedDMUnbound)
		}
	}
}

// TestRosterDriftOverlayNonMemberStaysNoEligible — a mentioned agent that is NOT
// a live channel member stays fail-closed mentioned_no_eligible even though the
// membership check ran.
func TestRosterDriftOverlayNonMemberStaysNoEligible(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Rooms[0].MentionWake = []string{"ollie"}
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{botOllie: true}, true, &calls) // riley NOT live
	h.openBarrier()

	ts := "1700000000.020030"
	if _, handled := h.admitViaHandler(t, humanMessage(ts, driftMention(botRiley)), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	r, _ := h.gw.store().Get(roomOrigin(ts))
	if r.Status != ingressStatusNoDelivery || r.Reason != wakeReasonMentionedNoEligible {
		t.Fatalf("status/reason = %q/%q, want no_delivery/mentioned_no_eligible", r.Status, r.Reason)
	}
	if n := len(gc.sessionCalls()); n != 0 {
		t.Fatalf("woke %d sessions, want 0", n)
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 0 {
		t.Errorf("company_roster_drift_wakes = %d, want 0 (not a live member)", got)
	}
	if n := atomic.LoadInt32(&calls); n != 1 {
		t.Errorf("membership probes = %d, want 1 (checked, then fell closed)", n)
	}
}

// TestRosterDriftOverlayProbeFailureFallsClosed — a membership-check failure
// (network, 429, missing scope) falls back to today's mentioned_no_eligible; the
// check can only add availability, never block.
func TestRosterDriftOverlayProbeFailureFallsClosed(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Rooms[0].MentionWake = []string{"ollie"}
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(nil, false, &calls) // membership API failure
	h.openBarrier()

	ts := "1700000000.020040"
	if _, handled := h.admitViaHandler(t, humanMessage(ts, driftMention(botRiley)), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	r, _ := h.gw.store().Get(roomOrigin(ts))
	if r.Status != ingressStatusNoDelivery || r.Reason != wakeReasonMentionedNoEligible {
		t.Fatalf("status/reason = %q/%q, want no_delivery/mentioned_no_eligible (probe failure → old behavior)", r.Status, r.Reason)
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 0 {
		t.Errorf("company_roster_drift_wakes = %d, want 0", got)
	}
}

// TestRosterDriftOverlayAmbientUnaffected — an unmentioned human message routes
// the roster-only ambient set and NEVER fires the live-membership probe.
func TestRosterDriftOverlayAmbientUnaffected(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{botRiley: true}, true, &calls)
	h.openBarrier()

	ts := "1700000000.020050"
	if _, handled := h.admitViaHandler(t, humanMessage(ts, "good morning team"), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	r, _ := h.gw.store().Get(roomOrigin(ts))
	if r.Status != ingressStatusDelivered {
		t.Fatalf("status = %q, want delivered (ambient ollie)", r.Status)
	}
	sc := gc.sessionCalls()
	if len(sc) != 1 || !strings.Contains(sc[0].path, "/session/ollie-main/") {
		t.Fatalf("session calls = %+v, want one to ollie-main (ambient)", sc)
	}
	if n := atomic.LoadInt32(&calls); n != 0 {
		t.Errorf("membership probes = %d, want 0 (ambient path never probes)", n)
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 0 {
		t.Errorf("company_roster_drift_wakes = %d, want 0 (ambient)", got)
	}
}

// TestRosterDriftOverlayMembershipCacheTTL — a burst of stale-roster mentions to
// the same channel fires ONE probe within the TTL; a mention past the TTL
// re-probes.
func TestRosterDriftOverlayMembershipCacheTTL(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Rooms[0].MentionWake = []string{"ollie"}
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	now, _ := time.Parse(time.RFC3339, fixedNow)
	clk := &selfHealClock{t: now}
	h.gw.now = clk.now
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{botRiley: true}, true, &calls)
	h.openBarrier()

	for i, ts := range []string{"1700000000.020060", "1700000000.020061"} {
		if _, handled := h.admitViaHandler(t, humanMessage(ts, driftMention(botRiley)), 0); !handled {
			t.Fatalf("mention %d not handled", i)
		}
		h.wait()
	}
	if n := atomic.LoadInt32(&calls); n != 1 {
		t.Fatalf("membership probes within TTL = %d, want 1 (second mention hits cache)", n)
	}

	clk.advance(companyChannelMembersTTL + time.Second)
	if _, handled := h.admitViaHandler(t, humanMessage("1700000000.020062", driftMention(botRiley)), 0); !handled {
		t.Fatal("third mention not handled")
	}
	h.wait()
	if n := atomic.LoadInt32(&calls); n != 2 {
		t.Errorf("membership probes after TTL = %d, want 2 (cache expired)", n)
	}
	if got := h.gw.rosterDriftWakes.Load(); got != 3 {
		t.Errorf("company_roster_drift_wakes = %d, want 3 (all three admitted)", got)
	}
}

// TestRosterDriftOverlayHealthzCounter — the admitted-wake counter surfaces on
// /healthz for operators.
func TestRosterDriftOverlayHealthzCounter(t *testing.T) {
	gc := newFakeGC(t)
	df := baseDirectoryFile()
	df.Rooms[0].MentionWake = []string{"ollie"}
	bf := baseBindingsFile()
	h := newCompanyHarness(t, gc.server.URL, &df, &bf, 4)
	setFixedClock(h)
	var calls int32
	h.gw.channelMembersProbe = countingMembersProbe(map[string]bool{botRiley: true}, true, &calls)
	h.openBarrier()

	if _, handled := h.admitViaHandler(t, humanMessage("1700000000.020070", driftMention(botRiley)), 0); !handled {
		t.Fatal("not handled")
	}
	h.wait()

	if detail := h.gw.healthzDetail(); !strings.Contains(detail, "company_roster_drift_wakes=1") {
		t.Errorf("healthz missing company_roster_drift_wakes=1: %q", detail)
	}
}

// ---- direct conversations.members probe (pagination / scope / rate limit) ----

func TestFetchChannelMembersPaginates(t *testing.T) {
	var reqs int32
	withSlackStub(t, func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&reqs, 1)
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Query().Get("cursor") == "" {
			_, _ = w.Write([]byte(`{"ok":true,"members":["U1","U2"],"response_metadata":{"next_cursor":"page2"}}`))
			return
		}
		_, _ = w.Write([]byte(`{"ok":true,"members":["U3"],"response_metadata":{"next_cursor":""}}`))
	})
	members, ok := fetchChannelMembers("xoxb-t", &http.Client{}, "C0AAAAAAA")
	if !ok {
		t.Fatal("ok=false, want true")
	}
	if !members["U1"] || !members["U2"] || !members["U3"] {
		t.Errorf("members = %v, want U1,U2,U3", members)
	}
	if n := atomic.LoadInt32(&reqs); n != 2 {
		t.Errorf("requests = %d, want 2 (two cursor pages)", n)
	}
}

func TestFetchChannelMembersMissingScopeFailsClosed(t *testing.T) {
	withSlackStub(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":false,"error":"missing_scope"}`))
	})
	if _, ok := fetchChannelMembers("xoxb-t", &http.Client{}, "C0AAAAAAA"); ok {
		t.Error("ok=true on missing_scope, want false (fail closed)")
	}
}

func TestFetchChannelMembersHonorsOneRetryAfter(t *testing.T) {
	var reqs int32
	withSlackStub(t, func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if atomic.AddInt32(&reqs, 1) == 1 {
			w.Header().Set("Retry-After", "1")
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
		_, _ = w.Write([]byte(`{"ok":true,"members":["U1"],"response_metadata":{"next_cursor":""}}`))
	})
	members, ok := fetchChannelMembers("xoxb-t", &http.Client{}, "C0AAAAAAA")
	if !ok || !members["U1"] {
		t.Fatalf("ok=%v members=%v, want true with U1 (retried after 429)", ok, members)
	}
	if n := atomic.LoadInt32(&reqs); n != 2 {
		t.Errorf("requests = %d, want 2 (429 then success)", n)
	}
}

func TestFetchChannelMembersSecond429FailsClosed(t *testing.T) {
	var reqs int32
	withSlackStub(t, func(w http.ResponseWriter, r *http.Request) {
		atomic.AddInt32(&reqs, 1)
		w.Header().Set("Retry-After", "1")
		w.WriteHeader(http.StatusTooManyRequests)
	})
	if _, ok := fetchChannelMembers("xoxb-t", &http.Client{}, "C0AAAAAAA"); ok {
		t.Error("ok=true after repeated 429, want false (one Retry-After honored, then fail closed)")
	}
	if n := atomic.LoadInt32(&reqs); n != 2 {
		t.Errorf("requests = %d, want 2 (initial + one retry)", n)
	}
}
