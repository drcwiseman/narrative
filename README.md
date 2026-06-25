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
- `GET /api/auth/me`
- `POST /api/admin/connector-keys` (admin)
- `GET /api/admin/connector-keys` (admin/coordinator)
- `POST /api/admin/alert-endpoints` (admin)
- `GET /api/admin/alert-endpoints` (admin/coordinator)
- `GET /api/admin/audit-logs` (admin)
- `GET /api/admin/users` (admin)
- `PATCH /api/admin/users/{user_id}/role?role=<role>` (admin)

### Monitoring and operations

- `POST /api/mentions` ingest and auto-analyze mention
- `POST /api/connectors/mentions` ingest via `X-Connector-Token` header
- `POST /api/connectors/scan-all` scan all supported social platforms and ingest generated mentions
- `GET /api/connectors/platforms` list supported social sources
- `GET /api/monitoring/mentions` recent analyzed mentions
- `GET /api/monitoring/alerts` harmful mention alerts
- `GET /api/monitoring/stream?token=<jwt>` SSE live event stream
- `GET /api/monitoring/alerts/export.csv` CSV export for harmful alerts
- `GET /api/kols/leaderboard` KOL rankings
- `POST /api/kols/rescore?constituency=<name>` bulk KOL rescore
- `POST /api/campaigns` create campaign message
- `GET /api/campaigns` list campaigns
- `POST /api/campaigns/{campaign_id}/outreach` attach KOL outreach list
- `GET /api/campaigns/{campaign_id}/outreach` list outreach tasks
- `PATCH /api/campaigns/outreach/{task_id}` update outreach status

## Role model

- `admin`: full access, user role updates, connector keys, alert endpoints, audit logs
- `coordinator`: campaigns, outreach, rescore, scan-all, monitoring
- `analyst`: monitoring, ingestion, leaderboard, scan-all
- `outreach`: monitoring, leaderboard, outreach status updates

## Notes

- Platform ingestion is modeled as API ingestion. You can integrate real connectors for X/Facebook/WhatsApp later by posting collected mentions into `POST /api/mentions`.
- Harmful claim detection and sentiment are rule-based for deterministic behavior and low-cost runtime.
- Vercel runtime: without `DATABASE_URL`, the app auto-uses `/tmp/narrative.db` so SQLite works on serverless.
- For production retention, set `DATABASE_URL` to managed Postgres.
- Set `JWT_SECRET` in production.
