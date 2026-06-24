from datetime import datetime

from pydantic import BaseModel, Field


class MentionCreate(BaseModel):
    platform: str
    author_handle: str
    author_name: str = ""
    followers: int = 0
    engagement_rate: float = 0.0
    constituency: str = "default"
    content: str = Field(min_length=1)
    posted_at: datetime | None = None


class MentionOut(BaseModel):
    id: int
    platform: str
    author_handle: str
    author_name: str
    followers: int
    engagement_rate: float
    constituency: str
    content: str
    posted_at: datetime
    sentiment_score: float
    topic: str
    harmful_claim_score: float
    is_harmful: bool

    class Config:
        from_attributes = True


class KOLOut(BaseModel):
    handle: str
    name: str
    constituency: str
    followers: int
    engagement_rate: float
    mention_count: int
    influence_score: float
    tier: str

    class Config:
        from_attributes = True


class CampaignCreate(BaseModel):
    name: str
    message: str
    constituency: str = "default"


class OutreachCreate(BaseModel):
    kol_handles: list[str]
    notes: str = ""


class OutreachStatusUpdate(BaseModel):
    status: str
    notes: str = ""
