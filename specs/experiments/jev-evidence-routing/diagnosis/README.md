# Root cause of the fresh-city initialization failure

Diagnosis on 2026-09-19, using the installed Gas City 1.4.2, Beads 1.3.0 and
Dolt 2.3.5 binaries. Binary hashes are in [manifest.json](manifest.json).
The evidence does not support a general incompatibility between these versions.

**Correction, 2026-09-23.** This diagnosis overstates the preflight as the
defect behind the failures. The code path is accurately described: bd v1.3.0
`countExistingIssues` (`cmd/bd/init.go` ~2670–2708) opens a writable store under
a five-second deadline, and `runInitReinitPreflight` ignores the error. But it
only causes harm when migrations take longer than five seconds. On this host a
plain `bd init` took 25–56 s because load averages were 20–74 on an 18-CPU
machine, with swapping and several concurrent Dolt servers; the
`full-original-001` and `full-fresh-001` probes also ran concurrently. This is a
latent, load-dependent Beads issue, not a demonstrated production bug. Gas City
`main` already has a related mitigation that is not in v1.4.2: 8c2b970fe
"fix(bd): corroborate a negative schema probe before force-reinitializing
(#5330)" (2026-09-12). The `HOME` override and 131-byte socket path described
below were harness errors, as the text already says. Original text is kept.

## Primary failure: a supposedly observational preflight migrates the database

1. Gas City writes a `.beads/metadata.json` stub before backend initialization.
   Its `gc-beads-bd.sh` sees the stub, creates/registers the empty `hq` database,
   finds no Beads schema, and calls `bd init --force --server …`.
2. Beads maps `--force` to `--reinit-local`. Before the real init, it calls
   `runInitReinitPreflight` → `countExistingIssues` to determine whether the
   destructive-operation confirmation is needed.
3. `countExistingIssues` opens **a writable store** with
   `newDoltStoreFromConfig` under **a five-second context deadline**. Opening a
   writable server store invokes schema migration. The empty database starts
   migrating during what was meant to be a count operation.
4. The deadline interrupts that migration on this machine. Its position varies
   with timing. `runInitReinitPreflight` treats the returned error as permission
   to continue (`if err != nil || count == 0 { return nil }`), so the actual
   preflight timeout is absent from the CLI diagnostic.
5. The real initialization now opens a partially migrated database. Without
   `BD_ALLOW_REMOTE_MIGRATE`, it rejects the apparent existing shared database
   needing an upgrade. With that override, it can instead reject uncommitted
   changes left by the interrupted migration as “pre-existing dirty tables.”
   This is the origin of the changing `events`, `child_counters`, and `issues`
   errors. Adding migration consent does not cure the interrupted preflight.

The defect is the mutating count preflight, triggered by Gas City's forced-init
path for a new metadata stub. Replacing `--force` with its newer spelling alone
would take the same path. This is not a stale old-version database or evidence
that the releases cannot operate together.

Correction, 2026-09-23: step 4 ("the deadline interrupts that migration on this
machine") is the load-dependent part. The interruption requires migrations to
exceed five seconds, which this host's load caused. "The defect" should read
"a latent preflight weakness exposed by host load"; it has not been shown to
affect a normally loaded installation.

## Evidence and controls

| Probe | Observed result |
| --- | --- |
| [Direct Beads creates database](owned-001/commands.json) | Exit 0, schema v66, clean Dolt working set. |
| [SQL pre-creates database, ordinary Beads init](precreate-002/commands.json) | Exit 0, schema v66, clean working set. Database ownership alone is not the cause. |
| [Same, 15-second listener timeout](precreate-short-001/commands.json) | Exit 0, schema v66, clean working set. That timeout alone is not the cause. |
| [Forced init with metadata stub](precreate-forced-001/commands.json) | Preflight partially migrated; the real init reported 44 remaining migrations and completed when consent was supplied. |
| [Pinned environment and managed settings, repetition 1](precreate-forced-pinned-managed-001/commands.json) | 36 migrations remained after preflight; completed with consent. |
| [Same, repetition 2](precreate-forced-pinned-managed-002/commands.json) | 29 migrations remained after preflight; completed with consent. |
| [Traced forced init without consent](precreate-forced-pinned-managed-trace-noconsent-001/commands.json) | Exit 1: supposedly fresh database stopped at v16; 50 migrations remained; `config` and `schema_migrations` were dirty. |
| [Original Gas City harness, unchanged](full-original-001/run.log) | Exit 1: 43 migrations remained; rejected dirty `issues`. Reproduces the original failure class against a newly created city. |
| [Same Gas City path with fresh-init diagnostic wrapper](full-fresh-001/run.log) | Database initialized with a project UUID and city registered. Proceeded beyond the database failure to a separate HOME error. |

[The full SQL trace](preflight-sql-trace.log) shows migrations and per-step
commits on the first connection, followed by a second open inspecting the
partially advanced schema and refusing the upgrade. The dirty-table outcome is
timing-sensitive: interrupted forced-init probes sometimes converge when consent
is supplied and sometimes fail on the table interrupted. These outcomes must not
be collapsed into an assertion that all forced inits fail.

`precreate-001` was an initial diagnostic setup mistake: the SQL client prompted
for a password rather than pre-creating the database. That attempt is retained,
but is not evidence about the pre-created-database variant. Later probes use an
explicit empty password for their private local server.

## Source chain

Frozen Beads v1.3.0 source:

- [init.go:2670](https://github.com/gastownhall/beads/blob/v1.3.0/cmd/bd/init.go#L2670): `countExistingIssues`, five-second context, writable open.
- [init.go:2702](https://github.com/gastownhall/beads/blob/v1.3.0/cmd/bd/init.go#L2702): preflight ignores the open/count error and continues.
- [store_factory.go:146](https://github.com/gastownhall/beads/blob/v1.3.0/cmd/bd/store_factory.go#L146): configured server opens through `dolt.NewFromConfig`.
- [store.go:2041](https://github.com/gastownhall/beads/blob/v1.3.0/internal/storage/dolt/store.go#L2041): writable opens initialize/migrate schema.
- [store_factory.go:235](https://github.com/gastownhall/beads/blob/v1.3.0/cmd/bd/store_factory.go#L235): existing nonmutating store-opening facility.

Frozen Gas City v1.4.2 source:

- [gc-beads-bd.sh:2819](https://github.com/gastownhall/gascity/blob/v1.4.2/examples/bd/assets/scripts/gc-beads-bd.sh#L2819): metadata stub intentionally triggers forced initialization when no live schema exists.
- [gc-beads-bd.sh:2534](https://github.com/gastownhall/gascity/blob/v1.4.2/examples/bd/assets/scripts/gc-beads-bd.sh#L2534): exact forced `bd init` invocation.

The installed `gc` build metadata embeds `github.com/steveyegge/beads v1.3.0`.
The Homebrew Beads formula builds the v1.3.0 source archive. Both direct controls
used the same installed binaries as the failing workflow.

## Separate harness errors uncovered after the database succeeded

The first diagnostic wrapper deferred only its own new metadata stub and removed
`--force`, letting ordinary init proceed with the same installed binaries. It
also removed the migration-consent override. This cleared database initialization.

The next failure was my experiment harness setting `HOME` to its scratch directory.
Gas City explicitly rejects that for platform supervisor startup and instructs
callers to keep real HOME and isolate via `GC_HOME`. This was a harness error.

Keeping real HOME exposed another harness error: the nested workspace produced a
131-byte supervisor Unix socket path. The supervisor's `listen unix …: bind:
invalid argument` failure is retained in the follow-up log. A short task-owned
workspace produces a 62-byte socket path instead. These supervisor errors happen
after database initialization; they did not cause the interrupted migration.

The diagnostic wrappers apply only to verified new task-owned paths. No installed
binary, user city/database, or upstream source was patched. Separate Git and Dolt
configuration and service-manager shims retain isolation. The latest probe also
skips Claude onboarding writes because this is setup-only diagnosis.

## Correction indicated by the evidence

The Beads issue-count preflight should use a nonmutating connection and must never
perform schema initialization/migrations. Its regression test needs to cover a
fresh server database plus a metadata stub under forced initialization, including
an open whose migrations would exceed the preflight deadline. A read/count error
must not silently authorize destructive reinitialization of unknown existing data.

Gas City's new-database bootstrap should avoid conflating its metadata stub with
an already initialized store requiring destructive reinit. Any adjustment must
preserve existing-database safety checks. The diagnostic wrapper is evidence, not
a production repair or permission to delete metadata in an existing city.

Correction, 2026-09-23: Gas City `main` already addresses part of this with
8c2b970fe (#5330), which corroborates a negative schema probe before
force-reinitializing. That commit is not in v1.4.2. These recommendations remain
reasonable hardening, but they are not driven by a demonstrated production bug.

The experiment harness separately needs real HOME, short GC_HOME/socket paths,
and isolated configuration files. A complete A/B run remains unperformed; these
probes evaluate initialization only and dispatch no experimental model work.

## Final control outcome

The short-path / real-HOME control initialized **both city and rig databases to
schema v66** and started its private supervisor. The original dirty-table error
was absent. The full setup nevertheless exceeded the harness's 300-second
limit later during city startup (last observed API phase: `projecting_mcp`;
subsequent supervisor log reached controller-state opening). This is a separate
startup-performance investigation, not a successful complete-workflow test.
See [the measured state](shortpath-observation.json).

The [real-HOME long-path supervisor log](full-fresh-realhome-001/supervisor.log)
records the Unix socket path failure. Diagnostic source snapshots are retained
as text; the original runnable scripts are in this thread's
`beads-init-diagnosis/` directory. Run each variant with a new output name;
previous diagnostic directories are intentionally exclusive-created.

The final [bounded setup log](full-fresh-realhome-shortpath-001/run.log) and
[supervisor log](full-fresh-realhome-shortpath-001/supervisor.log) retain the later
timeout. Automatic shutdown exceeded its wait budget; the task-owned supervisor and Dolt
processes were still present at the first check but exited before an explicit
TERM attempt. The cleanup helper also compares paths textually, so `/tmp` versus
`/private/tmp` needs normalization before its absence claim can be trusted.
This is a harness cleanup limitation, not the migration cause.

## Fix verification

The [local read-only-preflight patch and regression evidence](fix-validation/README.md)
now pass. The real patched CLI initializes a fresh forced stub to schema 66 with
a clean working set and preserves an existing issue when noninteractive reinit
is refused. Gas City setup also completed with city and rig schemas at 66.
The 300-second control timeout was too short on this host; the successful harness
setup took 365.929 seconds including its preparation and validation.

The installed Homebrew Beads binary remains unchanged. This is a tested local
experiment runtime, not an upstream release or a completed Jev A/B evaluation.

Correction, 2026-09-23: the patch is a workaround for a heavily loaded host, not
a fix for a demonstrated production bug. Future runs will use unpatched binaries,
follow the documented operator path, and check host load before starting.
