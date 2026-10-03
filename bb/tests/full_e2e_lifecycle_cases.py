"""Executable lifecycle cases restricted to one retained test installation.

Recorded PIDs are candidates, never authority by themselves. Immediately before
a signal, verify process birth, UID, command, parent and the exact isolated
state environment. Linux uses a pidfd when available. No name/port-wide kill,
process-group signal, normal service command or state reset is used.
"""

import errno
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import urllib.error
import urllib.parse

from full_e2e_fault_cases import FaultCases, require_owned_config, write_new
from live_assertions import AcceptanceFailure, verify_prompt_frame, verify_resume_identity
from live_lifecycle import LifecycleFailure


def inspect_process(pid, required_env, *, command_contains=None, parent=None):
    if type(pid) is not int or pid <= 1 or pid == os.getpid() or not required_env:
        raise LifecycleFailure("A lifecycle target needs a specific non-self PID and isolated environment")
    result = subprocess.run(["ps", "-ww", "-p", str(pid), "-o", "pid=", "-o", "ppid=", "-o", "uid=",
                             "-o", "lstart=", "-o", "command="], capture_output=True, text=True, timeout=10)
    fields = result.stdout.strip().split(None, 8)
    if result.returncode or len(fields) != 9:
        raise ProcessLookupError(pid)
    found_pid, ppid, uid = map(int, fields[:3])
    command = fields[8]
    if found_pid != pid or uid != os.getuid() or (parent is not None and ppid != parent):
        raise LifecycleFailure("Process owner or parent differs from the selected test component")
    birth = " ".join(fields[3:8])
    proc = Path("/proc") / str(pid)
    if sys.platform.startswith("linux"):
        try:
            stat = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if stat[0] == "Z":
                # Zombies may have a defunct command and an empty or unreadable
                # environment. Kernel state establishes exit before those checks.
                raise ProcessLookupError(pid)
            birth = stat[19]
            environment_error = None
            try:
                environ = (proc / "environ").read_bytes()
            except PermissionError as error:
                environment_error = error
            observed = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if observed[19] != birth:
                raise LifecycleFailure("Process identity changed during inspection")
            if observed[0] == "Z":
                raise ProcessLookupError(pid)
            if environment_error is not None:
                raise environment_error
        except FileNotFoundError as error:
            # An exiting process can disappear after ps succeeds. Normalize
            # only ENOENT; live access/I/O failures never authorize a signal.
            if error.errno != errno.ENOENT:
                raise
            raise ProcessLookupError(pid) from error
        env = dict(part.split(b"=", 1) for part in environ.split(b"\0") if b"=" in part)
        if any(env.get(key.encode()) != value.encode() for key, value in required_env.items()):
            raise LifecycleFailure("Process environment does not identify this isolated installation")
    elif sys.platform == "darwin":
        result = subprocess.run(["ps", "eww", "-p", str(pid), "-o", "command="], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise ProcessLookupError(pid)
        for key, value in required_env.items():
            if any(char.isspace() for char in value) or not re.search(r"(?:^|\s)" + re.escape(key + "=" + value) + r"(?=\s|$)", result.stdout):
                raise LifecycleFailure("Cannot prove the macOS process's exact isolated environment")
    else:
        raise LifecycleFailure("Retained process inspection supports Linux and macOS only")
    if command_contains is not None and command_contains not in command:
        raise LifecycleFailure("Process command differs from the selected test component")
    return {"pid": pid, "parent_pid": ppid, "uid": uid, "birth": birth,
            "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
            "environment_sha256": hashlib.sha256(json.dumps(required_env, sort_keys=True).encode()).hexdigest()}


def signal_verified(identity, required_env, *, command_contains=None, parent=None, graceful=False):
    """Signal one revalidated process; a changed or exited PID is never reused."""
    pidfd = None
    try:
        if sys.platform.startswith("linux") and hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
            pidfd = os.pidfd_open(identity["pid"])
        current = inspect_process(identity["pid"], required_env, command_contains=command_contains, parent=parent)
        if current != identity:
            raise LifecycleFailure("Refusing to signal a changed or stale process identity")
        signum = signal.SIGTERM if graceful else signal.SIGKILL
        if pidfd is not None:
            signal.pidfd_send_signal(pidfd, signum)
        else:
            os.kill(identity["pid"], signum)
    finally:
        if pidfd is not None:
            os.close(pidfd)


def children(parent_pid):
    result = subprocess.run(["ps", "-axo", "pid=,ppid="], capture_output=True, text=True, timeout=10, check=True)
    return [int(fields[0]) for line in result.stdout.splitlines()
            if len(fields := line.split()) == 2 and fields[1] == str(parent_pid)]


def canonical_executable_prefix(command, binary, *arguments):
    """Compare canonical files while retaining ps's actual command spelling."""
    parts = shlex.split(command)
    if (len(parts) < len(arguments) + 1 or parts[1:1 + len(arguments)] != list(arguments)
            or not Path(parts[0]).is_absolute()
            or Path(parts[0]).resolve(strict=True) != Path(binary).resolve(strict=True)):
        raise LifecycleFailure("Process does not execute the exact selected GC binary and command")
    prefix = " ".join(parts[:len(arguments) + 1])
    if not (command == prefix or command.startswith(prefix + " ")):
        raise LifecycleFailure("Cannot verify the exact process command prefix")
    return prefix


def canonical_entry_token(command, entry):
    """Node preserves the script's original /var/tmp spelling in its argv."""
    expected = Path(entry).resolve(strict=True)
    for token in shlex.split(command)[:2]:
        if Path(token).is_absolute() and Path(token).resolve(strict=True) == expected:
            return token
    raise LifecycleFailure("BB process does not execute the selected app entry")


def verify_systemd_manager(properties, *, unit, pid, gc_home, binary, fragment, uid, cgroup):
    """Bind an exact user unit to the fixture process and its preserving config."""
    expected_group = f"/user.slice/user-{uid}.slice/user@{uid}.service/app.slice/{unit}"
    if (not re.fullmatch(r"gascity-supervisor-[A-Za-z0-9_.-]+\.service", unit)
            or properties.get("Id") != unit or properties.get("MainPID") != str(pid)
            or properties.get("ActiveState") != "active" or properties.get("ControlGroup") != expected_group
            or cgroup != expected_group or properties.get("KillMode") != "process"
            or properties.get("Restart") != "always" or properties.get("DropInPaths")):
        raise LifecycleFailure("Systemd unit does not exclusively identify the owned preserving GC supervisor")
    effective = re.match(r"^\{ path=(.*?) ; argv\[\]=(.*?) ;", properties.get("ExecStart", ""))
    command = str(Path(binary).resolve(strict=True))
    expected_argv = [command, "supervisor", "run"]
    if (not effective or effective[1] != command or shlex.split(effective[2]) != expected_argv):
        raise LifecycleFailure("Owned systemd unit executes a different binary or command")
    section, environment, fragment_commands = "", {}, []
    for raw in fragment.splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            section = line
            continue
        if section != "[Service]":
            continue
        if line.endswith("\\") or line.startswith("EnvironmentFile="):
            raise LifecycleFailure("Cannot prove an indirect or continued systemd fixture environment")
        if line.startswith("Environment="):
            for value in shlex.split(line.split("=", 1)[1]):
                key, separator, content = value.partition("=")
                if not separator:
                    raise LifecycleFailure("Malformed environment in the owned unit")
                environment[key] = content
        if line.startswith("ExecStart="):
            fragment_commands.append(shlex.split(line.split("=", 1)[1]))
    if (fragment_commands != [expected_argv] or environment.get("GC_HOME") != str(gc_home)
            or environment.get("GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL") != "1"):
        raise LifecycleFailure("Systemd fragment does not preserve the exact isolated GC home and sessions")
    return {"unit": unit, "main_pid": pid, "control_group": expected_group,
            "fragment_path": properties.get("FragmentPath"),
            "fragment_sha256": hashlib.sha256(fragment.encode()).hexdigest(), "executable": command}


def verify_one_prompt(frame, receipt, prompt):
    evidence = verify_prompt_frame(frame, receipt["turn"], prompt)
    matching = []
    for message in frame["structured_messages"]:
        if message.get("role") != "user" or message.get("status") == "superseded":
            continue
        text = (message.get("user_prompt") or {}).get("text")
        if text is None:
            text = "\n".join(block.get("text", "") for block in message.get("blocks", []) if block.get("type") == "text")
        if prompt in text:
            matching.append(text)
    if len(matching) != 1 or matching[0].count(prompt) != 1:
        raise LifecycleFailure("Lifecycle recovery duplicated or truncated the faulted user prompt")
    return evidence


def visible_failure_fragment(events):
    if any(event.get("type") == "turn/completed" and (event.get("data") or {}).get("status") == "completed" for event in events):
        raise LifecycleFailure("The crashed busy bridge unexpectedly published success before explicit recovery")
    for event in events:
        if event.get("type") not in {"system/error", "client/turn/rejected", "turn/completed"}:
            continue
        data = event.get("data") or {}
        error = data.get("error")
        message = data.get("message") or (error.get("message") if isinstance(error, dict) else error)
        if isinstance(message, str) and message.strip():
            return message.strip().splitlines()[0][:100]
    return None


class LifecycleCases:
    def __init__(self, runner):
        self.runner = runner
        self.fault = FaultCases(runner)

    def guard(self):
        require_owned_config(self.runner)
        for key in ("bbUrl", "gcUrl"):
            address = urllib.parse.urlsplit(self.runner.manifest[key])
            if address.hostname not in {"127.0.0.1", "localhost", "::1"} or address.port in {38886, 8372}:
                raise LifecycleFailure("Lifecycle cases cannot target normal BB or GC endpoints")

    def conversation(self):
        try:
            conversation = self.runner.conversations["native.personal"]
        except KeyError as error:
            raise LifecycleFailure("Lifecycle tests require the verified native personal conversation first") from error
        frame = conversation["harness"].gc_fetch("/transcript?format=structured", "lifecycle-ready-" + secrets.token_hex(4))
        tail = frame.get("history", {}).get("tail_state", {})
        if (tail.get("activity") != "idle" or tail.get("degraded")
                or tail.get("open_tool_call_ids") or tail.get("pending_interaction_ids")):
            raise LifecycleFailure("Lifecycle action requires the owned conversation to be reliably idle")
        verify_resume_identity(conversation["frame"], frame)
        return conversation

    def evidence_dir(self, label):
        self.guard()
        path = self.runner.private / label
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
        return path

    def app_identity(self):
        env = {"BB_DATA_DIR": self.runner.env["BB_DATA_DIR"]}
        entry = str(Path(self.runner.manifest["commands"]["app"]).resolve())
        observed = subprocess.run(["ps", "-ww", "-p", str(self.runner.manifest["appPid"]), "-o", "command="],
                                  capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        actual_entry = canonical_entry_token(observed, entry)
        try:
            record = json.loads((Path(self.runner.env["BB_DATA_DIR"]) / "bb-app-runtime.json").read_text())
        except FileNotFoundError:
            # An older retained launcher can lack its advisory runtime file.
            # The actual PID, birth, UID, exact entry and isolated process env
            # still establish ownership. Never recreate or overwrite metadata.
            return inspect_process(self.runner.manifest["appPid"], env, command_contains=actual_entry), env
        if (record.get("pid") != self.runner.manifest["appPid"]
                or record.get("serverUrl") != self.runner.manifest["bbUrl"]
                or record.get("version") != self.runner.manifest["versions"]["bb"]
                or Path(record.get("entryPath") or "/").resolve() != Path(self.runner.manifest["commands"]["app"]).resolve()):
            raise LifecycleFailure("BB runtime record does not identify the prepared test launcher")
        identity = inspect_process(record["pid"], env, command_contains=actual_entry)
        return identity, env

    def bb_child(self, kind):
        app, _ = self.app_identity()
        suffix = "/server/dist/index.js" if kind == "server" else "/host-daemon/dist/daemon-bundle.mjs"
        env = {"BB_DATA_DIR": self.runner.env["BB_DATA_DIR"]}
        matches = []
        for pid in children(app["pid"]):
            try:
                matches.append(inspect_process(pid, env, command_contains=suffix, parent=app["pid"]))
            except (LifecycleFailure, ProcessLookupError):
                continue
        if len(matches) != 1:
            raise LifecycleFailure("Expected exactly one verified BB child of the prepared launcher")
        return matches[0], env, suffix, app

    def bridge_identity(self, conversation):
        thread = conversation["harness"].thread_id
        owner_path = Path(self.runner.env["XDG_STATE_HOME"]) / "gascity/bb/sessions" / (hashlib.sha256(thread.encode()).hexdigest() + ".json.lock/owner.json")
        owner = json.loads(owner_path.read_text())
        if owner.get("hostname") != socket.gethostname() or not re.fullmatch(r"[a-zA-Z0-9-]+", owner.get("token", "")):
            raise LifecycleFailure("The selected thread's bridge lease has unverifiable ownership")
        # BB 0.43.3 scrubs BB_DATA_DIR from bridge workers. The exact GC config
        # and journal roots identify the child; bb_child independently proves
        # BB_DATA_DIR on its host before the ancestry check below.
        env = {key: self.runner.env[key] for key in ("GC_BB_CONFIG", "XDG_STATE_HOME")}
        identity = inspect_process(owner["pid"], env, command_contains="bb-provider-bridge-worker.mjs")
        host, _, _, _ = self.bb_child("host")
        ancestor = identity["parent_pid"]
        for _ in range(8):
            if ancestor == host["pid"]:
                break
            ancestor = inspect_process(ancestor, {"BB_DATA_DIR": self.runner.env["BB_DATA_DIR"]})["parent_pid"]
        else:
            raise LifecycleFailure("Bridge lease PID is not descended from the verified isolated BB host")
        return identity, env

    def native_pane(self, conversation):
        state = conversation["harness"].gc_fetch("", "native-pane-" + secrets.token_hex(4))
        name = state.get("session_name")
        if not name or state.get("running") is not True:
            raise LifecycleFailure("The retained native GC session is not running")
        text = self.runner.command("tmux", "-L", self.runner.manifest["cityName"], "list-panes", "-a",
                                   "-F", "#{session_name}\t#{pane_id}\t#{pane_pid}")
        matches = [fields for line in text.splitlines() if len(fields := line.split("\t")) == 3 and fields[0] == name]
        if len(matches) != 1 or not matches[0][2].isdigit():
            raise LifecycleFailure("The native GC session does not identify exactly one retained tmux pane")
        return {"session_name": name, "pane_id": matches[0][1], "pane_pid": int(matches[0][2])}

    def await_exit(self, identity, env):
        def exited():
            try:
                current = inspect_process(identity["pid"], env)
                return current["birth"] != identity["birth"]
            except ProcessLookupError:
                return True
        self.fault.poll("selected process exit", exited)

    def bridge_idle(self):
        label = "lifecycle.bridge_idle_crash"
        artifacts, c = self.evidence_dir(label), self.conversation()
        identity, env = self.bridge_identity(c)
        write_new(artifacts / "before.json", identity)
        signal_verified(identity, env, command_contains="bb-provider-bridge-worker.mjs", parent=identity["parent_pid"])
        self.await_exit(identity, env)
        result = self.runner.recall(label + "-recall", c)
        after, _ = self.bridge_identity(c)
        if after == identity:
            raise LifecycleFailure("BB did not replace the crashed provider bridge")
        write_new(artifacts / "after.json", after)
        return {**result, "bridge_replaced": True, "native_conversation_preserved": True}

    def bridge_busy(self):
        label = "lifecycle.bridge_busy_crash"
        artifacts, c = self.evidence_dir(label), self.conversation()
        self.fault.agent, self.fault.reasoning = c["agent"], c["reasoning"]
        nonce, memory = secrets.token_hex(6), secrets.token_hex(12)
        marker = "BUSY_FINISHED_" + nonce
        prompt = (f"Remember the private word {memory}. Use your shell tool to run sleep 20, waiting for it to finish. "
                  f"Then reply with exactly {marker}. Do not change any files.")
        submitted = self.runner.browser(label + "-submit", c["agent"], c["project"], c["workspace"], prompt,
                                        thread=c["harness"].thread_id, reasoning=c["reasoning"], until="submitted")
        thread = submitted["threadId"]
        def active():
            receipt = self.fault.receipt(thread)
            if not receipt or (receipt.get("turn") or {}).get("state") != "accepted":
                return None
            frame = self.fault.read_gc(self.fault.city_path + "/session/" + receipt["sessionId"] + "/transcript?format=structured")
            if frame.get("history", {}).get("tail_state", {}).get("activity") != "in_turn":
                return None
            baseline = receipt["turn"].get("baselineMessageIds", [])
            delivered = [message for message in frame.get("structured_messages", []) if message.get("role") == "user"
                         and message.get("id") not in baseline and hashlib.sha256(((message.get("user_prompt") or {}).get("text")
                         or "\n".join(block.get("text", "") for block in message.get("blocks", []) if block.get("type") == "text")).encode()).hexdigest()
                         == receipt["turn"].get("messageDigest")]
            if len(delivered) != 1:
                return None
            return receipt
        before = self.fault.poll("accepted busy GC turn", active)
        write_new(artifacts / "receipt-before.json", before)
        identity, env = self.bridge_identity(c)
        write_new(artifacts / "bridge-before.json", identity)
        signal_verified(identity, env, command_contains="bb-provider-bridge-worker.mjs", parent=identity["parent_pid"])
        self.await_exit(identity, env)
        fragment = self.fault.poll("visible busy bridge failure", lambda: visible_failure_fragment(c["harness"].events(submitted["afterSeq"])))
        self.fault.browser_failure(label + "-visible-error", submitted, fragment)
        frame = self.fault.native_answer(before, prompt, marker, artifacts)
        proof = verify_one_prompt(frame, before, prompt)
        self.fault.cli_command("recover", "--thread", thread, "--confirm-reviewed")
        recovered = self.fault.receipt(thread)
        if recovered["sessionId"] != before["sessionId"] or recovered["turn"].get("state") != "completed":
            raise LifecycleFailure("Busy bridge crash did not recover the original completed GC turn")
        write_new(artifacts / "receipt-recovered.json", recovered)
        expected = "BUSY_MEMORY_" + nonce + " " + memory
        followup = f"Without tools, reply with BUSY_MEMORY_{nonce}, one space, and the private word from the preceding turn."
        result = self.runner.browser(label + "-followup", c["agent"], c["project"], c["workspace"], followup,
                                     thread=thread, expected=expected, reasoning=c["reasoning"])
        self.runner.verify_turn(c["harness"], result, followup, expected, provider=c["identity"], no_tools=True)
        verify_resume_identity(frame, c["harness"].last_gc_frame)
        verify_one_prompt(c["harness"].last_gc_frame, before, prompt)
        return {**proof, "bridge_crashed_while_busy": True, "visible_failure": True,
                "explicit_recovery": True, "rendered_memory_followup": True}

    def bb_restart(self, kind):
        label = "lifecycle.bb_" + kind + "_restart"
        artifacts, c = self.evidence_dir(label), self.conversation()
        native = self.native_pane(c)
        target, env, suffix, app = self.bb_child(kind)
        other_kind = "host" if kind == "server" else "server"
        other, _, _, _ = self.bb_child(other_kind)
        write_new(artifacts / "before.json", {"target": target, "unaffected": other, "launcher": app})
        signal_verified(target, env, command_contains=suffix, parent=app["pid"])
        self.await_exit(target, env)
        def replaced():
            try:
                after, _, _, _ = self.bb_child(kind)
                return after if after != target else None
            except (LifecycleFailure, ProcessLookupError):
                return None
        after = self.fault.poll("BB launcher replacement child", replaced)
        def connected():
            try:
                rows = self.runner.bb("machine", "list", "--json")
                return any(row["id"] == self.runner.manifest["hostId"] and row["status"] == "connected" for row in rows)
            except (AcceptanceFailure, OSError):
                return None
        self.fault.poll("same BB host reconnected", connected)
        current_other, _, _, current_app = self.bb_child(other_kind)
        if current_other != other or current_app != app:
            raise LifecycleFailure("BB restarted a component outside the selected failure scope")
        result = self.runner.recall(label + "-recall", c)
        if self.native_pane(c) != native:
            raise LifecycleFailure("A BB component restart replaced the independent native GC process")
        write_new(artifacts / "after.json", {"target": after, "unaffected": current_other, "launcher": current_app})
        return {**result, "component_replaced": kind, "unrelated_component_preserved": True}

    def gc_identity(self, binary=None, preserve=False):
        binary = binary or self.runner.manifest["commands"]["gc"]
        state = json.loads(self.runner.command(binary, "supervisor", "status", "--json"))
        socket_path = Path(state.get("socket_path") or "/").resolve()
        if (state.get("running") is not True or state.get("pid_source") != "control_socket"
                or not socket_path.is_relative_to(Path(self.runner.env["GC_HOME"]).resolve())):
            raise LifecycleFailure("GC PID was not obtained from this isolated control socket")
        env = {"GC_HOME": self.runner.env["GC_HOME"]}
        if preserve:
            env["GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL"] = "1"
        observed = subprocess.run(["ps", "-ww", "-p", str(state["pid"]), "-o", "command="],
                                  capture_output=True, text=True, timeout=10, check=True).stdout.strip()
        command = canonical_executable_prefix(observed, binary, "supervisor", "run")
        return inspect_process(state["pid"], env, command_contains=command), env, command

    def systemd_properties(self, unit):
        if not re.fullmatch(r"gascity-supervisor-[A-Za-z0-9_.-]+\.service", unit):
            raise LifecycleFailure("Refusing an unrecognized supervisor unit name")
        names = ("Id", "MainPID", "ActiveState", "ControlGroup", "KillMode", "Restart",
                 "DropInPaths", "FragmentPath", "ExecStart")
        output = self.runner.command("systemctl", "--user", "show", unit,
                                     *("--property=" + name for name in names))
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    def gc_manager(self, identity, binary):
        self.guard()
        env = {"GC_HOME": self.runner.env["GC_HOME"], "GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL": "1"}
        if inspect_process(identity["pid"], env) != identity:
            raise LifecycleFailure("GC process identity changed before manager validation")
        if sys.platform == "darwin":
            # A direct child has no launchd service PID. Do not compete with a
            # discovered launchd owner; that manager needs separate qualification.
            rows = self.runner.command("launchctl", "list").splitlines()
            if any(len(fields := row.split(None, 2)) == 3 and fields[0] == str(identity["pid"]) for row in rows):
                raise LifecycleFailure("GC is launchd-managed; this lifecycle manager is not qualified")
            return None
        if not sys.platform.startswith("linux"):
            raise LifecycleFailure("Cannot establish the GC supervisor lifecycle manager on this platform")
        proc = Path("/proc") / str(identity["pid"])
        if proc.stat().st_uid != os.getuid() or identity["uid"] != os.getuid():
            raise LifecycleFailure("GC supervisor is not owned by the fixture user")
        prefix = f"/user.slice/user-{os.getuid()}.slice/user@{os.getuid()}.service/app.slice/"
        groups = [line.split(":", 2)[2] for line in (proc / "cgroup").read_text().splitlines()]
        owners = {part for group in groups for part in group.split("/")
                  if part.endswith(".service") and part != f"user@{os.getuid()}.service"}
        if not owners:
            return None
        groups = list({group for group in groups if group.startswith(prefix) and group.endswith(".service")})
        if len(groups) != 1:
            raise LifecycleFailure("GC supervisor is not controlled by exactly one verified user service")
        group = groups[0]
        unit = group[len(prefix):]
        if owners != {unit}:
            raise LifecycleFailure("GC supervisor has conflicting service manager ownership")
        properties = self.systemd_properties(unit)
        fragment = Path(properties.get("FragmentPath") or "/")
        if (not fragment.is_file() or fragment.is_symlink() or fragment.stat().st_uid != os.getuid()
                or not fragment.is_absolute()):
            raise LifecycleFailure("Owned supervisor unit fragment is not a regular file owned by this user")
        return verify_systemd_manager(properties, unit=unit, pid=identity["pid"],
            gc_home=self.runner.env["GC_HOME"], binary=binary, fragment=fragment.read_text(),
            uid=os.getuid(), cgroup=group)

    def verify_running_executable(self, identity, binary):
        if not sys.platform.startswith("linux"):
            # gc_identity already checked the canonical executable argv on
            # platforms without /proc; retain the pinned artifact check too.
            if hashlib.sha256(Path(binary).read_bytes()).hexdigest() != self.runner.manifest["gcBinarySha256"]:
                raise LifecycleFailure("Selected supervisor binary differs from the pinned candidate")
            return
        executable = Path("/proc") / str(identity["pid"]) / "exe"
        if (executable.resolve(strict=True) != Path(binary).resolve(strict=True)
                or hashlib.sha256(executable.read_bytes()).hexdigest() != self.runner.manifest["gcBinarySha256"]):
            raise LifecycleFailure("Running supervisor executable is not the exact selected candidate binary")

    def gc_replace(self, graceful):
        label = "lifecycle.gc_binary_replacement" if graceful else "lifecycle.gc_controller_restart"
        artifacts, c = self.evidence_dir(label), self.conversation()
        native = self.native_pane(c)
        target, env, command = self.gc_identity(preserve=True)
        binary = Path(self.runner.manifest["commands"]["gc"]).resolve()
        manager = self.gc_manager(target, binary)
        write_new(artifacts / "before.json", {"supervisor": target, "native": native, "manager": manager})
        if graceful:
            replacement = self.runner.root / ("controller-replacement-" + secrets.token_hex(6))
            replacement.mkdir(mode=0o700)
            replacement = replacement / "gc"
            with binary.open("rb") as source, replacement.open("xb") as destination:
                shutil.copyfileobj(source, destination)
            replacement.chmod(0o755)
            if hashlib.sha256(replacement.read_bytes()).hexdigest() != self.runner.manifest["gcBinarySha256"]:
                raise LifecycleFailure("Replacement executable differs from the verified candidate artifact")
            binary = replacement
        # gc start installs a Restart=always unit. A competing bare start races
        # that manager and can silently select the original executable.
        if self.gc_manager(target, self.runner.manifest["commands"]["gc"]) != manager:
            raise LifecycleFailure("Supervisor unit identity changed before the lifecycle action")
        if graceful and manager is not None:
            # Stop only this proven fixture unit; do not rewrite it or suppress
            # already-running errors from the replacement executable.
            self.runner.command("systemctl", "--user", "stop", manager["unit"])
            self.await_exit(target, env)
            def inactive():
                state = self.systemd_properties(manager["unit"])
                return state if state.get("ActiveState") == "inactive" and state.get("MainPID") == "0" else None
            self.fault.poll("owned supervisor unit inactive", inactive)
            self.runner.command("env", "GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL=1", binary, "supervisor", "start")
        else:
            signal_verified(target, env, command_contains=command, graceful=graceful)
            self.await_exit(target, env)
            if manager is None:
                self.runner.command("env", "GC_SUPERVISOR_PRESERVE_SESSIONS_ON_SIGNAL=1", binary, "supervisor", "start")
        def ready():
            try:
                health = self.fault.read_gc("/health")
                return health if health.get("startup", {}).get("ready") else None
            except (urllib.error.URLError, OSError):
                return None
        health = self.fault.poll("replacement GC controller ready", ready)
        if (health.get("version") != self.runner.manifest["versions"]["gc"]
                or not self.runner.manifest["gcCommit"].startswith(health.get("build_id") or "MISSING")):
            raise LifecycleFailure("Replacement GC controller does not run the verified artifact")
        after, _, _ = self.gc_identity(binary=binary, preserve=True)
        if after == target:
            raise LifecycleFailure("GC did not replace the selected supervisor process")
        self.verify_running_executable(after, binary)
        if graceful and manager is not None:
            inactive = self.systemd_properties(manager["unit"])
            if inactive.get("ActiveState") != "inactive" or inactive.get("MainPID") != "0":
                raise LifecycleFailure("Stopped fixture unit unexpectedly competed with the copied supervisor")
            after_manager = {"unit": manager["unit"], "active_state": "inactive", "replacement_mode": "direct"}
        elif manager is not None:
            after_manager = self.gc_manager(after, binary)
            if {k: v for k, v in after_manager.items() if k != "main_pid"} != {k: v for k, v in manager.items() if k != "main_pid"}:
                raise LifecycleFailure("Controller crash did not restart under the same verified unit configuration")
        else:
            if self.gc_manager(after, binary) is not None:
                raise LifecycleFailure("A manager unexpectedly took ownership of the direct supervisor replacement")
            after_manager = None
        result = self.runner.recall(label + "-recall", c)
        if self.native_pane(c) != native:
            raise LifecycleFailure("GC controller replacement restarted the existing native agent")
        write_new(artifacts / "after.json", {"supervisor": after, "native": native, "manager": after_manager})
        return {**result, "supervisor_replaced": True, "graceful": graceful,
                "replacement_binary_sha256": self.runner.manifest["gcBinarySha256"]}


CASE_DEPENDENCIES = {case: ("native.personal",) for case in (
    "lifecycle.bridge_idle_crash", "lifecycle.bridge_busy_crash", "lifecycle.bb_host_restart",
    "lifecycle.bb_server_restart", "lifecycle.gc_controller_restart", "lifecycle.gc_binary_replacement")}


def case_functions(runner):
    cases = LifecycleCases(runner)
    return {"lifecycle.bridge_idle_crash": cases.bridge_idle,
            "lifecycle.bridge_busy_crash": cases.bridge_busy,
            "lifecycle.bb_host_restart": lambda: cases.bb_restart("host"),
            "lifecycle.bb_server_restart": lambda: cases.bb_restart("server"),
            "lifecycle.gc_controller_restart": lambda: cases.gc_replace(False),
            "lifecycle.gc_binary_replacement": lambda: cases.gc_replace(True)}
