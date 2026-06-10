"""Supabase-backed discussion and message CRUD service."""
import logging
from datetime import datetime
from typing import List, Optional

from app.database.supabase_client import get_supabase_client
from app.models import Discussion, Message, MessageRole

logger = logging.getLogger(__name__)

_discussion_service: Optional["DiscussionService"] = None


class DiscussionService:
    """Manages discussions and messages in Supabase."""

    def __init__(self):
        self._client = get_supabase_client()

    # ── Discussions ──────────────────────────────────────────────

    def list_discussions(self, user_id: str) -> List[Discussion]:
        resp = (
            self._client.table("discussions")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        return [self._row_to_discussion(r) for r in (resp.data or [])]

    def get_discussion(self, discussion_id: str, user_id: str) -> Optional[Discussion]:
        resp = (
            self._client.table("discussions")
            .select("*")
            .eq("id", discussion_id)
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None

        discussion = self._row_to_discussion(resp.data)
        msg_resp = (
            self._client.table("messages")
            .select("*")
            .eq("discussion_id", discussion_id)
            .order("created_at", desc=False)
            .execute()
        )
        discussion.messages = [self._row_to_message(m) for m in (msg_resp.data or [])]
        return discussion

    def create_discussion(self, user_id: str, title: str = "New Chat") -> Discussion:
        resp = (
            self._client.table("discussions")
            .insert({"user_id": user_id, "title": title})
            .execute()
        )
        return self._row_to_discussion(resp.data[0])

    def update_discussion(
        self, discussion_id: str, user_id: str, **updates
    ) -> Optional[Discussion]:
        payload: dict = {"updated_at": datetime.utcnow().isoformat()}
        for field in ("title", "is_active", "intent"):
            if field in updates:
                payload[field] = updates[field]

        resp = (
            self._client.table("discussions")
            .update(payload)
            .eq("id", discussion_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not resp.data:
            return None
        return self._row_to_discussion(resp.data[0])

    def delete_discussion(self, discussion_id: str, user_id: str) -> bool:
        resp = (
            self._client.table("discussions")
            .delete()
            .eq("id", discussion_id)
            .eq("user_id", user_id)
            .execute()
        )
        return bool(resp.data)

    def delete_all_discussions(self, user_id: str) -> int:
        resp = (
            self._client.table("discussions")
            .delete()
            .eq("user_id", user_id)
            .execute()
        )
        return len(resp.data) if resp.data else 0

    def deactivate_all(self, user_id: str) -> None:
        self._client.table("discussions").update(
            {"is_active": False}
        ).eq("user_id", user_id).eq("is_active", True).execute()

    # ── Messages ─────────────────────────────────────────────────

    def add_message(
        self,
        discussion_id: str,
        message: Message,
        user_display_name: Optional[str] = None,
        user_email: Optional[str] = None,
    ) -> None:
        row = {
            "id": message.id,
            "discussion_id": discussion_id,
            "role": message.role.value,
            "content": message.content,
            "tokens_used": message.tokens_used,
            "response_time_ms": message.response_time_ms,
            "intent": message.intent,
            "user_display_name": user_display_name,
            "user_email": user_email,
        }
        self._client.table("messages").insert(row).execute()
        self._client.table("discussions").update(
            {"updated_at": datetime.utcnow().isoformat()}
        ).eq("id", discussion_id).execute()

    def get_context_messages(
        self, discussion_id: str, limit: int = 20
    ) -> List[Message]:
        resp = (
            self._client.table("messages")
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
            is_active=row.get("is_active", False),
            intent=row.get("intent"),
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
            intent=row.get("intent"),
        )


def get_discussion_service() -> DiscussionService:
    global _discussion_service
    if _discussion_service is None:
        _discussion_service = DiscussionService()
    return _discussion_service
