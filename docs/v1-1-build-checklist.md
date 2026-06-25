# Narrative v1.1 Build Checklist

Use this as the implementation tracker across product, frontend, backend, and ops.

## P0 (Critical - make production-safe)

### Data and platform

- [ ] Replace serverless SQLite with managed Postgres (`DATABASE_URL`).
- [ ] Add DB migrations (Alembic or equivalent).
- [ ] Add startup health checks for DB connectivity.

### Auth and session

- [ ] Enforce robust JWT validation (issuer/audience when IdP is introduced).
- [ ] Add refresh-token or short-lived access token strategy.
- [ ] Add logout-all / token revocation strategy (server-side).

### Ingestion reliability

- [ ] Add request idempotency for inbound mentions.
- [ ] Add retry-safe connector ingestion with dedupe keys.
- [ ] Add structured error responses and retry hints for connectors.

### Security

- [ ] Store connector secrets hashed; expose only one-time plaintext on creation.
- [ ] Add webhook signature verification (`X-Signature`) for outbound callbacks.
- [ ] Add baseline rate limiting for auth and ingest endpoints.

### Observability

- [ ] Add structured logs (json) with correlation IDs.
- [ ] Add metrics for ingest latency, failed requests, harmful-alert counts.
- [ ] Add alerting for error-rate spikes and queue backlog (if queue enabled).

---

## P1 (High impact - operator effectiveness)

### UI workflows

- [ ] Campaign details page with embedded outreach task table.
- [ ] Campaign filter/search by constituency and status.
- [ ] Outreach bulk status update and CSV import/export.

### Monitoring and intelligence

- [ ] Time-range filters on mentions/alerts/leaderboard.
- [ ] Alert threshold controls by constituency/topic.
- [ ] Persisted saved views for analysts.

### Admin controls

- [ ] User management UI (role assignment, activation/deactivation).
- [ ] Alert endpoint test-fire button with result logs.
- [ ] Connector key rotation UI and expiration policy.

### Audit and compliance

- [ ] Add filtering/pagination to audit logs.
- [ ] Export audit logs to CSV.
- [ ] Add immutable event IDs and tamper-evidence notes.

---

## P2 (Scale and automation)

### Async architecture

- [ ] Introduce queue-based ingestion pipeline (SQS/Kafka/Rabbit).
- [ ] Move sentiment/topic/harmful scoring to async workers.
- [ ] Add dead-letter queue with re-drive tooling.

### Model improvements

- [ ] Add model confidence scores and triage labels.
- [ ] Add claim-clustering and trend detection.
- [ ] Add multilingual scoring support.

### Integrations

- [ ] Native connectors for X/Facebook/WhatsApp ingestion.
- [ ] CRM integration for outreach state sync.
- [ ] Slack/Teams notifications for harmful-alert routing.

---

## Definition of Done (v1.1 release gate)

- [ ] No auth bounce loops across redeploys/instance changes.
- [ ] Campaign, outreach, and admin workflows visible and actionable in UI.
- [ ] P95 API latency and error-rate dashboards in place.
- [ ] Security review completed for keys, webhooks, and RBAC boundaries.
- [ ] Rollback plan documented and tested.

