"""
Shared persistent metric cache for CoSight.

Backed by Supabase `cosight_metric_cache` table — survives Render restarts
and is shared across instances (in-memory dict is NOT sufficient).

Cache key: (channel, metric_key, date_range_hash)
TTL: 15 minutes
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional

from app.database.supabase_client import get_supabase_client
from app.models.cosight_metric import ChannelMetrics

logger = logging.getLogger(__name__)

_TTL_MINUTES = 15


def _cache_key(channel: str, start_date: date, end_date: date) -> str:
    raw = f"{channel}:{start_date}:{end_date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get_cached(channel: str, start_date: date, end_date: date) -> Optional[ChannelMetrics]:
    """Return a cached ChannelMetrics if present and not expired, else None."""
    try:
        client = get_supabase_client()
        key = _cache_key(channel, start_date, end_date)
        resp = (
            client.table("cosight_metric_cache")
            .select("payload, fetched_at")
            .eq("cache_key", key)
            .maybe_single()
            .execute()
        )
        if not resp.data:
            return None

        fetched_at_str = resp.data["fetched_at"]
        fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
        age_minutes = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 60

        if age_minutes > _TTL_MINUTES:
            return None

        payload = resp.data["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        metrics = ChannelMetrics.model_validate(payload)
        metrics.cached_at = fetched_at_str
        return metrics

    except Exception as exc:
        logger.warning("Cache read failed (non-fatal): %s", exc)
        return None


def set_cached(metrics: ChannelMetrics) -> None:
    """Write a ChannelMetrics result to the cache table."""
    try:
        client = get_supabase_client()
        key = _cache_key(
            metrics.channel.value,
            metrics.start_date,
            metrics.end_date,
        )
        payload = metrics.model_dump(mode="json")
        (
            client.table("cosight_metric_cache")
            .upsert(
                {
                    "cache_key": key,
                    "channel": metrics.channel.value,
                    "date_range": f"{metrics.start_date}/{metrics.end_date}",
                    "payload": payload,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="cache_key",
            )
            .execute()
        )
    except Exception as exc:
        logger.warning("Cache write failed (non-fatal): %s", exc)
