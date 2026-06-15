# Packer

Packer is a Gas City pack-development toolkit. It gives agents the prompts,
skills, formulas, and command helpers needed to build packs while testing them
inside a real city and rig.

Use it when the work is about pack authoring rather than product code:

- creating or editing `pack.toml`
- adding agent prompts, skills, formulas, commands, doctor checks, or assets
- validating pack imports and template rendering
- running `gc lint <pack>` and targeted pack tests
- exercising formulas with `gc formula show` or controlled `gc formula cook`
- checking registry entries and release metadata

Operational notes discovered while building packs live are kept in
[`learned-workflow-notes.md`](./learned-workflow-notes.md).

## Artifact Decisions

Use the smallest artifact that preserves the boundary.

- `skills/`: model-facing workflow, safety rules, and domain knowledge. Route
  to reference files for long material instead of pasting whole tutorials into
  prompts.
- `template-fragments/`: prompt text shared by one or more agents. Verify every
  fragment render with `gc prime <agent> --strict`.
- `assets/`: scripts, examples, fixtures, generated files, and static data used
  by commands, formulas, tests, or prompts.
- `commands/`: direct operator entry points that should be one CLI command.
- `formulas/`: multi-step operational workflows with vars, handoff, retry,
  validation, import, release, or live-city state.
- `agents/`: runtime roles. Canonical `gastown` polecat-style pools are agent
  templates with `min_active_sessions = 0` and `max_active_sessions = N`, not
  `[[named_session]]` entries.

## Pack Release Workflow

A pack is not live just because a workspace stack is correct. The live city uses
the import source and lock state in `city.toml` and `packs.lock`.

1. Verify the candidate:

   ```bash
   jj status
   jj log -r 'trunk() | stack' --limit 40
   gc lint <pack-path>
   gc prime <agent> --strict
   gc formula show <formula>
   python3 -m unittest <focused-test>
   ```

2. Publish a reachable commit:

   ```bash
   jj bookmark set <bookmark> -r <stack-head>
   jj git push --bookmark <bookmark>
   jj log -r <stack-head> --no-graph --template 'commit_id ++ "\n"'
   ```

3. Update the city import at the correct scope. For a rig-scoped pack:

   ```bash
   gc import add \
     https://github.com/<owner>/<repo>/tree/<commit>/<pack-dir> \
     --name <binding-name> \
     --version sha:<commit> \
     --city <city-root> \
     --rig <rig-name>
   ```

   If the binding already exists at that scope, remove the stale import first:

   ```bash
   gc import remove <binding-name> --city <city-root> --rig <rig-name>
   ```

4. Install and verify:

   ```bash
   gc import install --city <city-root>
   gc import check --city <city-root>
   gc import status --city <city-root>
   gc prime <rig>/<agent> --strict --city <city-root>
   ```

Avoid adding a workspace-level import when the pack belongs under
`[rigs.imports]`; duplicate bindings can hide which version is live.

## Converting a Repo or Tutorial Into a Pack

Use `mol-packer-convert-repo-to-pack` when starting from an existing repository,
tutorial, or notes. The workflow inventories the source, designs the pack
surface, classifies source material into pack artifacts, then validates the
result.

Classification rules:

- procedures and safety rules become `skills/`
- shared prompt prose becomes `template-fragments/`
- scripts, examples, fixtures, and generated files become `assets/`
- repeatable operator actions become `commands/`
- multi-step workflows become `formulas/`
- runtime roles become `agents/`

Suggested first formulas for a converted pack:

- `mol-<pack>-validate`: lint, render prompts, compile formulas, and run focused
  tests
- `mol-<pack>-import-local`: add the pack to a target city/rig and verify
  discovery
- `mol-<pack>-live-city-test`: render live prompts and compile live formulas
- `mol-<pack>-release`: publish a reachable commit and refresh the city import

Keep the first pack thin. Move large tutorial text into references or assets and
route to it from a skill instead of embedding it in every prompt.

## Common Entry Points

Import it with a local binding, adjusting the source for the target city:

```toml
[imports.packer]
source = "../gascity-packs/packer"
```

Start a packer session when a rig needs pack development help:

```bash
gc session new packer --rig <rig>
```

For repeatable checks, use the formula:

```bash
gc sling <target> mol-packer-validate --formula \
  --var pack_path=/absolute/path/to/pack \
  --var pack_name=packer
```

For live-city import work, use `mol-packer-import-local-pack` with the target
rig, binding name, and pack source instead of hard-coding one machine's paths.