from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class FieldDefault(BaseModel):
    """A remembered answer for one intake field, scoped to a user (and optionally a
    hubspace) and a request type. ``confidence`` is the number of times the user has
    submitted this same value; it drives the ask -> suggest -> silent progression."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    hubspace_id: Optional[str] = None  # None = user-global
    service_type: str
    field: str
    value: str
    confidence: int = 1
    always_confirm: bool = False
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
