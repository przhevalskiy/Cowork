from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import uuid


class TemplateBase(BaseModel):
    """Base template model."""
    name: str = "New Template"
    description: Optional[str] = None
    body: str = ""
    hubspace_id: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class TemplateCreate(TemplateBase):
    """Model for creating a new template."""
    pass


class TemplateUpdate(BaseModel):
    """Model for updating a template (all fields optional)."""
    name: Optional[str] = None
    description: Optional[str] = None
    body: Optional[str] = None
    hubspace_id: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class Template(TemplateBase):
    """Full template model with all fields."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
