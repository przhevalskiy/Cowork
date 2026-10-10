"""Dashboard brief SSE route — streamed executive summary with citations."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.brief_service import stream_dashboard_brief
from app.services.section_brief_service import stream_section_brief

router = APIRouter(prefix="/api/cosight/brief", tags=["cosight-brief"])


class BriefRequest(BaseModel):
    channel: str  # social | web | search | email | overview
    start_date: str
    end_date: str
    note: str | None = None


class SectionBriefRequest(BaseModel):
    channel: str
    section: str
    start_date: str
    end_date: str
    context: dict


def _parse_dates(start: str, end: str) -> tuple[date, date]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    if start_date > end_date:
        raise HTTPException(status_code=400, detail="start must be before end")
    return start_date, end_date


@router.post("/stream")
async def stream_brief(body: BriefRequest):
    if body.channel not in ("social", "web", "search", "email", "overview"):
        raise HTTPException(status_code=400, detail=f"Unknown channel: {body.channel}")

    start_date, end_date = _parse_dates(body.start_date, body.end_date)

    async def generate():
        async for event in stream_dashboard_brief(
            body.channel, start_date, end_date, note=body.note
        ):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/section/stream")
async def stream_section_brief_route(body: SectionBriefRequest):
    if body.channel not in ("social", "web", "search", "email", "overview"):
        raise HTTPException(status_code=400, detail=f"Unknown channel: {body.channel}")

    start_date, end_date = _parse_dates(body.start_date, body.end_date)

    async def generate():
        async for event in stream_section_brief(
            body.channel,
            body.section,
            start_date,
            end_date,
            body.context,
        ):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream")
async def stream_brief_get(
    channel: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
    note: str | None = Query(None),
):
    """GET variant for EventSource clients."""
    body = BriefRequest(channel=channel, start_date=start, end_date=end, note=note)
    return await stream_brief(body)
