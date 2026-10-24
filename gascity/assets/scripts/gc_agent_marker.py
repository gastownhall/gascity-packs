"""Universal machine-readable marker for everything the factory posts on GitHub.

Every comment or review body the Gas City factory posts (deterministic script
output and agent-written prose alike) carries ``GC_AGENT_MARKER`` on its own
line, normally the first line. Analytics (mdash) use it to classify the post as
automation exactly, independent of which account posted it. Workflow-specific
markers (``gc-approval-request:v1``, ``gc-merge-queue-eject:v1``, ...) stay in
the body as well; this marker is in addition to them, never a replacement.
"""

from __future__ import annotations

GC_AGENT_MARKER = "<!-- gc-agent:v1 -->"


def has_agent_marker(body: str) -> bool:
    """True when ``body`` already carries the marker on a line of its own."""
    return any(line.strip() == GC_AGENT_MARKER for line in body.splitlines())


def with_agent_marker(body: str) -> str:
    """Return ``body`` with the universal marker as its first line (idempotent)."""
    if has_agent_marker(body):
        return body
    return f"{GC_AGENT_MARKER}\n{body}"

