package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// stubExecRecord is one captured invocation by the fake exec.Command
// installed via dispatchExecCommand.
type stubExecRecord struct {
	Name string
	Args []string
	Dir  string
}

// installStubExecCommand replaces dispatchExecCommand with a fake that
// records the invocations and produces deterministic stdout per command
// name. It returns a pointer to the recorded slice and a restore func.
//
// `bd` invocations emit a JSON line containing {"id": bdID}; `gc`
// invocations emit a single OK line. Tests asserting failure modes can
// override behavior by inspecting Name/Args before this stub returns.
func installStubExecCommand(t *testing.T, bdID string, gcExitCode int) (*[]stubExecRecord, func()) {
	t.Helper()
	prev := dispatchExecCommand
	var records []stubExecRecord

	dispatchExecCommand = func(name string, args ...string) *exec.Cmd {
		records = append(records, stubExecRecord{Name: name, Args: append([]string(nil), args...)})

		// Each invocation routes to a tiny shell script that echoes a
		// canned line so the dispatcher can parse JSON from `bd create`
		// and proceed past `gc sling`.
		var script string
		switch name {
		case "bd":
			script = "printf '%s\\n' '" + `{"id":"` + bdID + `","title":"x","type":"task"}` + "'"
		case "gc":
			if gcExitCode != 0 {
				script = "echo gc-fail >&2; exit 1"
			} else {
				script = "echo ok"
			}
		default:
			script = "echo unhandled-stub-cmd: " + name
		}
		c := exec.Command("sh", "-c", script)
		// Caller will set Dir.
		return c
	}
	return &records, func() { dispatchExecCommand = prev }
}

// seedRoutesJSONL writes a routes.jsonl with the supplied prefix→relpath
// pairs (path is relative to cityPath; absolute when starting with /).
// Returns cityPath.
func seedRoutesJSONL(t *testing.T, cityPath string, entries map[string]string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Join(cityPath, ".beads"), 0o700); err != nil {
		t.Fatalf("mkdir .beads: %v", err)
	}
	var lines []string
	for prefix, p := range entries {
		b, err := json.Marshal(struct {
			Prefix string `json:"prefix"`
			Path   string `json:"path"`
		}{Prefix: prefix, Path: p})
		if err != nil {
			t.Fatalf("marshal route: %v", err)
		}
		lines = append(lines, string(b))
	}
	if err := os.WriteFile(filepath.Join(cityPath, ".beads", "routes.jsonl"),
		[]byte(strings.Join(lines, "\n")+"\n"), 0o600); err != nil {
		t.Fatalf("write routes.jsonl: %v", err)
	}
}

// capturedViewsOpen records a single observed views.open call body.
type capturedViewsOpen struct {
	Authorization string
	Body          string
}

// installFakeSlackAPI starts an httptest server that responds to
// /views.open with `{"ok":true}` (or the supplied response) and
// captures the request body+auth header. Returns the cleanup func and
// the channel where captures land. The slackAPIBase package var is
// rewritten to point at the fake; the cleanup restores the original.
func installFakeSlackAPI(t *testing.T, response string) (chan capturedViewsOpen, func()) {
	t.Helper()
	if response == "" {
		response = `{"ok":true}`
	}
	captures := make(chan capturedViewsOpen, 4)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		raw, _ := io.ReadAll(r.Body)
		select {
		case captures <- capturedViewsOpen{
			Authorization: r.Header.Get("Authorization"),
			Body:          string(raw),
		}:
		default:
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(response))
	}))
	prev := slackAPIBase
	slackAPIBase = srv.URL
	cleanup := func() {
		slackAPIBase = prev
		srv.Close()
	}
	return captures, cleanup
}

// signedSlashRequestForRig builds a signed slash-command request with
// trigger_id set so the modal-opening branch can fire views.open.
func signedSlashRequestForRig(t *testing.T, secret, teamID, channelID, command, text, userID, triggerID string) *http.Request {
	t.Helper()
	body := []byte(url.Values{
		"team_id":    {teamID},
		"channel_id": {channelID},
		"command":    {command},
		"text":       {text},
		"user_id":    {userID},
		"trigger_id": {triggerID},
	}.Encode())
	return signedSlackInteractionRequest(t, secret, body)
}

// rigViewSubmissionPayload wraps viewSubmissionPayloadJSON and injects a
// modal state.values shape that mirrors what Slack would send back from
// the rig-fix modal (one summary block + one optional context block).
func rigViewSubmissionPayload(t *testing.T, teamID, userID string, meta slackRigDispatchMetadata, summary, contextMd string) string {
	t.Helper()
	pm, err := encodeRigDispatchMetadata(meta)
	if err != nil {
		t.Fatalf("encode rig metadata: %v", err)
	}
	state := map[string]any{
		rigFixModalSummaryBlockID: map[string]any{
			rigFixModalSummaryActionID: map[string]string{
				"type":  "plain_text_input",
				"value": summary,
			},
		},
	}
	if contextMd != "" {
		state[rigFixModalContextBlockID] = map[string]any{
			rigFixModalContextActionID: map[string]string{
				"type":  "plain_text_input",
				"value": contextMd,
			},
		}
	}
	payload := map[string]any{
		"type":       "view_submission",
		"team":       map[string]string{"id": teamID, "domain": "x"},
		"user":       map[string]string{"id": userID},
		"trigger_id": "trig-1",
		"view": map[string]any{
			"id":               "V1",
			"callback_id":      rigFixModalCallbackID,
			"private_metadata": pm,
			"state":            map[string]any{"values": state},
		},
	}
	b, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("rigViewSubmissionPayload: marshal: %v", err)
	}
	return string(b)
}

// TestSlackInteractionsRigSlashOpensModal — the slash-command branch
// must call Slack views.open synchronously with a modal carrying our
// rig_fix private_metadata, instead of dispatching immediately. No bd
// or gc subprocess fires until the user submits the modal.
func TestSlackInteractionsRigSlashOpensModal(t *testing.T) {
	cityPath := t.TempDir()
	rigDir := filepath.Join(cityPath, "rigs", "alpha")
	if err := os.MkdirAll(rigDir, 0o700); err != nil {
		t.Fatal(err)
	}
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "rigs/alpha"})

	cfg := config{
		slackSigningKey: "secret",
		slackBotToken:   "xoxb-test",
		accountID:       "T1",
		cityName:        "test-city",
		cityPath:        cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		FixFormula:  "fix-bug",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}

	captures, cleanup := installFakeSlackAPI(t, "")
	t.Cleanup(cleanup)
	records, restore := installStubExecCommand(t, "bd-42", 0)
	t.Cleanup(restore)

	// Wire the completion hook BEFORE the request so an unexpected
	// dispatch goroutine racing with our assertion still trips the
	// channel — replaces the prior 50ms sleep that masked races.
	dispatched := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(dispatched) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	req := signedSlashRequestForRig(t, cfg.slackSigningKey, "T1", "C1", "/gc", "deploy now", "U1", "trig-xyz")
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}

	// views.open must have been called.
	select {
	case got := <-captures:
		if got.Authorization != "Bearer xoxb-test" {
			t.Errorf("views.open Authorization = %q, want Bearer xoxb-test", got.Authorization)
		}
		if !strings.Contains(got.Body, `"trigger_id":"trig-xyz"`) {
			t.Errorf("views.open body should embed trigger_id; got %s", got.Body)
		}
		// private_metadata is JSON-encoded then JSON-encoded again as a
		// string; assert kind+rig_name+sling_target landed in it.
		for _, want := range []string{"rig_fix", "alpha", "mission-control/polecat", "fix-bug", "deploy now"} {
			if !strings.Contains(got.Body, want) {
				t.Errorf("views.open body missing %q:\n%s", want, got.Body)
			}
		}
		// Modal block layout — both inputs must be present.
		for _, want := range []string{rigFixModalSummaryBlockID, rigFixModalContextBlockID, rigFixModalSummaryActionID, rigFixModalContextActionID} {
			if !strings.Contains(got.Body, want) {
				t.Errorf("views.open body missing block id %q", want)
			}
		}
	case <-time.After(2 * time.Second):
		t.Fatal("views.open not called within 2s")
	}

	// No bd/gc subprocess should fire from the slash command alone.
	select {
	case <-dispatched:
		t.Errorf("unexpected dispatch goroutine fired on slash-only path; records=%+v", *records)
	case <-time.After(50 * time.Millisecond):
	}
	if len(*records) != 0 {
		t.Errorf("expected no exec invocations on slash-only path; got %+v", *records)
	}
}

// TestSlackInteractionsRigSlashMissingTriggerID — slash-command form
// without trigger_id (defensive; Slack always sends one) surfaces an
// ephemeral and does not fire views.open.
func TestSlackInteractionsRigSlashMissingTriggerID(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret",
		slackBotToken:   "xoxb-test",
		accountID:       "T1",
		cityName:        "test-city",
		cityPath:        cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	captures, cleanup := installFakeSlackAPI(t, "")
	t.Cleanup(cleanup)

	req := signedSlashRequestForRig(t, cfg.slackSigningKey, "T1", "C1", "/gc", "hi", "U1", "")
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "trigger_id") {
		t.Errorf("ephemeral should mention trigger_id: %s", rec.Body.String())
	}
	select {
	case got := <-captures:
		t.Errorf("views.open should NOT fire when trigger_id missing; got %+v", got)
	case <-time.After(50 * time.Millisecond):
	}
}

// TestSlackInteractionsRigSlashViewsOpenFailure — when Slack returns
// {"ok":false} from views.open, surface the error verbatim as an
// ephemeral.
func TestSlackInteractionsRigSlashViewsOpenFailure(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret",
		slackBotToken:   "xoxb-test",
		accountID:       "T1",
		cityName:        "test-city",
		cityPath:        cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	_, cleanup := installFakeSlackAPI(t, `{"ok":false,"error":"trigger_id_expired"}`)
	t.Cleanup(cleanup)

	req := signedSlashRequestForRig(t, cfg.slackSigningKey, "T1", "C1", "/gc", "hi", "U1", "trig-1")
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "Could not open Slack modal") ||
		!strings.Contains(rec.Body.String(), "trigger_id_expired") {
		t.Errorf("ephemeral should surface views.open error: %s", rec.Body.String())
	}
}

// TestSlackInteractionsRigSlashMissingSlingTarget — sling_target empty
// at slash time short-circuits with an ephemeral and never opens the
// modal.
func TestSlackInteractionsRigSlashMissingSlingTarget(t *testing.T) {
	cityPath := t.TempDir()
	cfg := config{
		slackSigningKey: "secret", slackBotToken: "xoxb-test",
		accountID: "T1", cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs: []string{"C1"},
		// SlingTarget intentionally empty
		CreatedAt: now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	captures, cleanup := installFakeSlackAPI(t, "")
	t.Cleanup(cleanup)

	req := signedSlashRequestForRig(t, cfg.slackSigningKey, "T1", "C1", "/gc", "hi", "U1", "trig-1")
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "no sling target") {
		t.Errorf("ephemeral should surface resolver fix-it: %s", rec.Body.String())
	}
	select {
	case got := <-captures:
		t.Errorf("views.open should NOT fire when sling target missing; got %+v", got)
	case <-time.After(50 * time.Millisecond):
	}
}

// TestSlackInteractionsRigSlashMissingWorkdir — sling_target present
// but routes.jsonl has no entry. Same shape as missing sling target:
// ephemeral, no views.open.
func TestSlackInteractionsRigSlashMissingWorkdir(t *testing.T) {
	cityPath := t.TempDir() // no routes.jsonl seeded.

	cfg := config{
		slackSigningKey: "secret", slackBotToken: "xoxb-test",
		accountID: "T1", cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	captures, cleanup := installFakeSlackAPI(t, "")
	t.Cleanup(cleanup)

	req := signedSlashRequestForRig(t, cfg.slackSigningKey, "T1", "C1", "/gc", "hi", "U1", "trig-1")
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), "rig workdir not found") {
		t.Errorf("ephemeral should surface workdir error: %s", rec.Body.String())
	}
	select {
	case got := <-captures:
		t.Errorf("views.open should NOT fire when workdir missing; got %+v", got)
	case <-time.After(50 * time.Millisecond):
	}
}

// TestSlackInteractionsRigViewSubmissionDispatchesHappyPath — full
// round-trip: slash opens modal (skipped here; covered by the modal
// test above), user types summary + context, view_submission with
// rig_fix metadata fires bd create then gc sling with --var pairs.
func TestSlackInteractionsRigViewSubmissionDispatchesHappyPath(t *testing.T) {
	cityPath := t.TempDir()
	rigDir := filepath.Join(cityPath, "rigs", "alpha")
	if err := os.MkdirAll(rigDir, 0o700); err != nil {
		t.Fatal(err)
	}
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "rigs/alpha"})

	cfg := config{
		slackSigningKey: "secret",
		accountID:       "T1",
		cityName:        "test-city",
		cityPath:        cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		FixFormula:  "fix-bug",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}

	records, restore := installStubExecCommand(t, "bd-42", 0)
	t.Cleanup(restore)
	done := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(done) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	meta := slackRigDispatchMetadata{
		Kind:                metadataKindRigFix,
		WorkspaceID:         "T1",
		RigName:             "alpha",
		SlingTarget:         "mission-control/polecat",
		FixFormula:          "fix-bug",
		ChannelID:           "C1",
		UserID:              "U1",
		OriginalCommand:     "/gc",
		OriginalCommandText: "deploy now",
	}
	payload := rigViewSubmissionPayload(t, "T1", "U1", meta,
		"Fix the deploy queue stall", "Saw stall at 14:02 in #ops; logs at https://example.com")
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	if strings.TrimSpace(rec.Body.String()) != "{}" {
		t.Errorf("response should be `{}` (close current view); got %s", rec.Body.String())
	}

	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("rig-fix dispatch did not finish within 2s")
	}

	if len(*records) < 2 {
		t.Fatalf("expected >=2 exec calls, got %+v", *records)
	}

	// bd create title must contain the user's summary.
	bd := (*records)[0]
	if bd.Name != "bd" || bd.Args[0] != "create" {
		t.Errorf("first call should be `bd create`; got %+v", bd)
	}
	titleSeen := false
	for _, a := range bd.Args {
		if strings.Contains(a, "Fix the deploy queue stall") {
			titleSeen = true
		}
	}
	if !titleSeen {
		t.Errorf("bd title should reflect modal summary: %v", bd.Args)
	}

	// gc sling args must include --on fix-bug and --var summary=...,
	// --var context_markdown=..., --var slash_command_text=...
	gc := (*records)[1]
	if gc.Name != "gc" || gc.Args[0] != "sling" || gc.Args[1] != "mission-control/polecat" || gc.Args[2] != "bd-42" {
		t.Errorf("gc invocation = %+v, want `gc sling mission-control/polecat bd-42 …`", gc)
	}
	wantPairs := map[string]string{
		"summary":            "summary=Fix the deploy queue stall",
		"context_markdown":   "context_markdown=Saw stall at 14:02 in #ops; logs at https://example.com",
		"slash_command_text": "slash_command_text=deploy now",
		"slack_channel_id":   "slack_channel_id=C1",
		"slack_user_id":      "slack_user_id=U1",
		"slack_rig":          "slack_rig=alpha",
	}
	for key, want := range wantPairs {
		found := false
		for i, a := range gc.Args {
			if a == "--var" && i+1 < len(gc.Args) && gc.Args[i+1] == want {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("gc args missing --var %q (key=%s): %v", want, key, gc.Args)
		}
	}
	foundOn := false
	for i, a := range gc.Args {
		if a == "--on" && i+1 < len(gc.Args) && gc.Args[i+1] == "fix-bug" {
			foundOn = true
		}
	}
	if !foundOn {
		t.Errorf("gc args should include `--on fix-bug`: %v", gc.Args)
	}
}

// TestSlackInteractionsRigViewSubmissionEmptyContextOmitsVar — when
// context_markdown is empty, --var context_markdown is NOT emitted.
// (--var summary is still required.)
func TestSlackInteractionsRigViewSubmissionEmptyContextOmitsVar(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret", accountID: "T1",
		cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	records, restore := installStubExecCommand(t, "bd-99", 0)
	t.Cleanup(restore)
	done := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(done) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	meta := slackRigDispatchMetadata{
		Kind:        metadataKindRigFix,
		WorkspaceID: "T1", RigName: "alpha",
		SlingTarget: "mission-control/polecat",
		ChannelID:   "C1", UserID: "U1",
	}
	payload := rigViewSubmissionPayload(t, "T1", "U1", meta, "Trigger nightly", "")
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("dispatch did not finish")
	}

	if len(*records) < 2 {
		t.Fatalf("want >=2 exec records, got %+v", *records)
	}
	gc := (*records)[1]
	for i, a := range gc.Args {
		if a == "--var" && i+1 < len(gc.Args) {
			if strings.HasPrefix(gc.Args[i+1], "context_markdown=") {
				t.Errorf("expected NO context_markdown --var when empty: %v", gc.Args)
			}
		}
	}
	// --on must be omitted when fix_formula was empty.
	for _, a := range gc.Args {
		if a == "--on" {
			t.Errorf("expected no --on flag when fix_formula empty; args=%v", gc.Args)
		}
	}
}

// TestSlackInteractionsRigViewSubmissionMissingSummaryClearsModal —
// a submission with no summary value (defensive — Slack should
// enforce required) must respond with clear-modal and not dispatch.
func TestSlackInteractionsRigViewSubmissionMissingSummaryClearsModal(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret", accountID: "T1",
		cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	records, restore := installStubExecCommand(t, "bd-x", 0)
	t.Cleanup(restore)

	dispatched := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(dispatched) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	meta := slackRigDispatchMetadata{
		Kind:        metadataKindRigFix,
		WorkspaceID: "T1", RigName: "alpha",
		SlingTarget: "mission-control/polecat",
		ChannelID:   "C1", UserID: "U1",
	}
	payload := rigViewSubmissionPayload(t, "T1", "U1", meta, "   ", "")
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), `"response_action":"clear"`) {
		t.Errorf("response should be clear-modal: %s", rec.Body.String())
	}
	select {
	case <-dispatched:
		t.Errorf("unexpected dispatch goroutine fired on missing summary; records=%+v", *records)
	case <-time.After(50 * time.Millisecond):
	}
	if len(*records) != 0 {
		t.Errorf("expected no exec invocations on missing summary; got %+v", *records)
	}
}

// TestSlackInteractionsRigViewSubmissionRigUnmappedClearsModal — the
// rig was remapped/removed between modal-open and modal-submit.
// Re-resolution at submission time fails; the user sees clear-modal
// and no subprocess fires.
func TestSlackInteractionsRigViewSubmissionRigUnmappedClearsModal(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret", accountID: "T1",
		cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	// rigReg has NO record for "alpha" — the rig was removed between
	// modal open and submit.
	rigReg := newTestRigMappingRegistry(t)
	records, restore := installStubExecCommand(t, "bd-x", 0)
	t.Cleanup(restore)

	dispatched := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(dispatched) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	meta := slackRigDispatchMetadata{
		Kind:        metadataKindRigFix,
		WorkspaceID: "T1", RigName: "alpha",
		SlingTarget: "mission-control/polecat",
		ChannelID:   "C1", UserID: "U1",
	}
	payload := rigViewSubmissionPayload(t, "T1", "U1", meta, "summary text", "ctx")
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	if !strings.Contains(rec.Body.String(), `"response_action":"clear"`) {
		t.Errorf("response should be clear-modal: %s", rec.Body.String())
	}
	select {
	case <-dispatched:
		t.Errorf("unexpected dispatch goroutine fired on missing rig; records=%+v", *records)
	case <-time.After(50 * time.Millisecond):
	}
	if len(*records) != 0 {
		t.Errorf("no subprocess should fire on missing rig: %+v", *records)
	}
}

// TestSlackInteractionsRigViewSubmissionGcFailureClosesBead — gc sling
// fails post-bd-create; the dispatcher invokes bd close
// -r dispatch_failed.
func TestSlackInteractionsRigViewSubmissionGcFailureClosesBead(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret", accountID: "T1",
		cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}
	records, restore := installStubExecCommand(t, "bd-77", 1) // gc exit non-zero
	t.Cleanup(restore)
	done := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(done) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	meta := slackRigDispatchMetadata{
		Kind:        metadataKindRigFix,
		WorkspaceID: "T1", RigName: "alpha",
		SlingTarget: "mission-control/polecat",
		ChannelID:   "C1", UserID: "U1",
	}
	payload := rigViewSubmissionPayload(t, "T1", "U1", meta, "summary text", "")
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("dispatch goroutine did not finish")
	}
	if len(*records) < 3 {
		t.Fatalf("want >=3 exec records (bd create, gc sling, bd close); got %+v", *records)
	}
	last := (*records)[len(*records)-1]
	if last.Name != "bd" || last.Args[0] != "close" || last.Args[1] != "bd-77" {
		t.Errorf("expected `bd close bd-77 -r dispatch_failed`; got %+v", last)
	}
}

// TestSlackInteractionsRigViewSubmissionSaturationDrop — when the
// dispatch semaphore is full at slot-acquire time, the response
// surfaces a field-level error in the modal so the user sees the
// cause and can retry without losing their typed input. The earlier
// design closed the modal silently (response_action=clear); the
// review-time fix replaced it with response_action=errors.
func TestSlackInteractionsRigViewSubmissionSaturationDrop(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret", accountID: "T1",
		cityName: "test-city", cityPath: cityPath,
		dispatchSem: make(chan struct{}, 1),
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C1"},
		SlingTarget: "mission-control/polecat",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}

	holdRelease, _, ok := cfg.acquireDispatchSlot()
	if !ok {
		t.Fatal("acquireDispatchSlot: failed to take initial slot")
	}
	t.Cleanup(holdRelease)

	records, restoreExec := installStubExecCommand(t, "bd-x", 0)
	t.Cleanup(restoreExec)

	dispatched := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(dispatched) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	meta := slackRigDispatchMetadata{
		Kind:        metadataKindRigFix,
		WorkspaceID: "T1", RigName: "alpha",
		SlingTarget: "mission-control/polecat",
		ChannelID:   "C1", UserID: "U1",
	}
	payload := rigViewSubmissionPayload(t, "T1", "U1", meta, "summary", "")
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status=%d", rec.Code)
	}
	bodyStr := rec.Body.String()
	if !strings.Contains(bodyStr, `"response_action":"errors"`) {
		t.Errorf("response should surface field-level errors on saturation; got: %s", bodyStr)
	}
	if !strings.Contains(bodyStr, "saturated") {
		t.Errorf("response should mention saturation in the error message; got: %s", bodyStr)
	}
	if !strings.Contains(bodyStr, rigFixModalSummaryBlockID) {
		t.Errorf("error should target the summary block; got: %s", bodyStr)
	}
	select {
	case <-dispatched:
		t.Errorf("unexpected dispatch goroutine fired on saturation; records=%+v", *records)
	case <-time.After(50 * time.Millisecond):
	}
	if len(*records) != 0 {
		t.Errorf("no exec invocations expected on saturation; got %+v", *records)
	}
}

// TestSlackInteractionsRigDispatchBlockActionsHappyPath — block_actions
// stays on the immediate-dispatch path (modal capture is slash-only).
// This is unchanged from cby.18.3.
func TestSlackInteractionsRigDispatchBlockActionsHappyPath(t *testing.T) {
	cityPath := t.TempDir()
	seedRoutesJSONL(t, cityPath, map[string]string{"alpha": "."})

	cfg := config{
		slackSigningKey: "secret", accountID: "T1",
		cityName: "test-city", cityPath: cityPath,
		dispatchSem: defaultTestDispatchSem,
	}
	chanReg := newTestChannelMappingRegistry(t)
	rigReg := newTestRigMappingRegistry(t)
	now := time.Now().UTC()
	if err := rigReg.Set(rigMappingDiskRecord{
		WorkspaceID: "T1", RigName: "alpha",
		ChannelIDs:  []string{"C-RIG"},
		SlingTarget: "mission-control/polecat",
		FixFormula:  "fix-it",
		CreatedAt:   now, UpdatedAt: now,
	}); err != nil {
		t.Fatal(err)
	}

	records, restore := installStubExecCommand(t, "bd-101", 0)
	t.Cleanup(restore)
	done := make(chan struct{})
	prevHook := dispatchTestCompletionHook
	dispatchTestCompletionHook = func() { close(done) }
	t.Cleanup(func() { dispatchTestCompletionHook = prevHook })

	payload := blockActionsPayloadJSON(t, "T1", "U1", "C-RIG", "", "",
		[]map[string]string{{"action_id": "approve", "value": "shipit", "type": "button"}})
	body := []byte(url.Values{"payload": {payload}}.Encode())
	req := signedSlackInteractionRequest(t, cfg.slackSigningKey, body)
	rec := httptest.NewRecorder()
	handleSlackInteractions(cfg, chanReg, rigReg)(rec, req)

	if rec.Code != 200 {
		t.Fatalf("status=%d body=%s", rec.Code, rec.Body.String())
	}
	if !strings.Contains(rec.Body.String(), "Routing") || !strings.Contains(rec.Body.String(), "alpha") {
		t.Errorf("ephemeral should mention Routing+rig: %s", rec.Body.String())
	}
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		t.Fatal("block_actions dispatch did not finish")
	}
	if len(*records) < 2 {
		t.Fatalf("expected >=2 exec calls; got %+v", *records)
	}
	bd := (*records)[0]
	if bd.Name != "bd" || bd.Args[0] != "create" {
		t.Errorf("first call should be `bd create`; got %+v", bd)
	}
	titleSeen := false
	for _, a := range bd.Args {
		if strings.Contains(a, "shipit") {
			titleSeen = true
		}
	}
	if !titleSeen {
		t.Errorf("bd title should reflect action value 'shipit': %v", bd.Args)
	}
	// block_actions path passes nil vars → no --var flags expected.
	gc := (*records)[1]
	for _, a := range gc.Args {
		if a == "--var" {
			t.Errorf("block_actions path should NOT emit --var flags; got %v", gc.Args)
		}
	}
}

// TestDecodeRigDispatchMetadataRejectsLegacySessionID — the legacy
// {"session_id":"…"} shape must NOT be decoded as rig_fix metadata.
// view_submission routing relies on this discrimination to fall
// through to the cby.17 session path.
func TestDecodeRigDispatchMetadataRejectsLegacySessionID(t *testing.T) {
	_, ok := decodeRigDispatchMetadata(`{"session_id":"gc-2568"}`)
	if ok {
		t.Errorf("legacy session_id metadata should not decode as rig_fix")
	}
}

// TestDecodeRigDispatchMetadataRejectsUnknownFields — defense in
// depth: extra fields must trip DisallowUnknownFields.
func TestDecodeRigDispatchMetadataRejectsUnknownFields(t *testing.T) {
	raw := `{"kind":"rig_fix","workspace_id":"T1","rig_name":"alpha","extra":"foo"}`
	if _, ok := decodeRigDispatchMetadata(raw); ok {
		t.Errorf("unknown fields should be rejected")
	}
}

// TestDecodeRigDispatchMetadataRejectsOversize — payload above
// maxRigDispatchMetadataLen routes to false (would never fit in
// Slack's private_metadata anyway, but defend in depth).
func TestDecodeRigDispatchMetadataRejectsOversize(t *testing.T) {
	huge := strings.Repeat("a", maxRigDispatchMetadataLen+10)
	raw := `{"kind":"rig_fix","workspace_id":"T1","rig_name":"` + huge + `"}`
	if _, ok := decodeRigDispatchMetadata(raw); ok {
		t.Errorf("oversize metadata should be rejected")
	}
}
