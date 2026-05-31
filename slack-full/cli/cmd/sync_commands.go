package cmd

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"reflect"
	"sort"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"github.com/sjarmak/gc-slack-cli/internal/state/apps"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// Slack configuration access tokens (`xoxe.xoxp-...`) authenticate
// against Slack's app-management endpoints. They are app-level
// secrets — they MUST never appear in any output stream. Errors that
// originate inside slackPostForm wrap only `*url.Error` (URL/method,
// no headers), so transport errors don't leak the token. The 4xx
// body-dump and JSON-decode-error paths echo the *response* body,
// which is safe only because slackAPIBaseURLAllowed (below) refuses
// non-Slack base URLs in production — a hostile endpoint cannot be
// reached, so it cannot reflect the Authorization header back at us.
const (
	defaultSlackAPIBaseURL = "https://slack.com/api"
	slackConfigTokenEnv    = "SLACK_CONFIG_ACCESS_TOKEN"
	slackAPIURLEnv         = "GC_SLACK_API_URL"
)

// slackAPIBaseURLAllowed validates that a non-default GC_SLACK_API_URL
// points at *.slack.com over HTTPS. Indirected through a package var
// so tests can substitute a permit-all stub via
// testAllowAnySlackAPIBaseURL — production callers always see
// isSlackAPIBaseURL.
//
// WARNING: not safe for concurrent test access. Tests that swap this
// var must NOT call t.Parallel().
var slackAPIBaseURLAllowed = isSlackAPIBaseURL

func isSlackAPIBaseURL(raw string) error {
	if raw == defaultSlackAPIBaseURL {
		return nil
	}
	u, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("parse %s: %w", slackAPIURLEnv, err)
	}
	if u.Scheme != "https" {
		return fmt.Errorf("%s must use https scheme (got %q); the variable is for production override only and refusing non-https here prevents a hostile env from exfiltrating the bearer token", slackAPIURLEnv, u.Scheme)
	}
	h := u.Hostname()
	if h != "slack.com" && !strings.HasSuffix(h, ".slack.com") {
		return fmt.Errorf("%s must point at slack.com or *.slack.com (got host %q); refusing to send a configuration access token to a non-Slack host", slackAPIURLEnv, h)
	}
	return nil
}

// slackSlashCmd mirrors the `features.slash_commands[]` entries in the
// Slack manifest. Unknown fields are tolerated by the diff path because
// json.Unmarshal silently drops them; the *update* path uses the
// registry's verbatim manifest_raw bytes (not these structs), so
// unknown fields survive round-trip.
type slackSlashCmd struct {
	Command      string `json:"command"`
	Description  string `json:"description,omitempty"`
	URL          string `json:"url,omitempty"`
	UsageHint    string `json:"usage_hint,omitempty"`
	ShouldEscape bool   `json:"should_escape,omitempty"`
}

type slashCmdChange struct {
	Command string        `json:"command"`
	From    slackSlashCmd `json:"from"`
	To      slackSlashCmd `json:"to"`
}

// slashCmdDiff is the structured diff between local and live manifests.
// JSON tags match the contract pinned by TestSyncCommandsJSONOutput.
type slashCmdDiff struct {
	Added                   []slackSlashCmd  `json:"added"`
	Removed                 []slackSlashCmd  `json:"removed"`
	Changed                 []slashCmdChange `json:"changed"`
	NonCommandFieldsChanged bool             `json:"non_command_fields_changed"`
	NonCommandFieldsPaths   []string         `json:"non_command_fields_paths,omitempty"`
}

func (d slashCmdDiff) empty() bool {
	return len(d.Added) == 0 && len(d.Removed) == 0 && len(d.Changed) == 0 && !d.NonCommandFieldsChanged
}

type slackSyncOpts struct {
	workspaceID          string
	appID                string
	token                string
	dryRun               bool
	allowNonCommandDrift bool
	output               string
	timeout              time.Duration
}

// NewSyncCommandsCmd wires the cobra verb. The runner is split out
// so tests can drive the same code path without re-parsing flags.
func NewSyncCommandsCmd(stdout, _ io.Writer) *cobra.Command {
	var o slackSyncOpts
	cmd := &cobra.Command{
		Use:   "sync-commands",
		Short: "Reconcile the locally-imported Slack app's slash commands with what's live in Slack",
		Long: `Reconcile the locally-imported Slack app's slash commands with what's live in Slack.

Reads the imported app record from <cityPath>/.gc/slack/apps.json (built
by ` + "`gc slack import-app`" + `), calls Slack apps.manifest.export to read the
live manifest, diffs the two slash-command sets, and (unless --dry-run)
calls apps.manifest.update to push the local manifest. After update,
apps.manifest.export is called once more to verify convergence.

The verb refuses to push when manifest fields OUTSIDE features.slash_commands
have drifted from local — pass --allow-non-command-drift to opt into a
full-manifest replace.

The Slack configuration access token (xoxe.xoxp-...) is read from the
SLACK_CONFIG_ACCESS_TOKEN environment variable, or from --token. Token
values never appear in error or log output.

Schema: https://api.slack.com/methods/apps.manifest.update`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return runSlackSyncCommands(cmd.Context(), stdout, o)
		},
	}
	defaultWorkspace := workspace.IDDefault()
	cmd.Flags().StringVar(&o.workspaceID, "workspace-id", defaultWorkspace,
		workspace.IDFlagUsage)
	cmd.Flags().StringVar(&o.appID, "app-id", "",
		"Slack app id, e.g. A0123456 (required)")
	cmd.Flags().StringVar(&o.token, "token", "",
		"Slack configuration access token (xoxe.xoxp-...). Falls back to "+slackConfigTokenEnv)
	cmd.Flags().BoolVar(&o.dryRun, "dry-run", false,
		"Print the diff and exit without calling apps.manifest.update")
	cmd.Flags().BoolVar(&o.allowNonCommandDrift, "allow-non-command-drift", false,
		"Allow the push when non-command manifest fields differ from local")
	cmd.Flags().StringVar(&o.output, "output", "text",
		"Output format: text|json")
	cmd.Flags().DurationVar(&o.timeout, "timeout", 30*time.Second,
		"Hard timeout for the entire operation")
	if defaultWorkspace == "" {
		_ = cmd.MarkFlagRequired("workspace-id")
	}
	_ = cmd.MarkFlagRequired("app-id")
	return cmd
}

func runSlackSyncCommands(ctx context.Context, stdout io.Writer, o slackSyncOpts) error {
	if o.timeout <= 0 {
		return fmt.Errorf("--timeout must be positive (got %v)", o.timeout)
	}
	if o.output != "text" && o.output != "json" {
		return fmt.Errorf("--output %q: unsupported format; choose text or json", o.output)
	}
	ctx, cancel := context.WithTimeout(ctx, o.timeout)
	defer cancel()

	token := o.token
	if token == "" {
		token = os.Getenv(slackConfigTokenEnv)
	}
	if token == "" {
		return fmt.Errorf("missing slack configuration access token: pass --token or set %s in env", slackConfigTokenEnv)
	}

	cityPath, err := ResolveCityPath()
	if err != nil {
		return fmt.Errorf("resolve city: %w", err)
	}
	reg, err := apps.NewRegistry(apps.Path(cityPath))
	if err != nil {
		return fmt.Errorf("open slack app registry: %w", err)
	}
	rec, ok := reg.Get(o.workspaceID, o.appID)
	if !ok {
		return fmt.Errorf("no imported slack app for workspace=%s app=%s; run `gc slack import-app` first",
			o.workspaceID, o.appID)
	}

	baseURL := os.Getenv(slackAPIURLEnv)
	if baseURL == "" {
		baseURL = defaultSlackAPIBaseURL
	}
	if err := slackAPIBaseURLAllowed(baseURL); err != nil {
		return err
	}
	client := &http.Client{
		// Slack's apps.manifest.{export,update} do not redirect in
		// normal operation. Refuse any redirect so a hostile env that
		// somehow slipped past slackAPIBaseURLAllowed cannot bounce
		// the bearer token to a same-host attacker-controlled path.
		CheckRedirect: func(req *http.Request, _ []*http.Request) error {
			return fmt.Errorf("unexpected redirect to %s", req.URL.Redacted())
		},
	}

	live, err := slackManifestExport(ctx, client, baseURL, token, o.appID)
	if err != nil {
		return err
	}

	diff, err := computeManifestDiff(rec.ManifestRaw, live)
	if err != nil {
		return fmt.Errorf("compute manifest diff: %w", err)
	}

	if diff.empty() {
		if o.output == "json" {
			return emitJSONEnvelope(stdout, o, diff, false, false)
		}
		fmt.Fprintln(stdout, "Slack manifest in sync; no update issued.") //nolint:errcheck // best-effort stdout
		return nil
	}

	if diff.NonCommandFieldsChanged && !o.allowNonCommandDrift {
		return fmt.Errorf(
			"non-command manifest fields drifted from local: %s\n"+
				"pass --allow-non-command-drift to push the entire local manifest, "+
				"or re-run `gc slack import-app` to refresh local from a hand-edited manifest",
			strings.Join(diff.NonCommandFieldsPaths, ", "))
	}

	if o.dryRun {
		if o.output == "json" {
			return emitJSONEnvelope(stdout, o, diff, false, false)
		}
		printDiffText(stdout, diff)
		return nil
	}

	if o.output == "text" {
		printDiffText(stdout, diff)
	}

	if err := slackManifestUpdate(ctx, client, baseURL, token, o.appID, rec.ManifestRaw); err != nil {
		return err
	}

	verified, err := slackManifestExport(ctx, client, baseURL, token, o.appID)
	if err != nil {
		return fmt.Errorf("post-update verification: %w", err)
	}
	verifyDiff, err := computeManifestDiff(rec.ManifestRaw, verified)
	if err != nil {
		return fmt.Errorf("post-update verification diff: %w", err)
	}
	// Slash commands must converge. Non-command fields are not strictly
	// re-checked: the operator's --allow-non-command-drift consent (if
	// any) covered them on the way in.
	if len(verifyDiff.Added) != 0 || len(verifyDiff.Removed) != 0 || len(verifyDiff.Changed) != 0 {
		return fmt.Errorf("slack manifest diverged from local after update: added=%d removed=%d changed=%d",
			len(verifyDiff.Added), len(verifyDiff.Removed), len(verifyDiff.Changed))
	}

	if o.output == "json" {
		return emitJSONEnvelope(stdout, o, diff, true, true)
	}
	fmt.Fprintf(stdout, "Slack manifest synced for workspace=%s app=%s.\n", o.workspaceID, o.appID) //nolint:errcheck // best-effort stdout
	return nil
}

// --- Slack API client ---------------------------------------------------

type slackEnvelope struct {
	OK       bool                    `json:"ok"`
	Error    string                  `json:"error,omitempty"`
	Errors   []slackManifestSubError `json:"errors,omitempty"`
	Manifest json.RawMessage         `json:"manifest,omitempty"`
	AppID    string                  `json:"app_id,omitempty"`
}

type slackManifestSubError struct {
	Code    string `json:"code"`
	Message string `json:"message,omitempty"`
	Pointer string `json:"pointer,omitempty"`
}

// slackAPIError is returned when Slack responds with `{"ok": false}`.
// Format pinned by tests: top-level Slack error code + each
// errors[].pointer; token_expired adds the mint URL.
type slackAPIError struct {
	Method string
	Code   string
	Errors []slackManifestSubError
	AppID  string
}

func (e *slackAPIError) Error() string {
	parts := []string{fmt.Sprintf("slack %s: %s", e.Method, e.Code)}
	for _, sub := range e.Errors {
		parts = append(parts, fmt.Sprintf("  - %s at %s: %s", sub.Code, sub.Pointer, sub.Message))
	}
	msg := strings.Join(parts, "\n")
	if e.Code == "token_expired" {
		msg += fmt.Sprintf("\nMint a new configuration access token at https://api.slack.com/apps/%s/general", e.AppID)
	}
	return msg
}

func slackManifestExport(ctx context.Context, c *http.Client, baseURL, token, appID string) (json.RawMessage, error) {
	form := url.Values{}
	form.Set("app_id", appID)
	env, err := slackPostForm(ctx, c, baseURL+"/apps.manifest.export", token, form)
	if err != nil {
		return nil, err
	}
	if !env.OK {
		return nil, &slackAPIError{Method: "apps.manifest.export", Code: env.Error, Errors: env.Errors, AppID: appID}
	}
	if len(env.Manifest) == 0 {
		return nil, fmt.Errorf("slack apps.manifest.export: ok=true but manifest field is absent — refusing to treat as empty manifest (would mass-classify local commands as added)")
	}
	return env.Manifest, nil
}

func slackManifestUpdate(ctx context.Context, c *http.Client, baseURL, token, appID string, manifestRaw json.RawMessage) error {
	// Slack apps.manifest.update wants the manifest as a JSON string in
	// a form-urlencoded body. url.Values.Encode handles the form-level
	// escaping; we pass the raw JSON bytes verbatim as the value.
	form := url.Values{}
	form.Set("app_id", appID)
	form.Set("manifest", string(manifestRaw))
	env, err := slackPostForm(ctx, c, baseURL+"/apps.manifest.update", token, form)
	if err != nil {
		return err
	}
	if !env.OK {
		return &slackAPIError{Method: "apps.manifest.update", Code: env.Error, Errors: env.Errors, AppID: appID}
	}
	return nil
}

// slackPostForm POSTs an x-www-form-urlencoded body with a Bearer
// token. Token redaction is implicit: Go's http.Client does not echo
// the Authorization header in *url.Error or other transport errors,
// and we never include `form` or response headers in error messages.
func slackPostForm(ctx context.Context, c *http.Client, endpoint, token string, form url.Values) (*slackEnvelope, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := c.Do(req)
	if err != nil {
		// %w preserves the underlying *url.Error which references the
		// URL but not the headers, so the token does not leak here.
		return nil, fmt.Errorf("slack POST %s: %w", endpoint, err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, fmt.Errorf("read slack response: %w", err)
	}
	if resp.StatusCode >= 400 {
		// Body is the Slack response, never the request — safe to echo.
		return nil, fmt.Errorf("slack POST %s status %d: %s", endpoint, resp.StatusCode, string(body))
	}
	var env slackEnvelope
	if err := json.Unmarshal(body, &env); err != nil {
		return nil, fmt.Errorf("decode slack response: %w (body=%s)", err, string(body))
	}
	return &env, nil
}

// --- Diff -----------------------------------------------------------------

func computeManifestDiff(local, live json.RawMessage) (slashCmdDiff, error) {
	localCmds, localOther, err := splitManifestSlashCommands(local)
	if err != nil {
		return slashCmdDiff{}, fmt.Errorf("parse local manifest: %w", err)
	}
	liveCmds, liveOther, err := splitManifestSlashCommands(live)
	if err != nil {
		return slashCmdDiff{}, fmt.Errorf("parse live manifest: %w", err)
	}

	diff := slashCmdDiff{
		Added:   []slackSlashCmd{},
		Removed: []slackSlashCmd{},
		Changed: []slashCmdChange{},
	}

	localIdx := indexCmds(localCmds)
	liveIdx := indexCmds(liveCmds)

	for name, lc := range localIdx {
		if rc, ok := liveIdx[name]; !ok {
			diff.Added = append(diff.Added, lc)
		} else if !slashCmdEqual(lc, rc) {
			diff.Changed = append(diff.Changed, slashCmdChange{Command: name, From: rc, To: lc})
		}
	}
	for name, rc := range liveIdx {
		if _, ok := localIdx[name]; !ok {
			diff.Removed = append(diff.Removed, rc)
		}
	}
	sortSlashCmds(diff.Added)
	sortSlashCmds(diff.Removed)
	sort.Slice(diff.Changed, func(i, j int) bool { return diff.Changed[i].Command < diff.Changed[j].Command })

	var paths []string
	walkPaths(localOther, liveOther, "", &paths)
	if len(paths) > 0 {
		diff.NonCommandFieldsChanged = true
		diff.NonCommandFieldsPaths = paths
	}
	return diff, nil
}

// splitManifestSlashCommands extracts features.slash_commands as a
// typed slice and returns the remainder of the manifest (with
// slash_commands removed) for non-command-fields drift detection.
func splitManifestSlashCommands(raw json.RawMessage) ([]slackSlashCmd, map[string]any, error) {
	if len(raw) == 0 {
		return nil, map[string]any{}, nil
	}
	var top map[string]any
	if err := json.Unmarshal(raw, &top); err != nil {
		return nil, nil, err
	}
	var cmds []slackSlashCmd
	if features, ok := top["features"].(map[string]any); ok {
		if rawCmds, ok := features["slash_commands"]; ok {
			b, err := json.Marshal(rawCmds)
			if err != nil {
				return nil, nil, fmt.Errorf("re-marshal slash_commands: %w", err)
			}
			if err := json.Unmarshal(b, &cmds); err != nil {
				return nil, nil, fmt.Errorf("decode slash_commands array: %w", err)
			}
			delete(features, "slash_commands")
			if len(features) == 0 {
				delete(top, "features")
			}
		}
	}
	return cmds, top, nil
}

func indexCmds(cmds []slackSlashCmd) map[string]slackSlashCmd {
	out := make(map[string]slackSlashCmd, len(cmds))
	for _, c := range cmds {
		out[c.Command] = c
	}
	return out
}

func slashCmdEqual(a, b slackSlashCmd) bool {
	return a.Command == b.Command &&
		a.Description == b.Description &&
		a.URL == b.URL &&
		a.UsageHint == b.UsageHint &&
		a.ShouldEscape == b.ShouldEscape
}

func sortSlashCmds(cs []slackSlashCmd) {
	sort.Slice(cs, func(i, j int) bool { return cs[i].Command < cs[j].Command })
}

// walkPaths recursively diffs two `any` trees (decoded JSON) and
// records JSON-pointer-ish paths for keys whose values differ. Used
// for non-command-fields drift detection only — it does NOT need to
// be a complete JSON Pointer implementation.
func walkPaths(a, b any, prefix string, out *[]string) {
	if reflect.DeepEqual(a, b) {
		return
	}
	am, aok := a.(map[string]any)
	bm, bok := b.(map[string]any)
	if !aok || !bok {
		if prefix == "" {
			prefix = "/"
		}
		*out = append(*out, prefix)
		return
	}
	keys := map[string]struct{}{}
	for k := range am {
		keys[k] = struct{}{}
	}
	for k := range bm {
		keys[k] = struct{}{}
	}
	ks := make([]string, 0, len(keys))
	for k := range keys {
		ks = append(ks, k)
	}
	sort.Strings(ks)
	for _, k := range ks {
		walkPaths(am[k], bm[k], prefix+"/"+k, out)
	}
}

// --- Output --------------------------------------------------------------

func printDiffText(w io.Writer, d slashCmdDiff) {
	if d.NonCommandFieldsChanged {
		fmt.Fprintln(w, "Non-command manifest fields drifted from local:") //nolint:errcheck // best-effort writer
		for _, p := range d.NonCommandFieldsPaths {
			fmt.Fprintf(w, "  - %s\n", p) //nolint:errcheck // best-effort writer
		}
	}
	if len(d.Added) > 0 {
		fmt.Fprintln(w, "Added (in local, not live):") //nolint:errcheck // best-effort writer
		for _, c := range d.Added {
			fmt.Fprintf(w, "  - %s    %s\n", c.Command, c.Description) //nolint:errcheck // best-effort writer
		}
	}
	if len(d.Removed) > 0 {
		fmt.Fprintln(w, "Removed (in live, not local):") //nolint:errcheck // best-effort writer
		for _, c := range d.Removed {
			fmt.Fprintf(w, "  - %s    %s\n", c.Command, c.Description) //nolint:errcheck // best-effort writer
		}
	}
	if len(d.Changed) > 0 {
		fmt.Fprintln(w, "Changed (description / url / usage_hint differs):") //nolint:errcheck // best-effort writer
		for _, ch := range d.Changed {
			fmt.Fprintf(w, "  - %s\n", ch.Command)                              //nolint:errcheck // best-effort writer
			fmt.Fprintf(w, "      from: description=%q url=%q usage_hint=%q\n", //nolint:errcheck // best-effort writer
				ch.From.Description, ch.From.URL, ch.From.UsageHint)
			fmt.Fprintf(w, "      to:   description=%q url=%q usage_hint=%q\n", //nolint:errcheck // best-effort writer
				ch.To.Description, ch.To.URL, ch.To.UsageHint)
		}
	}
}

// jsonEnvelope is the structured output schema. Field tags are pinned
// by TestSyncCommandsJSONOutput.
type jsonEnvelope struct {
	WorkspaceID  string       `json:"workspace_id"`
	AppID        string       `json:"app_id"`
	Diff         slashCmdDiff `json:"diff"`
	UpdateIssued bool         `json:"update_issued"`
	Verified     bool         `json:"verified"`
}

func emitJSONEnvelope(w io.Writer, o slackSyncOpts, diff slashCmdDiff, updateIssued, verified bool) error {
	env := jsonEnvelope{
		WorkspaceID:  o.workspaceID,
		AppID:        o.appID,
		Diff:         diff,
		UpdateIssued: updateIssued,
		Verified:     verified,
	}
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(env)
}
