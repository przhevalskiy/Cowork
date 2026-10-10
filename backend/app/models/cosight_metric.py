"""
Canonical metric model for CoSight.

ALL four connectors (GA4, GSC, Emma, Sprout) normalize their raw vendor
responses into this single shape before anything downstream touches the data.
No component, route, or AI tool may branch on which vendor produced a metric.

Invariant: connector output ≡ NormalizedMetric — enforced by the service layer.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TopPost(BaseModel):
    """Top-performing Sprout post in the selected date range."""

    text: str
    platform: str
    profile_name: str
    created_time: str
    permalink: Optional[str] = None
    impressions: float = 0
    engagements: float = 0


class Channel(str, Enum):
    SOCIAL = "social"
    EMAIL = "email"
    WEB = "web"
    SEARCH = "search"


class MetricUnit(str, Enum):
    COUNT = "count"
    RATE = "rate"          # 0–1 float (e.g. open_rate = 0.23)
    PERCENT = "percent"    # 0–100 float (used when vendors return %)
    POSITION = "position"  # average rank (lower = better)
    DURATION = "duration"  # seconds
    CURRENCY = "currency"  # USD


class NormalizedMetric(BaseModel):
    """Single data point after connector normalization.

    Covers both aggregate KPI cards and time-series rows.
    - ``date_bucket``: date of the row (for time-series); None for aggregate summary.
    - ``prior_value``: value of the same metric for the immediately-prior equal-length
      window (fetched in the service layer, never recomputed downstream).
    - ``delta_pct``: ((value - prior_value) / prior_value) * 100, or None when
      prior_value is zero or unavailable.
    """

    channel: Channel
    metric_key: str = Field(
        ...,
        description=(
            "Snake-case canonical key, e.g. 'sessions', 'open_rate', 'avg_position'. "
            "Must match the Metrics Dictionary in Appendix A of COSIGHT_PLAN.md."
        ),
    )
    value: float
    prior_value: Optional[float] = None
    delta_pct: Optional[float] = None
    date_bucket: Optional[date] = None
    unit: MetricUnit = MetricUnit.COUNT
    # Optional: human-readable label for display (e.g. "Active Users")
    label: Optional[str] = None
    # Optional: sub-dimension (e.g. platform="linkedin", campaign="Q1 Admit")
    dimension: Optional[str] = None


class ChannelMetrics(BaseModel):
    """Aggregated result returned by a connector for a date range."""

    channel: Channel
    start_date: date
    end_date: date
    # Summary KPIs (no date_bucket)
    summary: List[NormalizedMetric] = Field(default_factory=list)
    # Time-series rows (each has a date_bucket)
    timeseries: List[NormalizedMetric] = Field(default_factory=list)
    top_posts: List[TopPost] = Field(default_factory=list)
    # Status from the last fetch attempt
    status: str = "ok"  # "ok" | "stale" | "error"
    error_message: Optional[str] = None
    # ISO timestamp of the cache entry that served this result (None = live)
    cached_at: Optional[str] = None


class OverviewPayload(BaseModel):
    """Response shape for GET /api/cosight/overview.

    Each channel includes a per-channel status so partial failures
    never cause a 500 — the route returns what succeeded.
    """

    social: Optional[ChannelMetrics] = None
    email: Optional[ChannelMetrics] = None
    web: Optional[ChannelMetrics] = None
    search: Optional[ChannelMetrics] = None
