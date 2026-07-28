"""
CoSight report artifact model.

A report artifact is the single source from which every export format renders.
The export pipeline (PDF / DOCX / PPTX / CSV) consumes this shape exclusively —
no format may bypass it or construct its own parallel representation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .cosight_metric import NormalizedMetric


class ChartSpec(BaseModel):
    """Declarative spec for a chart — the frontend renders it via Recharts."""

    chart_type: str = "line"            # "line" | "bar" | "area"
    title: str
    metric_keys: List[str]              # which NormalizedMetric keys to plot
    x_axis: str = "date_bucket"
    y_axis_label: Optional[str] = None
    dual_axis: bool = False


class ReportSection(BaseModel):
    """One logical section of the report (e.g. 'Social Media Summary')."""

    id: str
    title: str
    channel: Optional[str] = None       # channel this section covers, or None for cross-channel
    narrative: Optional[str] = None     # agent-generated prose
    kpis: List[NormalizedMetric] = Field(default_factory=list)
    charts: List[ChartSpec] = Field(default_factory=list)
    # Tabular data as list-of-dicts for CSV export and DataTable rendering
    table_rows: List[Dict[str, Any]] = Field(default_factory=list)
    table_headers: List[str] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    """
    Structured report produced by the `generate_report` AI tool or the
    'Save Report' button on the Overview dashboard.

    Persisted as JSONB in `cosight_reports.payload`.
    """

    id: Optional[str] = None            # set after DB insert
    title: str
    subtitle: Optional[str] = None
    date_range_start: str               # ISO date string
    date_range_end: str
    sections: List[ReportSection] = Field(default_factory=list)
    executive_summary: Optional[str] = None
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None    # user_id or display name
