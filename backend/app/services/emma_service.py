"""
Emma email marketing data service for CoSight.

Fetches email metrics: sends, open rate, click rate, unsubscribe rate per campaign.

Auth: HMAC-SHA1 signed requests using Emma public + private key.
Account: ap4395@gsb.columbia.edu / account ID 1982082
API docs: https://api.e2ma.net/
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import get_settings
from app.models.cosight_metric import Channel, ChannelMetrics, MetricUnit, NormalizedMetric

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.e2ma.net"
_MAX_RETRIES = 3


def _delta(value: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return round(((value - prior) / prior) * 100, 2)


def _prior_window(start: date, end: date):
    delta = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start, prior_end


class EmmaClient:
    def __init__(self, account_id: str, public_key: str, private_key: str):
        self.account_id = account_id
        self.auth = (public_key, private_key)

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        url = f"{_BASE_URL}/{self.account_id}{path}"
        for attempt in range(_MAX_RETRIES):
            try:
                resp = httpx.get(url, auth=self.auth, params=params, timeout=30)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if attempt == _MAX_RETRIES - 1:
                    raise
                logger.warning("Emma API error %s, retrying", e.response.status_code)
                time.sleep(2 ** attempt)
        raise RuntimeError("Emma API max retries exceeded")

    def list_mailings(self, start: date, end: date) -> List[Dict]:
        """List sent mailings in the date window."""
        result = self._get("/mailings", params={"status": "sent", "count": 200})
        mailings = result if isinstance(result, list) else result.get("mailings", [])
        # Filter by date client-side — Emma's filter params vary by account type
        return [
            m for m in mailings
            if m.get("send_started") and
               str(start) <= m["send_started"][:10] <= str(end)
        ]

    def get_mailing_stats(self, mailing_id: str) -> Dict:
        """Fetch stats for a single mailing."""
        return self._get(f"/mailings/{mailing_id}/stats") or {}


async def get_metrics(start_date: date, end_date: date) -> ChannelMetrics:
    """
    Fetch Emma email metrics for [start_date, end_date] plus the prior
    equal-length window. Returns summary KPIs aggregated across all campaigns.
    """
    settings = get_settings()
    if not all([settings.emma_public_key, settings.emma_private_key, settings.emma_account_id]):
        return ChannelMetrics(
            channel=Channel.EMAIL,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message="Emma credentials not configured",
        )

    try:
        client = EmmaClient(
            account_id=settings.emma_account_id,
            public_key=settings.emma_public_key,
            private_key=settings.emma_private_key,
        )
        prior_start, prior_end = _prior_window(start_date, end_date)

        def _aggregate(s: date, e: date) -> Dict[str, float]:
            mailings = client.list_mailings(s, e)
            totals: Dict[str, float] = {
                "sends": 0, "opens": 0, "clicks": 0, "unsubscribes": 0, "count": 0
            }
            for m in mailings:
                mid = str(m.get("mailing_id") or m.get("id", ""))
                if not mid:
                    continue
                try:
                    stats = client.get_mailing_stats(mid)
                except Exception as e:
                    logger.warning("Could not fetch stats for mailing %s: %s", mid, e)
                    continue
                totals["sends"] += stats.get("sends", 0) or 0
                totals["opens"] += stats.get("opens", 0) or 0
                totals["clicks"] += stats.get("clicks", 0) or 0
                totals["unsubscribes"] += stats.get("unsubscribes", 0) or 0
                totals["count"] += 1
            # Compute rates
            totals["open_rate"] = (totals["opens"] / totals["sends"]) if totals["sends"] else 0
            totals["click_rate"] = (totals["clicks"] / totals["sends"]) if totals["sends"] else 0
            totals["unsubscribe_rate"] = (totals["unsubscribes"] / totals["sends"]) if totals["sends"] else 0
            return totals

        current = _aggregate(start_date, end_date)
        prior = _aggregate(prior_start, prior_end)

        summary: List[NormalizedMetric] = [
            NormalizedMetric(
                channel=Channel.EMAIL,
                metric_key="email_sends",
                label="Emails Sent",
                value=current["sends"],
                prior_value=prior["sends"],
                delta_pct=_delta(current["sends"], prior["sends"]),
                unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.EMAIL,
                metric_key="open_rate",
                label="Open Rate",
                value=round(current["open_rate"] * 100, 2),
                prior_value=round(prior["open_rate"] * 100, 2) if prior["open_rate"] else None,
                delta_pct=_delta(current["open_rate"], prior["open_rate"]),
                unit=MetricUnit.PERCENT,
            ),
            NormalizedMetric(
                channel=Channel.EMAIL,
                metric_key="click_rate",
                label="Click Rate",
                value=round(current["click_rate"] * 100, 2),
                prior_value=round(prior["click_rate"] * 100, 2) if prior["click_rate"] else None,
                delta_pct=_delta(current["click_rate"], prior["click_rate"]),
                unit=MetricUnit.PERCENT,
            ),
            NormalizedMetric(
                channel=Channel.EMAIL,
                metric_key="unsubscribe_rate",
                label="Unsubscribe Rate",
                value=round(current["unsubscribe_rate"] * 100, 2),
                prior_value=round(prior["unsubscribe_rate"] * 100, 2) if prior["unsubscribe_rate"] else None,
                delta_pct=_delta(current["unsubscribe_rate"], prior["unsubscribe_rate"]),
                unit=MetricUnit.PERCENT,
            ),
        ]

        return ChannelMetrics(
            channel=Channel.EMAIL,
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            timeseries=[],   # Emma doesn't expose daily granularity easily; extend in v2
            status="ok",
        )

    except Exception as exc:
        logger.exception("Emma fetch failed: %s", exc)
        return ChannelMetrics(
            channel=Channel.EMAIL,
            start_date=start_date,
            end_date=end_date,
            status="error",
            error_message=str(exc),
        )
