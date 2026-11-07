Implement the stories in the existing implementation convoy recorded as
`gc.input_convoy_id`, using drain policy {{drain_policy}} and implementation
target {{implementation_target}}. Each convoy member runs BMAD story
development in its own worktree. Work only on the convoy members routed to this
stage.

Use the assigned BMAD story implementation skill for each story. When upstream
BMAD text asks for sub-agent/task handoff, represent that delegation as Gas City
beads, convoys, or graph lanes rather than provider-native execution. Record
item evidence so the review stage can map changes back to each story.

Do not invoke provider-native subagents or upstream BMAD runtime commands.
