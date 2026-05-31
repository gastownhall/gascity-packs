// gc-slack-cli — operator-facing CLI for the slack-pack.
//
// This binary is invoked by the slack-pack's commands/<cmd>.sh
// wrappers. Each subcommand is a thin facade over the on-disk slack
// runtime state under <city>/.gc/slack/ — the same files the adapter
// reads at startup and on SIGHUP.
//
// Phase 1 fans subcommands in one at a time (apps registry, channel
// mappings, rig mappings, etc.). This skeleton keeps the cobra root
// + RuntimePath helper in place so each port lands as a single
// self-contained leaf.
//
// The module deliberately avoids github.com/gastownhall/gascity
// internal imports: only stdlib + cobra. The adapter ships as an
// independent example; the CLI follows the same isolation rule.
package main

import (
	"fmt"
	"io"
	"os"

	"github.com/spf13/cobra"

	cmdpkg "github.com/sjarmak/gc-slack-cli/cmd"
)

func newRootCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:   "gc-slack-cli",
		Short: "Operator CLI for the gc slack-pack",
		Long: "gc-slack-cli operates on the on-disk slack runtime state " +
			"under <city>/.gc/slack/ — the same files the slack-adapter " +
			"reads at startup and on SIGHUP. Subcommands are added in " +
			"Phase 1 of the slack-cli relocation.",
		// SilenceUsage avoids dumping usage on every runtime error.
		// SilenceErrors lets the main() Execute caller print the
		// error itself with consistent formatting.
		SilenceUsage:  true,
		SilenceErrors: true,
		// Args: explicit "unknown command" rejection. The skeleton has
		// no subcommands yet, so cobra would otherwise accept arbitrary
		// positional args silently. Once subcommands are wired in
		// (Phase 1 leaves) cobra's own resolver takes precedence; this
		// validator only fires on truly-unknown args.
		Args: func(cmd *cobra.Command, args []string) error {
			if len(args) == 0 {
				return nil
			}
			return fmt.Errorf("unknown command %q for %q", args[0], cmd.CommandPath())
		},
		// RunE on no-args: print usage. The skeleton has nothing to
		// run, but a bare invocation should be useful — show the help
		// section (including the "Usage:" header) rather than just the
		// long description.
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}
	// Phase 1 subcommands. New leaves append one cmd.AddCommand line
	// here in alphabetical order — see PORTING.md "Cobra subcommand
	// registration in main.go".
	cmd.AddCommand(cmdpkg.NewEnableRoomLaunchCmd(os.Stdout, os.Stderr))
	cmd.AddCommand(cmdpkg.NewImportAppCmd(os.Stdout, os.Stderr))
	cmd.AddCommand(cmdpkg.NewMapChannelCmd(os.Stdout, os.Stderr))
	cmd.AddCommand(cmdpkg.NewMapRigCmd(os.Stdout, os.Stderr))
	cmd.AddCommand(cmdpkg.NewPostMessageCmd(os.Stdout, os.Stderr))
	cmd.AddCommand(cmdpkg.NewSyncCommandsCmd(os.Stdout, os.Stderr))
	cmd.AddCommand(cmdpkg.NewSyncSubteamAliasesCmd(os.Stdout, os.Stderr))
	return cmd
}

// run executes the CLI with args (excluding argv[0]) and writes any
// error to stderr. Extracted from main() so tests can drive the
// full os.Exit code path without spawning a subprocess.
func run(args []string, stderr io.Writer) int {
	cmd := newRootCmd()
	cmd.SetArgs(args)
	if err := cmd.Execute(); err != nil {
		fmt.Fprintln(stderr, "gc-slack-cli:", err)
		return 1
	}
	return 0
}

func main() {
	os.Exit(run(os.Args[1:], os.Stderr))
}
