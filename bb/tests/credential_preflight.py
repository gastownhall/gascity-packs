#!/usr/bin/env python3
"""Make one real model call through the runtime CLI before the expensive gates.

Prints only a classification (never prompts, keys or raw provider output) so CI
can say whether its inference credential works. A pass here certifies nothing
about BB or GC; a failure means every model-dependent case would fail too.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROMPT = "Reply with exactly: pong"
KNOWN = ("authentication_failed", "authentication_error", "permission_error", "invalid_api_key", "insufficient_quota",
         "rate_limit", "overloaded", "billing", "quota", "Unauthorized", "Forbidden")


def classify(text):
    """Reduce provider output to an HTTP status and known error words; nothing else."""
    statuses = sorted(set(re.findall(r"(?<![\d.])(40[0-9]|429|5\d\d)(?![\d.])", text)))
    words = sorted({word for word in KNOWN if word.lower() in text.lower()})
    return {"http_status": statuses, "error_kinds": words}


def run(argv, env, timeout):
    try:
        result = subprocess.run(argv, env=env, text=True, capture_output=True, timeout=timeout,
                                stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return None, ""
    return result.returncode, result.stdout + "\n" + result.stderr


def claude(env, home, timeout):
    env["CLAUDE_CONFIG_DIR"] = str(home / "claude-config")
    # Claude retries a rejected credential ten times with backoff; report it now.
    env["CLAUDE_CODE_MAX_RETRIES"] = "1"
    code, output = run([shutil.which("claude", path=env["PATH"]) or "claude", "-p", PROMPT,
                        "--output-format", "json"], env, timeout)
    if code is None:
        return False, {"reason": "timeout"}
    try:
        reply = json.loads(output.split("\n", 1)[0])
    except json.JSONDecodeError:
        return False, {"reason": "unparseable-output", "exit": code, **classify(output)}
    text = str(reply.get("result", ""))
    if code == 0 and not reply.get("is_error") and text.strip().strip(".").lower() == "pong":
        return True, {}
    return False, {"reason": "model-call-failed", "exit": code, "is_error": reply.get("is_error"), **classify(text)}


def codex(env, home, timeout):
    key = env.pop("OPENAI_API_KEY", "")
    if not key:
        return False, {"reason": "missing-OPENAI_API_KEY"}
    codex_home = home / "codex-config"
    codex_home.mkdir(mode=0o700)
    (codex_home / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": key}))
    env["CODEX_HOME"] = str(codex_home)
    last = home / "last-message.txt"
    code, output = run([shutil.which("codex", path=env["PATH"]) or "codex", "exec", "--skip-git-repo-check",
                        "--output-last-message", str(last), PROMPT], env, timeout)
    if code is None:
        return False, {"reason": "timeout"}
    text = last.read_text() if last.exists() else ""
    if code == 0 and text.strip().strip(".").lower() == "pong":
        return True, {}
    return False, {"reason": "model-call-failed", "exit": code, **classify(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", required=True, choices=["claude", "codex"])
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CONFIG_DIR", "CODEX_HOME"))}
    # Codex keeps cloning plugins into its home in the background after exec
    # returns; cleanup must not turn that race into a failed preflight.
    with tempfile.TemporaryDirectory(prefix="bb-credential-preflight-", ignore_cleanup_errors=True) as scratch:
        home = Path(scratch)
        os.chmod(home, 0o700)
        workdir = home / "work"
        workdir.mkdir()
        os.chdir(workdir)
        ok, detail = (claude if args.runtime == "claude" else codex)(env, home, args.timeout)
        print(json.dumps({"runtime": args.runtime, "credential_works": ok, **detail}, sort_keys=True), flush=True)
        os.chdir("/")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
