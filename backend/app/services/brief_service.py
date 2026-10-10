"""
Dashboard brief service — SSE-streamed executive summaries with inline citations.

Fetches channel metrics, builds a citation index, then streams a grounded brief
that references citations as [1], [2], etc.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import Any, AsyncIterator, Dict, List, Optional

from app.core.config import get_settings
from app.models.cosight_metric import Channel, ChannelMetrics, NormalizedMetric
from app.providers import get_claude_provider, get_mistral_provider
from app.services import emma_service, ga4_service, gsc_service, sprout_service
from app.services.cosight_cache_service import get_cached, set_cached

logger = logging.getLogger(__name__)

CHANNEL_SOURCES = {
    "social": "Sprout Social",
    "web": "Google Analytics 4",
    "search": "Google Search Console",
    "email": "Emma",
}

CHANNEL_LABELS = {
    "social": "Social Media (Columbia Business School)",
    "web": "Web Analytics",
    "search": "Search Performance",
    "email": "Email Marketing",
    "overview": "Marketing Overview (all channels)",
}


async def _fetch_channel(channel: str, start: date, end: date) -> ChannelMetrics:
    cache_key = channel if channel != "search" else "search"
    service_map = {
        "social": sprout_service,
        "web": ga4_service,
        "search": gsc_service,
        "email": emma_service,
    }
    svc = service_map[channel]
    cached = get_cached(cache_key, start, end)
    if cached:
        return cached
    result = await svc.get_metrics(start, end)
    if result.status == "ok":
        set_cached(result)
    return result


def _format_value(metric: NormalizedMetric) -> str:
    val = metric.value
    if metric.unit.value in ("percent",):
        return f"{val:.1f}%"
    if metric.unit.value == "rate":
        return f"{val * 100:.1f}%"
    if metric.unit.value == "position":
        return f"{val:.1f}"
    if val >= 1_000_000:
        return f"{val:,.0f}"
    if val >= 1_000:
        return f"{val:,.0f}"
    return f"{val:.0f}"


def build_citations(
    metrics: List[NormalizedMetric],
    channel: str,
    start: date,
    end: date,
) -> List[Dict[str, Any]]:
    """Build numbered citations from aggregate KPI rows (no dimensions)."""
    source = CHANNEL_SOURCES.get(channel, "CoSight")
    date_range = f"{start.isoformat()} to {end.isoformat()}"
    citations: List[Dict[str, Any]] = []

    for m in metrics:
        if m.dimension or m.date_bucket:
            continue
        cid = len(citations) + 1
        label = m.label or m.metric_key.replace("_", " ").title()
        entry: Dict[str, Any] = {
            "id": cid,
            "metric_key": m.metric_key,
            "label": label,
            "value": m.value,
            "formatted_value": _format_value(m),
            "unit": m.unit.value,
            "source": source,
            "channel": channel,
            "date_range": date_range,
            "detail": f"{label} for {date_range}, sourced from {source}.",
        }
        if m.delta_pct is not None:
            entry["delta_pct"] = m.delta_pct
            entry["detail"] += f" Change vs prior period: {m.delta_pct:+.1f}%."
        citations.append(entry)
    return citations


def _citation_lines(citations: List[Dict[str, Any]]) -> str:
    lines = []
    for c in citations:
        delta = ""
        if c.get("delta_pct") is not None:
            delta = f", {c['delta_pct']:+.1f}% vs prior period"
        lines.append(
            f"[{c['id']}] {c['label']}: {c['formatted_value']}{delta} "
            f"({c['source']}, {c['date_range']})"
        )
    return "\n".join(lines)


def _fallback_brief_text(
    channel: str,
    citations: List[Dict[str, Any]],
    note: Optional[str] = None,
) -> str:
    """Deterministic brief when LLM is unavailable."""
    if not citations:
        return "No complete metrics are available for this date range yet."

    label = CHANNEL_LABELS.get(channel, channel)
    parts: List[str] = [f"Here is your {label} summary for the selected period."]

    top = max(citations, key=lambda c: abs(c.get("delta_pct") or 0), default=citations[0])
    if top.get("delta_pct") is not None:
        direction = "up" if top["delta_pct"] >= 0 else "down"
        parts.append(
            f"The largest shift is {top['label'].lower()}, {direction} "
            f"{abs(top['delta_pct']):.1f}% vs the prior period [{top['id']}]."
        )

    if len(citations) >= 2:
        second = citations[1] if citations[0] is top else citations[0]
        parts.append(
            f"{second['label']} came in at {second['formatted_value']} [{second['id']}]."
        )

    if note:
        parts.append(note)

    return " ".join(parts)


async def _stream_text_chunks(text: str, chunk_size: int = 4) -> AsyncIterator[str]:
    """Simulate streaming by yielding small text slices at word boundaries when possible."""
    i = 0
    while i < len(text):
        end = min(i + chunk_size, len(text))
        if end < len(text):
            space = text.find(" ", end - 1, min(end + 8, len(text)))
            if space != -1:
                end = space + 1
        yield text[i:end]
        i = end
        await asyncio.sleep(0.012)


async def stream_dashboard_brief(
    channel: str,
    start: date,
    end: date,
    note: Optional[str] = None,
) -> AsyncIterator[str]:
    """
    Async generator yielding SSE-formatted event strings.
    Events: citations, chunk, done, error
    """
    settings = get_settings()

    try:
        if channel == "overview":
            social = await _fetch_channel("social", start, end)
            web = await _fetch_channel("web", start, end)
            search = await _fetch_channel("search", start, end)
            email = await _fetch_channel("email", start, end)
            citations = []
            for ch, result in [("web", web), ("search", search), ("email", email), ("social", social)]:
                if result.status != "ok":
                    continue
                citations.extend(build_citations(result.summary, ch, start, end))
            for i, c in enumerate(citations, start=1):
                c["id"] = i
            metrics_ok = bool(citations)
            result = social
        else:
            result = await _fetch_channel(channel, start, end)
            metrics_ok = result.status == "ok"
            citations = build_citations(result.summary, channel, start, end) if metrics_ok else []

        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

        if not metrics_ok or not citations:
            err = result.error_message if not metrics_ok and channel != "overview" else "Metrics unavailable for this date range."
            fallback = _fallback_brief_text(channel, citations, note) if citations else err
            async for piece in _stream_text_chunks(fallback):
                yield f"data: {json.dumps({'type': 'chunk', 'content': piece})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        channel_label = CHANNEL_LABELS.get(channel, channel)
        system = (
            "You are CoSight, a data analyst for CBS Marketing & Communications. "
            "Write concise, plain-language dashboard briefs for non-digital marketers. "
            "Use inline citation markers [1], [2], etc. for EVERY number you mention. "
            "Only cite numbers that appear in the citation list. Do not invent data. "
            "Write 3-5 sentences. No bullet lists. No markdown headers."
        )
        user_msg = (
            f"Write a brief for: {channel_label}\n"
            f"Date range: {start.isoformat()} to {end.isoformat()}\n\n"
            f"Citation list (use these IDs inline):\n{_citation_lines(citations)}\n"
        )
        if note:
            user_msg += f"\nInclude this data note naturally at the end: {note}\n"

        from datetime import datetime
        from app.models.message import Message, MessageRole

        messages = [Message(
            id="brief",
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
                    max_tokens=512,
                ):
                    streamed = True
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except Exception as exc:
                logger.warning("Brief LLM stream failed, using fallback: %s", exc)

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
                    max_tokens=512,
                ):
                    streamed = True
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            except Exception as exc:
                logger.warning("Brief Mistral fallback failed: %s", exc)

        if not streamed:
            fallback = _fallback_brief_text(channel, citations, note)
            async for piece in _stream_text_chunks(fallback):
                yield f"data: {json.dumps({'type': 'chunk', 'content': piece})}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as exc:
        logger.exception("Dashboard brief failed: %s", exc)
        yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"
