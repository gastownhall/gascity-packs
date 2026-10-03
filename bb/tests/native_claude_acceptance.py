"""Isolate native Manifold runtime state while retaining its authorized identity."""
import json
import hashlib
import os
from pathlib import Path
import sys


def native_memory_provenance(config_path):
    return json.loads(Path(config_path).with_suffix(".provenance.json").read_text())


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_new(path, content, mode=0o600):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)


def prepare_native_claude(root, source):
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    config = json.loads(source.read_text())
    executable = {"path": config["claude_binary"], "sha256": config["claude_sha256"]}
    if source.with_suffix(".provenance.json").is_file():
        inherited = native_memory_provenance(source)
        if (inherited["configSha256"] != digest(source)
                or inherited["wrapperExecutable"] != executable
                or digest(executable["path"]) != executable["sha256"]):
            raise ValueError("Native acceptance source differs from its recorded provenance")
        executable = inherited["originalExecutable"]
    binary = Path(executable["path"])
    if (not binary.is_absolute() or not binary.is_file() or not os.access(binary, os.X_OK)
            or digest(binary) != executable["sha256"]):
        raise ValueError("Native acceptance executable differs from its pinned identity")

    # The official native launcher scrubs this environment input. Its supported
    # executable/hash config seam lets a private child wrapper set only this
    # test isolation flag after scrubbing, then exec the same qualified binary.
    wrapper = root / "native-claude-no-auto-memory"
    write_new(wrapper, f'''#!{sys.executable}
import hashlib
import os
import sys
binary = {str(binary)!r}
with open(binary, "rb") as stream:
    if hashlib.file_digest(stream, "sha256").hexdigest() != {executable["sha256"]!r}:
        raise SystemExit("Native acceptance binary identity changed")
os.environ["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
os.execv(binary, [binary, *sys.argv[1:]])
''', 0o700)
    config["claude_binary"] = str(wrapper)
    config["claude_sha256"] = digest(wrapper)
    config["home_root"] = str(root / "native-claude-homes")
    config["session_root"] = str(root / "claude-config/projects")
    target = root / "native-claude-launch.json"
    write_new(target, json.dumps(config, indent=2) + "\n")
    provenance = {"autoMemoryDisabled": True, "originalExecutable": executable,
                  "wrapperExecutable": {"path": str(wrapper), "sha256": config["claude_sha256"]},
                  "sourceConfig": {"path": str(source), "sha256": digest(source)},
                  "configSha256": digest(target)}
    write_new(target.with_suffix(".provenance.json"), json.dumps(provenance, indent=2) + "\n")
    return target
