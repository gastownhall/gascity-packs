package cmd

// MapRigRestartReminder is the trailing line printed on every
// success path of `gc-slack-cli map-rig`, `gc-slack-cli map-channel`,
// and `gc-slack-cli enable-room-launch` so operators see how to make
// the new binding live. SIGHUP-driven reload (gc-cby.23) is the cheap
// path; a full restart still works as the fallback when the pid is
// unknown.
//
// Lives in its own file (rather than inside any single verb) because
// three Phase 1 leaves all depend on it; pulling it out keeps each
// verb-port commit self-contained and avoids merge conflicts when
// the verbs land out of order.
const MapRigRestartReminder = "Send SIGHUP to slack-pack adapter (e.g. `pkill -HUP gc-slack-adapter`) — or restart it via `gc service restart slack` — to pick up the binding."
