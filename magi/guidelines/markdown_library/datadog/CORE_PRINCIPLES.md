# Core Principles

This guide defines strict, practical standards for implementing observability at enterprise scale using Datadog. The goal is ensuring every team can diagnose issues within minutes, understand system behavior under all conditions, and maintain cost-effective telemetry that provides actionable insight rather than noise.

- **Signal Over Noise**: Every metric, log, and trace must earn its place; collecting data without purpose creates cost and confusion
- **Context Preservation**: Every telemetry datum must carry sufficient context to identify what, when, where, who, and why
- **Actionability**: If telemetry cannot drive a decision or action, it should not be collected
- **Cost Awareness**: Telemetry volume directly impacts cost; optimize collection for value, not completeness
- **Consistency**: Naming conventions, tagging strategies, and instrumentation patterns must be uniform across all services

### Primary Rule: Observability Serves Incident Response

The purpose of observability is answering questions during incidents:
- What is broken?
- When did it start?
- What changed?
- Who is affected?
- How do we fix it?

Every dashboard, alert, log, and trace must contribute to answering these questions. If it doesn't, it's noise.

### Secondary Rule: You Cannot Alert on What You Cannot Measure

Critical business operations require explicit instrumentation. Implicit metrics from infrastructure are insufficient. If a business process matters, instrument it explicitly:
- Orders placed per minute
- Payment failures per tenant
- User login success rate
- API response times by endpoint and customer tier

### Tertiary Rule: Context Is Everything

A metric without context is a number. A log without context is text. A trace without context is a list of spans. Context transforms data into insight:
- `http.status_code:500` tells you something failed
- `http.status_code:500, service:order-api, env:prod, tenant:acme-corp, endpoint:/api/v2/orders, trace_id:abc123` tells you exactly what to investigate

---
[Back to Overview](./OVERVIEW.md)
