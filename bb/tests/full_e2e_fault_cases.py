"""Real transport-failure cases for ``full_e2e.Runner``.

``case_functions(runner)`` adds independently runnable browser/model
cases. Each briefly routes the existing *isolated* connection through a real
HTTP proxy using the installed pack CLI, then restores its original URL. No
service is restarted. Lost submit recovery never retries the original prompt.
"""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from live_assertions import AcceptanceFailure, verify_prompt_frame, verify_resume_identity
from live_faults import FaultFailure, FaultProxy, verify_recovery


def write_new(path, value):
    with Path(path).open("x") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")


def require_owned_config(runner):
    root = Path(runner.root).resolve(strict=True)
    marker = root / ".bb-full-e2e-owned.json"
    if (root.parent not in {Path("/tmp").resolve(), Path("/var/tmp").resolve()}
            or not root.name.startswith("bb-live-") or not marker.is_file()
            or json.loads(marker.read_text()).get("root") != str(root)):
        raise FaultFailure("Fault injection requires the marked isolated test installation")
    for key in ("GC_HOME", "BB_DATA_DIR", "GC_BB_CONFIG", "XDG_STATE_HOME"):
        path = Path(runner.env[key]).resolve()
        if path == root or not path.is_relative_to(root):
            raise FaultFailure("Fault injection state must remain inside the isolated installation")
    config_path = Path(runner.env["GC_BB_CONFIG"])
    if config_path.is_symlink():
        raise FaultFailure("Fault injection cannot rewrite a symlinked connection config")
    return config_path


def canonical_config(config):
    """Connection order may change through the supported connect command."""
    return {**config, "connections": sorted(config["connections"], key=lambda row: row["id"])}


def verify_native_completion(frame, receipt, prompt, expected):
    """A real final GC answer must follow the exact independently hashed input."""
    evidence = verify_prompt_frame(frame, receipt["turn"], prompt)
    messages = frame["structured_messages"]
    index = next(index for index, message in enumerate(messages)
                 if message.get("id") == evidence["gc_user_message_id"])
    answer = None
    for message in messages[index + 1:]:
        if message.get("role") == "assistant":
            answer = message if message.get("status") == "final" else None
        elif message.get("role") == "system":
            event = message.get("system_event") or {}
            if event.get("category") in {"provider_error", "provider_retry"}:
                answer = None
    if not answer:
        raise FaultFailure("GC has no settled successful native answer after the faulted input")
    text = "\n".join(block.get("text", "") for block in answer.get("blocks", [])
                     if block.get("type") == "text")
    lines = text.strip().splitlines()
    if not lines or lines[-1] != expected:
        raise FaultFailure("GC native answer did not satisfy the fault case's final marker")
    return {**evidence, "gc_assistant_message_id": answer["id"],
            "answer_sha256": hashlib.sha256(text.encode()).hexdigest()}


class FaultCases:
    def __init__(self, runner):
        self.runner = runner
        self.agent = runner.agent("global")
        self.workspace = runner.manifest["workspaces"]["global"]
        self.project, self.reasoning = "proj_personal", "none"
        self.city_path = "/v0/city/" + urllib.parse.quote(self.agent["city"], safe="")
        self.cli = Path(runner.env["GC_BB_INSTALL_DIR"]) / "current/dist/cli.js"
        if not self.cli.is_file():
            raise FaultFailure("Fault cases require the installed pack's built CLI")

    def cli_command(self, *args):
        return self.runner.command("node", self.cli, *args)

    @contextmanager
    def routed(self, label):
        config_path = require_owned_config(self.runner)
        original = json.loads(config_path.read_text())
        connections = [row for row in original["connections"] if row["id"] == self.agent["connection"]]
        if len(connections) != 1 or connections[0]["url"].rstrip("/") != self.runner.manifest["gcUrl"].rstrip("/"):
            raise FaultFailure("The selected isolated connection does not point to the verified GC service")
        artifact_dir = self.runner.private / label
        artifact_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        write_new(artifact_dir / "config-before.json", original)
        proxy = FaultProxy(connections[0]["url"], artifacts=artifact_dir / "proxy")
        restored = False
        try:
            self.cli_command("connect", "--id", self.agent["connection"], "--url", proxy.url)
            current = json.loads(config_path.read_text())
            expected = {**original, "connections": [{**row, "url": proxy.url} if row["id"] == self.agent["connection"]
                                                    else row for row in original["connections"]]}
            if canonical_config(current) != canonical_config(expected):
                raise FaultFailure("Routing the isolated connection changed unrelated configuration")
            yield proxy, artifact_dir
        finally:
            try:
                self.cli_command("connect", "--id", self.agent["connection"], "--url", connections[0]["url"])
                current = json.loads(config_path.read_text())
                write_new(artifact_dir / "config-after.json", current)
                restored = canonical_config(current) == canonical_config(original)
                if not restored:
                    raise FaultFailure("Fault cleanup did not preserve the original isolated configuration")
            finally:
                if restored:
                    proxy.close()
                else:
                    # Keep a failed-cleanup route functional and all evidence
                    # intact. Never abandon a configured URL to a closed proxy.
                    retained = getattr(self.runner, "retained_fault_proxies", [])
                    self.runner.retained_fault_proxies = [*retained, proxy]

    def read_gc(self, path, *, allow_missing=False):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *_):
                return None
        headers = {"Accept": "application/json"}
        if self.runner.env.get("GC_BB_AUTH_TOKEN"):
            headers["Authorization"] = "Bearer " + self.runner.env["GC_BB_AUTH_TOKEN"]
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        request = urllib.request.Request(self.runner.manifest["gcUrl"].rstrip("/") + path, headers=headers)
        try:
            with opener.open(request, timeout=20) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if allow_missing and error.code == 404:
                return None
            raise

    def receipt(self, thread):
        path = Path(self.runner.env["XDG_STATE_HOME"]) / "gascity/bb/sessions" / (hashlib.sha256(thread.encode()).hexdigest() + ".json")
        return json.loads(path.read_text()) if path.is_file() else None

    def poll(self, label, probe):
        deadline, last_update = time.monotonic() + self.runner.timeout, 0
        while time.monotonic() < deadline:
            result = probe()
            if result:
                return result
            now = time.monotonic()
            if now - last_update >= 15:
                self.runner.progress(f"{label}: waiting for independently verified GC/BB evidence")
                last_update = now
            time.sleep(0.5)
        raise FaultFailure(f"{label}: required real evidence did not arrive before the deadline")

    def remote_session(self, receipt):
        alias = receipt.get("sessionId") or receipt["alias"]
        remote = self.read_gc(self.city_path + "/session/" + urllib.parse.quote(alias, safe=""), allow_missing=True)
        if not remote:
            return None
        if (not remote.get("id") or remote.get("template") != self.agent["agent"]
                or Path(remote.get("work_dir") or "/").resolve() != Path(self.workspace).resolve()
                or (not receipt.get("sessionId") and remote.get("alias") != receipt["alias"])):
            raise FaultFailure("GC resolved a different agent, alias or execution workspace")
        return remote

    def native_answer(self, receipt, prompt, expected, artifact_dir):
        path = self.city_path + "/session/" + urllib.parse.quote(receipt["sessionId"], safe="") + "/transcript?format=structured"
        latest = {}
        def ready():
            frame = self.read_gc(path)
            latest["frame"] = frame
            try:
                verify_native_completion(frame, receipt, prompt, expected)
                return frame
            except (AcceptanceFailure, FaultFailure):
                return None
        try:
            return self.poll("faulted native turn", ready)
        finally:
            write_new(artifact_dir / "native-transcript.json", latest.get("frame", {}))

    def browser_failure(self, label, submitted, expected_error):
        path = self.runner.private / label
        argv = ["node", str(Path(__file__).with_name("browser_driver.mjs")), "--url", self.runner.manifest["bbUrl"],
                "--host", self.runner.manifest["hostId"], "--project", self.project, "--model", self.agent["id"],
                "--workspace", str(self.workspace), "--reasoning", self.reasoning, "--action", "wait",
                "--existing-thread-id", submitted["threadId"], "--expected-error", expected_error,
                "--after-seq", str(submitted["afterSeq"]), "--timeout-ms", str(self.runner.timeout * 1000),
                "--artifacts", str(path)]
        if self.runner.channel:
            argv += ["--channel", self.runner.channel]
        self.runner.command(*argv, timeout=self.runner.timeout + 100)
        result = json.loads((path / "result.json").read_text())
        if result.get("status") != "passed" or not result.get("rejection"):
            raise FaultFailure("BB did not render the expected transport uncertainty")
        return result

    def start(self, label, prompt, *, expected=None, until="submitted", thread=None):
        return self.runner.browser(label, self.agent, self.project, self.workspace, prompt,
                                   expected=expected, reasoning=self.reasoning, until=until, thread=thread)

    def lost_create(self):
        label = "fault.create_response"
        marker = "CREATE_RECOVERED_" + secrets.token_hex(8)
        prompt = f"Do not use tools. Reply with exactly {marker}."
        with self.routed(label) as (proxy, artifacts):
            ticket = proxy.arm("create", path=self.city_path + "/sessions")
            submitted = self.start(label + "-submit", prompt)
            fault = ticket.wait(self.runner.timeout)
            thread = submitted["threadId"]
            before = self.poll("lost create receipt", lambda: self.receipt(thread))
            write_new(artifacts / "receipt-before.json", before)
            if before.get("create") or before.get("sessionId") or before.get("turn"):
                raise FaultFailure("BB observed or acted on a create response that the proxy dropped")
            self.browser_failure(label + "-visible-error", submitted, "fetch failed")
            remote = self.poll("original GC alias", lambda: self.remote_session(before))
            write_new(artifacts / "original-session.json", remote)
            capture = artifacts / "proxy" / f"request-{fault['index']:04d}"
            reviewed_creation = {"kind": "reviewed-lost-create", "before_receipt": before,
                "session": remote, "intercepted": fault,
                "request_body": capture.with_suffix(".body").read_bytes().decode("utf-8"),
                "response_body": capture.with_suffix(".response").read_bytes().decode("utf-8")}
            write_new(artifacts / "reviewed-create-evidence.json", reviewed_creation)
            startup = self.read_gc(self.city_path + "/session/" + urllib.parse.quote(remote["id"], safe="") + "/transcript?format=structured")
            write_new(artifacts / "reviewed-startup-transcript.json", startup)
            if proxy.counts()["create"] != 1 or proxy.counts()["submit"] != 0:
                raise FaultFailure("BB retried or submitted before explicit creation recovery")
            self.cli_command("recover", "--thread", thread, "--confirm-reviewed")
            harness = self.runner.new_harness(label, self.agent, self.project, self.workspace, thread)
            baseline = max((row["seq"] for row in harness.events()), default=0)
            self.runner.bb("thread", "retry", thread, "--json")
            result = self.runner.browser(label + "-recovered", self.agent, self.project, self.workspace,
                thread=thread, expected=marker, reasoning=self.reasoning, action="wait", after=baseline)
            self.runner.verify_turn(harness, result, prompt, marker, no_tools=True,
                                    reviewed_creation=reviewed_creation)
            after = self.receipt(thread)
            write_new(artifacts / "receipt-after.json", after)
            proof = verify_recovery(before=before, after=after, transcript=harness.last_gc_frame,
                                    expected_session_id=remote["id"], request_records=proxy.records(), expected_prompt=prompt)
            self.runner.bb("thread", "stop", thread)
            return {**proof, "fault_request_id": fault["accepted"]["request_id"], "visible_failure": True,
                    "explicit_recovery": True, "rendered_completion": True}

    def lost_submit(self, *, crash_bridge=False):
        label = "fault.bridge_uncertain_delivery" if crash_bridge else "fault.submit_response"
        nonce, memory = secrets.token_hex(8), secrets.token_hex(12)
        marker = "SUBMIT_ACCEPTED_" + nonce
        prompt = f"Remember the private word {memory} for our next turn. Do not use tools. Reply with exactly {marker}."
        with self.routed(label) as (proxy, artifacts):
            ticket = proxy.arm("submit", hold=crash_bridge)
            submitted = self.start(label + "-submit", prompt)
            if crash_bridge:
                # The native service has accepted the mutation, but its response
                # has not reached the bridge. Kill only this verified owned
                # worker while its durable receipt still records uncertainty.
                from full_e2e_lifecycle_cases import LifecycleCases, signal_verified, visible_failure_fragment
                from full_e2e_interaction_cases import events
                accepted = ticket.wait_accepted(self.runner.timeout)
                try:
                    uncertain = self.poll("uncertain bridge receipt", lambda: self.receipt(submitted["threadId"]))
                    if (uncertain.get("turn", {}).get("state") != "submitting"
                            or uncertain["turn"].get("request_id") or not accepted.get("accepted")):
                        raise FaultFailure("Bridge is not awaiting the held acceptance response")
                    harness = self.runner.new_harness(label, self.agent, self.project, self.workspace, submitted["threadId"])
                    lifecycle = LifecycleCases(self.runner)
                    identity, env = lifecycle.bridge_identity({"harness": harness})
                    write_new(artifacts / "bridge-before.json", {"process": identity, "receipt": uncertain})
                    signal_verified(identity, env, command_contains="bb-provider-bridge-worker.mjs", parent=identity["parent_pid"])
                    lifecycle.await_exit(identity, env)
                finally:
                    ticket.release()
            fault = ticket.wait(self.runner.timeout)
            thread = submitted["threadId"]
            before = self.poll("lost submit receipt", lambda: self.receipt(thread))
            write_new(artifacts / "receipt-before.json", before)
            if (not before.get("sessionId") or (before.get("turn") or {}).get("state") != "submitting"
                    or before["turn"].get("request_id")):
                raise FaultFailure("Lost submit acceptance was not preserved as an uncertain receipt")
            error = "Remote execution may continue"
            if crash_bridge:
                error = self.poll("uncertain bridge failure", lambda: visible_failure_fragment(
                    events(self.runner, thread, submitted["afterSeq"])))
            self.browser_failure(label + "-visible-error", submitted, error)
            frame = self.native_answer(before, prompt, marker, artifacts)
            if proxy.counts()["create"] != 1 or proxy.counts()["submit"] != 1:
                raise FaultFailure("BB blindly retried an accepted mutation")
            # Release the bridge lease only after GC is independently idle.
            # No interrupt or duplicate initial prompt is sent to GC.
            self.runner.bb("thread", "stop", thread)
            self.cli_command("recover", "--thread", thread, "--confirm-reviewed",
                             "--request-id", fault["accepted"]["request_id"],
                             "--event-cursor", str(fault["accepted"]["event_cursor"]))
            recovered = self.receipt(thread)
            write_new(artifacts / "receipt-recovered.json", recovered)
            proof = verify_recovery(before=before, after=recovered, transcript=frame,
                                    request_records=proxy.records(), expected_prompt=prompt)
            followup_marker = "RECOVERED_MEMORY_" + nonce
            expected = followup_marker + " " + memory
            followup = f"Without tools, reply with {followup_marker}, one space, and the private word from the previous turn. Recall it from the conversation."
            result = self.start(label + "-followup", followup, expected=expected, until="completed", thread=thread)
            harness = self.runner.new_harness(label + ("-recovered" if crash_bridge else ""), self.agent, self.project, self.workspace, thread)
            self.runner.verify_turn(harness, result, followup, expected, no_tools=True)
            verify_resume_identity(frame, harness.last_gc_frame)
            if proxy.counts()["create"] != 1 or proxy.counts()["submit"] != 2:
                raise FaultFailure("Recovery or follow-up duplicated a GC mutation")
            self.runner.bb("thread", "stop", thread)
            return {**proof, "visible_uncertainty": True, "explicit_recovery": True,
                    "rendered_memory_followup": True, "total_submit_requests": 2,
                    "bridge_crashed_before_acceptance_receipt": crash_bridge}

    def stream_disconnect(self):
        label = "fault.stream_disconnect"
        with self.routed(label) as (proxy, artifacts):
            warmup_marker = "STREAM_READY_" + secrets.token_hex(8)
            warmup = f"Do not use tools. Reply with exactly {warmup_marker}."
            initial = self.start(label + "-warmup", warmup, expected=warmup_marker, until="completed")
            thread = initial["threadId"]
            harness = self.runner.new_harness(label, self.agent, self.project, self.workspace, thread)
            _, identity = self.runner.verify_turn(harness, initial, warmup, warmup_marker, no_tools=True)
            warmup_frame = harness.last_gc_frame
            before = self.receipt(thread)
            write_new(artifacts / "receipt-before.json", before)
            prior = proxy.records()
            if proxy.counts()["create"] != 1 or proxy.counts()["submit"] != 1:
                raise FaultFailure("Stream warmup did not produce exactly one creation and submit")
            prefix = self.city_path + "/session/" + urllib.parse.quote(before["sessionId"], safe="") + "/stream?"
            ticket = proxy.arm("stream", path_prefix=prefix, after_bytes=1)
            marker = "STREAM_RECONNECTED_" + secrets.token_hex(8)
            prompt = f"Do not use tools. Reply with exactly {marker}."
            result = self.start(label + "-faulted", prompt, expected=marker, until="completed", thread=thread)
            fault = ticket.wait(self.runner.timeout)
            self.runner.verify_turn(harness, result, prompt, marker, provider=identity, no_tools=True)
            verify_resume_identity(warmup_frame, harness.last_gc_frame)
            after = self.receipt(thread)
            write_new(artifacts / "receipt-after.json", after)
            current = proxy.records()
            new = [row for row in current if row["index"] > max(row["index"] for row in prior)]
            # The warmup is a separately proven turn, not a recovery retry.
            # Retain its sole creation plus every fault-turn request for the
            # one-create/one-submit recovery invariant.
            create = [row for row in prior if row.get("operation") == "create"]
            proof = verify_recovery(before=before, after=after, transcript=harness.last_gc_frame,
                                    request_records=create + new, expected_prompt=prompt)
            streams = [row for row in new if row.get("operation") == "stream" and row["path"].startswith(prefix)]
            if len(streams) < 2 or fault.get("response_bytes") != 1:
                raise FaultFailure("The real session stream did not disconnect and reconnect")
            if proxy.counts()["create"] != 1 or proxy.counts()["submit"] != 2:
                raise FaultFailure("Stream recovery duplicated creation or prompt submission")
            self.runner.bb("thread", "stop", thread)
            return {**proof, "real_stream_connections": len(streams), "rendered_completion": True,
                    "fault_forwarded_bytes": fault["response_bytes"], "total_submit_requests": 2}


def case_functions(runner):
    cases = FaultCases(runner)
    return {"fault.create_response": cases.lost_create, "fault.submit_response": cases.lost_submit,
            "fault.stream_disconnect": cases.stream_disconnect,
            "fault.bridge_uncertain_delivery": lambda: cases.lost_submit(crash_bridge=True)}
