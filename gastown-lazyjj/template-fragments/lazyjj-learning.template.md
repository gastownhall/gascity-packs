{{ define "lazyjj-mental-model" }}
## LazyJJ Mental Model

LazyJJ leans on JJ's native graph instead of layering branch metadata on top.

- `@` is the working-copy commit, not a separate staging area
- a stack is the ancestry from `trunk()` to your current head
- editing an older commit automatically rebases descendants
- conflicts are recorded as state, so you can resolve them later without losing
  the graph
- `jj undo` and `jj op restore` are the fast recovery tools when you need to
  rewind or time-travel
{{ end }}

{{ define "lazyjj-stack-workflow" }}
## LazyJJ Stack Workflow

Use these commands as the default stack routine:

```bash
jj git fetch
jj log -r 'trunk()..@'
jj log -r 'stack & no_description'
jj absorb
jj diff --from branch_off
```

For a new stack head:

```bash
jj new trunk() -m "work: <short summary>"
```

For focused checkpoints inside the stack:

```bash
jj new -m "next"
jj describe -r @- -m "short description"
```
{{ end }}

{{ define "lazyjj-pr-workflow" }}
## LazyJJ PR Workflow

LazyJJ keeps PR publication close to the jj stack:

- `jj spr init` once per repo
- `jj spr diff --cherry-pick` for independent PRs
- `jj spr diff --all` only when the next change depends on the previous one
- `jj spr list` before landing
- `jj spr land --cherry-pick -r <change-id>` for independent land

If you are using the workspace-handoff mode instead of direct GitHub land,
bookmark the stack head and push that bookmark:

```bash
jj bookmark set <bookmark> -r @-
jj git push --bookmark <bookmark>
```
{{ end }}
