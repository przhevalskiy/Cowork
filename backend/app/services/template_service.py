"""Supabase-backed template CRUD service.

Templates are reusable request starters. A template's `body` seeds a new task
(chat), and an optional `hubspace_id` files that task under a hubspace so its
locked request type applies.
"""
import logging
from datetime import datetime
from typing import List, Optional

from app.database.supabase_client import get_supabase_client
from app.models import Template

logger = logging.getLogger(__name__)

_template_service: Optional["TemplateService"] = None

_EDITABLE_FIELDS = ("name", "description", "body", "hubspace_id", "icon", "color")


class TemplateService:
    """Manages templates in Supabase."""

    def __init__(self):
        self._client = get_supabase_client()

    def list_templates(self, user_id: str) -> List[Template]:
        resp = (
            self._client.table("templates")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return [self._row_to_template(r) for r in (resp.data or [])]

    def get_template(self, template_id: str, user_id: str) -> Optional[Template]:
        resp = (
            self._client.table("templates")
            .select("*")
            .eq("id", template_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not resp or not resp.data:
            return None
        return self._row_to_template(resp.data)

    def create_template(self, user_id: str, **fields) -> Template:
        row = {"user_id": user_id}
        for field in _EDITABLE_FIELDS:
            if fields.get(field) is not None:
                row[field] = fields[field]
        resp = self._client.table("templates").insert(row).execute()
        return self._row_to_template(resp.data[0])

    def update_template(
        self, template_id: str, user_id: str, **updates
    ) -> Optional[Template]:
        payload: dict = {"updated_at": datetime.utcnow().isoformat()}
        for field in _EDITABLE_FIELDS:
            if field in updates:
                payload[field] = updates[field]

        resp = (
            self._client.table("templates")
            .update(payload)
            .eq("id", template_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not resp.data:
            return None
        return self._row_to_template(resp.data[0])

    def delete_template(self, template_id: str, user_id: str) -> bool:
        resp = (
            self._client.table("templates")
            .delete()
            .eq("id", template_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(resp.data)

    @staticmethod
    def _row_to_template(row: dict) -> Template:
        return Template(
            id=row["id"],
            name=row.get("name", "New Template"),
            description=row.get("description"),
            body=row.get("body", ""),
            hubspace_id=row.get("hubspace_id"),
            icon=row.get("icon"),
            color=row.get("color"),
            created_at=row.get("created_at", datetime.utcnow()),
            updated_at=row.get("updated_at", datetime.utcnow()),
        )


def get_template_service() -> TemplateService:
    global _template_service
    if _template_service is None:
        _template_service = TemplateService()
    return _template_service
