from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
import uuid


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageBase(BaseModel):
    content: str
    role: MessageRole = MessageRole.USER


class MessageCreate(MessageBase):
    pass


class Message(MessageBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tokens_used: Optional[int] = None
    response_time_ms: Optional[int] = None
    intent: Optional[str] = None
    user_display_name: Optional[str] = None
    user_email: Optional[str] = None

    class Config:
        from_attributes = True
