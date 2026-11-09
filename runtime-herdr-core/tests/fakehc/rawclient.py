"""A bare JSON-RPC call to a socket, for tests that drive fake-hc below the pack's client."""

from __future__ import annotations

import json
import socket
from typing import Any, Dict, Mapping


def raw_call(socket_path: str, method: str, params: Mapping[str, object], *, timeout: float = 10.0) -> Dict[str, Any]:
    """Send one request on a fresh connection and return the whole reply object."""
    request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": dict(params)}) + "\n"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(timeout)
        conn.connect(socket_path)
        conn.sendall(request.encode("utf-8"))
        reply = b""
        while not reply.endswith(b"\n"):
            chunk = conn.recv(1 << 16)
            if not chunk:
                raise ConnectionError(f"{method}: connection closed before the reply")
            reply += chunk
    decoded: Dict[str, Any] = json.loads(reply)
    return decoded
