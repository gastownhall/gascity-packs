package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os/exec"
	"sort"
	"strings"
)

// dispatchExecCommand is the indirection point for `bd` and `gc`
// subprocess invocation, used by the rig-target dispatch path
// (gc-cby.18.3). Tests override this var to install a fake command
// runner that records invocations and returns canned output. Production
// uses exec.Command directly.
var dispatchExecCommand = exec.Command

// dispatchTestCompletionHook fires once at the end of every rig
// dispatch goroutine — happy path or error path. Tests install this
// hook to synchronize on dispatch completion without polling. Nil in
// production. Not exported (test-only).
var dispatchTestCompletionHook func()

// rigDispatchTitleMaxLen caps the bead title sourced from slash-command
// text or block-action value. Slack inputs can be arbitrarily long and
// `bd` titles flow into convoy summaries, log lines, and dashboard
// rows; cap them well below screen-line widths. The remaining text is
// preserved verbatim in the agent's view via the dispatch goroutine's
// system-reminder body in a follow-up modal capture (cby.18.4).
const rigDispatchTitleMaxLen = 200

// truncateForTitle returns s capped at rigDispatchTitleMaxLen runes,
// using a fall-back placeholder when s trims to empty. It runs after
// neutralizeMarkupBoundaries so callers don't lose sanitization.
//
// Uses []rune slicing (not byte slicing) so multibyte UTF-8 characters
// at the boundary don't produce invalid UTF-8 in the bead title.
func truncateForTitle(s string) string {
	t := strings.TrimSpace(s)
	if t == "" {
		return "(empty)"
	}
	runes := []rune(t)
	if len(runes) > rigDispatchTitleMaxLen {
		return string(runes[:rigDispatchTitleMaxLen])
	}
	return t
}

// runDispatchTestHook is internal; the rig dispatch goroutine calls it
// at the end of every code path so tests can synchronize on completion.
func runDispatchTestHook() {
	if dispatchTestCompletionHook != nil {
		dispatchTestCompletionHook()
	}
}

// openRigFixModalForSlash is the rig-target counterpart of
// dispatchSlashCommandToSession. It runs synchronous validation
// (sling-target lookup, rig workdir resolution) and — on success —
// calls Slack's views.open API with a modal collecting summary +
// context_markdown before any bead is created. Dispatch happens later,
// in handleViewSubmissionPayload, when the user submits the modal.
//
// Why pre-validate before opening the modal: a modal that submits to a
// misconfigured rig wastes the user's typing. We reject up front via
// ephemeral so the user can re-run after `gc slack map-rig` fixes.
//
// Slack's trigger_id is valid for ~3 seconds — the views.open call
// MUST fire synchronously inside this handler. The HTTP response to
// the slash command itself is empty (Slack treats `200` with empty
// body as "no slash response" while still surfacing the modal that
// the views.open call opened).
//
// gc-cby.18.4: replaces the cby.18.3 immediate-dispatch flow on
// slash. Block_actions still dispatches immediately
// (dispatchBlockActionsToRig); modal capture is slash-only by design
// — block_actions already carries an action_id+value of the user's
// choice, so prompting for a summary on top would be friction.
func openRigFixModalForSlash(
	ctx context.Context,
	w http.ResponseWriter,
	cfg config,
	rigReg *rigMappingRegistry,
	workspaceID, rigName, command, text, channelID, userID, triggerID string,
) {
	if rigReg == nil {
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"channel is bound to rig %q but no rig registry is loaded; ensure SLACK_RIG_MAPPING_PATH points at a readable rig_mappings.json and restart the adapter",
			rigName))
		return
	}
	target, fixFormula, err := rigReg.ResolveSlingTarget(workspaceID, rigName)
	if err != nil {
		writeEphemeral(w, http.StatusOK, err.Error())
		return
	}
	if _, err := rigWorkdir(cfg.cityPath, rigName); err != nil {
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"rig workdir not found in routes.jsonl: %v", err))
		return
	}
	if cfg.slackBotToken == "" {
		writeEphemeral(w, http.StatusOK,
			"Slack adapter has no bot token configured; cannot open modal. Set SLACK_BOT_TOKEN and restart.")
		return
	}
	if triggerID == "" {
		writeEphemeral(w, http.StatusOK,
			"Slack slash-command payload missing trigger_id; cannot open modal.")
		return
	}

	meta := slackRigDispatchMetadata{
		Kind:                metadataKindRigFix,
		WorkspaceID:         workspaceID,
		RigName:             rigName,
		SlingTarget:         target,
		FixFormula:          fixFormula,
		ChannelID:           channelID,
		UserID:              userID,
		OriginalCommand:     command,
		OriginalCommandText: text,
	}
	pm, err := encodeRigDispatchMetadata(meta)
	if err != nil {
		log.Printf("slack interactions: encode rig modal metadata rig=%q: %v", rigName, err)
		writeEphemeral(w, http.StatusOK,
			"Internal error preparing modal payload; please retry or use `gc slack map-rig` to verify configuration.")
		return
	}
	view, err := buildRigFixModalView(meta, pm)
	if err != nil {
		log.Printf("slack interactions: build rig modal view rig=%q: %v", rigName, err)
		writeEphemeral(w, http.StatusOK,
			"Internal error building modal view; please retry.")
		return
	}
	if _, err := callViewsOpen(ctx, cfg.slackBotToken, triggerID, view); err != nil {
		log.Printf("slack interactions: views.open rig=%q trigger=%q: %v",
			rigName, triggerID, err)
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"Could not open Slack modal: %v", err))
		return
	}
	log.Printf("interaction: workspace=%q channel=%q rig=%q opened rig-fix modal user=%q",
		workspaceID, channelID, rigName, userID)
	// Slack already received our modal-open via views.open — respond
	// with an empty 200 so no extra ephemeral fires (the modal itself
	// is the user-visible feedback).
	w.WriteHeader(http.StatusOK)
}

// dispatchBlockActionsToRig is the rig-target counterpart of
// dispatchBlockActionsToSession. The bead title carries the first
// action's identifier and value so an agent picking up the bead has
// enough context to decide what to do. Multi-action payloads are not
// flattened into the title — Slack typically sends length 1, and
// multi_*_select bursts are best surfaced via the modal capture path
// (cby.18.4).
func dispatchBlockActionsToRig(
	w http.ResponseWriter,
	cfg config,
	rigReg *rigMappingRegistry,
	workspaceID, rigName, channelID string,
	p *slackInteractionPayload,
) {
	if rigReg == nil {
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"channel is bound to rig %q but no rig registry is loaded; ensure SLACK_RIG_MAPPING_PATH points at a readable rig_mappings.json and restart the adapter",
			rigName))
		return
	}
	target, fixFormula, err := rigReg.ResolveSlingTarget(workspaceID, rigName)
	if err != nil {
		writeEphemeral(w, http.StatusOK, err.Error())
		return
	}
	workdir, err := rigWorkdir(cfg.cityPath, rigName)
	if err != nil {
		writeEphemeral(w, http.StatusOK, fmt.Sprintf(
			"rig workdir not found in routes.jsonl: %v", err))
		return
	}

	release, capacity, acquired := cfg.acquireDispatchSlot()
	if !acquired {
		log.Printf("slack adapter: dispatch queue full (cap=%d), dropping block_actions team=%q channel=%q rig=%q",
			capacity, workspaceID, channelID, rigName)
		writeEphemeral(w, http.StatusOK,
			"Slack adapter is currently saturated; please retry shortly.")
		return
	}

	writeEphemeral(w, http.StatusOK, fmt.Sprintf(
		"Routing block-action to rig %s…", rigName))

	var actionID, actionValue string
	if len(p.Actions) > 0 {
		actionID = p.Actions[0].ActionID
		actionValue = p.Actions[0].Value
		if actionValue == "" && p.Actions[0].SelectedOption != nil {
			actionValue = p.Actions[0].SelectedOption.Value
		}
	}
	title := fmt.Sprintf("[slack/%s block_actions %s by %s] %s",
		neutralizeMarkupBoundaries(channelID),
		neutralizeMarkupBoundaries(actionID),
		neutralizeMarkupBoundaries(p.User.ID),
		neutralizeMarkupBoundaries(actionValue),
	)
	title = truncateForTitle(title)

	dispatchInflightWG.Add(1)
	go func() {
		defer dispatchInflightWG.Done()
		defer release()
		defer runDispatchTestHook()
		runRigDispatch(workdir, cfg.cityPath, target, fixFormula, title, rigName, nil)
	}()
}

// dispatchRigFixFromViewSubmission handles a Slack view_submission
// whose private_metadata is a `rig_fix` envelope written by
// openRigFixModalForSlash. Block_actions doesn't reach here — modal
// submission is the only path.
//
// Re-resolves rig + workdir at submission time (the metadata is
// trusted insofar as Slack signed the interactions envelope, but the
// rig may have been remapped between open and submit; we want the
// authoritative current registry view, not the snapshot the modal
// opener captured).
//
// The summary input (required) becomes the bead title; the
// context_markdown input (optional) is forwarded to `gc sling` as
// `--var context_markdown=<value>`. The original slash-command text
// is forwarded as `--var slash_command_text=<value>` so the model
// sees both the user's modal-curated framing and the original raw
// trigger.
//
// Errors from rigReg/rigWorkdir at submission time route to
// clear-modal so the user sees the modal close + a logged warning;
// they have to re-run the slash command after fixing config.
func dispatchRigFixFromViewSubmission(
	w http.ResponseWriter,
	cfg config,
	rigReg *rigMappingRegistry,
	meta slackRigDispatchMetadata,
	p *slackInteractionPayload,
) {
	if rigReg == nil {
		log.Printf("slack interactions: view_submission rig_fix but rigReg=nil rig=%q", meta.RigName)
		writeViewClear(w)
		return
	}
	target, fixFormula, err := rigReg.ResolveSlingTarget(meta.WorkspaceID, meta.RigName)
	if err != nil {
		log.Printf("slack interactions: view_submission rig_fix re-resolve failed workspace=%q rig=%q: %v",
			meta.WorkspaceID, meta.RigName, err)
		writeViewClear(w)
		return
	}
	workdir, err := rigWorkdir(cfg.cityPath, meta.RigName)
	if err != nil {
		log.Printf("slack interactions: view_submission rig_fix workdir lookup failed rig=%q: %v",
			meta.RigName, err)
		writeViewClear(w)
		return
	}

	summary := strings.TrimSpace(extractModalInput(
		p.View.State.Values, rigFixModalSummaryBlockID, rigFixModalSummaryActionID))
	if summary == "" {
		// Slack enforces required input on its side, but defend in
		// depth in case the schema drifts.
		log.Printf("slack interactions: view_submission rig_fix missing summary rig=%q user=%q",
			meta.RigName, meta.UserID)
		writeViewClear(w)
		return
	}
	contextMarkdown := strings.TrimSpace(extractModalInput(
		p.View.State.Values, rigFixModalContextBlockID, rigFixModalContextActionID))

	release, capacity, acquired := cfg.acquireDispatchSlot()
	if !acquired {
		log.Printf("slack adapter: dispatch queue full (cap=%d), dropping view_submission rig_fix rig=%q user=%q",
			capacity, meta.RigName, meta.UserID)
		// Surface saturation to the user via the modal's field-level
		// errors response_action. Without this, writeViewClear silently
		// closes the modal and the user has no idea the work was lost.
		writeViewSubmissionErrors(w, map[string]string{
			rigFixModalSummaryBlockID: "Slack adapter is currently saturated; please retry shortly.",
		})
		return
	}

	// Respond `{}` synchronously so Slack closes only the current
	// view. The dispatch goroutine fires after the response.
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	if _, err := w.Write([]byte("{}")); err != nil {
		log.Printf("slack interactions: write view_submission rig_fix ack: %v", err)
	}
	log.Printf("interaction: workspace=%q user=%q rig=%q type=view_submission callback=%q kind=rig_fix",
		meta.WorkspaceID, meta.UserID, meta.RigName, p.View.CallbackID)

	title := fmt.Sprintf("[slack/%s by %s] %s",
		neutralizeMarkupBoundaries(meta.ChannelID),
		neutralizeMarkupBoundaries(meta.UserID),
		neutralizeMarkupBoundaries(summary),
	)
	title = truncateForTitle(title)

	// Neutralize markup boundaries on user-controlled fields before
	// they flow into --var values. The downstream formula MAY embed
	// these in a system-reminder block; without neutralization a user
	// could close the boundary tag and inject instructions into the
	// agent's prompt.
	vars := map[string]string{
		"slack_channel_id": meta.ChannelID,
		"slack_user_id":    meta.UserID,
		"slack_rig":        meta.RigName,
		"summary":          neutralizeMarkupBoundaries(summary),
	}
	if contextMarkdown != "" {
		vars["context_markdown"] = neutralizeMarkupBoundaries(contextMarkdown)
	}
	if meta.OriginalCommandText != "" {
		vars["slash_command_text"] = neutralizeMarkupBoundaries(meta.OriginalCommandText)
	}

	dispatchInflightWG.Add(1)
	go func() {
		defer dispatchInflightWG.Done()
		defer release()
		defer runDispatchTestHook()
		runRigDispatch(workdir, cfg.cityPath, target, fixFormula, title, meta.RigName, vars)
	}()
}

// runRigDispatch performs the two subprocess legs of a rig-target
// dispatch: `bd create` inside the rig workdir to mint a task bead,
// then `gc sling <target> <bead_id> [--on <fix_formula>] [--var k=v]…`
// from the city root to invoke dispatch. Failures at the gc-sling leg
// trigger a best-effort `bd close <bead_id> -r dispatch_failed` so the
// orphan task does not show up as queued work.
//
// Empty fixFormula deliberately omits the --on flag (cby.18.3 design
// choice): gc sling falls through to its own default formula
// resolution rather than the adapter inventing one.
//
// vars is forwarded as repeated --var k=v pairs in deterministic key
// order. nil/empty omits the flag entirely. Used by the modal-backed
// intake (gc-cby.18.4) to pipe captured summary/context_markdown to
// the dispatched formula.
func runRigDispatch(workdir, cityPath, target, fixFormula, title, rigName string, vars map[string]string) {
	beadID, err := runBdCreate(workdir, title)
	if err != nil {
		log.Printf("rig dispatch: bd create in %s rig=%q: %v", workdir, rigName, err)
		return
	}
	if err := runGcSling(cityPath, target, beadID, fixFormula, vars); err != nil {
		log.Printf("rig dispatch: gc sling target=%q bead=%s rig=%q: %v",
			target, beadID, rigName, err)
		closeOrphanBead(workdir, beadID)
		return
	}
	log.Printf("rig dispatch: bead=%s -> sling=%s formula=%q rig=%q OK",
		beadID, target, fixFormula, rigName)
}

// runBdCreate invokes `bd create --json <title> -t task` inside the
// rig workdir and returns the parsed bead id from stdout.
func runBdCreate(workdir, title string) (string, error) {
	cmd := dispatchExecCommand("bd", "create", "--json", title, "-t", "task")
	cmd.Dir = workdir
	out, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("bd create exec in %q: %w", workdir, err)
	}
	var rec struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal(out, &rec); err != nil {
		return "", fmt.Errorf("decode bd create output (%q): %w", string(out), err)
	}
	if rec.ID == "" {
		return "", fmt.Errorf("bd create returned empty id (output %q)", string(out))
	}
	return rec.ID, nil
}

// runGcSling invokes `gc sling <target> <beadID> [--on <fixFormula>]
// [--var k=v]…` from cityPath. Empty fixFormula omits --on so gc
// applies its configured default formula (cby.18.3). vars is emitted
// as repeated --var pairs in sorted-by-key order so the command line
// is deterministic across calls (test-friendly + log-readable).
// nil/empty vars omits the flag entirely.
func runGcSling(cityPath, target, beadID, fixFormula string, vars map[string]string) error {
	args := []string{"sling", target, beadID}
	if fixFormula != "" {
		args = append(args, "--on", fixFormula)
	}
	if len(vars) > 0 {
		keys := make([]string, 0, len(vars))
		for k := range vars {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			args = append(args, "--var", fmt.Sprintf("%s=%s", k, vars[k]))
		}
	}
	cmd := dispatchExecCommand("gc", args...)
	cmd.Dir = cityPath
	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("gc %s in %q: %w (output=%q)",
			strings.Join(args, " "), cityPath, err, string(out))
	}
	return nil
}

// closeOrphanBead best-effort closes a bead created by runBdCreate
// after `gc sling` failed. Errors are logged and swallowed — the bead
// is already orphaned at this point and a closure failure is at most a
// queued-work display nit, not a correctness issue.
func closeOrphanBead(workdir, beadID string) {
	cmd := dispatchExecCommand("bd", "close", beadID, "-r", "dispatch_failed")
	cmd.Dir = workdir
	if out, err := cmd.CombinedOutput(); err != nil {
		log.Printf("rig dispatch: bd close %s in %q: %v (output=%q)",
			beadID, workdir, err, string(out))
		return
	}
	log.Printf("rig dispatch: closed orphan bead=%s with reason=dispatch_failed", beadID)
}
