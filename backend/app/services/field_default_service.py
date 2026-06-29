"""Supabase-backed learned field defaults.

Each row remembers one answer a user has given for an intake field, scoped to a
request type (and optionally a hubspace). On every submission we diff what the
user submitted against what we pre-filled: unchanged fields gain confidence and
march toward being auto-applied silently, edited fields are overwritten and reset.
There is no background job — learning happens inline at submit time.
"""
import logging
from datetime import datetime
from typing import List, Optional

from app.database.supabase_client import get_supabase_client
from app.models import FieldDefault

logger = logging.getLogger(__name__)

_field_default_service: Optional["FieldDefaultService"] = None

# Fields that pre-fill but must always be restated for confirmation, never silent.
ALWAYS_CONFIRM_FIELDS = {"service_type"}

# Intake fields that are per-request by nature — never worth remembering.
_VOLATILE_FIELDS = {"brief", "summary", "is_event"}


class FieldDefaultService:
    """Manages learned intake defaults in Supabase."""

    def __init__(self):
        self._client = get_supabase_client()

    def get_defaults(
        self, user_id: str, service_type: str, hubspace_id: Optional[str] = None
    ) -> List[FieldDefault]:
        """Defaults for this user + request type. A hubspace-scoped row overrides a
        user-global (NULL hubspace) row for the same field."""
        rows = (
            self._client.table("field_defaults")
            .select("*")
            .eq("user_id", user_id)
            .eq("service_type", service_type)
            .execute()
            .data
            or []
        )
        merged: dict[str, FieldDefault] = {}
        # Apply global rows first, then let a matching hubspace row overwrite them.
        for row in sorted(rows, key=lambda r: r.get("hubspace_id") is not None):
            row_hub = row.get("hubspace_id")
            if row_hub is None or row_hub == hubspace_id:
                merged[row["field"]] = self._row_to_default(row)
        return list(merged.values())

    def learn(
        self,
        user_id: str,
        service_type: str,
        submitted: dict,
        injected: dict,
        hubspace_id: Optional[str] = None,
    ) -> None:
        """Update defaults from a confirmed submission. Unchanged pre-fills gain
        confidence; edited or new values overwrite and reset to confidence 1."""
        if not service_type:
            return
        for field, value in submitted.items():
            if field in _VOLATILE_FIELDS or not isinstance(value, str) or not value.strip():
                continue
            try:
                if injected.get(field) == value:
                    self._bump(user_id, service_type, field, value, hubspace_id)
                else:
                    self._write(user_id, service_type, field, value, hubspace_id, confidence=1)
            except Exception as e:  # never let learning break a submission
                logger.warning(f"field_defaults learn failed for '{field}': {e}")

    # -- internals ----------------------------------------------------------

    def _find(self, user_id, service_type, field, hubspace_id):
        q = (
            self._client.table("field_defaults")
            .select("*")
            .eq("user_id", user_id)
            .eq("service_type", service_type)
            .eq("field", field)
        )
        q = q.is_("hubspace_id", "null") if hubspace_id is None else q.eq("hubspace_id", hubspace_id)
        rows = q.limit(1).execute().data or []
        return rows[0] if rows else None

    def _bump(self, user_id, service_type, field, value, hubspace_id):
        existing = self._find(user_id, service_type, field, hubspace_id)
        if existing is None:
            self._write(user_id, service_type, field, value, hubspace_id, confidence=1)
        else:
            self._client.table("field_defaults").update(
                {"confidence": existing.get("confidence", 1) + 1,
                 "value": value,
                 "updated_at": datetime.utcnow().isoformat()}
            ).eq("id", existing["id"]).execute()

    def _write(self, user_id, service_type, field, value, hubspace_id, confidence):
        existing = self._find(user_id, service_type, field, hubspace_id)
        payload = {
            "value": value,
            "confidence": confidence,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if existing is None:
            payload.update({
                "user_id": user_id,
                "hubspace_id": hubspace_id,
                "service_type": service_type,
                "field": field,
                "always_confirm": field in ALWAYS_CONFIRM_FIELDS,
            })
            self._client.table("field_defaults").insert(payload).execute()
        else:
            self._client.table("field_defaults").update(payload).eq("id", existing["id"]).execute()

    @staticmethod
    def _row_to_default(row: dict) -> FieldDefault:
        return FieldDefault(
            id=row["id"],
            user_id=row["user_id"],
            hubspace_id=row.get("hubspace_id"),
            service_type=row["service_type"],
            field=row["field"],
            value=row["value"],
            confidence=row.get("confidence", 1),
            always_confirm=row.get("always_confirm", False),
            updated_at=row.get("updated_at", datetime.utcnow()),
        )


def get_field_default_service() -> FieldDefaultService:
    global _field_default_service
    if _field_default_service is None:
        _field_default_service = FieldDefaultService()
    return _field_default_service
