"""Local, filtered Claude CLI OTLP usage capture (no prompts or personal data)."""
from __future__ import annotations
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

COUNTERS = ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_creation_tokens')
FIELDS = {'event.name', 'request_id', 'client_request_id', 'session.id', 'event.sequence',
          'model', 'query_source', 'duration_ms', *COUNTERS}


def extract(payload):
    rows = []
    for resource in payload.get('resourceLogs', []):
        for scope in resource.get('scopeLogs', []):
            for record in scope.get('logRecords', []):
                attrs = {}
                for attr in record.get('attributes', []):
                    key, value = attr['key'], attr.get('value', {})
                    if key not in FIELDS:
                        continue
                    if 'intValue' in value:
                        attrs[key] = int(value['intValue'])
                    elif 'doubleValue' in value:
                        attrs[key] = value['doubleValue']
                    elif 'stringValue' in value:
                        attrs[key] = value['stringValue']
                if attrs.get('event.name') in ('api_request', 'claude_code.api_request'):
                    rows.append(attrs)
    return rows


def summarize(rows):
    unique = {}
    for row in rows:
        identity = row.get('request_id') or row.get('client_request_id')
        if not identity and row.get('session.id') and row.get('event.sequence') is not None:
            identity = (row['session.id'], row['event.sequence'])
        if not identity:
            return {'status': 'incomplete', 'totals': None, 'reason': 'missing request identity'}
        if identity in unique and unique[identity] != row:
            return {'status': 'incomplete', 'totals': None, 'reason': 'conflicting duplicate request'}
        unique[identity] = row
    result = {'status': 'observed' if unique else 'missing', 'request_count': len(unique),
              'models': sorted({r['model'] for r in unique.values() if r.get('model')}), 'totals': None}
    if not unique:
        return result
    if any(type(row.get(k)) is not int or row[k] < 0 for row in unique.values() for k in COUNTERS):
        result.update(status='incomplete', reason='missing or invalid token counters')
        return result
    result['totals'] = {k: sum(row[k] for row in unique.values()) for k in COUNTERS}
    result['totals']['total_tokens'] = sum(result['totals'].values())
    return result


class Collector:
    def __init__(self, output: Path):
        self.rows = []
        self.errors = 0
        self.lock = threading.Lock()
        self.file = output.open('x')
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size <= 8 * 1024 * 1024:
                        raise ValueError('invalid body size')
                    body = self.rfile.read(size)
                    if self.headers.get('Content-Encoding') == 'gzip':
                        body = gzip.decompress(body)
                    rows = extract(json.loads(body))
                    with owner.lock:
                        for row in rows:
                            owner.file.write(json.dumps(row) + '\n')
                        owner.file.flush()
                        owner.rows.extend(rows)
                    self.send_response(200)
                except Exception:
                    with owner.lock:
                        owner.errors += 1
                    self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{}')

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.env = {'CLAUDE_CODE_ENABLE_TELEMETRY': '1', 'OTEL_LOGS_EXPORTER': 'otlp',
                    'OTEL_METRICS_EXPORTER': 'none', 'OTEL_EXPORTER_OTLP_LOGS_PROTOCOL': 'http/json',
                    'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT': f'http://127.0.0.1:{self.server.server_port}/v1/logs',
                    'OTEL_LOGS_EXPORT_INTERVAL': '1000'}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.file.close()
        result = summarize(self.rows)
        result['collector_errors'] = self.errors
        if self.errors:
            result.update(status='incomplete', totals=None)
        return result
