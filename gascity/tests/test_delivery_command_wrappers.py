"""The scoped CLI form must reach the same pack action as the cwd form."""
from pathlib import Path
import os
import subprocess
import pytest

PACK = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("command,action", [("tutorial", "status"), ("source-delivery", "show")])
@pytest.mark.parametrize("scope", [
    ["--city", "/selected city"], ["--city=/selected city"],
    ["--rig", "project"], ["--rig=project"],
    ["--context", "staging"], ["--city-url", "https://example.invalid"],
])
def test_wrapper_consumes_gc_scope_before_its_action(tmp_path, command, action, scope):
    executable = tmp_path / "python3"
    executable.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    executable.chmod(0o755)
    result = subprocess.run(
        ["/bin/sh", str(PACK / "commands" / command / "run.sh"), *scope, action,
         "--root", "flow-1"], text=True, capture_output=True,
        env={**os.environ, "PATH": str(tmp_path), "GC_PACK_DIR": str(PACK)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[1:] == [action, "--root", "flow-1"]

@pytest.mark.parametrize("command,action", [("tutorial", "status"), ("source-delivery", "show")])
def test_wrapper_leaves_action_arguments_unchanged(tmp_path, command, action):
    executable = tmp_path / "python3"
    executable.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    executable.chmod(0o755)
    result = subprocess.run(
        ["/bin/sh", str(PACK / "commands" / command / "run.sh"), action,
         "--city", "child-owned-value"], text=True, capture_output=True,
        env={**os.environ, "PATH": str(tmp_path), "GC_PACK_DIR": str(PACK)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[1:] == [action, "--city", "child-owned-value"]
