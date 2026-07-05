package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

// --- test harness ---------------------------------------------------------

type recordedReq struct {
	method string
	path   string
	body   map[string]any
}

// rehydrateStub is a recording gc API used to assert the exact replay sequence.
// resp lets a test inject a status + body per (path, nth-hit); returning
// status 0 means "use the default 200 with defaultBody".
type rehydrateStub struct {
	mu          sync.Mutex
	reqs        []recordedReq
	hits        map[string]int
	resp        func(path string, nth int) (int, string)
	defaultBody string
}

func newRehydrateStub(resp func(path string, nth int) (int, string)) *rehydrateStub {
	return &rehydrateStub{hits: map[string]int{}, resp: resp, defaultBody: `{}`}
}

func (s *rehydrateStub) server(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		var body map[string]any
		_ = json.Unmarshal(raw, &body)
		s.mu.Lock()
		s.hits[r.URL.Path]++
		nth := s.hits[r.URL.Path]
		s.reqs = append(s.reqs, recordedReq{method: r.Method, path: r.URL.Path, body: body})
		s.mu.Unlock()
		status, respBody := 200, s.defaultBody
		if s.resp != nil {
			if st, b := s.resp(r.URL.Path, nth); st != 0 {
				status, respBody = st, b
			}
		}
		w.WriteHeader(status)
		_, _ = w.Write([]byte(respBody))
	}))
	t.Cleanup(srv.Close)
	return srv
}

func (s *rehydrateStub) requestsFor(suffix string) []recordedReq {
	s.mu.Lock()
	defer s.mu.Unlock()
	var out []recordedReq
	for _, r := range s.reqs {
		if strings.HasSuffix(r.path, suffix) {
			out = append(out, r)
		}
	}
	return out
}

func (s *rehydrateStub) orderedSuffixes() []string {
	s.mu.Lock()
	defer s.mu.Unlock()
	var out []string
	for _, r := range s.reqs {
		i := strings.LastIndex(r.path, "/extmsg/")
		if i >= 0 {
			out = append(out, r.path[i:])
		}
	}
	return out
}

func writeConfig(t *testing.T, cityPath, contents string) {
	t.Helper()
	dir := filepath.Join(cityPath, ".gc", "services", "slack", "data")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "config.json"), []byte(contents), 0o644); err != nil {
		t.Fatal(err)
	}
}

func testConfig(cityPath, gcURL string) config {
	return config{cityPath: cityPath, gcAPIBase: gcURL, cityName: "sct-city"}
}

func noSleep(time.Duration) {}

const oversightConfigJSON = `{
  "version": 1,
  "bindings": {
    "room:C0BED9MRXH7": {
      "kind": "room",
      "conversation": {
        "scope_id": "sct-city",
        "provider": "slack",
        "account_id": "T0BF5GQ0DNU",
        "conversation_id": "C0BED9MRXH7",
        "kind": "room"
      },
      "group_id": "grp_old_123",
      "default_handle": "mayor",
      "fanout_policy": {"enabled": true, "allow_untargeted_publication": true, "max_peer_triggered_publishes": 8, "max_total_peer_deliveries": 24},
      "participants": [
        {"handle": "mayor", "session_name": "oversight-rig.mayor"},
        {"handle": "geo-pl", "session_name": "geo/oversight-rig.project-lead"}
      ],
      "binding_owner": "gc-77139",
      "binding_record": "bnd_old_456"
    }
  }
}`

// --- tests ----------------------------------------------------------------

func TestRehydrate_FullReplaySequence(t *testing.T) {
	stub := newRehydrateStub(func(path string, nth int) (int, string) {
		if strings.HasSuffix(path, "/extmsg/groups") {
			return 200, `{"ID":"grp_new_789"}`
		}
		return 0, ""
	})
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, oversightConfigJSON)

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.total != 1 || sum.restored != 1 || sum.failed != 0 {
		t.Fatalf("summary = %+v, want total1 restored1 failed0", sum)
	}

	// order: group, then both participants, then bind.
	got := stub.orderedSuffixes()
	want := []string{"/extmsg/groups", "/extmsg/participants", "/extmsg/participants", "/extmsg/bind"}
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("call order = %v, want %v", got, want)
	}

	// group body
	groups := stub.requestsFor("/extmsg/groups")
	if len(groups) != 1 {
		t.Fatalf("group calls = %d, want 1", len(groups))
	}
	gb := groups[0].body
	if gb["mode"] != "launcher" {
		t.Errorf("group mode = %v, want launcher", gb["mode"])
	}
	if gb["default_handle"] != "mayor" {
		t.Errorf("group default_handle = %v, want mayor", gb["default_handle"])
	}
	rc, _ := gb["root_conversation"].(map[string]any)
	if rc["conversation_id"] != "C0BED9MRXH7" {
		t.Errorf("root_conversation.conversation_id = %v", rc["conversation_id"])
	}
	if rc["account_id"] != "T0BF5GQ0DNU" {
		t.Errorf("root_conversation.account_id = %v", rc["account_id"])
	}
	fp, ok := gb["fanout_policy"].(map[string]any)
	if !ok {
		t.Fatalf("fanout_policy missing/wrong type: %v", gb["fanout_policy"])
	}
	if fp["enabled"] != true {
		t.Errorf("fanout_policy.enabled = %v, want true", fp["enabled"])
	}

	// participants use the RETURNED group id, not the stored stale one.
	parts := stub.requestsFor("/extmsg/participants")
	if len(parts) != 2 {
		t.Fatalf("participant calls = %d, want 2", len(parts))
	}
	seen := map[string]string{}
	for _, p := range parts {
		if p.body["group_id"] != "grp_new_789" {
			t.Errorf("participant group_id = %v, want returned grp_new_789 (not stored grp_old_123)", p.body["group_id"])
		}
		if p.body["public"] != true {
			t.Errorf("participant public = %v, want true", p.body["public"])
		}
		seen[p.body["handle"].(string)] = p.body["session_id"].(string)
	}
	if seen["mayor"] != "oversight-rig.mayor" || seen["geo-pl"] != "geo/oversight-rig.project-lead" {
		t.Errorf("participant handle→session map wrong: %v", seen)
	}

	// bind body
	binds := stub.requestsFor("/extmsg/bind")
	if len(binds) != 1 {
		t.Fatalf("bind calls = %d, want 1", len(binds))
	}
	if binds[0].body["session_id"] != "gc-77139" {
		t.Errorf("bind session_id = %v, want gc-77139", binds[0].body["session_id"])
	}
	bc, _ := binds[0].body["conversation"].(map[string]any)
	if bc["conversation_id"] != "C0BED9MRXH7" {
		t.Errorf("bind conversation_id = %v", bc["conversation_id"])
	}
}

func TestRehydrate_BindConflictTolerated(t *testing.T) {
	stub := newRehydrateStub(func(path string, nth int) (int, string) {
		if strings.HasSuffix(path, "/extmsg/groups") {
			return 200, `{"ID":"grp1"}`
		}
		if strings.HasSuffix(path, "/extmsg/bind") {
			// gc rejects a re-bind of an already-bound conversation.
			return 409, "ErrBindingConflict: conversation already bound"
		}
		return 0, ""
	})
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, oversightConfigJSON)

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	// A bind conflict is the desired already-bound state — still restored.
	if sum.restored != 1 || sum.failed != 0 {
		t.Fatalf("summary = %+v, want restored1 failed0 (conflict tolerated)", sum)
	}
	// The conflict is a 4xx, so it must NOT have been retried.
	if n := len(stub.requestsFor("/extmsg/bind")); n != 1 {
		t.Errorf("bind attempts = %d, want 1 (409 is terminal, tolerated)", n)
	}
}

func TestRehydrate_GroupFailureCountsAsFailed(t *testing.T) {
	stub := newRehydrateStub(func(path string, nth int) (int, string) {
		if strings.HasSuffix(path, "/extmsg/groups") {
			return 500, "gc down"
		}
		return 0, ""
	})
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, oversightConfigJSON)

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.total != 1 || sum.restored != 0 || sum.failed != 1 {
		t.Fatalf("summary = %+v, want total1 restored0 failed1", sum)
	}
	// group retried up to maxAttempts; participants/bind never reached.
	if n := len(stub.requestsFor("/extmsg/groups")); n != 3 {
		t.Errorf("group attempts = %d, want 3 (retried to exhaustion)", n)
	}
	if n := len(stub.requestsFor("/extmsg/participants")); n != 0 {
		t.Errorf("participant calls = %d, want 0 (group never succeeded)", n)
	}
}

func TestRehydrate_5xxOnGroupThenSucceeds(t *testing.T) {
	stub := newRehydrateStub(func(path string, nth int) (int, string) {
		if strings.HasSuffix(path, "/extmsg/groups") {
			if nth < 3 {
				return 500, "transient"
			}
			return 200, `{"ID":"grp1"}`
		}
		return 0, ""
	})
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, oversightConfigJSON)

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(5), noSleep)

	if sum.restored != 1 {
		t.Fatalf("summary = %+v, want restored1 after transient 5xx", sum)
	}
	if n := len(stub.requestsFor("/extmsg/groups")); n != 3 {
		t.Errorf("group attempts = %d, want 3 (2 x 500 then 200)", n)
	}
}

func TestRehydrate_NoOwnerNoFanout(t *testing.T) {
	const cfgJSON = `{
      "bindings": {
        "room:C1": {
          "kind": "room",
          "conversation": {"scope_id":"sct-city","provider":"slack","account_id":"T0","conversation_id":"C1","kind":"room"},
          "group_id": "g1",
          "default_handle": "solo",
          "fanout_policy": null,
          "participants": [{"handle":"solo","session_name":"rig.solo"}],
          "binding_owner": null,
          "binding_record": null
        }
      }
    }`
	stub := newRehydrateStub(func(path string, nth int) (int, string) {
		if strings.HasSuffix(path, "/extmsg/groups") {
			return 200, `{"ID":"g1"}`
		}
		return 0, ""
	})
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, cfgJSON)

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.restored != 1 {
		t.Fatalf("summary = %+v, want restored1", sum)
	}
	// no owner → no bind call.
	if n := len(stub.requestsFor("/extmsg/bind")); n != 0 {
		t.Errorf("bind calls = %d, want 0 (no binding_owner)", n)
	}
	// null fanout_policy → key omitted from the group body.
	groups := stub.requestsFor("/extmsg/groups")
	if len(groups) != 1 {
		t.Fatalf("group calls = %d, want 1", len(groups))
	}
	if _, present := groups[0].body["fanout_policy"]; present {
		t.Errorf("fanout_policy should be omitted when null, got %v", groups[0].body["fanout_policy"])
	}
}

func TestRehydrate_MissingConfigIsNoOp(t *testing.T) {
	stub := newRehydrateStub(nil)
	srv := stub.server(t)
	cityPath := t.TempDir() // no config.json written

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.total != 0 || sum.restored != 0 || sum.failed != 0 {
		t.Fatalf("summary = %+v, want all zero on missing config", sum)
	}
	if len(stub.reqs) != 0 {
		t.Errorf("made %d gc calls, want 0 on missing config", len(stub.reqs))
	}
}

func TestRehydrate_EmptyBindingsIsNoOp(t *testing.T) {
	stub := newRehydrateStub(nil)
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, `{"version":1,"bindings":{}}`)

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.total != 0 {
		t.Fatalf("summary = %+v, want zero on empty bindings", sum)
	}
	if len(stub.reqs) != 0 {
		t.Errorf("made %d gc calls, want 0", len(stub.reqs))
	}
}

func TestRehydrate_NoCityPathIsNoOp(t *testing.T) {
	stub := newRehydrateStub(nil)
	srv := stub.server(t)

	sum := rehydrateBindingsWith(testConfig("", srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.total != 0 {
		t.Fatalf("summary = %+v, want zero when GC_CITY_PATH unset", sum)
	}
	if len(stub.reqs) != 0 {
		t.Errorf("made %d gc calls, want 0 with no cityPath", len(stub.reqs))
	}
}

func TestRehydrate_CorruptConfigIsNoOp(t *testing.T) {
	stub := newRehydrateStub(nil)
	srv := stub.server(t)
	cityPath := t.TempDir()
	writeConfig(t, cityPath, `{"bindings": {`) // truncated JSON

	sum := rehydrateBindingsWith(testConfig(cityPath, srv.URL), srv.Client(), fastRetry(3), noSleep)

	if sum.total != 0 || sum.failed != 0 {
		t.Fatalf("summary = %+v, want zero on corrupt config (no crash, no calls)", sum)
	}
	if len(stub.reqs) != 0 {
		t.Errorf("made %d gc calls, want 0 on corrupt config", len(stub.reqs))
	}
}

func TestHasFanoutPolicy(t *testing.T) {
	cases := map[string]bool{
		``:                 false,
		`null`:             false,
		`  null `:          false,
		`{}`:               true,
		`{"enabled":true}`: true,
	}
	for in, want := range cases {
		if got := hasFanoutPolicy(json.RawMessage(in)); got != want {
			t.Errorf("hasFanoutPolicy(%q) = %v, want %v", in, got, want)
		}
	}
}

func TestIsBindingConflict(t *testing.T) {
	yes := []string{
		"rehydrate-bind: 409 Conflict: x",
		"bind: ErrBindingConflict",
		"already bound to this conversation",
	}
	for _, s := range yes {
		if !isBindingConflict(errString(s)) {
			t.Errorf("isBindingConflict(%q) = false, want true", s)
		}
	}
	no := []string{
		"500 Internal Server Error",
		"connection refused",
		"404 not found",
	}
	for _, s := range no {
		if isBindingConflict(errString(s)) {
			t.Errorf("isBindingConflict(%q) = true, want false", s)
		}
	}
	if isBindingConflict(nil) {
		t.Error("isBindingConflict(nil) = true, want false")
	}
}

type errString string

func (e errString) Error() string { return string(e) }
