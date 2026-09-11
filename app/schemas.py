from datetime import datetime
from pydantic import BaseModel


class ContentBase(BaseModel):
    topic: str
    hook: str
    script: str
    caption: str
    hashtags: str
    visual_notes: str = ""
    disclaimer: str = ""


class ContentCreate(ContentBase):
    pass


class ContentUpdate(BaseModel):
    topic: str | None = None
    hook: str | None = None
    script: str | None = None
    caption: str | None = None
    hashtags: str | None = None
    visual_notes: str | None = None
    status: str | None = None
    scheduled_at: datetime | None = None


class ContentResponse(ContentBase):
    id: int
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None
    tiktok_post_id: str | None
    error_log: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
