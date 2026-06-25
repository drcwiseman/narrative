# Narrative v1.1 Roadmap

This roadmap translates product intent into scoped milestones with priority and rough effort.

## Assumptions

- Team: 1-2 full-stack engineers, part-time product/design support.
- Effort units: `S` (1-2 days), `M` (3-5 days), `L` (1-2 weeks).
- Current baseline: v1.0 dashboard and APIs are functional, with serverless constraints.

---

## Milestone 1: Stabilize Core Platform (P0)

Target: reliable auth + persistent data + secure admin primitives.

### Scope

- Managed Postgres migration and schema migrations.
- Harden JWT/session behavior and logout semantics.
- Secure connector-key handling (hashing/rotation).
- Logging + basic metrics/alerts.

### Tickets and estimates

- Postgres + migration setup: `L`
- Auth/session hardening: `M`
- Secret storage hardening: `M`
- Structured logs + metrics: `M`
- Smoke/regression test suite for auth + ingest: `M`

**Total:** `L +`

---

## Milestone 2: Operator Workflow Completion (P1)

Target: every critical operational loop fully visible and efficient in UI.

### Scope

- Campaign detail and outreach management improvements.
- Filtering/search for mentions/alerts/campaigns.
- Admin UX for users, connector keys, and alert endpoints.
- Audit log pagination/export.

### Tickets and estimates

- Campaign/outreach UI expansion: `L`
- Monitoring filters/saved views: `M`
- Admin user management UI: `M`
- Audit log enhancements: `S-M`
- UX polish + empty states + error copy: `S`

**Total:** `L`

---

## Milestone 3: Scale and Automation (P2)

Target: remove synchronous bottlenecks and prepare for high-volume operations.

### Scope

- Queue-backed ingestion and worker processing.
- DLQ + retries + observability for failed jobs.
- External connector integrations and webhook hardening.
- Advanced intelligence (confidence + clustering + multilingual support).

### Tickets and estimates

- Queue infrastructure + worker service: `L`
- DLQ tooling + retries: `M`
- Native platform connectors (initial set): `L`
- Model pipeline enhancements: `L`
- End-to-end load tests and tuning: `M`

**Total:** `XL`

---

## Prioritization Matrix

### Must-have first

1. Persistent DB + migrations
2. Auth/session stability
3. Connector key security
4. Monitoring/alerting baseline

### Next highest ROI

1. Campaign/outreach UX depth
2. Monitoring filters
3. Audit export

### Strategic scale work

1. Queue + workers
2. Native connectors
3. Advanced model workflows

---

## Suggested 6-Week Plan

- **Week 1-2:** Milestone 1 (P0 core hardening)
- **Week 3-4:** Milestone 2 (P1 operator UX completion)
- **Week 5-6:** Milestone 3 foundations (queue + first connector + load tests)

---

## Success Metrics by Milestone

### M1

- Auth success rate > 99%
- No login bounce incidents from session drift
- Zero plaintext connector secrets at rest

### M2

- Median time from alert to campaign launch reduced
- Outreach task completion visibility 100% in UI
- Audit retrieval/export under acceptable latency

### M3

- P95 ingest-to-visible latency target met under load
- Queue failure recovery works via DLQ replay
- Connector ingestion reliability target met

