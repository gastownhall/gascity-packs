#!/usr/bin/env python3
"""Exercise real BB turns and optional agent resume against an isolated GC agent.

The caller owns provisioning and teardown. This never retries a mutation, stops
a thread, or deletes evidence. Only report.json is suitable for CI upload;
private/ contains model/provider output and must remain private.
"""

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from credential_preflight import classify


class AcceptanceFailure(RuntimeError):
    pass


def safe_provider_failure(payload):
    """Recognize known failures without disclosing arbitrary provider text."""
    text = json.dumps(payload).lower()
    if "reliable turn activity" in text or "no reliable structured transcript" in text:
        return "GC runtime activity or structured history is unreliable"
    if "complete submitted prompt" in text or "missing or truncated delivery" in text:
        return "GC did not preserve the complete forwarded prompt"
    if "reliable idle transcript" in text:
        return "GC startup did not become ready; no BB prompt was sent"
    if "session is busy" in text or "needs a response" in text or "active gas city turn" in text:
        return "GC session is busy or waiting for a response"
    # CI discards private evidence; keep only HTTP statuses and allow-listed
    # error kinds so an unrecognized failure is still diagnosable.
    detail = classify(json.dumps(payload))
    suffix = "".join(f" {key}={','.join(value)}" for key, value in detail.items() if value)
    return "BB reported a provider failure;" + (suffix and suffix + ";") + " inspect private evidence"


def verify_prompt_frame(frame, turn, prompt):
    """Validate GC's own transcript independently of BB's rendered answer."""
    if frame.get("schema_version") != "session.structured.v1":
        raise AcceptanceFailure("GC returned an unsupported structured transcript schema")
    history = frame.get("history") or {}
    tail = history.get("tail_state") or {}
    # GC 1.4 uses omitempty for false; absent degraded is its reliable form.
    if tail.get("activity") != "idle" or tail.get("degraded", False) is not False:
        raise AcceptanceFailure("GC completed transcript is not reliably idle")
    if tail.get("open_tool_call_ids") or tail.get("pending_interaction_ids"):
        raise AcceptanceFailure("GC completed transcript still has pending tools or interactions")
    baseline = turn.get("baselineMessageIds")
    if not isinstance(baseline, list) or not all(isinstance(value, str) for value in baseline):
        raise AcceptanceFailure("Receipt has no valid baseline message identities")
    messages = frame.get("structured_messages")
    if not isinstance(messages, list):
        raise AcceptanceFailure("GC structured transcript has no message list")
    matches = []
    for message in messages:
        if (message.get("role") != "user" or not message.get("id")
                or message["id"] in baseline or message.get("status") == "superseded"):
            continue
        text = (message.get("user_prompt") or {}).get("text")
        if text is None:
            text = "\n".join(block.get("text", "") for block in message.get("blocks", [])
                             if block.get("type") == "text")
        if isinstance(text, str) and prompt in text and hashlib.sha256(text.encode()).hexdigest() == turn.get("messageDigest"):
            matches.append({"forwarded_prompt_sha256": turn["messageDigest"],
                    "forwarded_prompt_bytes": len(text.encode()),
                    "gc_user_message_id": message["id"]})
    if len(matches) > 1:
        raise AcceptanceFailure("GC must contain exactly one delivery of the forwarded prompt")
    if matches:
        return matches[0]
    raise AcceptanceFailure("GC transcript lacks a new user entry preserving the complete forwarded prompt")


def verify_resume_identity(before, after):
    """A restarted agent must retain the same GC and provider conversation."""
    for field in ("gc_session_id", "logical_conversation_id", "provider_session_id", "transcript_stream_id"):
        original = (before.get("history") or {}).get(field)
        if not original or original != (after.get("history") or {}).get(field):
            raise AcceptanceFailure("Agent resume changed a conversation or transcript identity")


def decode_identity(value, prefix):
    if not isinstance(value, str) or not value.startswith(prefix):
        raise AcceptanceFailure("Unexpected encoded GC identity")
    encoded = value[len(prefix):]
    return json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))


def verify_global_agent_config(target, config):
    """The personal route still requires a live, explicitly configured global agent."""
    agent = target.get("agent")
    if target.get("v") != 1 or not isinstance(agent, str) or not agent or "/" in agent:
        raise AcceptanceFailure("Personal conversations require an exact global agent")
    matches = [item for item in config.get("agents", []) if item.get("name") == agent
               and not item.get("dir") and item.get("scope") != "rig" and not item.get("suspended")]
    if (config.get("workspace") or {}).get("suspended") or len(matches) != 1:
        raise AcceptanceFailure("GC config does not expose the selected active global agent")


def verify_reviewed_lost_create(receipt, evidence, *, project, workspace):
    """Bind a dropped create ACK to its captured bytes and reviewed alias lookup.

    Only the lost-create fault case supplies this evidence. It never invents a
    receipt ACK: the bridge recovered the original session by deterministic alias.
    """
    if not isinstance(evidence, dict) or evidence.get("kind") != "reviewed-lost-create":
        raise AcceptanceFailure("Missing explicit reviewed lost-create evidence")
    before, session, record = (evidence.get(key) for key in ("before_receipt", "session", "intercepted"))
    if not all(isinstance(value, dict) for value in (before, session, record)):
        raise AcceptanceFailure("Incomplete reviewed lost-create evidence")
    alias = "bb-" + hashlib.sha256(receipt["threadId"].encode()).hexdigest()[:24]
    if (receipt.get("create") or receipt.get("alias") != alias
            or any(before.get(key) != receipt.get(key) for key in ("threadId", "target", "alias"))
            or any(before.get(key) for key in ("create", "sessionId", "turn"))):
        raise AcceptanceFailure("Reviewed lost-create evidence changed original thread, target or alias")
    target = receipt["target"]
    if (session.get("id") != receipt["sessionId"] or session.get("alias") != alias
            or session.get("template") != target["agent"]
            or Path(session.get("work_dir") or "/").resolve() != workspace):
        raise AcceptanceFailure("Reviewed lost-create evidence identifies another alias, session or target")
    accepted = record.get("accepted")
    if (record.get("method") != "POST" or record.get("operation") != "create"
            or record.get("path") != "/v0/city/" + urllib.parse.quote(target["city"], safe="") + "/sessions"
            or record.get("fault") != "accepted-response-drop" or not record.get("finished_at")
            or type(record.get("upstream_status")) is not int or not 200 <= record["upstream_status"] < 300
            or not isinstance(accepted, dict) or accepted.get("status") != "accepted"
            or not isinstance(accepted.get("request_id"), str) or not accepted["request_id"]
            or accepted.get("event_cursor") is None):
        raise AcceptanceFailure("Reviewed lost-create evidence lacks an intercepted accepted request/cursor")
    bodies = {}
    for operation in ("request", "response"):
        text = evidence.get(operation + "_body")
        if (not isinstance(text, str) or record.get(operation + "_bytes") != len(text.encode())
                or record.get(operation + "_sha256") != hashlib.sha256(text.encode()).hexdigest()):
            raise AcceptanceFailure("Reviewed lost-create capture bytes do not match the intercepted request")
        try:
            bodies[operation] = json.loads(text)
        except ValueError as error:
            raise AcceptanceFailure("Reviewed lost-create capture is not JSON") from error
    request = bodies["request"]
    if (not isinstance(request, dict) or request.get("kind") != "agent"
            or request.get("name") != target["agent"] or request.get("alias") != alias
            or request.get("project_id") != project or bodies["response"] != accepted):
        raise AcceptanceFailure("Reviewed lost-create capture does not bind this target and accepted identity")
    return {"gc_create_request_id": accepted["request_id"], "gc_create_event_cursor": accepted["event_cursor"],
            "gc_create_evidence": "reviewed-lost-create"}


class LiveAssertions:
    def __init__(self, *, bb_bin, host, project, model, workspace, artifacts,
                 timeout=240, env=None, existing_thread_id=None, exercise_resume=False):
        self.bb_bin = str(bb_bin)
        self.host, self.project, self.model = host, project, model
        self.personal_conversation = project == "proj_personal"
        if self.personal_conversation:
            target = decode_identity(model, "gc1_")
            agent = target.get("agent")
            if target.get("v") != 1 or not isinstance(agent, str) or not agent or "/" in agent:
                raise AcceptanceFailure("Personal conversations require an exact global agent")
        self.workspace = Path(workspace).resolve(strict=True)
        if not self.workspace.is_dir():
            raise AcceptanceFailure("Workspace must be an existing directory")
        self.artifacts = Path(artifacts)
        self.artifacts.mkdir(mode=0o700, parents=True, exist_ok=False)
        self.private = self.artifacts / "private"
        self.private.mkdir(mode=0o700)
        self.timeout = timeout
        self.env = os.environ.copy() if env is None else dict(env)
        self.counter = 0
        self.thread_id = existing_thread_id
        self.existing_thread = bool(existing_thread_id)
        self.exercise_resume = exercise_resume
        self.report = {"schema_version": 1, "status": "running", "model": model,
                       "assertions": [], "turns": []}

    def progress(self, message):
        print(f"[BB live acceptance] {message}", flush=True)

    def command(self, *args):
        self.counter += 1
        # No shell and no implicit default provider/model/project/host.
        try:
            result = subprocess.run([self.bb_bin, *args], env=self.env,
                                    cwd=self.workspace, capture_output=True,
                                    text=True, timeout=45, check=False)
        except subprocess.TimeoutExpired as error:
            raise AcceptanceFailure(f"BB command {self.counter} timed out; mutation outcome may be uncertain") from error
        for suffix, content in (("stdout", result.stdout), ("stderr", result.stderr)):
            path = self.private / f"command-{self.counter:04d}.{suffix}"
            with path.open("x") as stream:
                os.chmod(path, 0o600)
                stream.write(content)
        if result.returncode:
            raise AcceptanceFailure(f"BB command {self.counter} exited {result.returncode}; see private evidence")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise AcceptanceFailure(f"BB command {self.counter} returned invalid JSON") from error

    def events(self, after=0):
        rows = self.command("thread", "log", self.thread_id, "--json", "--all",
                            "--after-seq", str(after))
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise AcceptanceFailure("Unexpected BB event-log schema")
        # Do not let stale server responses satisfy a later turn.
        return [row for row in rows if isinstance(row.get("seq"), int) and row["seq"] > after]

    def verify_destination(self, attach_timeout=60):
        # BB attaches a spawned thread's environment asynchronously: spawn
        # returns no environmentId and the first show can still be "starting"
        # without one. Judge the destination only once BB has attached it.
        deadline = time.monotonic() + attach_timeout
        while True:
            state = self.command("thread", "show", self.thread_id, "--json")
            thread, environment = state.get("thread", {}), state.get("environment") or {}
            if environment.get("hostId") or thread.get("status") != "starting":
                break
            if time.monotonic() >= deadline:
                raise AcceptanceFailure("BB did not attach an environment to the thread")
            time.sleep(1)
        if thread.get("providerId") != "gas-city" or thread.get("projectId") != self.project:
            raise AcceptanceFailure("BB selected a different provider or project")
        if environment.get("hostId") != self.host:
            raise AcceptanceFailure("BB selected a different host")
        if self.personal_conversation:
            if environment.get("managed") is not False and not (
                    environment.get("managed") is True and environment.get("workspaceProvisionType") == "personal"):
                raise AcceptanceFailure("BB did not provision its own personal workspace")
        elif environment.get("managed") is not False:
            raise AcceptanceFailure("BB selected a managed project workspace")
        bb_workspace = Path(environment.get("path") or "/").resolve()
        if self.personal_conversation:
            data_dir, environment_id = self.env.get("BB_DATA_DIR"), environment.get("id")
            def component(value):
                return (isinstance(value, str) and bool(value) and value not in {".", ".."}
                        and Path(value).name == value)
            if (not data_dir or not Path(data_dir).is_absolute() or not component(environment_id)
                    or not Path(environment.get("path") or "/").is_absolute()):
                raise AcceptanceFailure("Cannot verify BB's isolated personal workspace")
            data_root = Path(data_dir).resolve()
            provider = environment.get("environmentProviderId")
            instance = environment.get("environmentProviderInstanceKey")
            if provider is not None or instance is not None:
                # BB 0.43 provisions one plugin-owned directory per thread.
                if (provider != "personal-workspace" or not component(self.thread_id)
                        or instance != self.thread_id or environment.get("managed") is not True
                        or environment.get("workspaceProvisionType") != "personal"):
                    raise AcceptanceFailure("BB personal workspace does not identify this thread's provider instance")
                personal_workspace = (data_root / "plugins/environment-personal-workspace/host-data/workspaces"
                                      / self.thread_id).resolve()
            else:
                # Older BB stores have no environment-provider identity and
                # retain their directory under the environment ID instead.
                if environment.get("workspaceProvisionType") not in {None, "personal"}:
                    raise AcceptanceFailure("BB did not provision its own personal workspace")
                personal_workspace = (data_root / "personal-workspaces" / environment_id).resolve()
            if (not personal_workspace.is_relative_to(data_root) or personal_workspace == data_root
                    or bb_workspace != personal_workspace or bb_workspace == self.workspace):
                raise AcceptanceFailure("BB must select its own personal workspace, separate from GC")
            self.report["assertions"].append("personal-global-separate-bb-workspace")
        else:
            if bb_workspace != self.workspace:
                raise AcceptanceFailure("BB selected a different workspace")
            self.report["assertions"].append("exact-provider-project-host-workspace")

    def verify_gc_prompt(self, prompt, provider_id, *, reviewed_creation=None):
        config_file, state_home = self.env.get("GC_BB_CONFIG"), self.env.get("XDG_STATE_HOME")
        if not config_file or not state_home or not Path(config_file).is_absolute() or not Path(state_home).is_absolute():
            raise AcceptanceFailure("Independent GC verification requires explicit isolated config and state paths")
        receipt_path = (Path(state_home) / "gascity/bb/sessions" /
                        (hashlib.sha256(self.thread_id.encode()).hexdigest() + ".json"))
        receipt = json.loads(receipt_path.read_text())
        config = json.loads(Path(config_file).read_text())

        target = decode_identity(self.model, "gc1_")
        remote = decode_identity(provider_id, "gcs1_")
        if (target.get("v") != 1 or remote.get("v") != 1 or receipt.get("threadId") != self.thread_id
                or receipt.get("target") != target or remote.get("target") != target
                or not receipt.get("sessionId") or remote.get("sessionId") != receipt["sessionId"]):
            raise AcceptanceFailure("GC receipt does not identify the exact BB thread, target, and session")
        turn = receipt.get("turn") or {}
        bb_request = self.report["turns"][-1]["client_request_id"]
        allowed_requests = {bb_request}
        # The initial thread/start RPC does not carry BB's request ID to the
        # bridge. Its durable receipt uses this documented deterministic ID.
        if len(self.report["turns"]) == 1:
            allowed_requests.add("initial-" + self.thread_id)
        if turn.get("state") != "completed" or turn.get("clientRequestId") not in allowed_requests:
            raise AcceptanceFailure("GC receipt is not completed for the matching BB request")
        creation_evidence = {}
        if reviewed_creation is not None:
            if len(self.report["turns"]) != 1:
                raise AcceptanceFailure("Reviewed lost-create evidence is only valid for the first recovered turn")
            creation_evidence = verify_reviewed_lost_create(receipt, reviewed_creation,
                                                          project=self.project, workspace=self.workspace)
        operations = (turn,) if creation_evidence else (receipt.get("create") or {}, turn)
        for operation in operations:
            if not operation.get("request_id") or operation.get("event_cursor") is None:
                raise AcceptanceFailure("GC receipt lacks durable create or submit acceptance identities")
        if turn.get("digest") != hashlib.sha256(prompt.encode()).hexdigest() or not turn.get("messageDigest"):
            raise AcceptanceFailure("GC receipt does not hash the original user prompt")
        connections = [connection for connection in config.get("connections", [])
                       if connection.get("id") == target.get("connection")]
        bindings = [binding for binding in config.get("bindings", []) if binding.get("projectId") == self.project]
        if len(connections) != 1:
            raise AcceptanceFailure("GC config no longer identifies the exact target connection")
        if self.personal_conversation:
            if bindings:
                raise AcceptanceFailure("Personal acceptance must exercise an unbound global conversation")
        elif (len(bindings) != 1 or bindings[0].get("connection") != target.get("connection")
              or bindings[0].get("city") != target.get("city")):
            raise AcceptanceFailure("GC config no longer maps the exact BB project and target")
        url = urllib.parse.urlsplit(connections[0]["url"])
        if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
                or url.username or url.password or url.query or url.fragment):
            raise AcceptanceFailure("Live acceptance only reads explicitly configured loopback GC HTTP endpoints")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        headers = {"Accept": "application/json"}
        if self.env.get("GC_BB_AUTH_TOKEN"):
            headers["Authorization"] = "Bearer " + self.env["GC_BB_AUTH_TOKEN"]
        city_endpoint = connections[0]["url"].rstrip("/") + "/v0/city/" + urllib.parse.quote(target["city"], safe="")
        endpoint = city_endpoint + "/session/" + urllib.parse.quote(receipt["sessionId"], safe="")

        def fetch(suffix, label, method="GET", *, city_resource=False):
            try:
                request_headers = dict(headers)
                if method != "GET":
                    request_headers.update({"X-GC-Request": "bb-provider", "Content-Type": "application/json"})
                request = urllib.request.Request((city_endpoint if city_resource else endpoint) + suffix, headers=request_headers,
                                                 method=method, data=b"{}" if method != "GET" else None)
                with opener.open(request, timeout=20) as response:
                    raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise AcceptanceFailure("GC evidence exceeded the response size limit")
            except urllib.error.URLError as error:
                raise AcceptanceFailure("GC evidence operation failed; inspect isolated state before any retry") from error
            with (self.private / f"gc-turn-{len(self.report['turns'])}-{label}.json").open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(raw)
            return json.loads(raw)

        if self.personal_conversation:
            verify_global_agent_config(target, fetch("/config", "city-config", city_resource=True))
        session = fetch("", "session")
        if (session.get("id") != receipt["sessionId"] or session.get("template") != target["agent"]
                or Path(session.get("work_dir") or "/").resolve() != self.workspace):
            raise AcceptanceFailure("GC session endpoint does not match the receipt target and workspace")
        if creation_evidence and session.get("alias") != receipt["alias"]:
            raise AcceptanceFailure("GC live session alias changed since reviewed lost-create recovery")
        frame = fetch("/transcript?format=structured", "transcript")
        evidence = verify_prompt_frame(frame, turn, prompt)
        evidence["gc_submit_request_id"] = turn["request_id"]
        evidence.update(creation_evidence)
        self.report["turns"][-1].update(evidence)
        self.report["assertions"].append(f"turn-{len(self.report['turns'])}-independent-full-forwarded-prompt")
        # This closure is bound only after independently validating the exact
        # owned thread, configured loopback endpoint, agent and workspace.
        self.gc_fetch, self.last_gc_frame = fetch, frame

    def verify_agent_resume(self, provider_id, memory, nonce):
        self.progress("suspending only the verified idle agent; GC and BB stay running")
        before = self.gc_fetch("/transcript?format=structured", "before-suspend")
        verify_resume_identity(self.last_gc_frame, before)
        tail = (before.get("history") or {}).get("tail_state") or {}
        if tail.get("activity") != "idle" or tail.get("degraded") or tail.get("open_tool_call_ids") or tail.get("pending_interaction_ids"):
            raise AcceptanceFailure("Refusing to suspend an agent without reliable idle history")
        self.gc_fetch("/suspend", "suspend-result", "POST")
        # Explicit suspension reports suspended; some controllers project asleep.
        # Both require independent evidence that the runtime actually stopped.
        deadline, poll = time.monotonic() + 30, 0
        while True:
            state = self.gc_fetch("", f"suspend-state-{poll}")
            if state.get("state") in {"suspended", "asleep"} and state.get("running") is False:
                break
            if time.monotonic() >= deadline:
                raise AcceptanceFailure("Controller did not settle the suspended agent as stopped")
            time.sleep(1)
            poll += 1
        self.report["assertions"].append("agent-suspended-and-runtime-stopped")
        after_seq = max((row["seq"] for row in self.events()), default=0)
        expected = f"RESUMED_{nonce} {memory}"
        prompt = ("Without tools, end your final answer with a standalone line containing "
                  f"RESUMED_{nonce}, one space, and the private test word from the first turn. "
                  "Use the conversation's retained memory; do not guess.")
        self.report["prompt_bytes"].append(len(prompt.encode()))
        self.report["prompt_sha256"].append(hashlib.sha256(prompt.encode()).hexdigest())
        self.command("thread", "tell", self.thread_id, prompt, "--mode", "auto", "--model", self.model, "--json")
        self.await_turn(after=after_seq, expected=expected, previous_provider_id=provider_id, forbid_tools=True)
        self.verify_gc_prompt(prompt, provider_id)
        verify_resume_identity(before, self.last_gc_frame)
        self.report["assertions"].extend(["same-provider-conversation-after-agent-resume", "resumed-conversation-memory"])

    def await_turn(self, *, after, expected, require_tool=False, previous_provider_id=None, forbid_tools=False):
        deadline = time.monotonic() + self.timeout
        last_progress = 0
        while time.monotonic() < deadline:
            rows = self.events(after)
            failures = [row for row in rows if row.get("type") in
                        {"system/error", "client/turn/rejected", "provider/modelFallback"}]
            if failures:
                raise AcceptanceFailure(safe_provider_failure(failures[0].get("data")))
            completed = [row for row in rows if row.get("type") == "turn/completed"]
            if completed:
                if len(completed) != 1:
                    raise AcceptanceFailure("Expected exactly one fresh completed turn")
                terminal = completed[0]
                data = terminal.get("data", {})
                if data.get("status") != "completed" or data.get("error"):
                    if data.get("error"):
                        raise AcceptanceFailure(safe_provider_failure(data["error"]))
                    status = data.get("status") if data.get("status") in {"failed", "interrupted"} else "unknown"
                    raise AcceptanceFailure(f"BB turn ended with {status} status")
                scope = terminal.get("scope", {})
                if scope.get("kind") != "turn" or not scope.get("turnId"):
                    raise AcceptanceFailure("Completed turn has no BB turn identity")
                scoped = [row for row in rows if row.get("scope") == scope]
                starts = [row for row in scoped if row.get("type") == "turn/started"]
                requests = [row for row in rows if row.get("type") == "client/turn/requested"]
                if len(starts) != 1 or len(requests) != 1:
                    raise AcceptanceFailure("Missing or duplicate BB turn start/request")
                accepted = [row for row in scoped if row.get("type") == "turn/input/accepted"]
                request_id = requests[0].get("data", {}).get("requestId")
                if (len(accepted) != 1 or not request_id
                        or accepted[0].get("data", {}).get("clientRequestId") != request_id):
                    raise AcceptanceFailure("BB completion is not correlated to the submitted request")
                if requests[0].get("data", {}).get("execution", {}).get("model") != self.model:
                    raise AcceptanceFailure("BB turn did not use the exact requested model")
                provider_id = data.get("providerThreadId")
                if not provider_id or (previous_provider_id and provider_id != previous_provider_id):
                    raise AcceptanceFailure("GC session identity missing or changed between turns")
                messages = [row.get("data", {}).get("item", {}) for row in scoped
                            if row.get("type") == "item/completed"]
                answers = [item.get("text", "") for item in messages
                           if item.get("type") == "agentMessage"]
                answer = answers[-1] if answers else ""
                answer_lines = answer.strip().splitlines()
                if not answer_lines or answer_lines[-1] != expected:
                    # These reports are public CI artifacts. Keep model output,
                    # expected markers and the private memory word out of them.
                    tokens = expected.split()
                    encoded = answer.encode()
                    self.report["marker_mismatch"] = {
                        "output_bytes": len(encoded),
                        "output_sha256": hashlib.sha256(encoded).hexdigest(),
                        "first_expected_token_present": bool(tokens) and tokens[0] in answer,
                        "last_expected_token_present": bool(tokens) and tokens[-1] in answer,
                        "expected_line_present": expected in answer_lines,
                    }
                    raise AcceptanceFailure("Fresh final assistant message did not match the requested markers")
                output = self.command("thread", "output", self.thread_id, "--json")
                output_lines = output.get("output", "").strip().splitlines()
                if not output_lines or output_lines[-1] != expected:
                    raise AcceptanceFailure("BB thread output did not expose the completed answer")
                tools = [item for item in messages if item.get("type") in {"toolCall", "commandExecution"}]
                if forbid_tools and tools:
                    raise AcceptanceFailure("Resumed conversation must recall its memory without tools")
                if require_tool and not any(item.get("status") == "completed" and not item.get("error")
                                            and item.get("exitCode", 0) == 0 for item in tools):
                    raise AcceptanceFailure("BB did not expose a successfully completed tool call")
                self.report["turns"].append({"turn_id": scope["turnId"], "provider_thread_id": provider_id,
                                             "client_request_id": request_id,
                                             "completed_seq": terminal["seq"], "tool_count": len(tools),
                                             "output_sha256": hashlib.sha256(expected.encode()).hexdigest()})
                return max(row["seq"] for row in rows), provider_id
            now = time.monotonic()
            if now - last_progress >= 15:
                self.progress(f"waiting for turn {len(self.report['turns']) + 1}; {len(rows)} new BB events")
                last_progress = now
            time.sleep(2)
        raise AcceptanceFailure(f"No verified BB completion within {self.timeout} seconds")

    def run(self):
        nonce = secrets.token_hex(12)
        prefix, suffix, memory = f"BEGIN_{nonce}", f"END_{nonce}", secrets.token_hex(16)
        expected_first = f"{prefix} {suffix}"
        first = (f"The beginning marker is {prefix}. Remember the private test word {memory} for the next turn.\n"
                 + "\n".join(f"Context line {index:02d}: Preserve this complete multiline acceptance request."
                             for index in range(24))
                 + f"\nThe ending marker is {suffix}. End your final answer with a standalone line containing "
                   "the beginning marker, one space, and the ending marker. Do not run tools on this turn.")
        proof = self.workspace / f"bb-live-proof-{nonce}.txt"
        if proof.exists() or proof.is_symlink():
            raise AcceptanceFailure("Refusing to replace an existing proof artifact")
        expected_bytes = f"{memory}\n".encode()
        expected_second = f"TOOLS_OK_{nonce}"
        second = ("Use your shell tool to create the new file " + proof.name
                  + " in the current workspace. Its entire contents must be the private test word "
                    "I asked you to remember in the previous turn, followed by exactly one newline. "
                    "Do not overwrite an existing file. Read the file back using a tool to verify it. "
                    f"End your final answer with this exact standalone line: {expected_second}.")
        self.report["prompt_bytes"] = [len(first.encode()), len(second.encode())]
        self.report["prompt_sha256"] = [hashlib.sha256(text.encode()).hexdigest() for text in (first, second)]
        try:
            before = 0
            if self.existing_thread:
                self.progress("continuing the explicitly selected BB thread")
                self.verify_destination()
                before = max((row["seq"] for row in self.events()), default=0)
                self.command("thread", "tell", self.thread_id, first, "--mode", "auto",
                             "--model", self.model, "--json")
                self.report["reused_thread"] = True
            else:
                self.progress("spawning exact GC agent through BB")
                environment_args = [] if self.personal_conversation else ["--environment", str(self.workspace)]
                spawned = self.command("thread", "spawn", "--project", self.project,
                                       "--host", self.host, "--provider", "gas-city", "--model", self.model,
                                       *environment_args, "--permission-mode", "full",
                                       "--reasoning-level", "none", "--service-tier", "default",
                                       "--prompt", first, "--json")
                self.thread_id = spawned.get("id")
                if not self.thread_id:
                    raise AcceptanceFailure("BB spawn returned no thread ID")
            self.report["thread_id"] = self.thread_id
            self.verify_destination()
            after, provider_id = self.await_turn(after=before, expected=expected_first)
            self.verify_gc_prompt(first, provider_id)
            self.report["assertions"].append("multiline-first-turn-markers-and-completion")
            self.progress("first turn passed; sending second turn with a real tool artifact")
            self.command("thread", "tell", self.thread_id, second, "--mode", "auto",
                         "--model", self.model, "--json")
            self.await_turn(after=after, expected=expected_second, require_tool=True,
                            previous_provider_id=provider_id)
            self.verify_gc_prompt(second, provider_id)
            if proof.is_symlink() or not proof.is_file() or proof.read_bytes() != expected_bytes:
                raise AcceptanceFailure("Tool artifact missing or contents do not prove first-turn memory")
            self.report["assertions"].extend(["same-session-second-turn-completion", "bb-tool-event",
                                              "tool-artifact-exact-bytes-and-conversation-memory"])
            self.report["artifact_sha256"] = hashlib.sha256(expected_bytes).hexdigest()
            if self.exercise_resume:
                self.verify_agent_resume(provider_id, memory, nonce)
            self.report["status"] = "passed"
            self.progress("real turns, retained context, tool artifact, and requested lifecycle checks passed")
            return self.report
        except Exception as error:
            self.report["status"] = "failed"
            # External command output is intentionally confined to private/.
            self.report["failure"] = str(error) if isinstance(error, AcceptanceFailure) else type(error).__name__
            raise
        finally:
            with (self.artifacts / "report.json").open("x") as stream:
                json.dump(self.report, stream, indent=2)
                stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bb-bin", default="bb")
    parser.add_argument("--existing-thread-id", help="Run fresh turns in this explicitly selected BB thread; preserves existing history and services")
    parser.add_argument("--exercise-resume", action="store_true", help="After two verified turns, suspend only this test agent and require a third turn with the same provider conversation and memory")
    for name in ("host", "project", "model", "workspace", "artifacts"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--timeout", type=int, default=240, help="Per-turn completion deadline in seconds")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    try:
        LiveAssertions(**vars(args)).run()
    except Exception as error:
        message = str(error) if isinstance(error, AcceptanceFailure) else type(error).__name__
        print(f"BB live acceptance failed: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
