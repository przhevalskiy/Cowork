"""
CoSight metrics routes — CP4.

All routes are open (no auth) for the initial build; auth can be layered later.
Partial-failure invariant: /overview never 500s when a connector fails — it
returns per-channel status fields and serves the channels that succeeded.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.models.cosight_metric import ChannelMetrics, OverviewPayload
from app.services import ga4_service, gsc_service, emma_service, sprout_service
from app.services.cosight_cache_service import get_cached, set_cached
from app.services.export.csv_export import channel_metrics_to_csv

router = APIRouter(prefix="/api/cosight", tags=["cosight-metrics"])
logger = logging.getLogger(__name__)

# ── Date range helpers ────────────────────────────────────────────────────────

_MAX_DAYS = 365


def _parse_dates(start: str | None, end: str | None) -> tuple[date, date]:
    """Parse and validate date params. Defaults to last 30 days."""
    today = date.today()
    end_date = date.fromisoformat(end) if end else today - timedelta(days=1)
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=29)

    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start must be before end")
    if (end_date - start_date).days > _MAX_DAYS:
        raise HTTPException(status_code=400, detail=f"Date range cannot exceed {_MAX_DAYS} days")
    return start_date, end_date


async def _fetch_with_cache(service_module, channel_value: str,
                            start: date, end: date) -> ChannelMetrics:
    cached = get_cached(channel_value, start, end)
    if cached:
        return cached
    result = await service_module.get_metrics(start, end)
    if result.status == "ok":
        set_cached(result)
    return result


# ── Channel routes ────────────────────────────────────────────────────────────

@router.get("/web", response_model=ChannelMetrics)
async def get_web_metrics(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
):
    start_date, end_date = _parse_dates(start, end)
    return await _fetch_with_cache(ga4_service, "web", start_date, end_date)


@router.get("/seo", response_model=ChannelMetrics)
async def get_seo_metrics(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
):
    start_date, end_date = _parse_dates(start, end)
    return await _fetch_with_cache(gsc_service, "search", start_date, end_date)


@router.get("/email", response_model=ChannelMetrics)
async def get_email_metrics(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
):
    start_date, end_date = _parse_dates(start, end)
    return await _fetch_with_cache(emma_service, "email", start_date, end_date)


@router.get("/social", response_model=ChannelMetrics)
async def get_social_metrics(
    start: str | None = Query(None, description="YYYY-MM-DD"),
    end: str | None = Query(None, description="YYYY-MM-DD"),
):
    start_date, end_date = _parse_dates(start, end)
    return await _fetch_with_cache(sprout_service, "social", start_date, end_date)


# ── Overview — partial failure safe ──────────────────────────────────────────

@router.get("/overview", response_model=OverviewPayload)
async def get_overview(
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    """
    Aggregate all four channels. Returns per-channel status.
    Never 500s when a single connector is down — returns what succeeded.
    """
    start_date, end_date = _parse_dates(start, end)

    results = await asyncio.gather(
        _fetch_with_cache(ga4_service, "web", start_date, end_date),
        _fetch_with_cache(gsc_service, "search", start_date, end_date),
        _fetch_with_cache(emma_service, "email", start_date, end_date),
        _fetch_with_cache(sprout_service, "social", start_date, end_date),
        return_exceptions=True,
    )

    def _safe(result, channel_value: str, start: date, end: date) -> ChannelMetrics:
        if isinstance(result, Exception):
            return ChannelMetrics(
                channel=channel_value,
                start_date=start,
                end_date=end,
                status="error",
                error_message=str(result),
            )
        return result

    web, search, email, social = (
        _safe(results[0], "web", start_date, end_date),
        _safe(results[1], "search", start_date, end_date),
        _safe(results[2], "email", start_date, end_date),
        _safe(results[3], "social", start_date, end_date),
    )

    return OverviewPayload(web=web, search=search, email=email, social=social)


# ── CSV export ────────────────────────────────────────────────────────────────

@router.get("/{channel}/export.csv")
async def export_channel_csv(
    channel: str,
    start: str | None = Query(None),
    end: str | None = Query(None),
):
    """Direct CSV download of a channel's metrics for a date range."""
    channel_map = {
        "web": (ga4_service, "web"),
        "seo": (gsc_service, "search"),
        "email": (emma_service, "email"),
        "social": (sprout_service, "social"),
    }
    if channel not in channel_map:
        raise HTTPException(status_code=404, detail=f"Unknown channel: {channel}")

    service_module, channel_value = channel_map[channel]
    start_date, end_date = _parse_dates(start, end)
    metrics = await _fetch_with_cache(service_module, channel_value, start_date, end_date)
    csv_content = channel_metrics_to_csv(metrics)

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="cosight-{channel}-{start_date}-{end_date}.csv"'
        },
    )
