# Narrative Monitoring System (Full Build)

Production-style full system for:

- real-time narrative monitoring
- sentiment/topic/harmful-claim analysis
- social mention logging across direct API and connector endpoints
- KOL intelligence with micro/macro/mega tier scoring
- campaign and outreach workflow coordination
- JWT auth, role-based access control, connector API keys, audit logs
- alert webhook routing for harmful claims

## Stack

- FastAPI + Uvicorn
- SQLAlchemy with `DATABASE_URL` support (SQLite/Postgres)
- Server-sent events (SSE) for live updates
- Plain HTML dashboard

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open: <http://127.0.0.1:8000>

## Seed demo data

In another terminal, with server running:

```bash
source .venv/bin/activate
python scripts/seed_demo.py
```

## Authentication flow

1. Register first user:

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","full_name":"Admin","password":"supersecret"}'
```

2. Use `access_token` as bearer token:

```bash
Authorization: Bearer <token>
```

## Main API endpoints

### Auth and admin

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `POST /api/auth/logout-all`
- `GET /api/auth/me`
- `POST /api/admin/connector-keys` (admin)
- `GET /api/admin/connector-keys` (admin/coordinator)
- `POST /api/admin/connector-keys/{key_id}/rotate` (admin)
- `POST /api/admin/alert-endpoints` (admin)
- `GET /api/admin/alert-endpoints` (admin/coordinator)
- `POST /api/admin/alert-endpoints/{endpoint_id}/test` (admin)
- `GET /api/admin/audit-logs` (admin)
- `GET /api/admin/audit-logs/export.csv` (admin)
- `GET /api/admin/users` (admin)
- `PATCH /api/admin/users/{user_id}/role?role=<role>` (admin)
- `PATCH /api/admin/users/{user_id}/active?is_active=0|1` (admin)

### Monitoring and operations

- `POST /api/mentions` ingest and auto-analyze mention
- `POST /api/connectors/mentions` ingest via `X-Connector-Token` header
- `GET /api/connectors/x/webhook` X CRC verification endpoint
- `POST /api/connectors/x/webhook` native X webhook receiver
- `GET /api/connectors/facebook/webhook` Facebook webhook verification endpoint
- `POST /api/connectors/facebook/webhook` native Facebook webhook receiver
- `GET /api/connectors/whatsapp/webhook` WhatsApp webhook verification endpoint
- `POST /api/connectors/whatsapp/webhook` native WhatsApp webhook receiver
- `POST /api/connectors/slack/events` Slack Events API receiver (url verification + signed events)
- `POST /api/connectors/scan-all` scan all supported social platforms and ingest generated mentions
- `GET /api/connectors/platforms` list supported social sources
- `GET /api/monitoring/mentions` recent analyzed mentions
- `GET /api/monitoring/alerts` harmful mention alerts
- `GET /api/monitoring/stream?token=<jwt>` SSE live event stream
- `GET /api/monitoring/alerts/export.csv` CSV export for harmful alerts
- `GET /api/monitoring/trends` topic/platform trend aggregates
- `POST /api/monitoring/saved-views` store analyst view presets
- `GET /api/monitoring/saved-views` retrieve analyst view presets
- `GET /api/kols/leaderboard` KOL rankings
- `POST /api/kols/rescore?constituency=<name>` bulk KOL rescore
- `POST /api/campaigns` create campaign message
- `GET /api/campaigns` list campaigns
- `POST /api/campaigns/{campaign_id}/outreach` attach KOL outreach list
- `GET /api/campaigns/{campaign_id}/outreach` list outreach tasks
- `PATCH /api/campaigns/outreach/{task_id}` update outreach status

### Queue and DLQ

- `POST /api/queue/jobs` enqueue async job
- `POST /api/queue/process` process pending jobs manually (admin)
- `GET /api/queue/jobs` inspect queue states
- `GET /api/queue/dlq` inspect dead-lettered jobs

## Role model

- `admin`: full access, user role updates, connector keys, alert endpoints, audit logs
- `coordinator`: campaigns, outreach, rescore, scan-all, monitoring
- `analyst`: monitoring, ingestion, leaderboard, scan-all
- `outreach`: monitoring, leaderboard, outreach status updates

## Notes

- X, Facebook, and WhatsApp connectors now support native webhook verification and signature checks. If signatures are absent (for manual tests), fallback shared-secret headers are accepted.
- Ingestion supports optional `Idempotency-Key` header for dedupe-safe retries.
- Harmful claim detection and sentiment are rule-based for deterministic behavior and low-cost runtime.
- Vercel runtime: without `DATABASE_URL`, the app auto-uses `/tmp/narrative.db` so SQLite works on serverless.
- For production retention, set `DATABASE_URL` to managed Postgres.
- Set `JWT_SECRET` in production.
- Use `python scripts/db_migrate.py` to ensure schema before serving.
- Configure platform secrets (`X_WEBHOOK_SECRET`, `FACEBOOK_WEBHOOK_SECRET`, `WHATSAPP_WEBHOOK_SECRET`) and verify tokens (`FACEBOOK_WEBHOOK_VERIFY_TOKEN`, `WHATSAPP_WEBHOOK_VERIFY_TOKEN`) for native webhook receivers.
- Configure Slack (`SLACK_WEBHOOK_URL`, `SLACK_SIGNING_SECRET`, optional `SLACK_VERIFICATION_TOKEN`) for outbound alerts and signed inbound Slack events.
- Configure `SLACK_WEBHOOK_URL` and `CRM_WEBHOOK_URL` to activate external outbound integrations.
- Set `APP_BASE_URL` so Slack alerts include one-click dashboard links.
- Optional severity routing: set `SLACK_CRITICAL_WEBHOOK_URL` and tune `SLACK_ALERT_THRESHOLD` / `SLACK_CRITICAL_THRESHOLD`.

## Product and UX docs

- UI/UX narrative guidelines: `docs/ui-ux-narrative-guidelines.md`
- v1.1 build checklist: `docs/v1-1-build-checklist.md`
- v1.1 roadmap: `docs/v1-1-roadmap.md`
- v1.1 execution status: `docs/roadmap-execution-status.md`
