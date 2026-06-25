# Narrative Dashboard UI/UX Guidelines

## 1) Header and Session State

The top bar anchors identity and access:

- `Logged in as <email> (<role>)`
- `Logout`

Rules:

- Keep this persistent on all protected pages.
- Always display role (`admin`, `coordinator`, `analyst`, `outreach`) so operators know available controls.
- Redirect unauthenticated users to `/login`.

---

## 2) Primary Workspaces

Split the body into two broad zones:

- **Action zone** (inputs that create/change state)
- **View zone** (live monitoring and decision support)

### A) Ingestion and Campaign Management (Action Zone)

#### Ingest Mention

- Manual entry form:
  - platform
  - author handle/name
  - followers/engagement
  - constituency
  - content
- Primary action: `Submit Mention`

#### Scan All Platforms

- Manual orchestration trigger:
  - constituency
  - platforms list
  - batch size per platform
- Primary action: `Run Scan`

Narrative note:

- In MVP, this simulates cross-platform ingestion using generated data.
- In production, this maps to connector pipelines and queues.

#### Create Campaign

- Create counter-messaging campaigns:
  - campaign name
  - constituency
  - core message

---

### B) Coordination Engine (Operational Zone)

#### Campaigns List

- Show active campaigns.
- Include `Refresh Campaigns`.
- Empty state copy:
  - `No campaigns yet. Create a campaign above to get started.`

#### Outreach Tasks

- `Create Outreach Tasks`: assign KOL handles to a campaign.
- `Load Tasks`: view assignments by campaign.
- `Update Outreach Status`: move task state:
  - `pending`
  - `contacted`
  - `completed`
  - `failed`

---

## 3) Monitoring and Intelligence (Live Data Zone)

Display as command-center cards:

- **Live Mention Feed**
  - real-time list of analyzed mentions (SSE)
- **Harmful Alerts**
  - filtered high-risk mentions with harmful score visibility
- **KOL Leaderboard**
  - ranked influence list with tier badge and manual refresh

Optional control:

- **KOL Rescore**
  - constituency-level recalculation trigger

---

## 4) System Administration (Infrastructure Zone)

Visually separate admin capabilities:

- **Connector Keys**
  - create + list keys
- **Alert Endpoints**
  - create + list outbound webhook routes
- **Audit Logs**
  - read action trail by actor/action/resource

Access:

- Admin-only visibility for sensitive sections.
- API-side authorization must still enforce role checks (`403` on forbidden operations).

---

## 5) Data Flow Narrative

```text
[Ingest Mention / Run Scan]
        |
        v
[Live Mention Feed] --(if harmful)--> [Harmful Alerts]
        |                                   |
  (recalculate)                             v
        |                            [Create Campaign]
        v                                   |
[KOL Leaderboard]                           v
        |                          [Create Outreach Tasks]
        +--------------(assign KOLs)-------->|
                                             v
                                  [Update Outreach Status]
```

Lifecycle:

1. **Spark**: operator ingests or scans.
2. **Reaction**: mention appears live; harmful items surface in alerts; KOLs update.
3. **Countermeasure**: campaign created and outreach tasks assigned.
4. **Paper trail**: actions logged in audit history.

---

## 6) Phase 2 Production Specifications

### Identity and Access

- OIDC/OAuth2 provider (Auth0/Keycloak/Clerk, etc.)
- strict RBAC in UI and API
- JWT claims for role/scope

### Ingestion

- webhook receivers + connector workers
- rate-limit and token rotation handling
- `Submit Mention` becomes debug/manual ingestion utility

### Intelligence Pipeline

- queue-backed async processing (SQS/Kafka/Rabbit/Upstash)
- workers for sentiment/topic/harmful scoring
- dead-letter queue for failed payloads

### Operations and Scale

- event-driven KOL updates
- background bulk rescore jobs
- CRM/messaging integration for outreach status synchronization

### Admin and Compliance

- one-time visible connector secrets with hashed-at-rest storage
- webhook signing + retries + exponential backoff
- append-only audit/compliance storage

---

## 7) Architecture Comparison

```text
PHASE 1 (MVP)
User Action -> Ingest API -> Inline scoring -> SQLite (/tmp) -> UI (SSE)

PHASE 2 (Production)
Webhooks -> Ingest API -> Queue -> ML Workers -> Distributed DB -> UI (SSE/WebSockets)
                                  |
                                  +-> DLQ / Retry
```

---

## 8) Technical Blueprint Summary

| Component | Phase 1 (MVP) | Phase 2 (Production) |
| --- | --- | --- |
| Authentication | local JWT session + RBAC basics | OIDC with scoped permissions |
| Data persistence | SQLite (`/tmp` fallback on serverless) | managed Postgres cluster |
| Ingestion | manual + simulated scan | native webhook/connectors |
| Model execution | synchronous rule-based scoring | async distributed workers |
| Fault tolerance | minimal retry logic | queue, retries, DLQ |
| Audit trails | basic DB records | immutable compliance-grade logging |

