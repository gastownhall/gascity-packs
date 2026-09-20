#!/usr/bin/env python3
"""Real BB UI -> GC -> model acceptance. State and evidence are always retained."""
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

from live_assertions import AcceptanceFailure, LiveAssertions, decode_identity, verify_resume_identity

HERE = Path(__file__).resolve().parent


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pack_hash(path):
    root = Path(path).resolve()
    digest = hashlib.sha256()
    for entry in sorted(root.rglob("*")):
        if any(part in {"node_modules", ".git", "dist"} for part in entry.relative_to(root).parts):
            continue
        if entry.is_file():
            digest.update(str(entry.relative_to(root)).encode() + b"\0")
            digest.update(entry.read_bytes())
    return digest.hexdigest()


def read_json(url, timeout=20):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


def validate_environment(manifest):
    root = Path(manifest["root"]).resolve(strict=True)
    marker = root / ".bb-full-e2e-owned.json"
    if (not root.name.startswith("bb-live-") or root.parent not in {Path("/tmp").resolve(), Path("/var/tmp").resolve()}
            or not marker.is_file() or json.loads(marker.read_text()).get("root") != str(root)):
        raise AcceptanceFailure("Full E2E requires a marked task-owned temporary installation")
    env = json.loads(Path(manifest["envFile"]).read_text())
    for key in ("GC_HOME", "BB_DATA_DIR", "GC_BB_CONFIG", "XDG_STATE_HOME"):
        if not Path(env[key]).resolve().is_relative_to(root):
            raise AcceptanceFailure(f"{key} escapes the isolated installation")
    for key in ("gcUrl", "bbUrl"):
        from urllib.parse import urlsplit
        address = urlsplit(manifest[key])
        if address.scheme != "http" or address.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise AcceptanceFailure("E2E services must use explicit loopback endpoints")
    return root, env


class Runner:
    def __init__(self, manifest, report_dir, timeout=240, channel=None):
        self.manifest = manifest
        self.root, self.env = validate_environment(manifest)
        self.reports = Path(report_dir).resolve()
        if self.reports.exists(): raise FileExistsError(self.reports)
        self.private = self.reports / "private"
        self.timeout, self.channel = timeout, channel
        self.counter = 0
        self.results, self.conversations = {}, {}
        self.runtime = manifest["runtime"]
        self.artifacts = self.verify_artifacts()

    def progress(self, text):
        print(f"[full E2E {self.runtime}] {text}", flush=True)

    def verify_artifacts(self):
        health = read_json(self.manifest["gcUrl"] + "/health")
        if not health.get("startup", {}).get("ready"):
            raise AcceptanceFailure("GC is not ready")
        actual_hash = file_hash(self.manifest["commands"]["gc"])
        if actual_hash != self.manifest["gcBinarySha256"]:
            raise AcceptanceFailure("GC binary differs from the prepared artifact")
        if health.get("version") != self.manifest["versions"]["gc"]:
            raise AcceptanceFailure("Running GC version differs from the prepared binary")
        commit = self.manifest.get("gcCommit")
        if not commit or not commit.startswith(health.get("build_id") or "MISSING"):
            raise AcceptanceFailure("Running GC build does not identify the expected exact commit")
        bb = read_json(self.manifest["bbUrl"] + "/api/v1/system/version")
        if bb.get("currentVersion") != self.manifest["versions"]["bb"]:
            raise AcceptanceFailure("Running BB differs from the prepared release")
        source = HERE.parent / "assets/plugin"
        installed = (Path(self.env["GC_BB_INSTALL_DIR"]) / "current").resolve(strict=True)
        if not installed.is_relative_to(self.root.resolve(strict=True)):
            raise AcceptanceFailure("Installed provider escapes the isolated installation")
        # Use the same public registration contract as the installer. A correct
        # current symlink alone does not prove BB actually loaded that source.
        try:
            registration = subprocess.run([self.manifest["commands"]["bb"], "plugin", "list", "--json"],
                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=20, check=True)
            rows = json.loads(registration.stdout)["plugins"]
            if not isinstance(rows, list): raise ValueError("Invalid plugin list")
            matches = [row for row in rows if row.get("id") == "gas-city"]
            if (len(matches) != 1 or matches[0].get("status") != "running"
                    or matches[0].get("enabled") is not True
                    or Path(matches[0]["rootDir"]).resolve(strict=True) != installed):
                raise ValueError("Registration differs from the prepared installation")
        except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
            raise AcceptanceFailure("BB has no unique running registration for the installed provider") from error

        def source_files(root, *, installation=False):
            files = {}
            for directory, children, names in os.walk(root):
                # Do not traverse generated dependency/build trees. This is a
                # complete source identity, not a hash of generated bundles.
                children[:] = [name for name in children if name not in {"node_modules", "dist", ".git"}]
                for name in children:
                    if (Path(directory) / name).is_symlink():
                        raise AcceptanceFailure("Provider source directories cannot be symlinks")
                for name in names:
                    entry = Path(directory) / name
                    relative = entry.relative_to(root)
                    if installation and relative.as_posix() == ".gc-bb-install.json": continue
                    if entry.is_symlink() or not entry.is_file():
                        raise AcceptanceFailure("Provider source must contain regular files")
                    files[relative.as_posix()] = entry.read_bytes()
            return files

        expected = source_files(source)
        if not {"package.json", "package-lock.json"} <= expected.keys():
            raise AcceptanceFailure("Provider source lacks its dependency manifests")
        if expected != source_files(installed, installation=True):
            raise AcceptanceFailure("Installed provider source or dependency manifests differ from the source under test")
        digest = hashlib.sha256()
        for name, content in sorted(expected.items()):
            digest.update(name.encode() + b"\0")
            digest.update(content)
        result = {"gc_commit": commit, "gc_binary_sha256": actual_hash, "gc_version": health["version"],
                  "pack_sha256": digest.hexdigest(), "bb_version": bb["currentVersion"],
                  "runtime": self.runtime, "runtime_version": re.search(r"\d+\.\d+\.\d+", self.manifest["versions"][self.runtime])[0],
                  "verification_mode": self.manifest["verificationMode"]}
        # A declared route label distinguishes models using the same CLI. It
        # does not prove the native request actually selected that model.
        if "modelRoute" in self.manifest:
            result["model_route"] = self.manifest["modelRoute"]
        return result

    def command(self, *args, timeout=60):
        cwd = self.root
        if args and Path(str(args[0])).resolve() == Path(self.manifest["commands"]["gc"]).resolve():
            # Pack subcommands are discovered from the selected city's config,
            # not from the surrounding scratch root or an ambient user city.
            cwd = Path(self.manifest["city"]).resolve(strict=True)
            root = self.root.resolve(strict=True)
            if cwd == root or not cwd.is_relative_to(root):
                raise AcceptanceFailure("GC command city escapes the isolated installation")
        self.counter += 1
        path = self.private / f"command-{self.counter:04d}.log"
        errors = path.with_suffix(".stderr.log")
        started = time.monotonic()
        with path.open("x") as output, errors.open("x") as stderr:
            process = subprocess.Popen([str(x) for x in args], cwd=cwd, env=self.env,
                                       text=True, stdout=output, stderr=stderr)
            while process.poll() is None:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    process.terminate()
                    raise AcceptanceFailure(f"Command exceeded {timeout}s; private evidence {path.name}")
                try: process.wait(timeout=min(15, remaining))
                except subprocess.TimeoutExpired:
                    if time.monotonic() - started >= 30:
                        self.progress(f"command {self.counter}: running for {int(time.monotonic() - started)}s; logs retained")
        if process.returncode:
            raise AcceptanceFailure(f"Command failed; private evidence {path.name}")
        return path.read_text()

    def bb(self, *args):
        value = self.command(self.manifest["commands"]["bb"], *args)
        return json.loads(value) if value.strip().startswith(("[", "{")) else value

    def agent(self, scope):
        choices = [a for a in self.manifest["agents"] if bool(a.get("rig")) == (scope == "rig")]
        if len(choices) != 1:
            raise AcceptanceFailure(f"Manifest must select one exact {scope} agent")
        row = choices[0]
        if "id" not in row:
            encoded = json.dumps({key: row[key] for key in ("v", "connection", "city", "agent")}, separators=(",", ":"))
            row = {**row, "id": "gc1_" + base64.urlsafe_b64encode(encoded.encode()).decode().rstrip("=")}
        return row

    def browser(self, label, agent, project, workspace, prompt=None, *, thread=None,
                expected=None, reasoning="medium", route="native", action="send", until="completed", after=None,
                expected_error=None, switch_from_provider=None):
        path = self.private / label
        argv = ["node", str(HERE / "browser_driver.mjs"), "--url", self.manifest["bbUrl"],
                "--host", self.manifest["hostId"], "--project", project, "--model", agent["id"],
                "--workspace", str(workspace), "--reasoning", reasoning, "--route", route,
                "--action", action, "--until", until, "--timeout-ms", str(self.timeout * 1000), "--artifacts", str(path)]
        if prompt is not None: argv += ["--prompt", prompt]
        if thread: argv += ["--existing-thread-id", thread]
        if expected: argv += ["--expected-response", expected]
        if expected_error: argv += ["--expected-error", expected_error]
        if switch_from_provider: argv += ["--switch-from-provider", switch_from_provider]
        if after is not None: argv += ["--after-seq", str(after)]
        if self.channel: argv += ["--channel", self.channel]
        self.command(*argv, timeout=self.timeout + 100)
        result = json.loads((path / "result.json").read_text())
        if result["status"] != ("passed" if until == "completed" else until):
            raise AcceptanceFailure(f"Browser did not satisfy {until}; inspect {label}")
        return result

    def new_harness(self, label, agent, project, workspace, thread):
        harness = LiveAssertions(bb_bin=self.manifest["commands"]["bb"], host=self.manifest["hostId"],
            project=project, model=agent["id"], workspace=workspace, artifacts=self.private / (label + "-proof"),
            env=self.env, timeout=self.timeout, existing_thread_id=thread)
        harness.verify_destination()
        return harness

    def verify_turn(self, harness, result, prompt, expected, *, provider=None, tool=False, no_tools=False,
                    reviewed_creation=None):
        after, identity = harness.await_turn(after=result["afterSeq"], expected=expected,
            previous_provider_id=provider, require_tool=tool, forbid_tools=no_tools)
        if reviewed_creation is None:
            harness.verify_gc_prompt(prompt, identity)
        else:
            harness.verify_gc_prompt(prompt, identity, reviewed_creation=reviewed_creation)
        receipt = json.loads((Path(self.env["XDG_STATE_HOME"]) / "gascity/bb/sessions" /
            (hashlib.sha256(harness.thread_id.encode()).hexdigest() + ".json")).read_text())
        selected = result["selection"]["reasoning"]
        if receipt.get("reasoningLevel", "none") != selected:
            raise AcceptanceFailure("GC receipt did not preserve the UI reasoning selection")
        target = receipt["target"]
        session = read_json(self.manifest["gcUrl"] + f"/v0/city/{target['city']}/session/{receipt['sessionId']}")
        if selected != "none" and (session.get("options") or {}).get("effort") != selected:
            raise AcceptanceFailure("GC did not apply the selected reasoning effort")
        if selected == "none":
            overrides = (session.get("metadata") or {}).get("template_overrides", "{}")
            if "effort" in (json.loads(overrides) if isinstance(overrides, str) else overrides):
                raise AcceptanceFailure("Agent default unexpectedly created an effort override")
        (harness.private.parent / "report.json").write_text(json.dumps(harness.report, indent=2) + "\n")
        return after, identity

    def conversation(self, label, scope, *, project, route="native", reasoning="medium"):
        agent, workspace = self.agent(scope), self.manifest["workspaces"][scope]
        nonce, memory = secrets.token_hex(6), secrets.token_hex(10)
        first_marker = f"BEGIN_{nonce}_END_{nonce}"
        first = (f"Remember the private test word {memory} for our next turn.\n"
                 + "\n".join(f"Line {i}: Preserve this complete multiline BB request." for i in range(28))
                 + f"\nDo not use tools. End your final response with exactly this standalone line: {first_marker}")
        result = self.browser(label + "-first", agent, project, workspace, first,
                              expected=first_marker, reasoning=reasoning, route=route)
        harness = self.new_harness(label, agent, project, workspace, result["threadId"])
        _, identity = self.verify_turn(harness, result, first, first_marker, no_tools=True)
        proof = Path(workspace) / f"bb-e2e-{nonce}.txt"
        if proof.exists(): raise AcceptanceFailure("Proof path already exists")
        marker = f"TOOLS_OK_{nonce}"
        second = (f"Use your shell tool to create {proof.name} in your execution workspace. "
                  "Write the private word remembered from my previous message followed by one newline. "
                  "Do not overwrite an existing file. Read it back using a tool. "
                  f"End your final reply with the standalone line {marker}.")
        result = self.browser(label + "-tools", agent, project, workspace, second,
            thread=harness.thread_id, expected=marker, reasoning=reasoning)
        self.verify_turn(harness, result, second, marker, provider=identity, tool=True)
        if proof.read_bytes() != (memory + "\n").encode():
            raise AcceptanceFailure("Tool artifact in GC's workspace does not contain retained memory")
        self.conversations[label] = {"agent": agent, "project": project, "workspace": workspace,
            "reasoning": reasoning, "harness": harness, "identity": identity, "memory": memory,
            "frame": harness.last_gc_frame}
        return {"thread_id": harness.thread_id, "artifact_sha256": file_hash(proof), "turns": 2}

    def recall(self, label, conversation):
        c = conversation; marker = "MEMORY_" + secrets.token_hex(6)
        expected = marker + " " + c["memory"]
        prompt = f"Without tools, end your final response with {marker}, one space, then the private word from our first turn. Recall it from this conversation."
        result = self.browser(label, c["agent"], c["project"], c["workspace"], prompt,
            thread=c["harness"].thread_id, expected=expected, reasoning=c["reasoning"])
        self.verify_turn(c["harness"], result, prompt, expected, provider=c["identity"], no_tools=True)
        verify_resume_identity(c["frame"], c["harness"].last_gc_frame)
        return {"thread_id": c["harness"].thread_id, "identity_preserved": True}

    def release_resume(self):
        c = self.conversations["native.personal"]
        self.bb("thread", "stop", c["harness"].thread_id)
        return self.recall("lifecycle.release_resume", c)

    def agent_resume(self, conversation=None, label="lifecycle.agent_resume"):
        c = conversation or self.conversations["native.personal"]; harness = c["harness"]
        frame = harness.gc_fetch("/transcript?format=structured", "before-native-resume")
        if frame.get("history", {}).get("tail_state", {}).get("activity") != "idle":
            raise AcceptanceFailure("Agent is not reliably idle before suspension")
        harness.gc_fetch("/suspend", "native-suspend", "POST")
        deadline, poll = time.monotonic() + 45, 0
        while time.monotonic() < deadline:
            # Suspend reports suspended immediately; the controller may later
            # project asleep or wake a manual session. Record actual stopped
            # runtime evidence instead of requiring that transient projection.
            state = harness.gc_fetch("", f"native-suspend-state-{poll}")
            if state.get("state") in {"suspended", "asleep"} and state.get("running") is False: break
            time.sleep(1)
            poll += 1
        else: raise AcceptanceFailure("GC never settled the suspended agent")
        return self.recall(label, c)

    def reasoning_case(self, level):
        label = "reasoning." + level
        result = self.conversation(label, "global", project="proj_personal", reasoning=level)
        self.agent_resume(self.conversations[label], label + "-resumed")
        return {**result, "reasoning": level, "resumed_with_same_reasoning": True}

    def run(self, selected=None):
        from e2e_report import E2ELedger
        from full_e2e_browser_cases import case_functions as browser_cases
        from full_e2e_fault_cases import case_functions as fault_cases
        from full_e2e_lifecycle_cases import case_functions as lifecycle_cases, CASE_DEPENDENCIES
        from full_e2e_install_cases import case_functions as install_cases
        from full_e2e_interaction_cases import case_functions as interaction_cases
        from full_e2e_desktop_cases import case_functions as desktop_cases
        from full_e2e_error_cases import case_functions as error_cases
        from full_e2e_fresh_install import case_functions as fresh_install_cases
        from e2e_matrix import required_cases
        cases = {
            "native.personal": lambda: self.conversation("native.personal", "global", project="proj_personal"),
            "native.project_global": lambda: self.conversation("native.project_global", "global", project=self.manifest["nativeProjects"]["global"]),
            "native.project_rig": lambda: self.conversation("native.project_rig", "rig", project=self.manifest["nativeProjects"]["rig"]),
            "launcher.global": lambda: self.conversation("launcher.global", "global", project=self.manifest["projectId"], route="launcher"),
            "launcher.rig": lambda: self.conversation("launcher.rig", "rig", project=self.manifest["projectId"], route="launcher"),
            "lifecycle.release_resume": self.release_resume,
            "lifecycle.agent_resume": self.agent_resume,
        }
        for level in self.agent("global")["reasoningLevels"]:
            cases["reasoning." + level] = lambda level=level: self.reasoning_case(level)
        cases.update(browser_cases(self))
        cases.update(fault_cases(self))
        cases.update(lifecycle_cases(self))
        cases.update(install_cases(self))
        cases.update(fresh_install_cases(self))
        cases.update(interaction_cases(self))
        cases.update(error_cases(self))
        if sys.platform == "darwin": cases.update(desktop_cases(self))
        required = required_cases(self.agent("global")["reasoningLevels"], desktop=sys.platform == "darwin")
        if set(cases) - set(required):
            raise AcceptanceFailure("Implemented E2E case is absent from the required behavior matrix")
        if selected and selected - set(required):
            raise AcceptanceFailure("Diagnostic subset contains an unknown E2E case")
        ledger = E2ELedger(self.reports, required_cases=required, artifacts=self.artifacts)
        dependencies = {**CASE_DEPENDENCIES, **{name: ("native.personal",) for name in (
            "lifecycle.release_resume", "lifecycle.agent_resume", "reasoning.immutable", "installation.upgrade_rollback")}}
        (self.private / "artifact-identities.json").write_text(json.dumps(self.artifacts, indent=2) + "\n")
        from full_e2e_fixture_catalog import prepare_fixtures
        try:
            prepare_fixtures(self, selected if selected is not None else set(required))
        except Exception as error:
            (self.private / "fixture-preparation-failure.txt").write_text(str(error) + "\n")
            ledger.finish()
            raise
        for index, (case, execute) in enumerate(cases.items(), 1):
            if selected and case not in selected: continue
            self.progress(f"[{index}/{len(cases)}] {case}")
            if any(self.results.get(dependency) != "passed" for dependency in dependencies.get(case, ())):
                ledger.record(case, "blocked", reason_code="dependency_failed")
                self.results[case] = "blocked"
                continue
            try:
                evidence = execute()
                proof = self.private / (case + "-result.json")
                proof.write_text(json.dumps(evidence, indent=2) + "\n")
                files = [proof, *self.private.glob(case + "*/result.json"), *self.private.glob(case + "*-proof/report.json")]
                ledger.record(case, "passed", assertions=["case-contract-verified"], evidence_files=files)
                self.results[case] = "passed"
            except Exception as error:
                (self.private / (case + "-failure.txt")).write_text(str(error) + "\n")
                ledger.record_error(case, error, reason_code="assertion_failed")
                self.results[case] = "failed"
                self.progress(f"FAILED {case}: {type(error).__name__}; retained private evidence")
        result = ledger.finish()
        self.progress(f"{result['status']}: {self.reports / 'summary.json'}")
        return 0 if result["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-manifest", type=Path)
    parser.add_argument("--runtime", choices=["claude", "codex"])
    for name in ("gc-bin", "bb-bin", "bb-app-bin", "gc-development-base", "gc-commit", "channel",
                 "claude-native-config", "runtime-raw-bin", "model-route"):
        parser.add_argument("--" + name)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--cases", help="Diagnostic subset; omitted required cases keep the overall result incomplete")
    args = parser.parse_args()
    if args.environment_manifest:
        manifest = json.loads(args.environment_manifest.read_text())
    else:
        for key in ("runtime", "gc_bin", "bb_bin", "bb_app_bin", "gc_commit"):
            if not getattr(args, key): parser.error("Missing --" + key.replace("_", "-"))
        prepare = args.report_dir.with_name(args.report_dir.name + "-prepare")
        command = [sys.executable, str(HERE / "live_acceptance.py"), "--runtime", args.runtime,
            "--gc-bin", args.gc_bin, "--bb-bin", args.bb_bin, "--bb-app-bin", args.bb_app_bin,
            "--gc-commit", args.gc_commit, "--timeout", str(args.timeout),
            "--report-dir", str(prepare), "--prepare-only"]
        for name in ("gc-development-base", "claude-native-config", "runtime-raw-bin", "model-route"):
            value = getattr(args, name.replace("-", "_"))
            if value is not None: command += ["--" + name, value]
        subprocess.run(command, check=True)
        manifest = json.loads((prepare / "environment.json").read_text())
    runner = Runner(manifest, args.report_dir, args.timeout, args.channel)
    return runner.run(set(args.cases.split(",")) if args.cases else None)


if __name__ == "__main__":
    sys.exit(main())
