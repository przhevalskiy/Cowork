"""
Google Search Console data service for CoSight.

Fetches search metrics: top queries, impressions, clicks, CTR, average position.

Auth pattern verified working 2026-06-29 — reuses same service-account JSON as GA4:
  build("searchconsole", "v1", credentials=creds)
  → searchanalytics().query(siteUrl="https://business.columbia.edu/", body={...})

Note: GSC has a ~2–3 day reporting lag. Callers should be aware that end_date
near today will return partial or no data. The service automatically shifts the
effective end_date back 3 days when it would otherwise fall within the lag window.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import List

from app.core.config import get_settings
from app.models.cosight_metric import Channel, ChannelMetrics, MetricUnit, NormalizedMetric

logger = logging.getLogger(__name__)

_GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_LAG_DAYS = 3   # GSC data lag — shift end_date back this many days if needed


def _get_credentials():
    from google.oauth2 import service_account

    settings = get_settings()
    if not settings.google_credentials_json:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not configured")
    info = json.loads(settings.google_credentials_json)
    return service_account.Credentials.from_service_account_info(info, scopes=_GSC_SCOPES)


def _effective_end(end_date: date) -> date:
    """Shift end_date back to avoid the GSC reporting lag."""
    lag_cutoff = date.today() - timedelta(days=_LAG_DAYS)
    return min(end_date, lag_cutoff)


def _prior_window(start: date, end: date):
    delta = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start, prior_end


def _delta(value: float, prior: float | None) -> float | None:
    if prior is None or prior == 0:
        return None
    return round(((value - prior) / prior) * 100, 2)


def _query_gsc(service, site_url: str, start_str: str, end_str: str,
               dimensions: list[str], row_limit: int = 100) -> list[dict]:
    body = {
        "startDate": start_str,
        "endDate": end_str,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }
    resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    return resp.get("rows", [])


async def get_metrics(start_date: date, end_date: date) -> ChannelMetrics:
    """
    Fetch GSC search metrics for [start_date, end_date] (lag-adjusted) plus
    the prior equal-length window for delta computation.
    """
    settings = get_settings()
    site_url = settings.gsc_site_url
    if not site_url:
        return ChannelMetrics(
            channel=Channel.SEARCH,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message="GSC_SITE_URL not configured",
        )

    effective_end = _effective_end(end_date)
    if effective_end < start_date:
        return ChannelMetrics(
            channel=Channel.SEARCH,
            start_date=start_date,
            end_date=end_date,
            status="stale",
            error_message="Requested date range is entirely within GSC's reporting lag window",
        )

    try:
        from googleapiclient.discovery import build

        creds = _get_credentials()
        service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
        prior_start, prior_end = _prior_window(start_date, effective_end)

        # ── Aggregate totals (no dimension → one row) ────────────────────────────
        def _totals(s: date, e: date) -> dict:
            rows = _query_gsc(service, site_url, str(s), str(e), [], row_limit=1)
            if rows:
                r = rows[0]
                return {
                    "clicks": r.get("clicks", 0),
                    "impressions": r.get("impressions", 0),
                    "ctr": r.get("ctr", 0),
                    "position": r.get("position", 0),
                }
            return {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}

        current = _totals(start_date, effective_end)
        prior = _totals(prior_start, prior_end)

        summary: List[NormalizedMetric] = [
            NormalizedMetric(
                channel=Channel.SEARCH,
                metric_key="clicks",
                label="Clicks",
                value=current["clicks"],
                prior_value=prior["clicks"],
                delta_pct=_delta(current["clicks"], prior["clicks"]),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SEARCH,
                metric_key="impressions",
                label="Impressions",
                value=current["impressions"],
                prior_value=prior["impressions"],
                delta_pct=_delta(current["impressions"], prior["impressions"]),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SEARCH,
                metric_key="ctr",
                label="CTR",
                value=round(current["ctr"] * 100, 2),
                prior_value=round(prior["ctr"] * 100, 2) if prior["ctr"] else None,
                delta_pct=_delta(current["ctr"], prior["ctr"]),
                unit=MetricUnit.PERCENT,
            ),
            NormalizedMetric(
                channel=Channel.SEARCH,
                metric_key="avg_position",
                label="Avg Position",
                value=round(current["position"], 2),
                prior_value=round(prior["position"], 2) if prior["position"] else None,
                delta_pct=_delta(current["position"], prior["position"]),
                unit=MetricUnit.POSITION,
            ),
        ]

        # ── Top queries (dimension=query) ────────────────────────────────────────
        query_rows = _query_gsc(service, site_url, str(start_date), str(effective_end),
                                ["query"], row_limit=25)
        for row in query_rows:
            keys = row.get("keys", [""])
            summary.append(NormalizedMetric(
                channel=Channel.SEARCH,
                metric_key="query_clicks",
                label="Query Clicks",
                value=row.get("clicks", 0),
                unit=MetricUnit.COUNT,
                dimension=keys[0],
            ))

        # ── Daily timeseries (dimension=date) ────────────────────────────────────
        date_rows = _query_gsc(service, site_url, str(start_date), str(effective_end),
                               ["date"], row_limit=90)
        timeseries: List[NormalizedMetric] = []
        for row in date_rows:
            raw_date = row.get("keys", [""])[0]  # "YYYY-MM-DD"
            try:
                bucket = date.fromisoformat(raw_date)
            except ValueError:
                continue
            timeseries.extend([
                NormalizedMetric(channel=Channel.SEARCH, metric_key="clicks", label="Clicks",
                                 value=row.get("clicks", 0), date_bucket=bucket, unit=MetricUnit.COUNT),
                NormalizedMetric(channel=Channel.SEARCH, metric_key="impressions", label="Impressions",
                                 value=row.get("impressions", 0), date_bucket=bucket, unit=MetricUnit.COUNT),
                NormalizedMetric(channel=Channel.SEARCH, metric_key="ctr", label="CTR",
                                 value=round(row.get("ctr", 0) * 100, 2), date_bucket=bucket, unit=MetricUnit.PERCENT),
                NormalizedMetric(channel=Channel.SEARCH, metric_key="avg_position", label="Avg Position",
                                 value=round(row.get("position", 0), 2), date_bucket=bucket, unit=MetricUnit.POSITION),
            ])

        return ChannelMetrics(
            channel=Channel.SEARCH,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            timeseries=timeseries,
            status="ok",
        )

    except Exception as exc:
        logger.exception("GSC fetch failed: %s", exc)
        return ChannelMetrics(
            channel=Channel.SEARCH,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message=str(exc),
        )
