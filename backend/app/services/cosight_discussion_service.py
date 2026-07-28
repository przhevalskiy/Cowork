"""
CoSight discussion and message CRUD — mirrors Cowork's DiscussionService
but writes to `cosight_discussions` and `cosight_messages` tables.
No auth dependency (auth is deferred to a later phase).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional

from app.database.supabase_client import get_supabase_client
from app.models.message import Message, MessageRole
from app.models.discussion import Discussion

logger = logging.getLogger(__name__)

_service: Optional["CoSightDiscussionService"] = None


class CoSightDiscussionService:
    def __init__(self):
        self._client = get_supabase_client()

    # ── Discussions ──────────────────────────────────────────────

    def list_discussions(self, user_id: Optional[str] = None) -> List[Discussion]:
        query = self._client.table("cosight_discussions").select("*")
        if user_id:
            query = query.eq("user_id", user_id)
        resp = query.order("updated_at", desc=True).execute()
        return [self._row_to_discussion(r) for r in (resp.data or [])]

    def get_discussion(self, discussion_id: str) -> Optional[Discussion]:
        resp = (
            self._client.table("cosight_discussions")
            .select("*")
            .eq("id", discussion_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None
        discussion = self._row_to_discussion(resp.data)
        msg_resp = (
            self._client.table("cosight_messages")
            .select("*")
            .eq("discussion_id", discussion_id)
            .order("created_at", desc=False)
            .execute()
        )
        discussion.messages = [self._row_to_message(m) for m in (msg_resp.data or [])]
        return discussion

    def create_discussion(self, title: str = "New Chat", user_id: Optional[str] = None) -> Discussion:
        row: dict = {"title": title}
        if user_id:
            row["user_id"] = user_id
        resp = self._client.table("cosight_discussions").insert(row).execute()
        return self._row_to_discussion(resp.data[0])

    def update_discussion(self, discussion_id: str, **updates) -> Optional[Discussion]:
        payload: dict = {"updated_at": datetime.utcnow().isoformat()}
        for field in ("title",):
            if field in updates:
                payload[field] = updates[field]
        resp = (
            self._client.table("cosight_discussions")
            .update(payload)
            .eq("id", discussion_id)
            .execute()
        )
        if not resp.data:
            return None
        return self._row_to_discussion(resp.data[0])

    def delete_discussion(self, discussion_id: str) -> bool:
        resp = (
            self._client.table("cosight_discussions")
            .delete()
            .eq("id", discussion_id)
            .execute()
        )
        return bool(resp.data)

    # ── Messages ─────────────────────────────────────────────────

    def add_message(self, discussion_id: str, message: Message) -> None:
        row = {
            "id": message.id,
            "discussion_id": discussion_id,
            "role": message.role.value,
            "content": message.content,
            "tokens_used": message.tokens_used,
            "response_time_ms": message.response_time_ms,
        }
        self._client.table("cosight_messages").insert(row).execute()
        self._client.table("cosight_discussions").update(
            {"updated_at": datetime.utcnow().isoformat()}
        ).eq("id", discussion_id).execute()

    def get_context_messages(self, discussion_id: str, limit: int = 20) -> List[Message]:
        resp = (
            self._client.table("cosight_messages")
            .select("*")
            .eq("discussion_id", discussion_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        messages = [self._row_to_message(m) for m in (resp.data or [])]
        messages.reverse()
        return messages

    # ── Row mappers ──────────────────────────────────────────────

    @staticmethod
    def _row_to_discussion(row: dict) -> Discussion:
        return Discussion(
            id=row["id"],
            title=row.get("title", "New Chat"),
            is_active=False,
            created_at=row.get("created_at", datetime.utcnow()),
            updated_at=row.get("updated_at", datetime.utcnow()),
            messages=[],
        )

    @staticmethod
    def _row_to_message(row: dict) -> Message:
        return Message(
            id=row["id"],
            content=row["content"],
            role=MessageRole(row["role"]),
            timestamp=row.get("created_at", datetime.utcnow()),
            tokens_used=row.get("tokens_used"),
            response_time_ms=row.get("response_time_ms"),
        )


def get_cosight_discussion_service() -> CoSightDiscussionService:
    global _service
    if _service is None:
        _service = CoSightDiscussionService()
    return _service
