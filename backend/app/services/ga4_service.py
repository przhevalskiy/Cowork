"""
GA4 data service for CoSight.

Fetches web metrics (sessions, pageviews, conversions, bounce rate, top pages)
plus organic-search traffic from Google Analytics Data API v1beta.

Auth pattern verified working 2026-06-29:
  service_account.Credentials.from_service_account_info(
      json.loads(GOOGLE_CREDENTIALS_JSON),
      scopes=["https://www.googleapis.com/auth/analytics.readonly"]
  ) → BetaAnalyticsDataClient → run_report(property="properties/288367390", ...)
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import List, Optional

from app.core.config import get_settings
from app.models.cosight_metric import Channel, ChannelMetrics, MetricUnit, NormalizedMetric

logger = logging.getLogger(__name__)

_GA4_SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


def _get_credentials():
    """Build service-account credentials from the JSON env var or file."""
    from google.oauth2 import service_account

    from app.services.google_credentials import load_service_account_info

    info = load_service_account_info()
    return service_account.Credentials.from_service_account_info(info, scopes=_GA4_SCOPES)


def _get_client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient

    return BetaAnalyticsDataClient(credentials=_get_credentials())


def _prior_window(start: date, end: date):
    delta = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start, prior_end


def _run_report(client, property_id: str, dimensions, metrics, date_ranges, dimension_filter=None):
    from google.analytics.data_v1beta.types import RunReportRequest

    kwargs = dict(
        property=f"properties/{property_id}",
        dimensions=dimensions,
        metrics=metrics,
        date_ranges=date_ranges,
    )
    if dimension_filter:
        kwargs["dimension_filter"] = dimension_filter
    return client.run_report(RunReportRequest(**kwargs))


def _delta(value: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return round(((value - prior) / prior) * 100, 2)


async def get_metrics(start_date: date, end_date: date) -> ChannelMetrics:
    """
    Fetch GA4 web metrics for [start_date, end_date] plus the prior equal-length
    window. Returns a ChannelMetrics with summary KPIs and daily timeseries.
    """
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric

    settings = get_settings()
    property_id = settings.ga4_property_id
    if not property_id:
        return ChannelMetrics(
            channel=Channel.WEB,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message="GA4_PROPERTY_ID not configured",
        )

    try:
        client = _get_client()
        prior_start, prior_end = _prior_window(start_date, end_date)

        date_ranges = [
            DateRange(start_date=str(start_date), end_date=str(end_date)),
            DateRange(start_date=str(prior_start), end_date=str(prior_end)),
        ]

        # ── Summary report (no date dimension, two date ranges → compare_periods) ──
        summary_response = _run_report(
            client,
            property_id,
            dimensions=[],
            metrics=[
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="activeUsers"),
                Metric(name="bounceRate"),
                Metric(name="conversions"),
                Metric(name="averageSessionDuration"),
            ],
            date_ranges=date_ranges,
        )

        # date_range_name "date_range_0" = current, "date_range_1" = prior
        current_vals: dict[str, float] = {}
        prior_vals: dict[str, float] = {}
        for row in summary_response.rows:
            dr = row.dimension_values[0].value if summary_response.dimension_headers else "date_range_0"
            vals = [float(v.value or 0) for v in row.metric_values]
            keys = ["sessions", "pageviews", "active_users", "bounce_rate", "conversions", "avg_session_duration"]
            target = prior_vals if "1" in dr else current_vals
            for k, v in zip(keys, vals):
                target[k] = v

        # Fall back: if response has no dimension_headers (single range), parse directly
        if not summary_response.dimension_headers and summary_response.rows:
            row = summary_response.rows[0]
            keys = ["sessions", "pageviews", "active_users", "bounce_rate", "conversions", "avg_session_duration"]
            for k, v in zip(keys, [float(m.value or 0) for m in row.metric_values]):
                current_vals[k] = v

        summary: List[NormalizedMetric] = [
            NormalizedMetric(
                channel=Channel.WEB,
                metric_key="sessions",
                label="Sessions",
                value=current_vals.get("sessions", 0),
                prior_value=prior_vals.get("sessions"),
                delta_pct=_delta(current_vals.get("sessions", 0), prior_vals.get("sessions")),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.WEB,
                metric_key="pageviews",
                label="Page Views",
                value=current_vals.get("pageviews", 0),
                prior_value=prior_vals.get("pageviews"),
                delta_pct=_delta(current_vals.get("pageviews", 0), prior_vals.get("pageviews")),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.WEB,
                metric_key="active_users",
                label="Active Users",
                value=current_vals.get("active_users", 0),
                prior_value=prior_vals.get("active_users"),
                delta_pct=_delta(current_vals.get("active_users", 0), prior_vals.get("active_users")),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.WEB,
                metric_key="bounce_rate",
                label="Bounce Rate",
                value=round(current_vals.get("bounce_rate", 0) * 100, 2),
                prior_value=round(prior_vals.get("bounce_rate", 0) * 100, 2) if prior_vals.get("bounce_rate") is not None else None,
                delta_pct=_delta(current_vals.get("bounce_rate", 0), prior_vals.get("bounce_rate")),
                unit=MetricUnit.PERCENT,
            ),
            NormalizedMetric(
                channel=Channel.WEB,
                metric_key="conversions",
                label="Conversions",
                value=current_vals.get("conversions", 0),
                prior_value=prior_vals.get("conversions"),
                delta_pct=_delta(current_vals.get("conversions", 0), prior_vals.get("conversions")),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.WEB,
                metric_key="avg_session_duration",
                label="Avg Session Duration",
                value=round(current_vals.get("avg_session_duration", 0), 1),
                prior_value=round(prior_vals.get("avg_session_duration", 0), 1) if prior_vals.get("avg_session_duration") is not None else None,
                delta_pct=_delta(current_vals.get("avg_session_duration", 0), prior_vals.get("avg_session_duration")),
                unit=MetricUnit.DURATION,
            ),
        ]

        # ── Daily timeseries ──────────────────────────────────────────────────────
        ts_response = _run_report(
            client,
            property_id,
            dimensions=[Dimension(name="date")],
            metrics=[
                Metric(name="sessions"),
                Metric(name="activeUsers"),
                Metric(name="screenPageViews"),
            ],
            date_ranges=[DateRange(start_date=str(start_date), end_date=str(end_date))],
        )

        timeseries: List[NormalizedMetric] = []
        for row in ts_response.rows:
            raw_date = row.dimension_values[0].value  # YYYYMMDD
            bucket = date(int(raw_date[:4]), int(raw_date[4:6]), int(raw_date[6:8]))
            sessions_val = float(row.metric_values[0].value or 0)
            users_val = float(row.metric_values[1].value or 0)
            pv_val = float(row.metric_values[2].value or 0)
            timeseries.extend([
                NormalizedMetric(channel=Channel.WEB, metric_key="sessions", label="Sessions",
                                 value=sessions_val, date_bucket=bucket, unit=MetricUnit.COUNT),
                NormalizedMetric(channel=Channel.WEB, metric_key="active_users", label="Active Users",
                                 value=users_val, date_bucket=bucket, unit=MetricUnit.COUNT),
                NormalizedMetric(channel=Channel.WEB, metric_key="pageviews", label="Page Views",
                                 value=pv_val, date_bucket=bucket, unit=MetricUnit.COUNT),
            ])

        # ── Organic search traffic (channel group = Organic Search) ──────────────
        from google.analytics.data_v1beta.types import FilterExpression, Filter

        organic_response = _run_report(
            client,
            property_id,
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
            date_ranges=[DateRange(start_date=str(start_date), end_date=str(end_date))],
            dimension_filter=FilterExpression(
                filter=Filter(
                    field_name="sessionDefaultChannelGroup",
                    string_filter=Filter.StringFilter(value="Organic Search"),
                )
            ),
        )
        organic_sessions = 0.0
        organic_users = 0.0
        for row in organic_response.rows:
            organic_sessions += float(row.metric_values[0].value or 0)
            organic_users += float(row.metric_values[1].value or 0)

        summary.append(NormalizedMetric(
            channel=Channel.WEB,
            metric_key="organic_sessions",
            label="Organic Sessions",
            value=organic_sessions,
            unit=MetricUnit.COUNT,
        ))
        summary.append(NormalizedMetric(
            channel=Channel.WEB,
            metric_key="organic_users",
            label="Organic Users",
            value=organic_users,
            unit=MetricUnit.COUNT,
        ))

        return ChannelMetrics(
            channel=Channel.WEB,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            timeseries=timeseries,
            status="ok",
        )

    except Exception as exc:
        logger.exception("GA4 fetch failed: %s", exc)
        return ChannelMetrics(
            channel=Channel.WEB,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message=str(exc),
        )
