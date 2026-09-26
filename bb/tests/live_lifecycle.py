"""Lifecycle actions restricted to child processes this test harness created.

No PID discovery, process-group signals, automatic restart, state reset or log
replacement. A restart creates one fresh child with the same cwd/environment
and a new exclusive log. Evidence stays in the caller's scratch root.
"""

import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


class LifecycleFailure(RuntimeError):
    pass


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class OwnedProcess:
    def __init__(self, name, argv, *, scratch_root, cwd, env, isolated_paths, artifacts):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name):
            raise LifecycleFailure("An owned component needs a stable, safe name")
        if (not isinstance(argv, (tuple, list)) or not argv
                or not all(isinstance(arg, str) and arg for arg in argv)):
            raise LifecycleFailure("An owned component needs an explicit argument vector")
        self.name, self.argv, self.env = name, list(argv), dict(env)
        self.root = Path(scratch_root).resolve(strict=True)
        self.cwd = Path(cwd).resolve(strict=True)
        if self.root == self.cwd or not self.cwd.is_relative_to(self.root):
            raise LifecycleFailure("Component cwd must be a child of the test scratch root")
        if not self.cwd.is_dir() or not isolated_paths:
            raise LifecycleFailure("Component needs a workspace and explicit isolated state paths")
        for key, value in isolated_paths.items():
            path = Path(value).resolve()
            if (not isinstance(key, str) or self.env.get(key) != str(value)
                    or path == self.root or not path.is_relative_to(self.root)):
                raise LifecycleFailure("Every declared process state path must be isolated in scratch")
        self.artifacts = Path(artifacts).resolve()
        if self.artifacts == self.root or not self.artifacts.is_relative_to(self.root):
            raise LifecycleFailure("Process evidence must stay in scratch")
        self.artifacts.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._journal = (self.artifacts / "events.jsonl").open("xb")
        os.fchmod(self._journal.fileno(), 0o600)
        self.process, self._stdout = None, None
        self.generation = 0
        self.identity = None
        self._configuration_digest = _digest({"argv": self.argv, "cwd": str(self.cwd), "env": self.env})

    def _event(self, action, **fields):
        event = {"component": self.name, "generation": self.generation,
                 "action": action, "at": time.time(), **fields}
        self._journal.write(json.dumps(event).encode() + b"\n")
        self._journal.flush()

    def start(self):
        if self.process is not None and self.process.poll() is None:
            raise LifecycleFailure("Refusing to start a second live copy of this component")
        if _digest({"argv": self.argv, "cwd": str(self.cwd), "env": self.env}) != self._configuration_digest:
            raise LifecycleFailure("Refusing to restart a component with changed command, cwd or environment")
        if self._stdout is not None:
            self._stdout.close()
        self.generation += 1
        self._stdout = (self.artifacts / f"generation-{self.generation:03d}.log").open("xb")
        os.fchmod(self._stdout.fileno(), 0o600)
        self.process = subprocess.Popen(self.argv, cwd=self.cwd, env=self.env,
                                        stdin=subprocess.DEVNULL, stdout=self._stdout,
                                        stderr=subprocess.STDOUT)
        self.identity = {"component": self.name, "generation": self.generation,
                         "pid": self.process.pid, "created_by_pid": os.getpid(),
                         "started_monotonic_ns": time.monotonic_ns(),
                         "configuration_sha256": self._configuration_digest}
        self.identity["fingerprint"] = _digest(self.identity)
        self._event("started", identity=self.identity)
        return dict(self.identity)

    def snapshot(self):
        if self.process is None:
            raise LifecycleFailure("This component has never been launched by the harness")
        return {**self.identity, "returncode": self.process.poll()}

    def interrupt(self, identity, *, crash=False, timeout=30):
        """Signal exactly the still-owned child; never escalate a timeout.

        ``crash=True`` deliberately SIGKILLs this test child for a named failure
        case. Descendants are untouched and must have their own owned handles.
        """
        if (self.process is None or identity != self.identity or self.process.pid != identity.get("pid")
                or self.process.poll() is not None):
            raise LifecycleFailure("Refusing to signal a stale, foreign, or exited process identity")
        if not 0 < timeout <= 60:
            raise LifecycleFailure("Lifecycle waits must be between zero and 60 seconds")
        signum = signal.SIGKILL if crash else signal.SIGTERM
        self._event("signal", signal=signum.name, identity=self.identity)
        # Popen's own handle checks child status before signaling; a caller can
        # never supply an arbitrary PID or accidentally signal a replacement.
        self.process.send_signal(signum)
        try:
            result = self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            self._event("signal-timeout")
            raise LifecycleFailure("Owned component did not exit; no escalation was attempted") from error
        self._event("exited", returncode=result)
        self._stdout.close()
        self._stdout = None
        return result

    def close_evidence(self):
        """Close files only; this method never stops a retained service."""
        if self.process is not None and self.process.poll() is None:
            raise LifecycleFailure("Keep evidence open while the owned process is running")
        if self._stdout is not None:
            self._stdout.close()
            self._stdout = None
        self._journal.close()
