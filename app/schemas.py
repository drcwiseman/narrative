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


class RegisterRequest(BaseModel):
    email: str
    full_name: str = ""
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class ConnectorKeyCreate(BaseModel):
    name: str
    platform: str


class AlertEndpointCreate(BaseModel):
    name: str
    url: str
    min_harmful_score: float = 0.8


class ConnectorScanRequest(BaseModel):
    constituency: str = "default"
    platforms: list[str] = ["x", "facebook", "whatsapp", "instagram", "telegram", "tiktok"]
    batch_size_per_platform: int = Field(default=2, ge=1, le=20)
