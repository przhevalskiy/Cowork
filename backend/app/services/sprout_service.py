"""
Sprout Social data service for CoSight.

Fetches social metrics: impressions, engagement, reach, follower growth
per platform (LinkedIn, Instagram, Twitter/X).

Status: SPROUT_API_TOKEN not yet obtained — this service returns a
        graceful "pending credential" error until the token is configured.
        Stubbed with the correct connector interface so the rest of the system
        (routes, AI tools, overview partial-failure logic) can be built now.

API reference: https://api.sproutsocial.com/docs/
Rate limits: 1,000 requests/hr per token (Sprout docs, 2024).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.models.cosight_metric import Channel, ChannelMetrics, MetricUnit, NormalizedMetric

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.sproutsocial.com/v1"
_MAX_RETRIES = 3
_PLATFORM_MAP = {
    1: "facebook",
    2: "twitter",
    3: "instagram",
    7: "linkedin",
}


def _delta(value: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return round(((value - prior) / prior) * 100, 2)


def _prior_window(start: date, end: date):
    delta = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start, prior_end


class SproutClient:
    def __init__(self, api_token: str):
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: Dict) -> Any:
        url = f"{_BASE_URL}{path}"
        for attempt in range(_MAX_RETRIES):
            try:
                resp = httpx.post(url, json=payload, headers=self.headers, timeout=30)
                if resp.status_code == 429:
                    import time
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if attempt == _MAX_RETRIES - 1:
                    raise
                import time
                logger.warning("Sprout API error %s, retrying", e.response.status_code)
                time.sleep(2 ** attempt)
        raise RuntimeError("Sprout API max retries exceeded")

    def get_profiles(self) -> List[Dict]:
        """List all connected social profiles."""
        resp = httpx.get(f"{_BASE_URL}/profiles", headers=self.headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def profile_metrics(self, profile_ids: List[str], start: date, end: date) -> Dict:
        """Fetch aggregate profile metrics for the given date range."""
        payload = {
            "filters": {
                "customer_profile_ids": profile_ids,
                "reporting_period": {
                    "type": "custom",
                    "date_range": {"date_start": str(start), "date_end": str(end)},
                },
            },
            "metrics": [
                "lifetime_snapshot.followers_count",
                "followers_gained",
                "impressions",
                "engagements",
                "engagement_rate_by_impressions",
                "reach",
            ],
        }
        return self._post("/analytics/profiles", payload)


async def get_metrics(start_date: date, end_date: date) -> ChannelMetrics:
    """
    Fetch Sprout Social metrics for [start_date, end_date] plus the prior window.
    Returns a ChannelMetrics with summary KPIs per platform + aggregated totals.
    """
    settings = get_settings()
    if not settings.sprout_api_token:
        # Credential not yet obtained — return graceful pending state
        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message="Sprout Social API token not yet configured (pending credential)",
        )

    try:
        client = SproutClient(settings.sprout_api_token)
        prior_start, prior_end = _prior_window(start_date, end_date)

        profiles = client.get_profiles()
        profile_ids = [str(p["customer_profile_id"]) for p in profiles]

        if not profile_ids:
            return ChannelMetrics(
                channel=Channel.SOCIAL,
                start_date=start_date,
                end_date=end_date,
                status="error",
                error_message="No Sprout Social profiles found",
            )

        current_data = client.profile_metrics(profile_ids, start_date, end_date)
        prior_data = client.profile_metrics(profile_ids, prior_start, prior_end)

        def _extract_totals(data: Dict) -> Dict[str, float]:
            totals: Dict[str, float] = {
                "impressions": 0, "engagements": 0, "reach": 0, "followers_gained": 0
            }
            for profile in data.get("data", {}).get("by_profile", []):
                metrics = profile.get("metrics", {})
                totals["impressions"] += metrics.get("impressions", 0) or 0
                totals["engagements"] += metrics.get("engagements", 0) or 0
                totals["reach"] += metrics.get("reach", 0) or 0
                totals["followers_gained"] += metrics.get("followers_gained", 0) or 0
            return totals

        current = _extract_totals(current_data)
        prior = _extract_totals(prior_data)

        summary: List[NormalizedMetric] = [
            NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key="impressions",
                label="Impressions",
                value=current["impressions"],
                prior_value=prior["impressions"],
                delta_pct=_delta(current["impressions"], prior["impressions"]),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key="engagements",
                label="Engagements",
                value=current["engagements"],
                prior_value=prior["engagements"],
                delta_pct=_delta(current["engagements"], prior["engagements"]),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key="reach",
                label="Reach",
                value=current["reach"],
                prior_value=prior["reach"],
                delta_pct=_delta(current["reach"], prior["reach"]),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key="followers_gained",
                label="Followers Gained",
                value=current["followers_gained"],
                prior_value=prior["followers_gained"],
                delta_pct=_delta(current["followers_gained"], prior["followers_gained"]),
                unit=MetricUnit.COUNT,
            ),
        ]

        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            timeseries=[],
            status="ok",
        )

    except Exception as exc:
        logger.exception("Sprout fetch failed: %s", exc)
        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message=str(exc),
        )
