"""Additional real-browser cases. All fixtures are additive and task-owned.

No fixture fabricates a provider reply or grants approval through a side API.
The browser chooses each answer; GC's independent pending interaction and
filesystem artifacts establish whether the permission gate actually worked.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import time
import tomllib
import urllib.request

from live_assertions import AcceptanceFailure, verify_prompt_frame, verify_resume_identity
from native_claude_acceptance import prepare_native_claude, native_memory_provenance
from runtime_artifact import runtime_artifact

HERE = Path(__file__).resolve().parent


def read_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=20) as response:
        return json.load(response)


def save_json(path, value):
    with Path(path).open("x") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, indent=2)
        stream.write("\n")


def permission_provider(runtime, name, binary, *, defaults=None, environment=None):
    if runtime not in {"claude", "codex"} or not re.fullmatch(r"[a-z][a-z0-9-]+", name):
        raise AcceptanceFailure("Invalid permission fixture runtime/name")
    values = dict(defaults or {})
    values["permission_mode"] = "auto-edit" if runtime == "claude" else "suggest"
    text = (f'[providers.{name}]\nbase = "builtin:{runtime}"\n'
            f'command = {json.dumps(binary)}\nready_delay_ms = 0\n'
            f'resume_command = {json.dumps(shlex.quote(binary) + (" --resume {{.SessionKey}}" if runtime == "claude" else " resume {{.SessionKey}}"))}\n')
    if runtime == "claude":
        text += 'session_id_flag = "--session-id"\n'
    text += 'options_schema_merge = "by_key"\n'
    permission = "auto-edit" if runtime == "claude" else "suggest"
    flags = ["--permission-mode", "manual"] if runtime == "claude" else ["--ask-for-approval", "on-request", "--sandbox", "read-only"]
    text += (f'[providers.{name}.permission_modes]\n'
             f'{permission} = {json.dumps(" ".join(flags))}\n')
    text += f'[providers.{name}.option_defaults]\n'
    text += ''.join(f'{json.dumps(key)} = {json.dumps(value)}\n' for key, value in values.items())
    if environment:
        text += f'[providers.{name}.env]\n'
        text += ''.join(f'{json.dumps(key)} = {json.dumps(value)}\n' for key, value in environment.items())
    text += (f'[[providers.{name}.options_schema]]\nkey = "permission_mode"\nlabel = "Permissions"\n'
             f'type = "select"\ndefault = {json.dumps(permission)}\n'
             f'[[providers.{name}.options_schema.choices]]\nvalue = {json.dumps(permission)}\nlabel = "Manual approval"\n'
             f'flag_args = {json.dumps(flags)}\n')
    return text


def require_pending_gate(interactions, native_pending, proof, *, expected_bytes=None):
    proof = Path(proof)
    if expected_bytes is None:
        if proof.exists(): raise AcceptanceFailure("The command ran before explicit approval")
    elif not proof.is_file() or proof.read_bytes() != expected_bytes:
        raise AcceptanceFailure("The repeated command ran before its new approval")
    pending = native_pending.get("pending") or {}
    if (native_pending.get("supported") is not True or pending.get("kind") != "approval"
            or pending.get("metadata", {}).get("source") != "tmux"):
        raise AcceptanceFailure("GC has no supported native approval interaction")
    candidates = []
    for interaction in interactions:
        if interaction.get("status") not in (None, "pending"): continue
        payload = interaction.get("payload") or {}
        if payload.get("kind") != "user_question": continue
        questions = payload.get("questions") or []
        if (len(questions) == 1 and questions[0].get("id") == pending.get("request_id")
                and {option.get("value") for option in questions[0].get("options", [])} == {"approve", "deny"}):
            candidates.append(interaction)
    if len(candidates) != 1:
        raise AcceptanceFailure("BB has no unique approval question matching GC's pending request")
    return candidates[0]


def require_native_denial(frame, turn, prompt, command, bb_tool):
    evidence = verify_prompt_frame(frame, turn, prompt)
    messages = frame['structured_messages']
    index = next(index for index, message in enumerate(messages)
                 if message.get('id') == evidence['gc_user_message_id'])
    following = [message for message in messages[index + 1:] if message.get('status') != 'superseded']
    if any((message.get('system_event') or {}).get('category') in {'provider_error', 'provider_retry'} for message in following):
        raise AcceptanceFailure('A provider failure cannot satisfy native permission denial')
    blocks = [block for message in following for block in message.get('blocks', [])]
    calls = [block for block in blocks if block.get('type') == 'tool_use']
    results = [block for block in blocks if block.get('type') == 'tool_result']
    if (len(calls) != 1 or not calls[0].get('id') or calls[0].get('input', {}).get('command') != command
            or bb_tool.get('arguments', {}).get('command') != command):
        raise AcceptanceFailure('Denial must identify one exact native command without a retry')
    if len(results) != 1 or results[0].get('tool_call_id') != calls[0]['id'] or results[0].get('is_error') is not True:
        raise AcceptanceFailure('Native denial lacks the matching rejected tool result')
    category = (results[0].get('structured') or {}).get('error', {}).get('category')
    if (category not in {'user_rejection', 'user_rejection_with_reason'}
            or bb_tool.get('result', {}).get('error', {}).get('category') != category):
        raise AcceptanceFailure('BB and GC must agree that the tool was rejected by the user')
    return {**evidence, 'gc_tool_call_id': calls[0]['id'], 'tool_error_category': category}


def require_empty_native_fixture(fixture):
    native = fixture.get("nativeConfiguration")
    if not native:
        return
    root = Path(native["homeRoot"])
    if root.is_symlink() or root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise AcceptanceFailure("Native fixture already has runtime homes; fresh trust is not established")


def native_fixture_evidence(runner, fixture, thread, label, frame):
    native = fixture.get("nativeConfiguration")
    if not native:
        return None
    config_path = Path(native["path"])
    if hashlib.sha256(config_path.read_bytes()).hexdigest() != native["sha256"]:
        raise AcceptanceFailure("Native fixture launch configuration changed")
    home_root = Path(native["homeRoot"])
    if home_root.is_symlink() or not home_root.resolve().is_relative_to(runner.root):
        raise AcceptanceFailure("Native fixture runtime home escaped the owned installation")
    homes = list(home_root.iterdir()) if home_root.is_dir() else []
    if len(homes) != 1 or homes[0].is_symlink() or not homes[0].is_dir():
        raise AcceptanceFailure("Native fixture does not identify one actual private runtime home")
    home = homes[0]
    settings = home / ".claude.json"
    if settings.is_symlink() or not settings.is_file():
        raise AcceptanceFailure("Native fixture lacks its actual private onboarding state")
    projects = json.loads(settings.read_text()).get("projects", {})
    session_root = Path(native["sessionRoot"]).resolve(strict=True)
    if not session_root.is_relative_to(runner.root):
        raise AcceptanceFailure("Native fixture observation root escaped the owned installation")
    if (home / "projects").resolve(strict=True) != session_root:
        raise AcceptanceFailure("Native fixture transcripts are not in the configured observation root")
    provider_id = (frame.get("history") or {}).get("provider_session_id")
    if not isinstance(provider_id, str) or not re.fullmatch(r"[A-Za-z0-9-]+", provider_id):
        raise AcceptanceFailure("Native fixture lacks a provider conversation identity")
    transcripts = list(session_root.rglob(provider_id + ".jsonl"))
    if len(transcripts) != 1 or not transcripts[0].is_file() or not transcripts[0].resolve().is_relative_to(session_root):
        raise AcceptanceFailure("Native fixture lacks its exact observed provider transcript")
    evidence = {"threadId": thread, "home": str(home), "projects": projects,
                "workspaceProjectState": projects.get(fixture["workspace"]),
                "transcript": str(transcripts[0]), "providerSessionId": provider_id,
                "homeRootInitiallyEmpty": True, "trustPreseeded": False}
    save_json(runner.private / (label + "-native-runtime.json"), evidence)
    return evidence


def fixture(runner, *, trusted=True, configured_mayor=False):
    if hasattr(runner, "prepared_browser_fixtures"):
        from full_e2e_fixture_catalog import browser_fixture
        return browser_fixture(runner, (trusted, configured_mayor))
    return create_fixture(runner, trusted=trusted, configured_mayor=configured_mayor)


def create_fixture(runner, *, trusted=True, configured_mayor=False):
    """Build a new role/config without modifying any existing agent or credentials."""
    label = ("mayor" if configured_mayor else "permissions" if trusted else "fresh-trust") + "-" + secrets.token_hex(5)
    name = "e2e-" + runner.runtime + "-" + label
    city = (runner.root / "city").resolve(strict=True)
    if not city.is_relative_to(runner.root): raise AcceptanceFailure("City escaped owned scratch root")
    city_config = city / "city.toml"
    original = city_config.read_bytes()
    parsed = tomllib.loads(original.decode())
    original_agent = runner.agent("global")
    source_provider = parsed.get("providers", {}).get(original_agent.get("provider", runner.runtime), {})
    provider_env = dict(source_provider.get("env") or {})
    source_agent_file = city / "agents" / original_agent["agent"] / "agent.toml"
    if source_agent_file.is_file(): provider_env.update(tomllib.loads(source_agent_file.read_text()).get("env") or {})
    key = "CLAUDE_CONFIG_DIR" if runner.runtime == "claude" else "CODEX_HOME"
    source_config = Path(provider_env.get(key) or runner.env[key]).resolve(strict=True)
    if not source_config.is_relative_to(runner.root): raise AcceptanceFailure("Runtime credentials are not owned by this test installation")
    location = runner.root / "browser-fixtures" / name
    location.mkdir(mode=0o700, parents=True, exist_ok=False)
    workspace, runtime_config = location / "workspace_with_underscores", location / "runtime-config"
    workspace.mkdir(mode=0o700); runtime_config.mkdir(mode=0o700)
    native_source = (provider_env.get("MANIFOLD_CLAUDE_LAUNCH_CONFIG") or runner.env.get("MANIFOLD_CLAUDE_LAUNCH_CONFIG")) if runner.runtime == "claude" else None
    native = None
    if native_source:
        source = Path(native_source).resolve(strict=True)
        if not source.is_relative_to(runner.root):
            raise AcceptanceFailure("Native fixture source configuration escapes the test installation")
        launch = prepare_native_claude(location, source)
        launch_config = json.loads(launch.read_text())
        native = {"path": str(launch), "homeRoot": launch_config["home_root"],
                  "sessionRoot": launch_config["session_root"],
                  "memoryIsolation": native_memory_provenance(launch),
                  "sha256": hashlib.sha256(launch.read_bytes()).hexdigest()}
        require_empty_native_fixture({"nativeConfiguration": native})
        provider_env["MANIFOLD_CLAUDE_LAUNCH_CONFIG"] = str(launch)
        provider_env.pop(key, None)
    # Copy only runtime settings/credentials, never existing sessions or histories.
    for filename in (() if native else ("auth.json", "config.toml", ".claude.json", "settings.json", ".credentials.json")):
        source = source_config / filename
        if source.is_file() and not (not trusted and filename == "config.toml"):
            if not source.resolve().is_relative_to(runner.root): raise AcceptanceFailure("Runtime setting symlink escaped scratch")
            shutil.copyfile(source, runtime_config / filename)
            (runtime_config / filename).chmod(0o600)
    if runner.runtime == "claude" and not native:
        settings_path = runtime_config / ".claude.json"
        settings = json.loads(settings_path.read_text()) if settings_path.exists() else {}
        settings.update(hasCompletedOnboarding=True, theme="dark")
        settings.setdefault("projects", {})[str(workspace)] = {
            "hasTrustDialogAccepted": trusted, "hasCompletedProjectOnboarding": trusted,
            "projectOnboardingSeenCount": int(trusted)}
        # This is the new private copy; its original remains in source_config.
        settings_path.write_text(json.dumps(settings) + "\n"); settings_path.chmod(0o600)
    elif runner.runtime == "codex" and trusted:
        from codex_hook_trust import trust_config
        with (runtime_config / "config.toml").open("a") as stream:
            stream.write(f'\n[projects.{json.dumps(str(workspace))}]\ntrust_level = "trusted"\n')
            stream.write(trust_config([workspace], runner.manifest["versions"]["codex"]))
    binary = shutil.which(runner.runtime, path=runner.env["PATH"])
    if not binary: raise AcceptanceFailure("The selected runtime executable is unavailable")
    if runner.command(binary, "--version").strip() != runner.manifest["versions"][runner.runtime]:
        raise AcceptanceFailure("Permission fixture runtime differs from the artifact under test")
    if runner.runtime == "codex":
        from codex_hook_trust import write_provider_commands
        write_provider_commands(location, binary, runtime_config, [workspace])
        binary = str(location / "codex-verified")
    elif source_provider.get("command"):
        # A prepared Claude provider may load authorized API credentials from
        # its private wrapper. Keep that source rather than falling back to
        # stale ambient OAuth. Its workspace-specific config remains this copy.
        wrapper = Path(source_provider["command"]).resolve(strict=True)
        if not wrapper.is_file():
            raise AcceptanceFailure("Claude credential wrapper is not a regular file")
        if not wrapper.is_relative_to(runner.root):
            artifact = runtime_artifact(wrapper, runner.manifest["versions"][runner.runtime], runner.command)
            if artifact != runner.manifest.get("runtimeLaunchArtifact"):
                raise AcceptanceFailure("External Claude credential wrapper differs from the pinned launch artifact")
        binary = str(wrapper)
    if not native:
        provider_env[key] = str(runtime_config)
    declaration = permission_provider(runner.runtime, name, binary,
        defaults=source_provider.get("option_defaults"), environment=provider_env)
    if configured_mayor:
        declaration = (f'[providers.{name}]\nbase = "builtin:{runner.runtime}"\n'
            f'command = {json.dumps(binary)}\n'
            f'resume_command = {json.dumps(shlex.quote(binary) + (" --resume {{.SessionKey}}" if runner.runtime == "claude" else " resume {{.SessionKey}}"))}\n'
            + ('session_id_flag = "--session-id"\n' if runner.runtime == "claude" else '') +
            f'[providers.{name}.env]\n' + ''.join(f'{json.dumps(k)} = {json.dumps(v)}\n' for k,v in provider_env.items()))
    agent_dir = city / "agents" / name
    agent_dir.mkdir(mode=0o700, exist_ok=False)
    if configured_mayor:
        role = HERE.parents[1] / 'gastown/agents/mayor'
        fragments = HERE.parents[1] / 'gastown/template-fragments'
        # These are the actual shipped role instructions and template definitions,
        # evaluated by GC with this scratch city's paths. No user city is copied.
        prompt = ''.join(path.read_text() + '\n' for path in sorted(fragments.glob('*.template.md')))
        prompt += (role / 'prompt.template.md').read_text()
        (agent_dir / 'prompt.template.md').write_text(prompt)
        template = (role / 'agent.toml').read_text()
        template = re.sub(r'(?m)^work_dir\s*=.*$', 'work_dir = ' + json.dumps(str(workspace)), template)
        (agent_dir / 'agent.toml').write_text(template + f'\nname = {json.dumps(name)}\nprovider = {json.dumps(name)}\nmin_active_sessions = 0\n')
    else:
        shutil.copyfile(HERE / "conversation-agent-prompt.md", agent_dir / "prompt.md")
        (agent_dir / "agent.toml").write_text(
            f'name = {json.dumps(name)}\nprovider = {json.dumps(name)}\nwork_dir = {json.dumps(str(workspace))}\n'
            'min_active_sessions = 0\nmax_active_sessions = 3\n')
    # Add observe paths while retaining every previous path; the running GC
    # controller adopts config changes without starting another supervisor.
    observe = parsed.get("daemon", {}).get("observe_paths", [])
    fixture_observe = [native["sessionRoot"]] if native else [str(runtime_config / "projects"), str(runtime_config / "sessions")]
    replacement = "observe_paths = " + json.dumps([*observe, *fixture_observe])
    updated, count = re.subn(r"(?m)^observe_paths\s*=\s*\[[^\n]*\]\s*$", replacement, original.decode())
    if count != 1: raise AcceptanceFailure("Fixture requires the existing explicit one-line observe_paths setting")
    updated += "\n" + declaration
    tomllib.loads(updated)  # Reject invalid additions before touching config.
    backup = runner.private / (name + "-city-before.toml")
    with backup.open("xb") as stream: stream.write(original)
    if city_config.read_bytes() != original: raise AcceptanceFailure("City config changed concurrently; fixture was not activated")
    pending = city / ("." + name + ".toml")
    with pending.open("x") as stream: stream.write(updated)
    os.replace(pending, city_config)
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        config = read_json(runner.manifest["gcUrl"] + f"/v0/city/{original_agent['city']}/config")
        if any(row.get("name") == name for row in config.get("agents", [])): break
        time.sleep(0.5)
    else: raise AcceptanceFailure("GC did not discover the additive browser fixture")
    runner.bb("plugin", "reload", "gas-city", "--json")
    target = {"v": 1, "connection": original_agent["connection"], "city": original_agent["city"], "agent": name}
    encoded = base64.urlsafe_b64encode(json.dumps(target, separators=(",", ":")).encode()).decode().rstrip("=")
    row = {"agent": {**target, "id": "gc1_" + encoded, "reasoningLevels": ["none"]},
           "workspace": str(workspace), "project": "proj_personal", "reasoning": "none", "trusted": trusted if not native else False,
           "nativeConfiguration": native}
    save_json(runner.private / (name + "-fixture.json"), {**row, "runtimeConfig": str(runtime_config) if not native else None, "sourceConfig": str(source_config),
        "originalCitySha256": hashlib.sha256(original).hexdigest()})
    return row


def receipt(runner, thread):
    return json.loads((Path(runner.env["XDG_STATE_HOME"]) / "gascity/bb/sessions" /
        (hashlib.sha256(thread.encode()).hexdigest() + ".json")).read_text())


def gc_frame(runner, value):
    return read_json(runner.manifest["gcUrl"] + f"/v0/city/{value['target']['city']}/session/{value['sessionId']}/transcript?format=structured")


def await_gate(runner, thread, proof, label, *, expected_bytes=None):
    deadline, last_log = time.monotonic() + runner.timeout, 0
    last = {}
    while time.monotonic() < deadline:
        if expected_bytes is None and Path(proof).exists(): raise AcceptanceFailure("Tool executed without a BB approval")
        if expected_bytes is not None and (not Path(proof).is_file() or Path(proof).read_bytes() != expected_bytes):
            raise AcceptanceFailure("Repeated tool executed before a fresh approval")
        pending = read_json(runner.manifest["bbUrl"] + f"/api/v1/threads/{thread}/interactions")
        if pending:
            value = receipt(runner, thread)
            frame = gc_frame(runner, value)
            native_pending = read_json(runner.manifest["gcUrl"] +
                f"/v0/city/{value['target']['city']}/session/{value['sessionId']}/pending")
            last = {"bb": pending, "gc": frame, "native_pending": native_pending, "receipt": value}
            try:
                gate = require_pending_gate(pending, native_pending, proof, expected_bytes=expected_bytes)
            except AcceptanceFailure as error:
                # BB and GC publish independently; neither observation alone
                # establishes that the same approval is ready on both sides.
                last["correlation_error"] = str(error)
            else:
                save_json(runner.private / (label + "-pending.json"), last)
                return gate
        state = read_json(runner.manifest["bbUrl"] + f"/api/v1/threads/{thread}")
        if state.get("status") == "error":
            # A failed startup cannot produce this turn's permission question.
            # Preserve the actual error and any independent native gate instead
            # of turning it into a misleading, empty timeout report.
            last.update(thread=state, bb=pending, events=read_json(runner.manifest["bbUrl"] +
                f"/api/v1/threads/{thread}/events?limit=100&order=desc"))
            try:
                value = receipt(runner, thread)
            except FileNotFoundError:
                last["receipt_missing"] = True
            else:
                last.update(receipt=value, gc=gc_frame(runner, value),
                    native_pending=read_json(runner.manifest["gcUrl"] +
                        f"/v0/city/{value['target']['city']}/session/{value['sessionId']}/pending"))
            save_json(runner.private / (label + "-pending-failed.json"), last)
            raise AcceptanceFailure("BB turn failed before a real permission interaction; see pending-failed evidence")
        if time.monotonic() - last_log > 15:
            runner.progress(f"{label}: waiting for the real permission interaction; command has not run")
            last_log = time.monotonic()
        time.sleep(0.5)
    save_json(runner.private / (label + "-pending-timeout.json"), last)
    raise AcceptanceFailure("No real BB permission interaction appeared before timeout")


def provider_switch(runner):
    agent, workspace = runner.agent("global"), runner.manifest["workspaces"]["global"]
    marker = "PROVIDER_SWITCH_" + secrets.token_hex(6)
    prompt = f"Without tools, reply with exactly {marker}."
    result = runner.browser("provider.switch", agent, "proj_personal", workspace, prompt,
        expected=marker, switch_from_provider="Claude Code" if runner.runtime == "codex" else "Codex")
    harness = runner.new_harness("provider.switch", agent, "proj_personal", workspace, result["threadId"])
    runner.verify_turn(harness, result, prompt, marker, no_tools=True)
    return {"thread_id": result["threadId"], "provider_selected_in_ui": "gas-city"}


def reasoning_immutable(runner):
    c = runner.conversations["native.personal"]
    level = next(level for level in c["agent"]["reasoningLevels"] if level != c["reasoning"])
    prompt = "REJECT_REASONING_" + secrets.token_hex(12)
    before = receipt(runner, c["harness"].thread_id)
    result = runner.browser("reasoning.immutable", c["agent"], c["project"], c["workspace"], prompt,
        thread=c["harness"].thread_id, reasoning=level, expected_error="reasoning is fixed at")
    after = receipt(runner, c["harness"].thread_id)
    if before != after: raise AcceptanceFailure("Rejected reasoning changed the durable GC receipt")
    frame = gc_frame(runner, after)
    if prompt in json.dumps(frame): raise AcceptanceFailure("Rejected reasoning prompt reached GC")
    save_json(runner.private / "reasoning.immutable-gc.json", frame)
    return {"thread_id": result["threadId"], "visible_rejection": True, "gc_receipt_unchanged": True}


def approval(runner, action, *, repeated=False):
    label = "approvals.repeated" if repeated else "approvals." + action
    f = fixture(runner)
    nonce = secrets.token_hex(8)
    proof = Path(f["workspace"]) / ("approval-" + nonce + ".txt")
    command = "python3 -c " + shlex.quote(f"from pathlib import Path; p=Path({str(proof)!r}); f=p.open('a'); f.write({(nonce + chr(10))!r}); f.close()")
    marker = "APPROVED_" + nonce
    prompt = (f"Remember the private word {nonce} for my next request. "
              "Use only your shell tool to run this exact command once. Do not use another tool or a workaround. "
              "If permission is denied, do not retry the command.\n" + command +
              (f"\nThen finish with exactly this standalone line: {marker}" if action == 'approve'
               else '\nIf I deny permission, stop and wait for my next message.'))
    started = runner.browser(label + "-start", f["agent"], f["project"], f["workspace"], prompt,
        reasoning="none", until="submitted")
    thread = started["threadId"]
    gate = await_gate(runner, thread, proof, label)
    if f.get("nativeConfiguration"):
        native_fixture_evidence(runner, f, thread, label, gc_frame(runner, receipt(runner, thread)))
    finished = runner.browser(label + "-answer", f["agent"], f["project"], f["workspace"],
        thread=thread, action=action, expected=marker if action == 'approve' else None,
        reasoning="none", after=started["afterSeq"])
    harness = runner.new_harness(label, f["agent"], f["project"], f["workspace"], thread)
    if action == "deny":
        return finish_denial(runner, f, started, finished, harness, gate, prompt, command, proof, nonce)
    _, identity = runner.verify_turn(harness, finished, prompt, marker, tool=True)
    expected = (nonce + "\n").encode()
    if proof.read_bytes() != expected: raise AcceptanceFailure("Approved command did not execute exactly once")
    if repeated:
        again = "Run that identical shell command one more time, with a new explicit approval if requested. Do not change the command.\n" + command + f"\nFinish with {marker}."
        start2 = runner.browser(label + "-repeat", f["agent"], f["project"], f["workspace"], again,
            thread=thread, reasoning="none", until="submitted")
        gate2 = await_gate(runner, thread, proof, label + "-repeat", expected_bytes=expected)
        if gate2["id"] == gate["id"]: raise AcceptanceFailure("Repeated approval reused the previous BB interaction")
        finish2 = runner.browser(label + "-answer2", f["agent"], f["project"], f["workspace"],
            thread=thread, action="approve", expected=marker, reasoning="none", after=start2["afterSeq"])
        runner.verify_turn(harness, finish2, again, marker, provider=identity, tool=True)
        if proof.read_bytes() != expected * 2: raise AcceptanceFailure("Repeated approved command did not execute exactly once more")
    evidence = {"thread_id": thread, "artifact_sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
                "artifact_path": str(proof), "workspace": f["workspace"], "explicit_approvals": 2 if repeated else 1}
    runner.underscore_evidence = evidence
    return evidence


def finish_denial(runner, f, started, finished, harness, gate, prompt, command, proof, nonce):
    from full_e2e_fault_cases import FaultCases
    thread, completed = started['threadId'], finished['completion']
    native_question = gate['payload']['questions'][0]['id']
    if completed['interactionId'] != gate['id'] or completed['nativeQuestionId'] != native_question:
        raise AcceptanceFailure('The visible denial answered another native approval')
    if proof.exists(): raise AcceptanceFailure('Denied tool command created its artifact')
    value = receipt(runner, thread)
    def settled():
        frame = gc_frame(runner, value)
        tail = frame.get('history', {}).get('tail_state', {})
        pending = read_json(runner.manifest['gcUrl'] +
            f"/v0/city/{value['target']['city']}/session/{value['sessionId']}/pending")
        interactions = read_json(runner.manifest['bbUrl'] + f'/api/v1/threads/{thread}/interactions')
        if (tail.get('activity') == 'idle' and not tail.get('degraded') and not tail.get('open_tool_call_ids')
                and not tail.get('pending_interaction_ids') and pending.get('supported') is True
                and not pending.get('pending') and not interactions):
            return frame
    frame = FaultCases(runner).poll('denied tool and native approval settled', settled)
    evidence = require_native_denial(frame, value['turn'], prompt, command, completed['toolItem'])
    # These identities came from the independently correlated rendered denial.
    # Reuse the normal receipt/target/workspace validator without pretending that
    # a denied tool produced an assistant message.
    harness.report['turns'].append({'turn_id': completed['turnId'], 'provider_thread_id': completed['providerThreadId'],
        'client_request_id': completed['requestId'], 'completed_seq': completed['completedSeq'], 'tool_count': 1,
        'permission_denied': True})
    harness.verify_gc_prompt(prompt, completed['providerThreadId'])
    save_json(runner.private / 'approvals.deny-native.json', {'frame': frame, 'receipt': value, 'evidence': evidence})
    marker = 'AFTER_DENIAL_' + secrets.token_hex(6)
    followup = f'Do not run tools or retry the denied command. Reply exactly {marker}, one space, then the private word from my last request.'
    answer = runner.browser('approvals.deny-followup', f['agent'], f['project'], f['workspace'], followup,
        thread=thread, expected=marker + ' ' + nonce, reasoning='none')
    runner.verify_turn(harness, answer, followup, marker + ' ' + nonce,
        provider=completed['providerThreadId'], no_tools=True)
    verify_resume_identity(frame, harness.last_gc_frame)
    if proof.exists(): raise AcceptanceFailure('Denied command executed during the later follow-up')
    return {'thread_id': thread, 'denied_artifact_absent': True, 'interaction_id': gate['id'],
            'same_conversation_followup': True, 'native_tool_call_id': evidence['gc_tool_call_id']}


def underscore_workspace(runner):
    # One real approved tool journey supplies both independent promises: the
    # permission boundary and execution inside an underscore-containing path.
    evidence = getattr(runner, "underscore_evidence", None) or approval(runner, "approve")
    proof, workspace = Path(evidence["artifact_path"]), Path(evidence["workspace"])
    if ("_" not in workspace.name or proof.resolve().parent != workspace.resolve()
            or hashlib.sha256(proof.read_bytes()).hexdigest() != evidence["artifact_sha256"]):
        raise AcceptanceFailure("Underscore workspace lacks its real approved tool artifact")
    value = receipt(runner, evidence["thread_id"])
    frame = gc_frame(runner, value)
    if (frame.get("history", {}).get("tail_state", {}).get("activity") != "idle"):
        raise AcceptanceFailure("Underscore workspace did not settle after actual execution")
    save_json(runner.private / "workspace.underscores-native.json", frame)
    return evidence


def mismatched_workspace(runner):
    agent = runner.agent("global")
    workspace = runner.root / ("mismatched_workspace_" + secrets.token_hex(6))
    workspace.mkdir(mode=0o700)
    prompt = "MISMATCH_MUST_NOT_REACH_AGENT_" + secrets.token_hex(10)
    started = runner.browser("workspace.mismatch-start", agent, runner.manifest["projectId"], workspace,
                             prompt, route="launcher", until="submitted")
    result = runner.browser("workspace.mismatch-rejection", agent, runner.manifest["projectId"], workspace,
                            thread=started["threadId"], action="wait", after=started["afterSeq"], expected_error="GC works in")
    value = receipt(runner, started["threadId"])
    if value.get("turn"): raise AcceptanceFailure("Workspace mismatch created a submitted turn receipt")
    frame = gc_frame(runner, value)
    if prompt in json.dumps(frame): raise AcceptanceFailure("Mismatched workspace request reached the native agent")
    if list(workspace.iterdir()): raise AcceptanceFailure("Mismatched workspace received generated files")
    save_json(runner.private / "workspace.mismatch-native.json", {"receipt": value, "frame": frame})
    return {"thread_id": result["threadId"], "visible_workspace_error": True, "prompt_not_delivered": True}


def fresh_trust(runner):
    f = fixture(runner, trusted=False)
    marker = "FRESH_TRUST_" + secrets.token_hex(8)
    require_empty_native_fixture(f)
    # Intentionally do not pre-accept workspace or hook trust. If GC/BB cannot
    # expose and handle this first-run boundary, the required case fails.
    result = runner.browser("trust.fresh", f["agent"], f["project"], f["workspace"],
        f"Do not use tools. Reply exactly {marker}.", expected=marker, reasoning="none")
    harness = runner.new_harness("trust.fresh", f["agent"], f["project"], f["workspace"], result["threadId"])
    runner.verify_turn(harness, result, f"Do not use tools. Reply exactly {marker}.", marker, no_tools=True)
    native_fixture_evidence(runner, f, result["threadId"], "trust.fresh", harness.last_gc_frame)
    return {"thread_id": result["threadId"], "fresh_workspace_not_pretrusted": True}


def configured_agent(runner):
    f = fixture(runner, configured_mayor=True)
    marker, word = 'MAYOR_' + secrets.token_hex(6), secrets.token_hex(8)
    prompt = f'Remember the private word {word}. Without tools, finish with exactly {marker}.'
    result = runner.browser('native.configured_agent-first', f['agent'], f['project'], f['workspace'],
                            prompt, expected=marker, reasoning='none')
    harness = runner.new_harness('native.configured_agent', f['agent'], f['project'], f['workspace'], result['threadId'])
    _, identity = runner.verify_turn(harness, result, prompt, marker, no_tools=True)
    native_fixture_evidence(runner, f, result["threadId"], "native.configured_agent", harness.last_gc_frame)
    first_frame = harness.last_gc_frame
    marker2 = 'MAYOR_MEMORY_' + secrets.token_hex(6)
    followup = f'Without tools, reply exactly {marker2}, a space, then the private word from my last message.'
    reply = runner.browser('native.configured_agent-followup', f['agent'], f['project'], f['workspace'],
                           followup, thread=result['threadId'], expected=marker2 + ' ' + word, reasoning='none')
    runner.verify_turn(harness, reply, followup, marker2 + ' ' + word, provider=identity, no_tools=True)
    from live_assertions import verify_resume_identity
    verify_resume_identity(first_frame, harness.last_gc_frame)
    return {'thread_id': result['threadId'], 'configured_role': 'gastown/mayor', 'actual_role_prompt': True, 'turns': 2}


def case_functions(runner):
    return {
        "provider.switch": lambda: provider_switch(runner),
        "reasoning.immutable": lambda: reasoning_immutable(runner),
        "approvals.approve": lambda: approval(runner, "approve"),
        "approvals.deny": lambda: approval(runner, "deny"),
        "approvals.repeated": lambda: approval(runner, "approve", repeated=True),
        "trust.fresh": lambda: fresh_trust(runner),
        "native.configured_agent": lambda: configured_agent(runner),
        "workspace.underscores": lambda: underscore_workspace(runner),
        "workspace.mismatch": lambda: mismatched_workspace(runner),
    }
