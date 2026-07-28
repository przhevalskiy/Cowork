"""
CoSight reports routes — save, list, fetch, and export report artifacts.

All exports render from the single ReportArtifact stored in cosight_reports.payload.
Invariant: no export format bypasses the artifact pipeline.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse

from app.database.supabase_client import get_supabase_client
from app.models.cosight_report import ReportArtifact
from app.services.export.csv_export import report_to_csv
from app.services.export.slides_export import export_report_to_pptx

router = APIRouter(prefix="/api/cosight/reports", tags=["cosight-reports"])
logger = logging.getLogger(__name__)


def _get_client():
    return get_supabase_client()


# ── Save a report ─────────────────────────────────────────────────────────────

@router.post("", response_model=dict)
async def save_report(artifact: ReportArtifact):
    report_id = str(uuid.uuid4())
    artifact.id = report_id
    artifact.created_at = datetime.utcnow()

    payload = json.loads(artifact.model_dump_json())
    _get_client().table("cosight_reports").insert({
        "id": report_id,
        "title": artifact.title,
        "payload": payload,
        "date_range": f"{artifact.date_range_start}/{artifact.date_range_end}",
        "created_at": artifact.created_at.isoformat(),
    }).execute()

    return {"id": report_id, "title": artifact.title, "status": "saved"}


# ── List reports ──────────────────────────────────────────────────────────────

@router.get("", response_model=list)
async def list_reports():
    resp = (
        _get_client().table("cosight_reports")
        .select("id, title, date_range, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


# ── Fetch a report ────────────────────────────────────────────────────────────

@router.get("/{report_id}", response_model=ReportArtifact)
async def get_report(report_id: str):
    resp = (
        _get_client().table("cosight_reports")
        .select("payload")
        .eq("id", report_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Report not found")
    payload = resp.data["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return ReportArtifact.model_validate(payload)


# ── Export a report ───────────────────────────────────────────────────────────

@router.get("/{report_id}/export")
async def export_report(
    report_id: str,
    format: str = Query(..., description="pdf | docx | slides | csv"),
):
    resp = (
        _get_client().table("cosight_reports")
        .select("payload, title")
        .eq("id", report_id)
        .maybe_single()
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Report not found")

    payload = resp.data["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    artifact = ReportArtifact.model_validate(payload)

    if format == "csv":
        csv_content = report_to_csv(artifact)
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="cosight-report-{report_id[:8]}.csv"'
            },
        )

    if format == "slides":
        pptx_bytes = export_report_to_pptx(artifact)
        return Response(
            content=pptx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={
                "Content-Disposition": f'attachment; filename="cosight-report-{report_id[:8]}.pptx"'
            },
        )

    # PDF and DOCX are generated client-side from the artifact payload
    # (the frontend's pdfExport / docxExport services render from the JSON).
    # Return the artifact payload so the client can trigger its own export.
    if format in ("pdf", "docx"):
        return {
            "format": format,
            "artifact": payload,
            "message": "Render this artifact client-side using the CoSight export utilities.",
        }

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use pdf|docx|slides|csv")
