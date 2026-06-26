from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid


class ProjectBase(BaseModel):
    """Base project model."""
    name: str = "New Project"
    instructions: Optional[str] = None
    # Request type that tasks started in this project are locked to.
    locked_intent: Optional[str] = None
    locked_service_type: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    parent_project_id: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Model for creating a new project."""
    pass


class ProjectUpdate(BaseModel):
    """Model for updating a project (all fields optional)."""
    name: Optional[str] = None
    instructions: Optional[str] = None
    locked_intent: Optional[str] = None
    locked_service_type: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    parent_project_id: Optional[str] = None


class Project(ProjectBase):
    """Full project model with all fields."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class ProjectFile(BaseModel):
    """A persistent file attached to a project ("Files & sources")."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: Optional[int] = None
    storage_path: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
