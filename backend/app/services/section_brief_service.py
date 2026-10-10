"""
Section-level dashboard insights — short SSE-streamed summaries for KPI cards
and chart blocks, one section at a time.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime
from typing import Any, AsyncIterator, Dict, List, Optional

from app.core.config import get_settings
from app.models.message import Message, MessageRole
from app.providers import get_claude_provider, get_mistral_provider
from app.services.brief_service import CHANNEL_LABELS, CHANNEL_SOURCES, _stream_text_chunks

logger = logging.getLogger(__name__)

SECTION_LABELS = {
    "kpi": "KPI card",
    "platform_breakdown": "By Platform",
    "timeseries": "Trend chart",
    "table": "Data table",
}


def _fmt_num(val: float) -> str:
    if val >= 1_000_000:
        return f"{val:,.0f}"
    if val >= 1_000:
        return f"{val:,.0f}"
    return f"{val:.0f}"


def _fallback_section_text(channel: str, section: str, context: Dict[str, Any]) -> str:
    """Deterministic 1–2 sentence insight when LLM is unavailable."""
    ctx_type = context.get("type", section)
    title = context.get("title") or context.get("label") or section.replace("_", " ").title()
    source = CHANNEL_SOURCES.get(channel, "CoSight")

    if ctx_type == "kpi":
        label = context.get("label", title)
        value = context.get("formatted_value") or _fmt_num(float(context.get("value", 0)))
        delta = context.get("delta_pct")
        if delta is not None:
            direction = "rose" if delta >= 0 else "fell"
            return (
                f"{label} finished at {value} for this period, {direction} "
                f"{abs(float(delta)):.1f}% compared with the prior period ({source})."
            )
        return f"{label} came in at {value} for this period ({source})."

    if ctx_type == "platform_breakdown":
        platforms: List[Dict[str, Any]] = context.get("platforms") or []
        if not platforms:
            return "Platform-level data is not available for this date range yet."
        top = platforms[0]
        name = top.get("platform", "Top platform")
        imps = top.get("formatted_impressions") or _fmt_num(float(top.get("impressions", 0)))
        share = top.get("impression_share")
        share_txt = f", accounting for {share:.0f}% of impressions" if share is not None else ""
        second = platforms[1] if len(platforms) > 1 else None
        lead = f"{name} led with {imps} impressions{share_txt}."
        if second:
            sname = second.get("platform")
            simps = second.get("formatted_impressions") or _fmt_num(float(second.get("impressions", 0)))
            return f"{lead} {sname} followed at {simps}."
        return lead

    if ctx_type == "timeseries":
        series: List[Dict[str, Any]] = context.get("series") or []
        if not series:
            return f"No trend data is available for {title} in this period."
        parts: List[str] = []
        for s in series[:2]:
            label = s.get("label", s.get("key", "Metric"))
            start_v = s.get("formatted_start") or _fmt_num(float(s.get("start_value", 0)))
            end_v = s.get("formatted_end") or _fmt_num(float(s.get("end_value", 0)))
            change = s.get("change_pct")
            if change is not None:
                direction = "up" if change >= 0 else "down"
                parts.append(f"{label} moved from {start_v} to {end_v}, {direction} {abs(float(change)):.1f}% over the window")
            else:
                parts.append(f"{label} ran from {start_v} to {end_v} across the period")
        return f"For {title}: {'; '.join(parts)}."

    if ctx_type == "table":
        rows = context.get("row_count", 0)
        highlight = context.get("highlight")
        if highlight:
            return f"{title} highlights {highlight} among {rows} entries this period."
        return f"{title} includes {rows} entries for this period."

    return f"{title} data is available for review in this section ({source})."


async def stream_section_brief(
    channel: str,
    section: str,
    start: date,
    end: date,
    context: Dict[str, Any],
) -> AsyncIterator[str]:
    """Async generator yielding SSE events: chunk, done, error."""
    settings = get_settings()

    try:
        channel_label = CHANNEL_LABELS.get(channel, channel)
        section_title = context.get("title") or context.get("label") or section.replace("_", " ").title()
        ctx_type = context.get("type", section)

        system = (
            "You are CoSight, a data analyst for CBS Marketing & Communications. "
            "Write exactly 1–2 plain-language sentences summarizing what happened in ONE dashboard section. "
            "Be specific with numbers from the context only. Do not invent data. "
            "No bullet lists, headers, or citation markers."
        )
        user_msg = (
            f"Channel: {channel_label}\n"
            f"Section: {section_title} ({SECTION_LABELS.get(ctx_type, ctx_type)})\n"
            f"Date range: {start.isoformat()} to {end.isoformat()}\n\n"
            f"Context JSON:\n{json.dumps(context, indent=2)}\n"
        )

        messages = [Message(
            id="section-brief",
            role=MessageRole.USER,
            content=user_msg,
            timestamp=datetime.utcnow(),
        )]

        streamed = False
        if settings.anthropic_api_key:
            try:
                provider = get_claude_provider(
                    api_key=settings.anthropic_api_key,
                    model=settings.anthropic_model,
                )
                async for chunk in provider.stream_completion(
                    messages=messages,
                    system_prompt=system,
                    temperature=0.2,
                    max_tokens=120,
                ):
                    streamed = True
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except Exception as exc:
                logger.warning("Section brief LLM failed, using fallback: %s", exc)

        if not streamed and settings.mistral_api_key:
            try:
                mistral = get_mistral_provider(
                    api_key=settings.mistral_api_key,
                    model=settings.mistral_model,
                )
                async for chunk in mistral.stream_completion(
                    messages=messages,
                    system_prompt=system,
                    temperature=0.2,
                    max_tokens=120,
                ):
                    streamed = True
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except Exception as exc:
                logger.warning("Section brief Mistral fallback failed: %s", exc)

        if not streamed:
            fallback = _fallback_section_text(channel, section, context)
            async for piece in _stream_text_chunks(fallback):
                yield f"data: {json.dumps({'type': 'chunk', 'content': piece})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as exc:
        logger.exception("Section brief failed: %s", exc)
        yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
