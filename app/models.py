from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Mention(Base):
    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    author_handle: Mapped[str] = mapped_column(String(128), index=True)
    author_name: Mapped[str] = mapped_column(String(128), default="")
    followers: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    constituency: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text)
    origin_ip: Mapped[str] = mapped_column(String(64), default="", index=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    analysis: Mapped["Analysis"] = relationship(back_populates="mention", uselist=False)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mention_id: Mapped[int] = mapped_column(ForeignKey("mentions.id"), unique=True)
    sentiment_score: Mapped[float] = mapped_column(Float, index=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    harmful_claim_score: Mapped[float] = mapped_column(Float, index=True)
    is_harmful: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mention: Mapped[Mention] = relationship(back_populates="analysis")


class MentionIngestTrace(Base):
    __tablename__ = "mention_ingest_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mention_id: Mapped[int] = mapped_column(ForeignKey("mentions.id"), unique=True, index=True)
    source_ip: Mapped[str] = mapped_column(String(64), index=True)
    forwarded_for: Mapped[str] = mapped_column(Text, default="")
    user_agent: Mapped[str] = mapped_column(String(512), default="")
    ingest_channel: Mapped[str] = mapped_column(String(64), default="unknown", index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class KOLScore(Base):
    __tablename__ = "kol_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    handle: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    constituency: Mapped[str] = mapped_column(String(128), index=True)
    followers: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    influence_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    tier: Mapped[str] = mapped_column(String(16), default="micro", index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    message: Mapped[str] = mapped_column(Text)
    constituency: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    outreach_items: Mapped[list["OutreachTask"]] = relationship(back_populates="campaign")


class OutreachTask(Base):
    __tablename__ = "outreach_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    kol_handle: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    campaign: Mapped[Campaign] = relationship(back_populates="outreach_items")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="analyst", index=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConnectorKey(Base):
    __tablename__ = "connector_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(64), index=True)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AlertEndpoint(Base):
    __tablename__ = "alert_endpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    url: Mapped[str] = mapped_column(String(512))
    min_harmful_score: Mapped[float] = mapped_column(Float, default=0.8)
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_email: Mapped[str] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    prev_hash: Mapped[str] = mapped_column(String(128), default="")
    event_hash: Mapped[str] = mapped_column(String(128), index=True, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    jti: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    reason: Mapped[str] = mapped_column(String(64), default="logout")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RevokedSubject(Base):
    __tablename__ = "revoked_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    revoke_before_epoch: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(128), index=True)
    response_json: Mapped[str] = mapped_column(Text, default="{}")
    status_code: Mapped[int] = mapped_column(Integer, default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SavedView(Base):
    __tablename__ = "saved_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_email: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(128))
    view_type: Mapped[str] = mapped_column(String(64), index=True)
    query_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QueueJob(Base):
    __tablename__ = "queue_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeadLetterJob(Base):
    __tablename__ = "dead_letter_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    queue_job_id: Mapped[int] = mapped_column(Integer, index=True)
    job_type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DetectionRuleConfig(Base):
    __tablename__ = "detection_rule_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    negative_words_json: Mapped[str] = mapped_column(Text, default="[]")
    harmful_patterns_json: Mapped[str] = mapped_column(Text, default="[]")
    topic_keywords_json: Mapped[str] = mapped_column(Text, default="{}")
    default_harmful_threshold: Mapped[float] = mapped_column(Float, default=0.5)
    platform_harmful_thresholds_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IntegrationCredential(Base):
    __tablename__ = "integration_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    platform: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    webhook_secret: Mapped[str] = mapped_column(String(512), default="")
    verify_token: Mapped[str] = mapped_column(String(512), default="")
    is_active: Mapped[int] = mapped_column(Integer, default=1, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    sector: Mapped[str] = mapped_column(String(128), default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(Integer, index=True)
    user_email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(64), default="analyst", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Narrative(Base):
    __tablename__ = "narratives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    constituency: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(64), default="emerging", index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NarrativeEvent(Base):
    __tablename__ = "narrative_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    narrative_id: Mapped[int] = mapped_column(Integer, index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str] = mapped_column(String(255))
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    narrative_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    mention_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    text: Mapped[str] = mapped_column(Text)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    status: Mapped[str] = mapped_column(String(64), default="under_review", index=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class EmotionSignal(Base):
    __tablename__ = "emotion_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mention_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    anger: Mapped[float] = mapped_column(Float, default=0.0)
    fear: Mapped[float] = mapped_column(Float, default=0.0)
    hope: Mapped[float] = mapped_column(Float, default=0.0)
    confusion: Mapped[float] = mapped_column(Float, default=0.0)
    trust: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReportRun(Base):
    __tablename__ = "report_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_email: Mapped[str] = mapped_column(String(255), index=True)
    report_type: Mapped[str] = mapped_column(String(64), index=True)
    format: Mapped[str] = mapped_column(String(32), index=True)
    filters_json: Mapped[str] = mapped_column(Text, default="{}")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
