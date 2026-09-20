"""Real provider/startup failures and a real HTTP deadline through the BB UI.

Only additive, owned runtime fixtures receive invalid credentials or an exiting
executable. The timeout holds a real accepted GC response. Nothing fabricates
an assistant reply, retries a prompt, or changes an existing provider.
"""
import base64
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import sys
import time
import tomllib
import urllib.parse

from full_e2e_browser_cases import permission_provider, read_json, save_json
from full_e2e_fault_cases import FaultCases, require_owned_config
from full_e2e_interaction_cases import events
from live_assertions import AcceptanceFailure, verify_prompt_frame
from runtime_artifact import verified_runtime_artifact


ERROR_PATTERNS = {
    "provider": r"incorrect.{0,20}api.{0,10}key|invalid.{0,20}(api.{0,10}key|token)|(?:access\s+)?token\s+is\s+invalid|authentication|unauthorized|refresh token.{0,30}(revoked|expired)",
    "startup": r"create failed|startup|exited|exit status|session is closed",
    "timeout": r"timeout|timed out|deadline exceeded",
}


def require_bb_failure(rows, *, mode, model):
    """An expected error must belong to one request and cannot coexist with success."""
    if mode not in ERROR_PATTERNS:
        raise AcceptanceFailure("Unknown real error case")
    if any(row.get("type") == "provider/modelFallback" or
           (row.get("type") == "turn/completed" and row.get("data", {}).get("status") == "completed")
           for row in rows):
        raise AcceptanceFailure("Error case unexpectedly produced a successful completion or fallback")
    failures = [row for row in rows if row.get("type") in {"system/error", "client/turn/rejected"}
                or row.get("type") == "turn/completed" and row.get("data", {}).get("status") == "failed"]
    if not failures:
        return None
    requests = [row for row in rows if row.get("type") == "client/turn/requested"]
    if len(requests) != 1 or not requests[0].get("data", {}).get("requestId"):
        raise AcceptanceFailure("Error case requires exactly one BB input request")
    request = requests[0]["data"]
    if request.get("execution", {}).get("model") != model:
        raise AcceptanceFailure("Error case did not use the selected agent")
    for failure in failures:
        data = failure.get("data") or {}
        error = data.get("error") or {}
        for text in (error.get("message"), data.get("detail"), data.get("message")):
            if isinstance(text, str) and re.search(ERROR_PATTERNS[mode], text, re.I):
                return {"expected_error": text, "event": failure, "request_id": request["requestId"]}
    raise AcceptanceFailure(f"BB did not report the required {mode} error; inspect private evidence")


def require_error_delivery(mode, records, receipt, frame, prompt):
    """Independently count GC mutations and prove whether input reached native history."""
    creates = sum(row.get("operation") == "create" for row in records)
    submits = sum(row.get("operation") == "submit" for row in records)
    if creates != 1 or submits > 1:
        raise AcceptanceFailure("GC creation or prompt delivery occurred more than once")
    if mode != "provider" and (submits or receipt.get("turn")):
        raise AcceptanceFailure("The error case sent input before readiness was established")
    proof = {"create_requests": creates, "submit_requests": submits}
    messages = (frame or {}).get("structured_messages", [])
    if submits:
        if not receipt.get("turn") or not frame:
            raise AcceptanceFailure("Submitted error case lacks its durable receipt and native history")
        proof.update(verify_prompt_frame(frame, receipt["turn"], prompt))
        index = next(i for i, message in enumerate(messages) if message.get("id") == proof["gc_user_message_id"])
        messages = messages[index + 1:]
    elif any(prompt in str(message.get("user_prompt", {}).get("text", ""))
             or any(prompt in block.get("text", "") for block in message.get("blocks", []))
             for message in messages if message.get("role") == "user"):
        raise AcceptanceFailure("An unsent error-case prompt appeared in GC native history")
    if mode == "provider":
        if not frame or frame.get("history", {}).get("tail_state", {}).get("degraded"):
            raise AcceptanceFailure("Provider failure lacks reliable native history")
        errors = [message for message in messages if message.get("role") == "system"
                  and message.get("status") == "final"
                  and message.get("system_event", {}).get("kind") == "error"
                  and message.get("system_event", {}).get("category") == "provider_error"
                  and re.search(ERROR_PATTERNS["provider"], message.get("system_event", {}).get("message", ""), re.I)]
        if not errors:
            raise AcceptanceFailure("BB error has no corresponding native provider error")
        if any(message.get("role") == "assistant" and message.get("status") == "final" for message in messages):
            raise AcceptanceFailure("Provider error case unexpectedly has a successful native answer")
        proof["native_error_ids"] = [message["id"] for message in errors]
    return proof


def error_fixture(runner, mode):
    if hasattr(runner, "prepared_error_fixtures"):
        from full_e2e_fixture_catalog import error_fixture as prepared_error_fixture
        return prepared_error_fixture(runner, mode)
    return create_error_fixture(runner, mode)


def create_error_fixture(runner, mode):
    """Install one additive fixture, without reading or changing real credentials."""
    require_owned_config(runner)
    if mode not in {"provider", "startup"} or runner.runtime not in {"claude", "codex"}:
        raise AcceptanceFailure("Unknown runtime failure fixture")
    artifact = verified_runtime_artifact(runner)
    binary = artifact["path"]
    name = f"e2e-{runner.runtime}-{mode}-" + secrets.token_hex(5)
    city = (runner.root / "city").resolve(strict=True)
    if not city.is_relative_to(runner.root):
        raise AcceptanceFailure("Error fixture city escaped the isolated installation")
    city_config = city / "city.toml"
    original = city_config.read_bytes()
    parsed = tomllib.loads(original.decode())
    location = runner.root / "error-fixtures" / name
    location.mkdir(mode=0o700, parents=True, exist_ok=False)
    workspace, runtime_config = location / "workspace", location / "runtime-config"
    workspace.mkdir(mode=0o700); runtime_config.mkdir(mode=0o700)
    invalid = "sk-bb-e2e-intentionally-invalid-" + secrets.token_hex(16)
    key = "CODEX_HOME" if runner.runtime == "codex" else "CLAUDE_CONFIG_DIR"
    if runner.runtime == "codex":
        from codex_hook_trust import trust_config
        save_json(runtime_config / "auth.json", {"OPENAI_API_KEY": invalid})
        with (runtime_config / "config.toml").open("x") as stream:
            stream.write('cli_auth_credentials_store = "file"\n')
            stream.write(f'[projects.{json.dumps(str(workspace))}]\ntrust_level = "trusted"\n')
            stream.write(trust_config([workspace], runner.manifest["versions"]["codex"]))
    else:
        save_json(runtime_config / ".claude.json", {"hasCompletedOnboarding": True, "theme": "dark",
            "projects": {str(workspace): {"hasTrustDialogAccepted": True,
                "hasCompletedProjectOnboarding": True, "projectOnboardingSeenCount": 1}}})
        invalid = "sk-ant-oat01-bb-e2e-intentionally-invalid-" + secrets.token_hex(16)
    wrapper = location / "runtime"
    script = location / "launch.py"
    log = location / "launches.jsonl"
    # The program owns its new append-only launch log. No history or credentials
    # are copied from a live runtime; API authentication is deliberately invalid.
    code = f'''import hashlib, json, os, sys, time
from pathlib import Path
if hashlib.sha256(Path({binary!r}).read_bytes()).hexdigest() != {artifact["sha256"]!r}:
    raise SystemExit("Pinned raw runtime changed before launch")
with Path({str(log)!r}).open("a") as stream:
    stream.write(json.dumps({{"pid": os.getpid(), "started_at": time.time(), "mode": {mode!r}, "runtimeArtifact": {artifact!r}}}) + "\\n")
if {mode!r} == "startup":
    print("E2E deliberate runtime startup exit 73", file=sys.stderr, flush=True)
    sys.exit(73)
for key in list(os.environ):
    if key.startswith(("ANTHROPIC_", "OPENAI_", "CODEX_AUTH_", "MANIFOLD_")) or key in ("CLAUDE_CODE_OAUTH_TOKEN", "CODEX_API_KEY"):
        os.environ.pop(key)
os.environ[{key!r}] = {str(runtime_config)!r}
os.environ[{("OPENAI_API_KEY" if runner.runtime == "codex" else "CLAUDE_CODE_OAUTH_TOKEN")!r}] = {invalid!r}
'''
    if runner.runtime == "codex":
        code += f'''sys.path.insert(0, {str(Path(__file__).resolve().parent)!r})
from codex_hook_trust import verify_launch
verify_launch(Path.cwd(), {str(runtime_config)!r}, [{str(workspace)!r}], os.environ)
'''
    code += f'os.execv({binary!r}, [{binary!r}, *sys.argv[1:]])\n'
    with script.open("x") as stream: stream.write(code)
    script.chmod(0o600)
    with wrapper.open("x") as stream:
        stream.write("#!/bin/sh\nexec " + shlex.join([sys.executable, str(script)]) + ' "$@"\n')
    wrapper.chmod(0o700)
    declaration = permission_provider(runner.runtime, name, str(wrapper), environment={key: str(runtime_config)})
    agent_dir = location / "agent"
    agent_dir.mkdir(mode=0o700, exist_ok=False)
    shutil.copyfile(Path(__file__).with_name("conversation-agent-prompt.md"), agent_dir / "prompt.md")
    with (agent_dir / "agent.toml").open("x") as stream:
        stream.write(f'name = {json.dumps(name)}\nprovider = {json.dumps(name)}\nwork_dir = {json.dumps(str(workspace))}\n'
                     'min_active_sessions = 0\nmax_active_sessions = 3\n')
    observe = parsed.get("daemon", {}).get("observe_paths", [])
    replacement = "observe_paths = " + json.dumps([*observe, str(runtime_config / "projects"), str(runtime_config / "sessions")])
    updated, count = re.subn(r"(?m)^observe_paths\s*=\s*\[[^\n]*\]\s*$", replacement, original.decode())
    if count != 1:
        raise AcceptanceFailure("Error fixture requires an explicit one-line observe_paths setting")
    updated += "\n" + declaration
    tomllib.loads(updated)
    with (runner.private / (name + "-city-before.toml")).open("xb") as stream: stream.write(original)
    if city_config.read_bytes() != original:
        raise AcceptanceFailure("City config changed concurrently; error fixture was not activated")
    pending = city / ("." + name + ".toml")
    with pending.open("x") as stream: stream.write(updated)
    os.replace(pending, city_config)
    # Publish the agent only once its provider exists, so observing between the
    # two writes cannot invalidate the city's previously valid agent catalog.
    os.rename(agent_dir, city / "agents" / name)
    original_agent = runner.agent("global")
    waiter = FaultCases(runner)
    waiter.poll("new error fixture", lambda: any(row.get("name") == name for row in
        read_json(runner.manifest["gcUrl"] + f"/v0/city/{original_agent['city']}/config").get("agents", [])))
    runner.bb("plugin", "reload", "gas-city", "--json")
    target = {"v": 1, "connection": original_agent["connection"], "city": original_agent["city"], "agent": name}
    encoded = base64.urlsafe_b64encode(json.dumps(target, separators=(",", ":")).encode()).decode().rstrip("=")
    fixture = {"agent": {**target, "id": "gc1_" + encoded, "reasoningLevels": ["none"]},
               "workspace": str(workspace), "launchLog": str(log), "runtimeConfig": str(runtime_config),
               "runtimeArtifact": artifact}
    save_json(runner.private / (name + "-fixture.json"), fixture)
    return fixture


def error_case(runner, mode):
    label = "error." + mode
    cases = FaultCases(runner)
    fixture = None
    if mode != "timeout":
        fixture = error_fixture(runner, mode)
        cases.agent, cases.workspace = fixture["agent"], fixture["workspace"]
    prompt = "Do not use tools. Reply exactly ERROR_CASE_UNEXPECTED_SUCCESS_" + secrets.token_hex(12)
    with cases.routed(label) as (proxy, artifacts):
        ticket = proxy.arm("create", path=cases.city_path + "/sessions", hold=True) if mode == "timeout" else None
        started_at = time.monotonic()
        started = cases.start(label + "-submitted", prompt)
        held = ticket.wait_accepted(runner.timeout) if ticket else None
        try:
            def failed():
                rows = events(runner, started["threadId"], started["afterSeq"])
                return require_bb_failure(rows, mode=mode, model=cases.agent["id"])
            failure = cases.poll(label + " expected BB failure", failed)
            visible = cases.browser_failure(label + "-visible", started, failure["expected_error"])
        finally:
            if ticket: ticket.release()
        elapsed = time.monotonic() - started_at
        if ticket:
            fault = ticket.wait(runner.timeout)
            if (not held.get("accepted") or fault.get("fault") != "accepted-response-drop"
                    or fault.get("finished_at", 0) - fault["started_at"] < 19):
                raise AcceptanceFailure("Timeout did not wait for the real 20-second HTTP deadline")
            save_json(artifacts / "held-response.json", {"held": held, "fault": fault, "elapsed_seconds": elapsed})
        value = cases.poll(label + " durable receipt", lambda: cases.receipt(started["threadId"]))
        frame = None
        remote = cases.remote_session(value)
        if remote:
            frame = cases.read_gc(cases.city_path + "/session/" + urllib.parse.quote(remote["id"], safe="") + "/transcript?format=structured")
        if mode == "startup":
            launches = [json.loads(line) for line in Path(fixture["launchLog"]).read_text().splitlines()]
            if not launches or any(row.get("mode") != "startup" for row in launches):
                raise AcceptanceFailure("Startup failure lacks evidence that its exiting process was launched")
            save_json(artifacts / "runtime-launches.json", launches)
        proof = require_error_delivery(mode, proxy.records(), value, frame, prompt)
        # Re-read after native evidence so a delayed successful terminal cannot
        # pass merely because the first error event reached the UI sooner.
        final_rows = events(runner, started["threadId"], started["afterSeq"])
        require_bb_failure(final_rows, mode=mode, model=cases.agent["id"])
        save_json(artifacts / "verified-error.json", {"receipt": value, "frame": frame, "remote": remote,
            "bb_events": final_rows, "request_records": proxy.records(), "proof": proof})
        return {**proof, "thread_id": started["threadId"], "visible_error_seq": visible["rejection"]["seq"],
                "no_automatic_retry": True, "elapsed_seconds": elapsed}


def case_functions(runner):
    return {"error." + mode: (lambda mode=mode: error_case(runner, mode))
            for mode in ("provider", "startup", "timeout")}
