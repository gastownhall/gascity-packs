package cmd

import (
	"fmt"
	"io"
	"time"

	"github.com/spf13/cobra"

	"github.com/sjarmak/gc-slack-cli/internal/state/channels"
	"github.com/sjarmak/gc-slack-cli/internal/state/rigs"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// NewMapChannelCmd returns `gc-slack-cli map-channel` — the verb that
// persists a (workspace_id, channel_id) → session binding (or
// removes one) at <cityPath>/.gc/slack/channel_mappings.json. The
// slack-pack adapter reads this file at startup and routes
// /slack/interactions slash-command requests to the bound session.
//
// Per-channel `map-channel --session` bindings are overrides on top of
// the rig→{channels} default written by `gc-slack-cli map-rig`; channel
// mapping wins.
//
// The legacy `--rig` flag is deprecated (gc-cby.25) — use `gc-slack-cli
// map-rig` for rig→channel bindings. Cobra's MarkDeprecated handles
// the redirect: hides from --help and emits a stderr warning on
// every invocation. While active, the cby.4 cross-store conflict
// check still applies: a `--rig` write is rejected when the channel
// is already bound to a DIFFERENT rig in the rig-mapping registry.
func NewMapChannelCmd(stdout, _ io.Writer) *cobra.Command {
	var (
		workspaceID string
		rigName     string
		sessionID   string
		remove      bool
	)
	cmd := &cobra.Command{
		Use:   "map-channel <channel-id>",
		Short: "Bind a Slack channel to a gc session for slash-command routing",
		Long: `Bind a Slack channel to a gc session for slash-command routing.

Persists a (workspace_id, channel_id) → session record at
<cityPath>/.gc/slack/channel_mappings.json. The slack-pack adapter
reads this file at startup and routes incoming /slack/interactions
slash-command requests for the channel to the bound session.

--session is required (unless --remove). The binding is idempotent:
re-binding the same channel preserves the original CreatedAt and
overwrites the target fields. --remove always exits 0 — if no
binding exists, the command is a no-op.

For rig→channel bindings, use 'gc slack map-rig' (gc-cby.4). The
legacy '--rig' flag on this verb is deprecated (gc-cby.25); cobra
hides it from --help and emits a stderr deprecation warning on
every use.`,
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return runSlackMapChannel(stdout, args[0], workspaceID, rigName, sessionID, remove)
		},
	}
	defaultWorkspace := workspace.IDDefault()
	cmd.Flags().StringVar(&workspaceID, "workspace-id", defaultWorkspace,
		workspace.IDFlagUsage)
	cmd.Flags().StringVar(&rigName, "rig", "",
		"DEPRECATED (gc-cby.25): use 'gc slack map-rig' instead. Bind the channel to a gc rig.")
	cmd.Flags().StringVar(&sessionID, "session", "",
		"Bind the channel to a gc session (mutually exclusive with --rig)")
	cmd.Flags().BoolVar(&remove, "remove", false,
		"Remove the binding for <channel-id> if one exists (idempotent)")
	if defaultWorkspace == "" {
		_ = cmd.MarkFlagRequired("workspace-id")
	}
	cmd.MarkFlagsMutuallyExclusive("rig", "session")
	// MarkDeprecated auto-hides --rig from --help and emits
	// "Flag --rig has been deprecated, ..." on stderr at parse time.
	// Pattern mirrors cmd_events.go's --json deprecation.
	_ = cmd.Flags().MarkDeprecated("rig",
		"use 'gc slack map-rig <rig> --workspace-id <ws> --channel <c1> [--channel <c2> ...]' instead; the flag will be removed in a future release")
	return cmd
}

func runSlackMapChannel(stdout io.Writer, channelID, workspaceID, rigName, sessionID string, remove bool) error {
	cityPath, err := ResolveCityPath()
	if err != nil {
		return fmt.Errorf("resolve city: %w", err)
	}
	if remove {
		if rigName != "" || sessionID != "" {
			return fmt.Errorf("--remove cannot be combined with --rig or --session")
		}
		reg, err := channels.NewRegistry(channels.Path(cityPath))
		if err != nil {
			return fmt.Errorf("open slack channel mapping registry: %w", err)
		}
		existed, err := reg.Remove(workspaceID, channelID)
		if err != nil {
			return fmt.Errorf("remove slack channel mapping for %q: %w", channelID, err)
		}
		if existed {
			fmt.Fprintf(stdout, "Removed channel mapping %s (workspace=%s)\n", channelID, workspaceID) //nolint:errcheck
		} else {
			fmt.Fprintf(stdout, "No binding for channel %s (workspace=%s); nothing to remove\n", channelID, workspaceID) //nolint:errcheck
		}
		fmt.Fprintln(stdout, MapRigRestartReminder) //nolint:errcheck
		return nil
	}

	if rigName == "" && sessionID == "" {
		return fmt.Errorf("exactly one of --rig or --session is required (or use --remove)")
	}

	var (
		targetKind string
		targetID   string
	)
	switch {
	case rigName != "":
		targetKind = channels.TargetKindRig
		targetID = rigName
	default:
		targetKind = channels.TargetKindSession
		targetID = sessionID
	}

	// Cross-store conflict check is best-effort: load registry A, then write registry B.
	// CLI invocations are not atomic across both stores. Concurrent invocations between
	// check and write may produce overlap; the adapter detects and surfaces this via
	// `gc slack status` (conflict annotation) and a startup WARN log.
	//
	// Cross-store conflict check (cby.4 → cby.3 direction): only
	// applies to --rig writes. Session bindings are explicit
	// overrides on top of any rig default — that's the intended
	// composition pattern.
	if targetKind == channels.TargetKindRig {
		rigReg, err := rigs.NewRegistry(rigs.Path(cityPath))
		if err != nil {
			return fmt.Errorf("open slack rig mapping registry: %w", err)
		}
		if owner, _, ok := rigReg.LookupRigForChannel(workspaceID, channelID); ok && owner.RigName != rigName {
			return fmt.Errorf("map-channel: channel %q is already bound to rig %q via 'gc slack map-rig'; remove that binding first or use --rig %q to keep the same target rig",
				channelID, owner.RigName, owner.RigName)
		}
	}

	now := time.Now().UTC()
	rec := channels.Record{
		WorkspaceID: workspaceID,
		ChannelID:   channelID,
		TargetKind:  targetKind,
		TargetID:    targetID,
		CreatedAt:   now,
		UpdatedAt:   now,
	}
	reg, err := channels.NewRegistry(channels.Path(cityPath))
	if err != nil {
		return fmt.Errorf("open slack channel mapping registry: %w", err)
	}
	if err := reg.Set(rec); err != nil {
		return fmt.Errorf("persist slack channel mapping: %w", err)
	}
	fmt.Fprintf(stdout, "Mapped channel %s (workspace=%s) → %s:%s\n", //nolint:errcheck
		channelID, workspaceID, targetKind, targetID)
	fmt.Fprintln(stdout, MapRigRestartReminder) //nolint:errcheck
	return nil
}
