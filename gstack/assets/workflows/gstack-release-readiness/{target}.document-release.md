Run the gstack document-release lane.

Check README, architecture docs, usage docs, changelog, and contributor docs
that are affected by the change. Write exact documentation updates or state why
no docs need to change.

Current review_mode is {{review_mode}}. In report mode, put proposed wording in
the findings artifact and do not edit, stage, or commit documentation or other
product source.

Write findings under the artifact root.

Close with `gc.outcome=pass`,
`gstack.release.docs_verdict=approve|iterate`, and
`gstack.release.output_path=<document-release report path>`.

Do not invoke provider-native subagents. You are the docs lane.
