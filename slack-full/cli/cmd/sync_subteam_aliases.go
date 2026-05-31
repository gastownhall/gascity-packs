package cmd

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// sync-subteam-aliases reconciles <city>/.gc/slack/subteam-aliases.json
// — the operator-edited Slack User Group ("subteam") ID → gc handle map
// the adapter consults when routing unlabeled `<!subteam^Sxxx>` mentions
// — with the workspace's live Slack User Groups.
//
// The write is a MERGE, never a replace: every entry already on disk is
// preserved. Entries whose subteam ID matches a live User Group have
// their handle refreshed to the live value; brand-new live User Groups
// are added; entries with no matching live User Group are left in place
// and reported under "local-only" so a hand-added or now-deleted binding
// is visible without being clobbered.
//
// usergroups.list needs the bot token to carry the `usergroups:read`
// scope. Apps without it get a readable `missing_scope` error — the
// operator can still hand-edit the file, exactly as before this verb
// existed.

const (
	// subteamAliasesFilename is the on-disk name under <city>/.gc/slack/.
	// Must match the adapter's default subteamAliasStorePath so a write
	// here is the same file the adapter reads on SIGHUP.
	subteamAliasesFilename = "subteam-aliases.json"

	// slackUsergroupsListMethod is the Slack web API method this verb
	// calls. Documented at https://api.slack.com/methods/usergroups.list
	slackUsergroupsListMethod = "usergroups.list"
)

type subteamSyncOpts struct {
	workspaceID string
	token       string
	apiBase     string
	dryRun      bool
	output      string
	timeout     time.Duration
}

// subteamAliasEntry is a (subteam_id, handle) pair used for the added,
// unchanged, and local-only diff buckets.
type subteamAliasEntry struct {
	SubteamID string `json:"subteam_id"`
	Handle    string `json:"handle"`
}

// subteamAliasChange records a binding whose handle differs between the
// saved file and the live Slack User Group.
type subteamAliasChange struct {
	SubteamID string `json:"subteam_id"`
	From      string `json:"from"`
	To        string `json:"to"`
}

// subteamAliasDiff is the structured diff between the saved file and the
// live usergroups list.
//
// LocalOnly entries are on disk but absent from the live list. They are
// PRESERVED in the written file — operator-added bindings are never
// dropped — and surfaced here only so the operator can spot a binding
// Slack no longer knows about (e.g. a deleted User Group, or a hand-
// added entry whose ID was mistyped).
type subteamAliasDiff struct {
	Added     []subteamAliasEntry  `json:"added"`
	Changed   []subteamAliasChange `json:"changed"`
	Unchanged []subteamAliasEntry  `json:"unchanged"`
	LocalOnly []subteamAliasEntry  `json:"local_only"`
}

// writeNeeded reports whether the merge would alter the file. Only adds
// and handle changes mutate disk; unchanged and local-only entries
// round-trip identically, so a diff with only those is a no-op write we
// skip.
func (d subteamAliasDiff) writeNeeded() bool {
	return len(d.Added) > 0 || len(d.Changed) > 0
}

// NewSyncSubteamAliasesCmd wires the cobra verb. The runner is split out
// so tests can drive the same code path without re-parsing flags
// (mirrors NewSyncCommandsCmd).
func NewSyncSubteamAliasesCmd(stdout, _ io.Writer) *cobra.Command {
	var o subteamSyncOpts
	cmd := &cobra.Command{
		Use:   "sync-subteam-aliases",
		Short: "Reconcile subteam-aliases.json with the workspace's live Slack User Groups",
		Long: `Reconcile <city>/.gc/slack/subteam-aliases.json with the workspace's
live Slack User Groups.

Calls Slack usergroups.list, then MERGES the result into the on-disk
map of Slack User Group ("subteam") ids → gc handles. The merge is
non-destructive: existing entries are preserved, handles are refreshed
where the live User Group name differs, and brand-new User Groups are
added. Entries with no matching live User Group are left in place and
reported as "local-only".

The adapter reads this file at startup and on SIGHUP to route the
unlabeled '<!subteam^Sxxx>' mention shape to the bound handle.

The Slack bot token (xoxb-...) is read from --token or $` + slackBotTokenEnv + `
and MUST carry the usergroups:read scope; without it the verb reports
a readable missing_scope error and writes nothing.

Schema: https://api.slack.com/methods/usergroups.list`,
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return runSlackSyncSubteamAliases(cmd.Context(), stdout, o)
		},
	}
	defaultWorkspace := workspace.IDDefault()
	cmd.Flags().StringVar(&o.workspaceID, "workspace-id", defaultWorkspace,
		workspace.IDFlagUsage)
	cmd.Flags().StringVar(&o.token, "token", "",
		"Slack bot token (xoxb-...) with the usergroups:read scope. Falls back to $"+slackBotTokenEnv)
	cmd.Flags().StringVar(&o.apiBase, "api-base", "",
		"Slack web API base URL (defaults to $"+slackAPIBaseEnv+" or "+slackChatAPIDefaultBase+"). "+
			"Trusted operator-only flag — do not source from untrusted input; the verb sends the bot token to whatever host this resolves to.")
	cmd.Flags().BoolVar(&o.dryRun, "dry-run", false,
		"Print the diff and exit without writing subteam-aliases.json")
	cmd.Flags().StringVar(&o.output, "output", "text",
		"Output format: text|json")
	cmd.Flags().DurationVar(&o.timeout, "timeout", 30*time.Second,
		"Hard timeout for the entire operation")
	if defaultWorkspace == "" {
		_ = cmd.MarkFlagRequired("workspace-id")
	}
	return cmd
}

func runSlackSyncSubteamAliases(ctx context.Context, stdout io.Writer, o subteamSyncOpts) error {
	if ctx == nil {
		ctx = context.Background()
	}
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
		token = strings.TrimSpace(os.Getenv(slackBotTokenEnv))
	}
	if token == "" {
		return fmt.Errorf("slack bot token not provided (--token or $%s); it must carry the usergroups:read scope", slackBotTokenEnv)
	}

	apiBase := o.apiBase
	if apiBase == "" {
		apiBase = strings.TrimSpace(os.Getenv(slackAPIBaseEnv))
	}
	if apiBase == "" {
		apiBase = slackChatAPIDefaultBase
	}

	cityPath, err := ResolveCityPath()
	if err != nil {
		return fmt.Errorf("resolve city: %w", err)
	}
	path := filepath.Join(cityPath, ".gc", "slack", subteamAliasesFilename)

	existing, err := loadSubteamAliasFile(path)
	if err != nil {
		return err
	}

	live, err := slackUsergroupsList(ctx, apiBase, token, o.workspaceID)
	if err != nil {
		return err
	}

	diff, merged := computeSubteamAliasDiff(existing, live)

	wrote := false
	if !o.dryRun && diff.writeNeeded() {
		if err := writeSubteamAliasFile(path, merged); err != nil {
			return err
		}
		wrote = true
	}

	if o.output == "json" {
		return emitSubteamSyncJSON(stdout, o, path, diff, wrote, len(merged))
	}

	printSubteamDiffText(stdout, diff)
	switch {
	case o.dryRun:
		fmt.Fprintf(stdout, "Dry run: would write %d entries to %s (no changes applied).\n", len(merged), path) //nolint:errcheck // best-effort stdout
	case wrote:
		fmt.Fprintf(stdout, "Wrote %d entries to %s\n", len(merged), path) //nolint:errcheck // best-effort stdout
		fmt.Fprintln(stdout, MapRigRestartReminder)                        //nolint:errcheck // best-effort stdout
	default:
		fmt.Fprintf(stdout, "subteam-aliases.json already in sync (%d entries); no write issued.\n", len(merged)) //nolint:errcheck // best-effort stdout
	}
	return nil
}

// --- Slack API client -----------------------------------------------------

// slackUsergroup is the subset of a usergroups.list entry we consume.
// `handle` is the workspace-admin-chosen short name (e.g. "zelda-pl")
// and is what an adapter routes a `<!subteam^Sxxx>` mention to.
type slackUsergroup struct {
	ID     string `json:"id"`
	TeamID string `json:"team_id"`
	Handle string `json:"handle"`
	Name   string `json:"name"`
}

// slackUsergroupsListResponse is the usergroups.list envelope. `needed`
// / `provided` accompany an `ok:false` missing_scope error and let the
// verb name the exact scope to add.
type slackUsergroupsListResponse struct {
	OK         bool             `json:"ok"`
	Error      string           `json:"error,omitempty"`
	Needed     string           `json:"needed,omitempty"`
	Provided   string           `json:"provided,omitempty"`
	Usergroups []slackUsergroup `json:"usergroups,omitempty"`
}

// slackUsergroupsList calls usergroups.list with the bot token and
// returns the live User Groups. When workspaceID is set, results are
// filtered to that team client-side (a regular workspace bot token is
// already single-workspace; this also keeps an org-level token from
// polluting the file with other workspaces' groups). The `team_id`
// request param is deliberately NOT sent — it is only valid for
// org-level tokens and would error on a plain workspace token.
func slackUsergroupsList(ctx context.Context, apiBase, token, workspaceID string) ([]slackUsergroup, error) {
	endpoint := strings.TrimRight(apiBase, "/") + "/" + slackUsergroupsListMethod
	form := url.Values{}
	// include_disabled defaults to false; deleted/disabled groups are
	// excluded so they surface as "local-only" rather than being
	// re-confirmed.
	form.Set("include_disabled", "false")
	form.Set("include_count", "false")

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, strings.NewReader(form.Encode()))
	if err != nil {
		return nil, fmt.Errorf("build %s request: %w", slackUsergroupsListMethod, err)
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Authorization", "Bearer "+token)
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		// %w preserves *url.Error, which references the URL but not the
		// Authorization header, so the token does not leak here.
		return nil, fmt.Errorf("post %s: %w", endpoint, err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return nil, fmt.Errorf("read %s response: %w", slackUsergroupsListMethod, err)
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("slack %s http %d: %s", slackUsergroupsListMethod, resp.StatusCode, truncatePost(string(body), slackErrorBodyMaxLen))
	}
	var out slackUsergroupsListResponse
	if err := json.Unmarshal(body, &out); err != nil {
		return nil, fmt.Errorf("decode %s response: %w (body=%s)", slackUsergroupsListMethod, err, truncatePost(string(body), slackErrorBodyMaxLen))
	}
	if !out.OK {
		if out.Error == "missing_scope" {
			needed := out.Needed
			if needed == "" {
				needed = "usergroups:read"
			}
			return nil, fmt.Errorf("slack %s: missing_scope — the bot token needs the %q scope (provided: %q). Add it to the Slack app's bot OAuth scopes, reinstall the app, then retry.",
				slackUsergroupsListMethod, needed, out.Provided)
		}
		return nil, fmt.Errorf("slack %s api error: %s", slackUsergroupsListMethod, out.Error)
	}

	if workspaceID == "" {
		return out.Usergroups, nil
	}
	filtered := out.Usergroups[:0:0]
	for _, ug := range out.Usergroups {
		if ug.TeamID != "" && ug.TeamID != workspaceID {
			continue
		}
		filtered = append(filtered, ug)
	}
	return filtered, nil
}

// --- Diff & merge ----------------------------------------------------------

// computeSubteamAliasDiff classifies each live User Group against the
// saved map and returns both the diff (for reporting) and the merged
// map to write. The merged map starts as a copy of existing — so no
// on-disk binding is ever dropped — with live handles layered on top.
func computeSubteamAliasDiff(existing map[string]string, live []slackUsergroup) (subteamAliasDiff, map[string]string) {
	merged := make(map[string]string, len(existing)+len(live))
	for id, h := range existing {
		merged[id] = h
	}

	diff := subteamAliasDiff{
		Added:     []subteamAliasEntry{},
		Changed:   []subteamAliasChange{},
		Unchanged: []subteamAliasEntry{},
		LocalOnly: []subteamAliasEntry{},
	}

	liveIDs := make(map[string]struct{}, len(live))
	for _, ug := range live {
		// The adapter's parseSubteamAliasMap rejects empty ids and empty
		// handles; never write one or a SIGHUP reload would fail. Skip
		// defensively rather than poison the file.
		if ug.ID == "" || ug.Handle == "" {
			continue
		}
		liveIDs[ug.ID] = struct{}{}
		switch prev, ok := existing[ug.ID]; {
		case !ok:
			diff.Added = append(diff.Added, subteamAliasEntry{SubteamID: ug.ID, Handle: ug.Handle})
		case prev != ug.Handle:
			diff.Changed = append(diff.Changed, subteamAliasChange{SubteamID: ug.ID, From: prev, To: ug.Handle})
		default:
			diff.Unchanged = append(diff.Unchanged, subteamAliasEntry{SubteamID: ug.ID, Handle: ug.Handle})
		}
		merged[ug.ID] = ug.Handle
	}

	for id, h := range existing {
		if _, ok := liveIDs[id]; !ok {
			diff.LocalOnly = append(diff.LocalOnly, subteamAliasEntry{SubteamID: id, Handle: h})
		}
	}

	sortSubteamEntries(diff.Added)
	sortSubteamEntries(diff.Unchanged)
	sortSubteamEntries(diff.LocalOnly)
	sort.Slice(diff.Changed, func(i, j int) bool { return diff.Changed[i].SubteamID < diff.Changed[j].SubteamID })
	return diff, merged
}

func sortSubteamEntries(es []subteamAliasEntry) {
	sort.Slice(es, func(i, j int) bool { return es[i].SubteamID < es[j].SubteamID })
}

// --- File IO ---------------------------------------------------------------

// loadSubteamAliasFile reads the on-disk map. A missing file yields an
// empty map (first sync), matching the adapter's "missing file = empty"
// semantics.
func loadSubteamAliasFile(path string) (map[string]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return map[string]string{}, nil
		}
		return nil, fmt.Errorf("read %s: %w", path, err)
	}
	var m map[string]string
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("decode %s: %w", path, err)
	}
	if m == nil {
		m = map[string]string{}
	}
	return m, nil
}

// writeSubteamAliasFile atomically writes the merged map with 0600 perms
// under a 0700 dir, mirroring the rigs/channels registry write so the
// adapter's permission-tightener never has to loosen anything.
func writeSubteamAliasFile(path string, m map[string]string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return fmt.Errorf("mkdir slack runtime dir %q: %w", dir, err)
	}
	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return fmt.Errorf("encode subteam alias map: %w", err)
	}
	data = append(data, '\n')
	f, err := os.CreateTemp(dir, "subteam-aliases-*.json.tmp")
	if err != nil {
		return fmt.Errorf("create subteam alias store tmp: %w", err)
	}
	tmpName := f.Name()
	cleanup := func() { _ = os.Remove(tmpName) }
	if err := f.Chmod(0o600); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("chmod subteam alias store tmp: %w", err)
	}
	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		cleanup()
		return fmt.Errorf("write subteam alias store tmp: %w", err)
	}
	if err := f.Close(); err != nil {
		cleanup()
		return fmt.Errorf("close subteam alias store tmp: %w", err)
	}
	if err := os.Rename(tmpName, path); err != nil {
		cleanup()
		return fmt.Errorf("rename subteam alias store: %w", err)
	}
	return nil
}

// --- Output ----------------------------------------------------------------

func printSubteamDiffText(w io.Writer, d subteamAliasDiff) {
	if len(d.Added) > 0 {
		fmt.Fprintln(w, "Added (live User Group, not on disk):") //nolint:errcheck // best-effort writer
		for _, e := range d.Added {
			fmt.Fprintf(w, "  + %s -> %s\n", e.SubteamID, e.Handle) //nolint:errcheck // best-effort writer
		}
	}
	if len(d.Changed) > 0 {
		fmt.Fprintln(w, "Changed (handle differs from live):") //nolint:errcheck // best-effort writer
		for _, c := range d.Changed {
			fmt.Fprintf(w, "  ~ %s: %s -> %s\n", c.SubteamID, c.From, c.To) //nolint:errcheck // best-effort writer
		}
	}
	if len(d.LocalOnly) > 0 {
		fmt.Fprintln(w, "Local-only (on disk, not in live Slack — preserved, not removed):") //nolint:errcheck // best-effort writer
		for _, e := range d.LocalOnly {
			fmt.Fprintf(w, "  = %s -> %s\n", e.SubteamID, e.Handle) //nolint:errcheck // best-effort writer
		}
	}
	if len(d.Unchanged) > 0 {
		fmt.Fprintf(w, "Unchanged: %d entr%s\n", len(d.Unchanged), plural(len(d.Unchanged))) //nolint:errcheck // best-effort writer
	}
}

func plural(n int) string {
	if n == 1 {
		return "y"
	}
	return "ies"
}

// subteamSyncEnvelope is the structured --output json schema.
type subteamSyncEnvelope struct {
	WorkspaceID string           `json:"workspace_id"`
	Path        string           `json:"path"`
	Diff        subteamAliasDiff `json:"diff"`
	WriteIssued bool             `json:"write_issued"`
	DryRun      bool             `json:"dry_run"`
	Total       int              `json:"total"`
}

func emitSubteamSyncJSON(w io.Writer, o subteamSyncOpts, path string, diff subteamAliasDiff, wrote bool, total int) error {
	env := subteamSyncEnvelope{
		WorkspaceID: o.workspaceID,
		Path:        path,
		Diff:        diff,
		WriteIssued: wrote,
		DryRun:      o.dryRun,
		Total:       total,
	}
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(env)
}
