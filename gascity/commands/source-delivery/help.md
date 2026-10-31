Manage the quick-start workflow source evidence and native owned worktree.

`gc gc source-delivery <prepare|show|review|check|integrate|cleanup> --root <workflow-id>`

Prepare also requires --source, --repo, --workspace-root and --verify-command.
Review requires --sha and --status; rejected reviews require --findings.
Check runs the fixed verification command with a ten-minute bound. Integrate
requires matching output, review and test SHAs. Native workflow finalization
closes the linked source after integration and required cleanup pass.
Cleanup delegates to native ownership, attempt and reachability gates.
