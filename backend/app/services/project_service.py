"""Supabase-backed project CRUD service.

Projects are containers that conversations (discussions) can be filed under.
Nesting is limited to a single level (parent ▸ child); the DB trigger
`enforce_project_nesting_depth` is the source of truth for that constraint.
"""
import logging
from datetime import datetime
from typing import List, Optional

from app.database.supabase_client import get_supabase_client
from app.models import Project

logger = logging.getLogger(__name__)

_project_service: Optional["ProjectService"] = None

# Columns a client is allowed to set/update on a project.
_EDITABLE_FIELDS = (
    "name",
    "instructions",
    "locked_intent",
    "locked_service_type",
    "icon",
    "color",
    "parent_project_id",
)


class ProjectService:
    """Manages projects in Supabase."""

    def __init__(self):
        self._client = get_supabase_client()

    def list_projects(self, user_id: str) -> List[Project]:
        resp = (
            self._client.table("projects")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return [self._row_to_project(r) for r in (resp.data or [])]

    def get_project(self, project_id: str, user_id: str) -> Optional[Project]:
        resp = (
            self._client.table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None
        return self._row_to_project(resp.data)

    def create_project(self, user_id: str, **fields) -> Project:
        row = {"user_id": user_id}
        for field in _EDITABLE_FIELDS:
            if fields.get(field) is not None:
                row[field] = fields[field]
        resp = self._client.table("projects").insert(row).execute()
        return self._row_to_project(resp.data[0])

    def update_project(
        self, project_id: str, user_id: str, **updates
    ) -> Optional[Project]:
        payload: dict = {"updated_at": datetime.utcnow().isoformat()}
        for field in _EDITABLE_FIELDS:
            if field in updates:
                payload[field] = updates[field]

        resp = (
            self._client.table("projects")
            .update(payload)
            .eq("id", project_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not resp.data:
            return None
        return self._row_to_project(resp.data[0])

    def delete_project(self, project_id: str, user_id: str) -> bool:
        resp = (
            self._client.table("projects")
            .delete()
            .eq("id", project_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(resp.data)

    # ── Row mappers ──────────────────────────────────────────────

    @staticmethod
    def _row_to_project(row: dict) -> Project:
        return Project(
            id=row["id"],
            name=row.get("name", "New Project"),
            instructions=row.get("instructions"),
            locked_intent=row.get("locked_intent"),
            locked_service_type=row.get("locked_service_type"),
            icon=row.get("icon"),
            color=row.get("color"),
            parent_project_id=row.get("parent_project_id"),
            created_at=row.get("created_at", datetime.utcnow()),
            updated_at=row.get("updated_at", datetime.utcnow()),
        )


def get_project_service() -> ProjectService:
    global _project_service
    if _project_service is None:
        _project_service = ProjectService()
    return _project_service
