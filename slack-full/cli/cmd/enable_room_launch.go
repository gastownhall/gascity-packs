package cmd

import (
	"fmt"
	"io"
	"strings"
	"time"

	"github.com/spf13/cobra"

	"github.com/sjarmak/gc-slack-cli/internal/state/rooms"
	"github.com/sjarmak/gc-slack-cli/internal/state/workspace"
)

// NewEnableRoomLaunchCmd returns `gc-slack-cli enable-room-launch` —
// the verb that enables Slack-launcher mode on a channel by binding
// (workspace_id, channel_id) → pool_template at
// <cityPath>/.gc/slack/room_launch_mappings.json. The slack-pack adapter
// reads this file at startup and uses it to handle `@@<handle>` posts:
// such a post in an enabled channel spawns a new gc session under the
// configured pool template, registers <handle> as the session's alias,
// and binds (channelID, threadTS) → sessionID so subsequent posts in
// the thread converge on the same session (gc-cby.5).
//
// The pool_template is opaque (operator-supplied). Gas City has ZERO
// hardcoded role names; whatever the operator wires here is what the
// adapter passes to gc's session-create endpoint as the `name` field.
//
// The binding is idempotent: re-binding the same channel preserves the
// original CreatedAt and replaces PoolTemplate. A future P3 follow-up
// (gc-cby.5.disable, file when needed) will mirror this with a
// `gc-slack-cli disable-room-launch` for removal.
func NewEnableRoomLaunchCmd(stdout, _ io.Writer) *cobra.Command {
	var (
		workspaceID  string
		poolTemplate string
	)
	cmd := &cobra.Command{
		Use:   "enable-room-launch <channel-id>",
		Short: "Enable Slack-launcher mode on a channel — `@@<handle>` posts spawn new sessions",
		Long: `Enable Slack-launcher mode on a Slack channel.

Persists a (workspace_id, channel_id) → pool_template record at
<cityPath>/.gc/slack/room_launch_mappings.json. The slack-pack adapter
reads this file at startup and uses it to handle '@@<handle>' posts:
such a post in an enabled channel spawns a new gc session under the
configured pool template, registers <handle> as the session's alias,
and binds the Slack thread to the new session so subsequent '@<handle>'
posts in the same thread route to it.

The binding is idempotent: re-binding the same channel preserves the
original CreatedAt and replaces pool_template.

The pool_template is operator-supplied and intentionally opaque to gc.
Gas City has ZERO hardcoded role names; the slack-pack adapter passes
this string verbatim to gc's session-create endpoint as the 'name'
field, so it must match an agent template the city actually configures.`,
		Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			return runSlackEnableRoomLaunch(stdout, args[0], workspaceID, poolTemplate)
		},
	}
	defaultWorkspace := workspace.IDDefault()
	cmd.Flags().StringVar(&workspaceID, "workspace-id", defaultWorkspace,
		workspace.IDFlagUsage)
	cmd.Flags().StringVar(&poolTemplate, "launcher", "",
		"Pool template (agent name) the slack-pack adapter spawns for `@@<handle>` posts in this channel (required)")
	if defaultWorkspace == "" {
		_ = cmd.MarkFlagRequired("workspace-id")
	}
	_ = cmd.MarkFlagRequired("launcher")
	return cmd
}

// runSlackEnableRoomLaunch persists the (workspaceID, channelID) →
// poolTemplate binding. Validation errors short-circuit before touching
// disk so a partial write is impossible. The trailing
// MapRigRestartReminder line is shared with the sibling map-channel
// and map-rig verbs because the slack-pack adapter loads every registry
// once at startup.
func runSlackEnableRoomLaunch(stdout io.Writer, channelID, workspaceID, poolTemplate string) error {
	channelID = strings.TrimSpace(channelID)
	if channelID == "" {
		return fmt.Errorf("channel-id is required (non-empty)")
	}
	if strings.TrimSpace(poolTemplate) == "" {
		return fmt.Errorf("--launcher is required (non-empty pool template)")
	}
	cityPath, err := ResolveCityPath()
	if err != nil {
		return fmt.Errorf("resolve city: %w", err)
	}
	reg, err := rooms.NewRegistry(rooms.Path(cityPath))
	if err != nil {
		return fmt.Errorf("open slack room-launch mapping registry: %w", err)
	}
	now := time.Now().UTC()
	rec := rooms.Record{
		WorkspaceID:  workspaceID,
		ChannelID:    channelID,
		PoolTemplate: poolTemplate,
		CreatedAt:    now,
		UpdatedAt:    now,
	}
	if err := reg.Set(rec); err != nil {
		return fmt.Errorf("persist slack room-launch mapping: %w", err)
	}
	fmt.Fprintf(stdout, "Enabled launcher mode on channel %s (workspace=%s) → pool %s\n", //nolint:errcheck
		channelID, workspaceID, poolTemplate)
	fmt.Fprintln(stdout, MapRigRestartReminder) //nolint:errcheck
	return nil
}
