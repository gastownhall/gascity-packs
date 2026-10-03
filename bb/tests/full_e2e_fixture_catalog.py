"""Prepare additive fixtures together and respect BB's stored catalog lifetime.

BB 0.43.3 caches picker catalogs for ten minutes, including across server and
plugin restarts. Its public API has no refresh operation. Create fixtures before
cases, then wait for ordinary public discovery only when a fixture is first used.
Never edit BB's cache, settings, clock, or stored rows to force discovery.
"""
from collections import defaultdict, deque
import time
import urllib.parse

from live_assertions import AcceptanceFailure


def prepare_fixtures(runner, selected):
    from full_e2e_browser_cases import create_fixture, save_json
    from full_e2e_error_cases import create_error_fixture
    browser, errors = defaultdict(deque), {}
    for case in sorted(selected & {"approvals.approve", "approvals.deny", "approvals.repeated",
                                  "approvals.interrupt", "workspace.underscores"}):
        runner.progress("preparing separate untouched fixture for " + case)
        browser[(True, False)].append(create_fixture(runner))
    for case, key in (("trust.fresh", (False, False)), ("native.configured_agent", (True, True))):
        if case in selected:
            runner.progress("preparing separate untouched fixture for " + case)
            browser[key].append(create_fixture(runner, trusted=key[0], configured_mayor=key[1]))
    for mode in ("provider", "startup"):
        if "error." + mode in selected:
            runner.progress("preparing separate untouched fixture for error." + mode)
            errors[mode] = create_error_fixture(runner, mode)
    fixtures = [item for queue in browser.values() for item in queue] + list(errors.values())
    runner.prepared_browser_fixtures = browser
    runner.prepared_error_fixtures = errors
    runner.prepared_catalog_ids = {item["agent"]["id"] for item in fixtures}
    runner.prepared_catalog_ready = not fixtures
    save_json(runner.private / "prepared-fixtures.json", fixtures)


def wait_for_fixture_catalog(runner, *, timeout=660, now=time.monotonic, sleep=time.sleep, read=None):
    if runner.prepared_catalog_ready:
        return
    from full_e2e_browser_cases import read_json, save_json
    read = read or read_json
    query = urllib.parse.urlencode({"hostId": runner.manifest["hostId"], "providerId": "gas-city"})
    url = runner.manifest["bbUrl"] + "/api/v1/system/execution-options?" + query
    started, last_progress = now(), float("-inf")
    attempts = 0
    while now() - started <= timeout:
        catalog = read(url)
        attempts += 1
        actual = {row.get("id") for row in catalog.get("models", [])}
        missing = runner.prepared_catalog_ids - actual
        if not missing and not catalog.get("modelLoadError"):
            runner.prepared_catalog_ready = True
            save_json(runner.private / "fixture-catalog-ready.json", {
                "elapsed_seconds": now() - started, "requests": attempts,
                "required_model_ids": sorted(runner.prepared_catalog_ids), "catalog": catalog,
                "cache_modified": False})
            return
        if now() - last_progress >= 15:
            runner.progress(f"waiting for BB's ordinary catalog refresh: {len(missing)} new fixture models absent; "
                            f"{int(now() - started)}s elapsed (at most {timeout}s)")
            last_progress = now()
        sleep(min(2, max(0.01, timeout - (now() - started))))
    raise AcceptanceFailure("BB's public catalog did not discover the prepared fixtures within its bounded cache lifetime")


def browser_fixture(runner, key):
    wait_for_fixture_catalog(runner)
    queue = runner.prepared_browser_fixtures.get(key)
    if not queue:
        raise AcceptanceFailure("Case requested an unprepared browser fixture")
    return queue.popleft()


def error_fixture(runner, mode):
    wait_for_fixture_catalog(runner)
    if mode not in runner.prepared_error_fixtures:
        raise AcceptanceFailure("Case requested an unprepared error fixture")
    return runner.prepared_error_fixtures.pop(mode)
