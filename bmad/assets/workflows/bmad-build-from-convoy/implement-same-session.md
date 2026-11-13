Implement the stories in the existing implementation convoy recorded as
`gc.input_convoy_id` in one shared drain session, using implementation target
{{implementation_target}}. Stories run one at a time, in drain order, in the
one shared worktree recorded on each member as `work_dir`. Work only on the
convoy members routed to this stage.

Use the assigned BMAD story implementation skill for each story. When upstream
BMAD text asks for sub-agent/task handoff, represent that delegation as Gas City
beads, convoys, or graph lanes rather than provider-native execution. If one
story fails, skip the remaining stories and record the failure reason.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
