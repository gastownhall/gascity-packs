#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import os
import socketserver
import subprocess
import threading
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any

import github_intake_common as common

PROCESSING_LOCK = threading.Lock()
PROCESSING_REQUESTS: set[str] = set()


class ThreadingUnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str) -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def request_summary(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request.get("request_id"),
        "status": request.get("status"),
        "command": request.get("command"),
        "repository_full_name": request.get("repository_full_name"),
        "issue_number": request.get("issue_number"),
        "dispatch_target": request.get("dispatch_target", ""),
        "dispatch_formula": request.get("dispatch_formula", ""),
        "reason": request.get("reason", ""),
    }


def trim_output(value: str, limit: int = 1200) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def human_reason(code: str) -> str:
    mapping = {
        "repo_mapping_missing": "no repository mapping exists for this repo",
        "command_not_configured": "this repository does not configure that /gc command",
        "gc_not_available": "the gc CLI is not available in this runtime",
    }
    return mapping.get(code, code or "unknown_error")


def run_dispatch(request: dict[str, Any], mapping: dict[str, Any], command_cfg: dict[str, Any]) -> dict[str, Any]:
    formula = str(command_cfg.get("formula", ""))
    target = str(mapping.get("target", ""))
    gc_bin = os.environ.get("GC_BIN", "gc")
    if not formula or not target:
        return {"status": "ignored", "reason": "command_not_configured"}
    variables = {
        "github_command": request.get("command", ""),
        "github_repository": request.get("repository_full_name", ""),
        "github_repository_id": request.get("repository_id", ""),
        "github_issue_number": request.get("issue_number", ""),
        "github_comment_id": request.get("comment_id", ""),
        "github_comment_url": request.get("comment_url", ""),
        "github_installation_id": request.get("installation_id", ""),
        "github_request_id": request.get("request_id", ""),
    }
    command = [gc_bin, "sling", target, formula, "--formula"]
    for key, value in variables.items():
        if value:
            command.extend(["--var", f"{key}={value}"])
    try:
        result = subprocess.run(
            command,
            cwd=common.city_root() or ".",
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {"status": "dispatch_failed", "reason": "gc_not_available"}
    outcome = {
        "dispatch_target": target,
        "dispatch_formula": formula,
        "dispatch_command": command,
        "dispatch_exit_code": result.returncode,
        "dispatch_stdout": trim_output(result.stdout),
        "dispatch_stderr": trim_output(result.stderr),
    }
    if result.returncode == 0:
        outcome["status"] = "dispatched"
    else:
        outcome["status"] = "dispatch_failed"
        outcome["reason"] = "dispatch_failed"
    return outcome


def build_ack_comment(request: dict[str, Any]) -> str:
    command = request.get("command", "")
    comment_url = request.get("comment_url", "")
    request_ref = f"[this request]({comment_url})" if comment_url else "this request"
    status = request.get("status")
    if status == "dispatched":
        body = [
            f"Gas City queued `/{'gc ' + command}` for {request_ref}.",
            "",
            f"Dispatch target: `{request.get('dispatch_target', '')}`",
            f"Formula: `{request.get('dispatch_formula', '')}`",
            f"Request id: `{request.get('request_id', '')}`",
        ]
    else:
        body = [
            f"Gas City could not route `/{'gc ' + command}` for {request_ref}.",
            "",
            f"Reason: {human_reason(str(request.get('reason', '')))}",
            f"Request id: `{request.get('request_id', '')}`",
        ]
        stderr = request.get("dispatch_stderr", "")
        if stderr:
            body.extend(["", "Dispatch stderr:", "```text", stderr, "```"])
    body.extend(["", f"<!-- gc-intake-request:{request.get('request_id', '')}:ack -->"])
    return "\n".join(body)


def maybe_post_ack_comment(request: dict[str, Any]) -> dict[str, Any]:
    config = common.load_config()
    app_cfg = config.get("app", {})
    installation_id = request.get("installation_id", "")
    owner = request.get("repository_owner", "")
    repo = request.get("repository_name", "")
    issue_number = request.get("issue_number", "")
    if not app_cfg or not installation_id or not owner or not repo or not issue_number:
        return request
    try:
        comment = common.post_issue_comment(
            app_cfg,
            str(installation_id),
            str(owner),
            str(repo),
            str(issue_number),
            build_ack_comment(request),
        )
    except Exception as exc:  # noqa: BLE001
        request["ack_comment_error"] = str(exc)
        return request
    request["ack_comment_id"] = str(comment.get("id", ""))
    request["ack_comment_url"] = str(comment.get("html_url", ""))
    return request


def process_request(request_id: str) -> None:
    try:
        request = common.load_request(request_id)
        if not request:
            return
        config = common.load_config()
        mapping = common.resolve_repo_mapping(
            config,
            str(request.get("repository_full_name", "")),
            str(request.get("repository_id", "")),
        )
        if not mapping:
            request["status"] = "ignored"
            request["reason"] = "repo_mapping_missing"
        else:
            commands = mapping.get("commands", {})
            command_cfg = commands.get(str(request.get("command", "")), {})
            outcome = run_dispatch(request, mapping, command_cfg)
            request.update(outcome)
        request = maybe_post_ack_comment(request)
        common.save_request(request)
    except Exception as exc:  # noqa: BLE001
        payload = common.load_request(request_id) or {"request_id": request_id}
        payload["status"] = "internal_error"
        payload["reason"] = str(exc)
        payload["traceback"] = traceback.format_exc(limit=20)
        common.save_request(payload)
    finally:
        with PROCESSING_LOCK:
            PROCESSING_REQUESTS.discard(request_id)


def enqueue_request(request_id: str) -> None:
    with PROCESSING_LOCK:
        if request_id in PROCESSING_REQUESTS:
            return
        PROCESSING_REQUESTS.add(request_id)
    thread = threading.Thread(target=process_request, args=(request_id,), daemon=True)
    thread.start()


def render_admin_home() -> str:
    snapshot = common.build_status_snapshot(limit=20)
    config = snapshot["config"]
    app_cfg = config.get("app", {})
    manifest_json = ""
    manifest_error = ""
    try:
        manifest_json = json.dumps(common.build_manifest(), indent=2, sort_keys=True)
    except Exception as exc:  # noqa: BLE001
        manifest_error = str(exc)

    install_url = common.install_url(app_cfg) if isinstance(app_cfg, dict) else ""
    register_form = ""
    if manifest_json:
        escaped_manifest = html.escape(manifest_json, quote=True)
        register_form = f"""
<form action="https://github.com/settings/apps/new" method="post">
  <input type="hidden" name="manifest" value="{escaped_manifest}">
  <button type="submit">Register GitHub App</button>
</form>
"""

    install_html = ""
    if install_url:
        install_html = f'<p><a href="{html.escape(install_url)}">Install the GitHub App</a></p>'

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>GitHub Intake Admin</title>
  <style>
    body {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; margin: 2rem; line-height: 1.45; }}
    pre {{ background: #f5f5f5; padding: 1rem; overflow-x: auto; }}
    code {{ background: #f5f5f5; padding: 0.1rem 0.25rem; }}
    .warning {{ color: #8a3b12; }}
  </style>
</head>
<body>
  <h1>GitHub Intake</h1>
  <p>Admin URL: <code>{html.escape(snapshot['admin_url'] or '(not published yet)')}</code></p>
  <p>Webhook URL: <code>{html.escape(snapshot['webhook_url'] or '(not published yet)')}</code></p>
  <h2>App Setup</h2>
  {register_form or f'<p class="warning">{html.escape(manifest_error or "Manifest unavailable")}</p>'}
  {install_html}
  <p>For organization-owned apps, use the manifest JSON below from the org settings app-registration page.</p>
  <pre>{html.escape(manifest_json or manifest_error or "manifest unavailable")}</pre>
  <h2>Config</h2>
  <pre>{html.escape(json.dumps(config, indent=2, sort_keys=True))}</pre>
  <h2>Recent Requests</h2>
  <pre>{html.escape(json.dumps(snapshot['recent_requests'], indent=2, sort_keys=True))}</pre>
  <h2>Repository Mapping</h2>
  <p>Use <code>gc github-intake map-repo owner/repo rig/polecat --review-formula ...</code> to update repo routing.</p>
</body>
</html>
"""


class IntakeHandler(BaseHTTPRequestHandler):
    server_version = "GitHubIntake/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{common.current_service_name() or 'github-intake'}] {fmt % args}")

    def _parsed(self) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(self.path)

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length) if length > 0 else b"{}"
        if not data:
            return {}
        parsed = json.loads(data.decode("utf-8"))
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("request body must be a JSON object")

    def do_GET(self) -> None:  # noqa: N802
        parsed = self._parsed()
        service_name = common.current_service_name()
        if parsed.path == "/healthz":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
            return
        if service_name == common.ADMIN_SERVICE_NAME:
            self._do_admin_get(parsed)
            return
        self._do_webhook_get(parsed)

    def do_POST(self) -> None:  # noqa: N802
        parsed = self._parsed()
        service_name = common.current_service_name()
        if service_name == common.ADMIN_SERVICE_NAME:
            self._do_admin_post(parsed)
            return
        self._do_webhook_post(parsed)

    def _do_admin_get(self, parsed: urllib.parse.ParseResult) -> None:
        if parsed.path == "/":
            text_response(self, HTTPStatus.OK, render_admin_home(), "text/html; charset=utf-8")
            return
        if parsed.path == "/v0/github/status":
            json_response(self, HTTPStatus.OK, common.build_status_snapshot(limit=20))
            return
        if parsed.path == "/v0/github/requests":
            json_response(self, HTTPStatus.OK, {"requests": common.list_recent_requests(limit=50)})
            return
        if parsed.path == "/v0/github/app/manifest":
            try:
                manifest = common.build_manifest()
            except Exception as exc:  # noqa: BLE001
                json_response(self, HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)})
                return
            json_response(self, HTTPStatus.OK, manifest)
            return
        if parsed.path == "/v0/github/app/manifest/callback":
            params = urllib.parse.parse_qs(parsed.query)
            code = params.get("code", [""])[0]
            if not code:
                text_response(self, HTTPStatus.BAD_REQUEST, "missing manifest conversion code\n", "text/plain; charset=utf-8")
                return
            try:
                converted = common.exchange_manifest_code(code)
                config = common.import_app_config(common.load_config(), converted)
            except Exception as exc:  # noqa: BLE001
                text_response(
                    self,
                    HTTPStatus.BAD_GATEWAY,
                    f"manifest conversion failed: {exc}\n",
                    "text/plain; charset=utf-8",
                )
                return
            app_cfg = config.get("app", {})
            body = [
                "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>GitHub Intake Ready</title></head><body>",
                "<h1>GitHub App Imported</h1>",
                f"<p>App id: <code>{html.escape(str(app_cfg.get('app_id', '')))}</code></p>",
            ]
            install_url = common.install_url(app_cfg)
            if install_url:
                body.append(f'<p><a href="{html.escape(install_url)}">Install the GitHub App</a></p>')
            body.append("</body></html>")
            text_response(self, HTTPStatus.OK, "".join(body), "text/html; charset=utf-8")
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _do_admin_post(self, parsed: urllib.parse.ParseResult) -> None:
        if parsed.path != "/v0/github/app/import":
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        try:
            body = self._read_json_body()
        except Exception as exc:  # noqa: BLE001
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        config = common.import_app_config(common.load_config(), body)
        json_response(self, HTTPStatus.OK, {"config": common.redact_config(config)})

    def _do_webhook_get(self, parsed: urllib.parse.ParseResult) -> None:
        if parsed.path == "/":
            json_response(
                self,
                HTTPStatus.OK,
                {
                    "service": common.current_service_name(),
                    "status": "ok",
                    "webhook_url": common.webhook_url(),
                },
            )
            return
        json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def _do_webhook_post(self, parsed: urllib.parse.ParseResult) -> None:
        if parsed.path != "/v0/github/webhook":
            json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b""
        config = common.load_config()
        app_cfg = config.get("app", {})
        secret = str(app_cfg.get("webhook_secret", ""))
        if not secret:
            json_response(self, HTTPStatus.SERVICE_UNAVAILABLE, {"error": "github app webhook secret is not configured"})
            return
        signature = self.headers.get("X-Hub-Signature-256", "")
        if not common.verify_github_signature(secret, body, signature):
            json_response(self, HTTPStatus.UNAUTHORIZED, {"error": "invalid webhook signature"})
            return
        delivery_id = self.headers.get("X-GitHub-Delivery", "")
        event = self.headers.get("X-GitHub-Event", "")
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            json_response(self, HTTPStatus.BAD_REQUEST, {"error": f"invalid JSON payload: {exc}"})
            return

        common.save_delivery(
            {
                "delivery_id": delivery_id or "unknown-delivery",
                "received_at": common.utcnow(),
                "event": event,
                "payload": payload,
            }
        )

        if event != "issue_comment":
            json_response(self, HTTPStatus.ACCEPTED, {"status": "ignored", "event": event})
            return
        request = common.extract_issue_comment_request(payload)
        if not request:
            json_response(self, HTTPStatus.ACCEPTED, {"status": "ignored", "reason": "not_an_actionable_pr_comment"})
            return
        request["event"] = event
        request["delivery_id"] = delivery_id
        existing = common.load_request(request["request_id"])
        if existing:
            json_response(
                self,
                HTTPStatus.ACCEPTED,
                {"status": "duplicate", "request": request_summary(existing)},
            )
            return
        common.save_request(request)
        enqueue_request(request["request_id"])
        json_response(self, HTTPStatus.ACCEPTED, {"status": "accepted", "request": request_summary(request)})


def main() -> int:
    common.ensure_layout()
    socket_path = os.environ.get("GC_SERVICE_SOCKET")
    if not socket_path:
        raise SystemExit("GC_SERVICE_SOCKET is required")
    try:
        os.remove(socket_path)
    except FileNotFoundError:
        pass
    with ThreadingUnixHTTPServer(socket_path, IntakeHandler) as server:
        print(f"[{common.current_service_name() or 'github-intake'}] listening on {socket_path}")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
