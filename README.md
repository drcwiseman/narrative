# Narrative Monitoring System (MVP)

End-to-end MVP for:

- real-time narrative monitoring
- AI-like sentiment/topic/harmful-claim analysis
- social mention logging across multiple platforms
- KOL identification with micro/macro/mega tier scoring
- KOL leaderboard and bulk constituency rescore
- counter-messaging campaign and outreach coordination

## Stack

- FastAPI + Uvicorn
- SQLite + SQLAlchemy
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

## Main API endpoints

- `POST /api/mentions` ingest and auto-analyze mention
- `GET /api/monitoring/mentions` recent analyzed mentions
- `GET /api/monitoring/alerts` harmful mention alerts
- `GET /api/monitoring/stream` SSE live event stream
- `GET /api/kols/leaderboard` KOL rankings
- `POST /api/kols/rescore?constituency=<name>` bulk KOL rescore
- `POST /api/campaigns` create campaign message
- `GET /api/campaigns` list campaigns
- `POST /api/campaigns/{campaign_id}/outreach` attach KOL outreach list
- `GET /api/campaigns/{campaign_id}/outreach` list outreach tasks
- `PATCH /api/campaigns/outreach/{task_id}` update outreach status

## Notes

- Platform ingestion is modeled as API ingestion. You can integrate real connectors for X/Facebook/WhatsApp later by posting collected mentions into `POST /api/mentions`.
- Harmful claim detection and sentiment are rule-based in this MVP for reliability and zero external model dependency.
# narrative
# narrative
