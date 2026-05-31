package cmd

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"github.com/sjarmak/gc-slack-cli/internal/state/apps"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// maxManifestBytes caps the size of a Slack manifest we will accept on
// import. Slack's own manifests are O(1 KiB); the cap exists so a hostile
// or accidental large input fails fast instead of inflating the on-disk
// apps.json blob (manifest_raw stores the bytes verbatim).
const maxManifestBytes = 1 << 20 // 1 MiB

// slackManifest decodes only the manifest fields the import flow reads
// directly. Unknown fields are tolerated by encoding/json and the raw
// manifest bytes are preserved on the record (manifest_raw) so future
// beads can re-parse fields this struct ignores.
//
// Schema reference: https://api.slack.com/reference/manifests
type slackManifest struct {
	DisplayInformation slackManifestDisplay  `json:"display_information"`
	Features           slackManifestFeatures `json:"features"`
	OAuthConfig        slackManifestOAuth    `json:"oauth_config"`
}

type slackManifestDisplay struct {
	Name string `json:"name"`
}

type slackManifestFeatures struct {
	SlashCommands []slackManifestSlashCmd `json:"slash_commands"`
}

type slackManifestSlashCmd struct {
	Command string `json:"command"`
}

type slackManifestOAuth struct {
	Scopes slackManifestScopes `json:"scopes"`
}

type slackManifestScopes struct {
	Bot []string `json:"bot"`
}

// requiredBotScopes is the single source of truth shared by the
// validator and the per-scope test; downstream beads (.2-.9) assume
// every imported app declares all of these.
func requiredBotScopes() []string {
	return []string{
		"commands",
		"chat:write",
		"chat:write.customize",
		"channels:history",
		"groups:history",
		"im:history",
		"mpim:history",
		"files:read",
		"files:write",
		"reactions:write",
	}
}

func parseSlackManifest(data []byte) (slackManifest, error) {
	var m slackManifest
	if err := json.Unmarshal(data, &m); err != nil {
		return slackManifest{}, fmt.Errorf("decode slack manifest: %w", err)
	}
	return m, nil
}

func validateSlackManifest(m slackManifest) error {
	have := make(map[string]struct{}, len(m.OAuthConfig.Scopes.Bot))
	for _, s := range m.OAuthConfig.Scopes.Bot {
		have[s] = struct{}{}
	}
	var missing []string
	for _, want := range requiredBotScopes() {
		if _, ok := have[want]; !ok {
			missing = append(missing, want)
		}
	}
	if len(missing) > 0 {
		sort.Strings(missing)
		return fmt.Errorf("slack manifest missing required bot scopes: %s", strings.Join(missing, ", "))
	}
	return nil
}

// NewImportAppCmd constructs the cobra subcommand for `gc-slack-cli
// import-app`. Mirrors cmd/gc/cmd_slack_import_app.go's
// newSlackImportAppCmd: same flags, same defaults, same outputs, same
// errors. The stderr writer is accepted to match the cmd-package
// constructor signature even though import-app routes all messages
// through stdout.
func NewImportAppCmd(stdout, _ io.Writer) *cobra.Command {
	var (
		workspaceID string
		appID       string
	)
	cmd := &cobra.Command{
		Use:   "import-app <manifest.json>",
		Short: "Import a Slack app manifest into the gc city's slack-pack registry",
		Long: `Import a Slack app manifest into the gc city's slack-pack registry.

Reads the JSON manifest at <manifest.json>, validates that it declares
the bot scopes the slack-pack adapter and downstream commands require,
and persists an app record keyed by (workspace_id, app_id) at
<cityPath>/.gc/slack/apps.json.

Slack manifests do not contain workspace_id or app_id (Slack assigns
the latter when the app is created); both are required CLI flags.
Re-importing the same (workspace_id, app_id) updates the record in
place — the registry never grows from idempotent re-imports.

Schema reference: https://api.slack.com/reference/manifests`,
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return runSlackImportApp(stdout, args[0], workspaceID, appID)
		},
	}
	defaultWorkspace := workspace.IDDefault()
	cmd.Flags().StringVar(&workspaceID, "workspace-id", defaultWorkspace,
		workspace.IDFlagUsage)
	cmd.Flags().StringVar(&appID, "app-id", "",
		"Slack app id, e.g. A0123456 — assigned by Slack post-create (required)")
	if defaultWorkspace == "" {
		_ = cmd.MarkFlagRequired("workspace-id")
	}
	_ = cmd.MarkFlagRequired("app-id")
	return cmd
}

func runSlackImportApp(stdout io.Writer, manifestPath, workspaceID, appID string) error {
	cityPath, err := ResolveCityPath()
	if err != nil {
		return fmt.Errorf("resolve city: %w", err)
	}

	absManifestPath, err := filepath.Abs(manifestPath)
	if err != nil {
		return fmt.Errorf("resolve slack manifest path %q: %w", manifestPath, err)
	}

	fi, err := os.Stat(absManifestPath)
	if err != nil {
		return fmt.Errorf("stat slack manifest %q: %w", absManifestPath, err)
	}
	if fi.Size() > maxManifestBytes {
		return fmt.Errorf("slack manifest %q too large (%d bytes, limit %d)", absManifestPath, fi.Size(), maxManifestBytes)
	}

	data, err := os.ReadFile(absManifestPath)
	if err != nil {
		return fmt.Errorf("read slack manifest %q: %w", absManifestPath, err)
	}

	m, err := parseSlackManifest(data)
	if err != nil {
		return err
	}
	if err := validateSlackManifest(m); err != nil {
		return err
	}

	slashCmds := make([]string, 0, len(m.Features.SlashCommands))
	for _, sc := range m.Features.SlashCommands {
		if sc.Command != "" {
			slashCmds = append(slashCmds, sc.Command)
		}
	}

	rec := apps.Record{
		WorkspaceID:   workspaceID,
		AppID:         appID,
		DisplayName:   m.DisplayInformation.Name,
		Scopes:        append([]string(nil), m.OAuthConfig.Scopes.Bot...),
		SlashCommands: slashCmds,
		ManifestPath:  absManifestPath,
		ManifestRaw:   data,
		ImportedAt:    time.Now().UTC(),
	}

	reg, err := apps.NewRegistry(apps.Path(cityPath))
	if err != nil {
		return fmt.Errorf("open slack app registry: %w", err)
	}
	if err := reg.Set(rec); err != nil {
		return fmt.Errorf("persist slack app record: %w", err)
	}

	v := rec.SafeLogFields()
	fmt.Fprintf(stdout, "Imported Slack app %s/%s (display_name=%q, scopes=%d, slash_commands=%d)\n", //nolint:errcheck
		v.WorkspaceID, v.AppID, v.DisplayName, v.ScopeCount, v.SlashCommandCount)
	return nil
}
