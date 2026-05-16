# Telemetry Pipeline Shakedown

### Definition

A Datadog shakedown is an **end-to-end telemetry pipeline validation run** that emits canary metrics, logs, traces, and monitor signals from the **real Datadog Agent** and verifies, **via the Datadog API**, that each signal lands in the intended backend index with the intended tag set and routes through the intended notification channel.

A dashboard that renders on a sample is **not** a shakedown. A unit test that mocks the StatsD client is **not** a shakedown. **Only real emission with real backend verification counts.**

### Preflight vs Shakedown vs Testing

| Stage | What it does |
|:------|:-------------|
| Preflight | Inspects static prerequisites: Agent installed, API key loaded, unified service tagging labels present, network egress to ingestion endpoint reachable |
| **Shakedown** | **Exercises the full telemetry pipeline under real conditions: canary metric emitted by the real Agent, canary log parsed by the real pipeline, canary span stitched into a real trace, canary monitor evaluating a known condition and routing a notification** |
| Testing | Behavioral correctness at scale: dashboard load performance, monitor false-positive rate, alert fatigue analysis |

### Mandatory Triggers

- First-ever enablement of Datadog on a new service or new environment
- Datadog Agent version upgrade (major, minor, or patch that touches ingestion)
- Change to Agent configuration (`datadog.yaml`, `conf.d/*.yaml`) that affects ingestion
- Change to log pipeline processors (grok-parser, attribute-remapper, status-remapper, trace-id-remapper)
- Change to trace sampling rules, tail-based sampling configuration, or ingestion rules
- Change to metric naming conventions, required tag set, or tag processor logic
- Change to monitor queries, alert routing, notification channels, or PagerDuty/Slack integrations
- Change to unified service tagging labels (`env`, `service`, `version`, `team`, `region`) on workload manifests
- Infrastructure change that reroutes Agent egress: new proxy, new cluster, new region, new VPC peering
- Restoration after a telemetry outage or Datadog-side incident that impacted ingestion
- Extended dormancy on a service whose telemetry configuration may have drifted

### Non-Triggers

- Dashboard widget additions that query existing metrics already covered by prior shakedowns
- Monitor threshold tuning within the same query
- Notebook creation or annotation changes
- SLO target adjustments on existing metrics
- Downtime scheduling or silencing window updates

### Validation Categories

1. **Canary metric emission and query**
   - Emit `shakedown.canary.count` with `env:$env,service:$service,shakedown_run:$run_id,shakedown_phase:metric`
   - Query `/api/v1/query` within 90s; confirm series with shakedown_run tag and expected host/pod tags
   - Failure mode: Agent not reaching ingestion, or metric dropped by ingestion filter

2. **Canary log emission and parsing**
   - Emit JSON log: `{"level":"INFO","service":"$service","env":"$env","message":"shakedown canary","shakedown_run_id":"$run_id","correlation_id":"$corr"}`
   - Query `/api/v2/logs/events/search` within 120s for `@shakedown_run_id:$run_id`
   - Confirm pipeline correctly remapped `kubernetes.pod.name` to `pod` and didn't drop required fields
   - Failure mode: log collection broken, pipeline rejecting record, or exclusion filter dropping it

3. **Canary trace span emission and service map**
   - Emit `shakedown.canary.parent` and `shakedown.canary.child` from instrumented service
   - Query `/api/v2/spans/events/search` for `@shakedown_run:$run_id` within 120s
   - Confirm parent-child relationship preserved, trace ID in APM, service map reflects expected node and edge
   - Failure mode: APM instrumentation or trace propagation headers misconfigured

4. **Canary monitor evaluation and notification**
   - Provision shakedown monitor: `sum:shakedown.canary.count{shakedown_run:$run_id} > 0 over last 5m`
   - Confirm transition to Alert state, notification fires to configured channel (test PagerDuty service / Slack channel / dedicated shakedown notifier), payload contains run_id
   - Recover the monitor and confirm transition back to OK
   - Failure mode: monitor never fires (query broken or metric not ingesting); monitor fires but notification never arrives (integration broken)

5. **Tag propagation integrity** — required tag set (`env`, `service`, `version`, `team`, `region`) present on every canary signal

6. **Trace-log correlation** — canary `trace_id` present on the canary log line via `trace-id-remapper`; clicking the trace in APM reveals the correlated log

7. **Cost envelope check** — shakedown emission does not unexpectedly appear on a high-cardinality index; custom metric count and log index volume stay within bounds

### Execution Principles

- **Conservative execution** — canary signals only; fixed run ID; fixed tag values; no randomized stress, no fuzz, no production traffic amplification
- **Progressive stress** — metric first, then log, then trace, then monitor; stop at the first category that fails
- **Controlled environment** — dedicated shakedown service name or `shakedown_run` tag; dedicated shakedown notification channel; **do not page the on-call rotation during a shakedown**
- **Observable execution** — every API verification call logs the Datadog request ID and search query
- **Known-good inputs** — fixed metric name, fixed log shape, fixed span names, fixed monitor query
- **No optimization during shakedown** — do not tune sampling rules, adjust retention, or rewrite the pipeline mid-run

### Execution Sequence

```text
Step 1:  Confirm preflight: Agent status healthy, API key resolves, unified service tags present on workload, shakedown_run ID generated
Step 2:  Initialize: provision the shakedown monitor against the canary query and the shakedown notification channel
Step 3:  Emit canary metric from the real Agent on the target host/pod
Step 4:  Verify metric via Datadog API query with bounded polling (≤ 90s) for the shakedown_run tag
Step 5:  Emit canary log line through the real application logger
Step 6:  Verify log via Logs API with bounded polling (≤ 120s) for the shakedown_run_id attribute
Step 7:  Emit canary trace span pair through the real APM tracer
Step 8:  Verify trace via Traces API and confirm service map edge
Step 9:  Verify the shakedown monitor has transitioned to Alert and the notification arrived at the shakedown channel
Step 10: Recover the monitor, delete the shakedown monitor, record all observations, classify results
```

### Result Classification

- **pass** — Every canary signal arrived with the expected tag set, trace-log correlation held, monitor notification routed correctly. Proceed.
- **fail-blocking** — A canary metric, log, or trace did not arrive; the monitor did not fire; or the notification did not route. Fix the defect; re-run shakedown from step 1.
- **fail-nonblocking** — Signals arrived but outside expected latency bound, or a non-required tag was missing. Log to issue tracker with Datadog request IDs and proceed with explicit sign-off.
- **inconclusive** — Datadog API returned throttled or unavailable responses during verification. Adjust polling window or wait for upstream condition to clear.

### Required Artifacts

- **Execution log** — timestamped log of every Agent emission, every Datadog API verification call with request ID, every monitor state transition, every notification delivery receipt
- **Result summary** — pass/fail per validation category with specific metric series, log event IDs, trace IDs, monitor IDs
- **Issue list** — every anomaly classified blocking/non-blocking/deferred with reproduction context (`shakedown_run_id`, host/pod, `correlation_id`, `trace_id`)
- **Environment snapshot** — Agent version, instrumentation library versions, unified service tag values, pipeline processor versions, monitor definition JSON, dashboard definition JSON if touched

### Anti-Patterns (Forbidden)

- Treating a rendered dashboard widget as proof of shakedown — dashboards read the backend; they do not prove the Agent is reaching the backend for the current change
- Running shakedown against a mocked StatsD client, recorded API fixture, or local log tailer
- Firing the shakedown monitor into the production PagerDuty rotation
- Emitting canary signals with unbounded tag values (`user_id`, `request_id`, timestamp) that expand custom metric cardinality
- Leaving the shakedown monitor provisioned in production after the run
- Declaring shakedown passed without preserving execution log, result summary, issue list, environment snapshot

### Reference Canary Emitter

```python
# datadog_shakedown.py — telemetry pipeline validator
# Usage: DATADOG_API_KEY=... DATADOG_APP_KEY=... python datadog_shakedown.py
import os
import time
import uuid
from datadog import api, initialize, statsd
from ddtrace import tracer
import logging
import requests

SHAKEDOWN_RUN_ID: str = uuid.uuid4().hex
SERVICE: str = os.environ["SHAKEDOWN_SERVICE"]
ENV: str = os.environ["SHAKEDOWN_ENV"]
DD_SITE: str = os.environ.get("DD_SITE", "datadoghq.com")

initialize(api_key=os.environ["DATADOG_API_KEY"], app_key=os.environ["DATADOG_APP_KEY"])
logger = logging.getLogger("shakedown")
logger.setLevel(logging.INFO)
tags = [f"env:{ENV}", f"service:{SERVICE}", f"shakedown_run:{SHAKEDOWN_RUN_ID}", "shakedown_phase:metric"]

# 1. Canary metric via real Agent
statsd.increment("shakedown.canary.count", tags=tags)

# 2. Canary log via real logger
logger.info(
    "shakedown canary",
    extra={"shakedown_run_id": SHAKEDOWN_RUN_ID, "correlation_id": SHAKEDOWN_RUN_ID, "service": SERVICE, "env": ENV},
)

# 3. Canary trace via real APM tracer
with tracer.trace("shakedown.canary.parent", service=SERVICE) as parent:
    parent.set_tag("shakedown_run", SHAKEDOWN_RUN_ID)
    parent.set_tag("env", ENV)
    with tracer.trace("shakedown.canary.child", service=SERVICE) as child:
        child.set_tag("shakedown_run", SHAKEDOWN_RUN_ID)

# 4. Verify metric arrived within 90s
deadline = time.time() + 90
query = f"sum:shakedown.canary.count{{shakedown_run:{SHAKEDOWN_RUN_ID}}}"
while time.time() < deadline:
    result = api.Metric.query(start=int(time.time()) - 120, end=int(time.time()), query=query)
    if result.get("series"):
        break
    time.sleep(5)
else:
    raise SystemExit(f"fail-blocking: metric never arrived for run {SHAKEDOWN_RUN_ID}")

# 5. Verify log arrived within 120s
log_search_url = f"https://api.{DD_SITE}/api/v2/logs/events/search"
log_deadline = time.time() + 120
log_payload = {
    "filter": {
        "query": f"@shakedown_run_id:{SHAKEDOWN_RUN_ID} service:{SERVICE}",
        "from": "now-5m",
        "to": "now",
    },
    "page": {"limit": 10},
}
headers = {"DD-API-KEY": os.environ["DATADOG_API_KEY"], "DD-APPLICATION-KEY": os.environ["DATADOG_APP_KEY"]}
while time.time() < log_deadline:
    response = requests.post(log_search_url, json=log_payload, headers=headers, timeout=10)
    response.raise_for_status()
    if response.json().get("data"):
        break
    time.sleep(5)
else:
    raise SystemExit(f"fail-blocking: log never arrived for run {SHAKEDOWN_RUN_ID}")

print(f"pass: shakedown run {SHAKEDOWN_RUN_ID} verified end-to-end")
```

---
[Back to Overview](./OVERVIEW.md)
