#!/usr/bin/env python3
"""Minimal stdlib Jev client used by the gascity-jev gates.

Every failure raises JevUnavailable with a short machine-readable reason so a
gate can fail open to the ordinary gascity path and record why. The API key is
read from TYPESAFE_API_KEY and never written anywhere.
"""
from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_URL = 'https://api.typesafe.ai/v1/systemone'
DEFAULT_MODEL = 'jev-1.13.0'
# Jev accepts 64K tokens per request with state plus the longest question under
# 32K. Stay well inside that: roughly 3 characters per token for code.
MAX_STATE_BYTES = 90_000


class JevUnavailable(Exception):
    """Jev could not give a usable answer; the caller must fail open."""

    def __init__(self, reason: str, detail: str = ''):
        super().__init__(f'{reason}: {detail}' if detail else reason)
        self.reason = reason
        self.detail = detail


LOOPBACK = ('127.0.0.1', 'localhost', '::1')


def endpoint() -> str:
    """The API URL. JEV_API_URL may point at a loopback stub for tests only."""
    url = os.environ.get('JEV_API_URL', '').strip() or DEFAULT_URL
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in LOOPBACK):
        return url
    raise JevUnavailable('bad_endpoint', 'JEV_API_URL must be https or a loopback http URL')


def opener(url: str):
    """Loopback stubs bypass HTTP(S)_PROXY; the real API honors the environment."""
    if urllib.parse.urlparse(url).hostname in LOOPBACK:
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def unit(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1


def validate_answer(question: dict, answer: object) -> dict:
    """Check one answer against its question type; return it or raise."""
    if not isinstance(answer, dict):
        raise JevUnavailable('invalid_response', 'answer is not an object')
    kind = question['type']
    if kind == 'noul':
        if not unit(answer.get('noul')):
            raise JevUnavailable('invalid_response', 'noul answer lacks a probability')
    elif kind == 'choice':
        probabilities = answer.get('probabilities')
        choice = answer.get('choice')
        if (not isinstance(probabilities, dict) or set(probabilities) != set(question['criteria'])
                or not all(unit(v) for v in probabilities.values())
                or choice not in probabilities or not unit(answer.get('confidence'))):
            raise JevUnavailable('invalid_response', 'choice answer is malformed')
    elif kind == 'score':
        if not isinstance(answer, dict) or not answer:
            raise JevUnavailable('invalid_response', 'score answer is empty')
    return answer


def ask(state: dict, questions: dict, *, model: str = DEFAULT_MODEL, timeout: float = 30,
        key: str | None = None) -> dict:
    """POST one Jev call and return {'answers', 'model', 'usage', 'elapsed_seconds'}.

    No hidden retries: one call, one answer or one JevUnavailable.
    """
    key = key if key is not None else os.environ.get('TYPESAFE_API_KEY', '')
    if not key:
        raise JevUnavailable('no_key', 'TYPESAFE_API_KEY is not set')
    if not questions:
        raise JevUnavailable('no_questions')
    state_bytes = len(json.dumps(state).encode())
    if state_bytes > MAX_STATE_BYTES:
        raise JevUnavailable('state_too_large', f'{state_bytes} bytes')
    body = json.dumps({'model': model, 'state': state, 'questions': questions}).encode()
    url = endpoint()
    request = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    started = time.monotonic()
    try:
        with opener(url).open(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise JevUnavailable('http_error', f'HTTP {error.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise JevUnavailable('network_error', type(error).__name__) from None
    except ValueError:
        raise JevUnavailable('invalid_response', 'response is not JSON') from None
    elapsed = time.monotonic() - started
    if not isinstance(payload, dict) or not isinstance(payload.get('answers'), dict):
        raise JevUnavailable('invalid_response', 'response has no answers')
    answers = payload['answers']
    if set(answers) != set(questions):
        raise JevUnavailable('invalid_response', 'answer ids do not match question ids')
    for qid, question in questions.items():
        validate_answer(question, answers[qid])
    usage = payload.get('usage') if isinstance(payload.get('usage'), dict) else {}
    return {'answers': answers, 'model': payload.get('model') or model, 'usage': usage,
            'elapsed_seconds': round(elapsed, 3)}
