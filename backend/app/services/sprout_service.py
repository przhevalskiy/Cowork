"""
Sprout Social data service for CoSight.

Fetches CBS (Columbia Business School) social metrics from Sprout profiles
in the Business School, The Hub, and Executive Education groups.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.models.cosight_metric import (
    Channel,
    ChannelMetrics,
    MetricUnit,
    NormalizedMetric,
    TopPost,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.sproutsocial.com/v1"
_MAX_RETRIES = 3
_PROFILE_BATCH = 50
_TOP_POSTS_LIMIT = 25
_POST_FETCH_MAX_PAGES = 3

_BASE_METRICS = ["followers_gained", "impressions", "engagements", "impressions_unique"]
_EXTENDED_METRICS = _BASE_METRICS + ["lifetime_snapshot.followers_count"]

_POST_FIELDS = ["created_time", "perma_link", "text", "customer_profile_id"]
_POST_METRICS = [
    "lifetime.impressions",
    "lifetime.reactions",
    "lifetime.comments_count",
    "lifetime.shares_count",
]

# Networks Sprout excludes from /analytics/profiles (API returns 400 if included).
_UNSUPPORTED_NETWORKS = {"bluesky"}


def _sprout_latest_date(lag_days: int) -> date:
    """Last calendar day with reliable Sprout profile analytics."""
    return date.today() - timedelta(days=lag_days)


def _resolve_sprout_range(
    start_date: date, end_date: date, lag_days: int
) -> Tuple[date, date]:
    """Clamp the requested window to exclude unsynced recent days."""
    effective_end = min(end_date, _sprout_latest_date(lag_days))
    effective_start = min(start_date, effective_end)
    return effective_start, effective_end


def _filter_profile_rows_through(data: Dict, through: date) -> Dict:
    """Drop daily profile rows after the reliable-through date."""
    rows: List[Dict] = []
    for row in data.get("data", []):
        day_str = (row.get("dimensions") or {}).get("reporting_period.by(day)")
        if day_str:
            try:
                if date.fromisoformat(day_str) > through:
                    continue
            except ValueError:
                pass
        rows.append(row)
    return {"data": rows}


def _filter_timeseries_through(
    timeseries: List[NormalizedMetric], through: date
) -> List[NormalizedMetric]:
    return [
        m for m in timeseries
        if m.date_bucket is None or m.date_bucket <= through
    ]


def _parse_group_ids(raw: str) -> set[int]:
    ids: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _supported_profiles(profiles: List[Dict]) -> List[Dict]:
    return [p for p in profiles if p.get("network_type") not in _UNSUPPORTED_NETWORKS]


def _cbs_profiles(profiles: List[Dict], group_ids: set[int]) -> List[Dict]:
    """Keep profiles that belong to at least one configured CBS Sprout group."""
    supported = _supported_profiles(profiles)
    if not group_ids:
        return supported
    return [
        p for p in supported
        if group_ids.intersection(p.get("groups") or [])
    ]


def _delta(value: float, prior: Optional[float]) -> Optional[float]:
    if prior is None or prior == 0:
        return None
    return round(((value - prior) / prior) * 100, 2)


def _prior_window(start: date, end: date) -> Tuple[date, date]:
    delta = (end - start).days + 1
    prior_end = start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=delta - 1)
    return prior_start, prior_end


def _platform_label(network_type: str) -> str:
    nt = (network_type or "").lower()
    if "instagram" in nt:
        return "Instagram"
    if "linkedin" in nt:
        return "LinkedIn"
    if "facebook" in nt or nt == "fb":
        return "Facebook"
    if "twitter" in nt or nt == "x":
        return "X"
    if "youtube" in nt:
        return "YouTube"
    if "tiktok" in nt:
        return "TikTok"
    return (network_type or "Other").replace("_", " ").title()


def _platform_slug(label: str) -> str:
    return label.lower().replace(" ", "_")


def _metric_val(metrics: Dict[str, Any], key: str) -> Optional[float]:
    val = metrics.get(key)
    if val is None and "." in key:
        # Some responses may nest dotted keys; flat access is the common case.
        parts = key.split(".")
        cur: Any = metrics
        for part in parts:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(part)
        val = cur
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _engagement_rate(engagements: float, impressions: float) -> float:
    if not impressions:
        return 0.0
    return round((engagements / impressions) * 100, 2)


def _profile_maps(profiles: List[Dict]) -> Tuple[Dict[int, str], Dict[int, str]]:
    platform_by_id: Dict[int, str] = {}
    name_by_id: Dict[int, str] = {}
    for p in profiles:
        pid = int(p["customer_profile_id"])
        platform_by_id[pid] = _platform_label(p.get("network_type", ""))
        name_by_id[pid] = p.get("name") or p.get("native_name") or str(pid)
    return platform_by_id, name_by_id


class SproutClient:
    def __init__(self, api_token: str):
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._customer_id: Optional[int] = None

    def _request(self, method: str, path: str, payload: Optional[Dict] = None) -> Any:
        url = f"{_BASE_URL}{path}"
        for attempt in range(_MAX_RETRIES):
            try:
                if method == "GET":
                    resp = httpx.get(url, headers=self.headers, timeout=30)
                else:
                    resp = httpx.post(url, json=payload, headers=self.headers, timeout=30)
                if resp.status_code == 429:
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if attempt == _MAX_RETRIES - 1:
                    detail = e.response.text[:300] if e.response.text else str(e)
                    raise RuntimeError(f"Sprout API {e.response.status_code}: {detail}") from e
                logger.warning("Sprout API error %s, retrying", e.response.status_code)
                time.sleep(2 ** attempt)
        raise RuntimeError("Sprout API max retries exceeded")

    def get_customer_id(self) -> int:
        if self._customer_id is not None:
            return self._customer_id
        data = self._request("GET", "/metadata/client")
        clients = data.get("data", [])
        if not clients:
            raise RuntimeError("No Sprout customer accounts found for this token")
        self._customer_id = int(clients[0]["customer_id"])
        return self._customer_id

    def get_profiles(self, group_ids: Optional[set[int]] = None) -> List[Dict]:
        """List connected social profiles, optionally scoped to CBS Sprout groups."""
        customer_id = self.get_customer_id()
        data = self._request("GET", f"/{customer_id}/metadata/customer")
        profiles = data.get("data", [])
        if group_ids is None:
            return _supported_profiles(profiles)
        return _cbs_profiles(profiles, group_ids)

    def _profile_metrics_batch(
        self,
        profile_ids: List[int],
        start: date,
        end: date,
        page: int = 1,
        metrics: Optional[List[str]] = None,
    ) -> Dict:
        customer_id = self.get_customer_id()
        ids = ",".join(str(pid) for pid in profile_ids)
        payload = {
            "filters": [
                f"customer_profile_id.eq({ids})",
                f"reporting_period.in({start}...{end})",
            ],
            "metrics": metrics or _EXTENDED_METRICS,
            "page": page,
        }
        return self._request("POST", f"/{customer_id}/analytics/profiles", payload)

    def profile_metrics(
        self,
        profile_ids: List[int],
        start: date,
        end: date,
        metrics: Optional[List[str]] = None,
    ) -> Dict:
        """Fetch profile-level metrics, batching IDs and paginating each batch."""
        all_rows: List[Dict] = []
        for i in range(0, len(profile_ids), _PROFILE_BATCH):
            batch = profile_ids[i : i + _PROFILE_BATCH]
            page = 1
            while True:
                data = self._profile_metrics_batch(batch, start, end, page, metrics)
                all_rows.extend(data.get("data", []))
                paging = data.get("paging") or {}
                total_pages = paging.get("total_pages") or 1
                if page >= total_pages:
                    break
                page += 1
        return {"data": all_rows}

    def post_metrics(self, profile_ids: List[int], start: date, end: date) -> List[Dict]:
        """Fetch post-level analytics for the date range (paginated, batched)."""
        customer_id = self.get_customer_id()
        start_dt = f"{start}T00:00:00"
        end_dt = f"{end}T23:59:59"
        all_posts: List[Dict] = []

        for i in range(0, len(profile_ids), _PROFILE_BATCH):
            batch = profile_ids[i : i + _PROFILE_BATCH]
            ids = ",".join(str(pid) for pid in batch)
            page = 1
            while page <= _POST_FETCH_MAX_PAGES:
                payload = {
                    "fields": _POST_FIELDS,
                    "filters": [
                        f"customer_profile_id.eq({ids})",
                        f"created_time.in({start_dt}..{end_dt})",
                    ],
                    "metrics": _POST_METRICS,
                    "timezone": "America/New_York",
                    "page": page,
                }
                data = self._request("POST", f"/{customer_id}/analytics/posts", payload)
                all_posts.extend(data.get("data", []))
                paging = data.get("paging") or {}
                total_pages = paging.get("total_pages") or 1
                if page >= total_pages:
                    break
                page += 1
        return all_posts


def _accumulate_row(
    bucket: Dict[str, float],
    metrics: Dict[str, Any],
    include_followers: bool = True,
) -> None:
    bucket["impressions"] += _metric_val(metrics, "impressions") or 0
    bucket["engagements"] += _metric_val(metrics, "engagements") or 0
    bucket["reach"] += (
        _metric_val(metrics, "reach")
        or _metric_val(metrics, "impressions_unique")
        or 0
    )
    bucket["followers_gained"] += _metric_val(metrics, "followers_gained") or 0
    if include_followers:
        fc = _metric_val(metrics, "lifetime_snapshot.followers_count")
        if fc is not None:
            bucket["followers_count"] = fc


def _extract_totals(
    data: Dict,
    platform_by_id: Dict[int, str],
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    overall: Dict[str, float] = {
        "impressions": 0,
        "engagements": 0,
        "reach": 0,
        "followers_gained": 0,
    }
    by_platform: Dict[str, Dict[str, float]] = {}
    # Latest follower snapshot per profile (end-of-period audience).
    profile_latest: Dict[int, Tuple[str, float]] = {}

    for row in data.get("data", []):
        metrics = row.get("metrics") or {}
        dims = row.get("dimensions") or {}
        pid = dims.get("customer_profile_id")
        platform = platform_by_id.get(int(pid)) if pid is not None else "Other"

        _accumulate_row(overall, metrics, include_followers=False)

        plat_bucket = by_platform.setdefault(
            platform,
            {"impressions": 0, "engagements": 0, "reach": 0, "followers_gained": 0},
        )
        _accumulate_row(plat_bucket, metrics, include_followers=False)

        if pid is not None:
            day = dims.get("reporting_period.by(day)") or ""
            fc = _metric_val(metrics, "lifetime_snapshot.followers_count")
            if fc is not None:
                prev = profile_latest.get(int(pid))
                if prev is None or day >= prev[0]:
                    profile_latest[int(pid)] = (day, fc)

    overall["followers_count"] = sum(v[1] for v in profile_latest.values())

    platform_followers: Dict[str, float] = {}
    for pid, (_, count) in profile_latest.items():
        platform = platform_by_id.get(pid, "Other")
        platform_followers[platform] = platform_followers.get(platform, 0) + count

    for platform, count in platform_followers.items():
        by_platform.setdefault(platform, {
            "impressions": 0, "engagements": 0, "reach": 0, "followers_gained": 0,
        })["followers_count"] = count

    return overall, by_platform


def _build_timeseries(
    data: Dict,
    platform_by_id: Dict[int, str],
) -> List[NormalizedMetric]:
    """Aggregate daily rows into channel-level and per-platform series."""
    by_date: Dict[str, Dict[str, float]] = {}
    by_date_platform: Dict[Tuple[str, str], Dict[str, float]] = {}
    by_date_followers: Dict[str, float] = {}

    for row in data.get("data", []):
        dims = row.get("dimensions") or {}
        day = dims.get("reporting_period.by(day)")
        if not day:
            continue
        metrics = row.get("metrics") or {}
        pid = dims.get("customer_profile_id")
        platform = platform_by_id.get(int(pid)) if pid is not None else "Other"

        bucket = by_date.setdefault(day, {
            "impressions": 0, "engagements": 0, "reach": 0, "followers_gained": 0,
        })
        _accumulate_row(bucket, metrics, include_followers=False)

        plat_key = (day, platform)
        plat_bucket = by_date_platform.setdefault(plat_key, {
            "impressions": 0, "engagements": 0,
        })
        plat_bucket["impressions"] += _metric_val(metrics, "impressions") or 0
        plat_bucket["engagements"] += _metric_val(metrics, "engagements") or 0

        fc = _metric_val(metrics, "lifetime_snapshot.followers_count")
        if fc is not None:
            by_date_followers[day] = by_date_followers.get(day, 0) + fc

    timeseries: List[NormalizedMetric] = []
    for day in sorted(by_date):
        try:
            bucket_date = date.fromisoformat(day)
        except ValueError:
            continue
        vals = by_date[day]
        timeseries.extend([
            NormalizedMetric(
                channel=Channel.SOCIAL, metric_key="impressions", label="Impressions",
                value=vals["impressions"], date_bucket=bucket_date, unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL, metric_key="engagements", label="Engagements",
                value=vals["engagements"], date_bucket=bucket_date, unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL, metric_key="reach", label="Reach",
                value=vals["reach"], date_bucket=bucket_date, unit=MetricUnit.COUNT,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL, metric_key="followers_gained", label="Followers Gained",
                value=vals["followers_gained"], date_bucket=bucket_date, unit=MetricUnit.COUNT,
            ),
        ])
        if day in by_date_followers:
            timeseries.append(NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key="followers_count",
                label="Total Followers",
                value=by_date_followers[day],
                date_bucket=bucket_date,
                unit=MetricUnit.COUNT,
            ))

    for (day, platform), vals in sorted(by_date_platform.items()):
        try:
            bucket_date = date.fromisoformat(day)
        except ValueError:
            continue
        slug = _platform_slug(platform)
        timeseries.extend([
            NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key=f"{slug}_impressions",
                label=f"{platform} Impressions",
                value=vals["impressions"],
                date_bucket=bucket_date,
                unit=MetricUnit.COUNT,
                dimension=platform,
            ),
            NormalizedMetric(
                channel=Channel.SOCIAL,
                metric_key=f"{slug}_engagements",
                label=f"{platform} Engagements",
                value=vals["engagements"],
                date_bucket=bucket_date,
                unit=MetricUnit.COUNT,
                dimension=platform,
            ),
        ])
    return timeseries


def _summary_metric(
    metric_key: str,
    label: str,
    value: float,
    prior: float,
    unit: MetricUnit,
    dimension: Optional[str] = None,
) -> NormalizedMetric:
    return NormalizedMetric(
        channel=Channel.SOCIAL,
        metric_key=metric_key,
        label=label,
        value=value,
        prior_value=prior,
        delta_pct=_delta(value, prior),
        unit=unit,
        dimension=dimension,
    )


def _build_summary(
    current: Dict[str, float],
    prior: Dict[str, float],
    current_by_platform: Dict[str, Dict[str, float]],
    prior_by_platform: Dict[str, Dict[str, float]],
) -> List[NormalizedMetric]:
    summary: List[NormalizedMetric] = [
        _summary_metric("impressions", "Impressions", current["impressions"], prior["impressions"], MetricUnit.COUNT),
        _summary_metric("engagements", "Engagements", current["engagements"], prior["engagements"], MetricUnit.COUNT),
        _summary_metric("reach", "Reach", current["reach"], prior["reach"], MetricUnit.COUNT),
        _summary_metric(
            "followers_gained", "Followers Gained",
            current["followers_gained"], prior["followers_gained"], MetricUnit.COUNT,
        ),
    ]

    if current.get("followers_count"):
        summary.append(_summary_metric(
            "followers_count", "Total Followers",
            current["followers_count"],
            prior.get("followers_count", 0),
            MetricUnit.COUNT,
        ))

    platforms = sorted(set(current_by_platform) | set(prior_by_platform))
    for platform in platforms:
        cur = current_by_platform.get(platform, {})
        prv = prior_by_platform.get(platform, {})
        for key, label, unit in [
            ("impressions", "Impressions", MetricUnit.COUNT),
            ("engagements", "Engagements", MetricUnit.COUNT),
            ("engagement_rate", "Engagement Rate", MetricUnit.PERCENT),
        ]:
            if key == "engagement_rate":
                val = _engagement_rate(cur.get("engagements", 0), cur.get("impressions", 0))
                prv_val = _engagement_rate(prv.get("engagements", 0), prv.get("impressions", 0))
            else:
                val = cur.get(key, 0)
                prv_val = prv.get(key, 0)
            summary.append(_summary_metric(key, label, val, prv_val, unit, dimension=platform))

        if cur.get("followers_count"):
            summary.append(_summary_metric(
                "followers_count", "Followers",
                cur["followers_count"],
                prv.get("followers_count", 0),
                MetricUnit.COUNT,
                dimension=platform,
            ))

    return summary


def _post_engagements(metrics: Dict[str, Any]) -> float:
    return (
        (_metric_val(metrics, "lifetime.reactions") or 0)
        + (_metric_val(metrics, "lifetime.comments_count") or 0)
        + (_metric_val(metrics, "lifetime.shares_count") or 0)
    )


def _build_top_posts(
    posts: List[Dict],
    platform_by_id: Dict[int, str],
    name_by_id: Dict[int, str],
) -> List[TopPost]:
    ranked: List[TopPost] = []
    for post in posts:
        metrics = post.get("metrics") or {}
        impressions = _metric_val(metrics, "lifetime.impressions") or 0
        pid_raw = post.get("customer_profile_id")
        pid = int(pid_raw) if pid_raw is not None else None
        platform = platform_by_id.get(pid, "Other") if pid is not None else "Other"
        profile_name = name_by_id.get(pid, "Unknown") if pid is not None else "Unknown"
        text = (post.get("text") or "").strip()
        if len(text) > 140:
            text = text[:137] + "..."
        ranked.append(TopPost(
            text=text or "(no text)",
            platform=platform,
            profile_name=profile_name,
            created_time=post.get("created_time") or "",
            permalink=post.get("perma_link"),
            impressions=impressions,
            engagements=_post_engagements(metrics),
        ))

    ranked.sort(key=lambda p: p.impressions, reverse=True)
    return ranked[:_TOP_POSTS_LIMIT]


def _fetch_profile_data(
    client: SproutClient,
    profile_ids: List[int],
    start: date,
    end: date,
) -> Dict:
    """Fetch profile analytics, falling back to base metrics if extended fail."""
    try:
        return client.profile_metrics(profile_ids, start, end, metrics=_EXTENDED_METRICS)
    except RuntimeError as exc:
        logger.warning("Extended Sprout metrics unavailable, using base set: %s", exc)
        return client.profile_metrics(profile_ids, start, end, metrics=_BASE_METRICS)


async def get_metrics(start_date: date, end_date: date) -> ChannelMetrics:
    """
    Fetch Sprout Social metrics for [start_date, end_date] plus the prior window.
    Returns a ChannelMetrics with summary KPIs, timeseries, and top posts.

    Recent days are excluded per sprout_data_lag_days (Facebook sync lag).
    """
    settings = get_settings()
    lag_days = settings.sprout_data_lag_days
    effective_start, effective_end = _resolve_sprout_range(start_date, end_date, lag_days)

    if not settings.sprout_api_token:
        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=effective_start,
            end_date=effective_end,
            status="error",
            error_message="Sprout Social API token not yet configured (pending credential)",
        )

    if effective_start > effective_end:
        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=effective_start,
            end_date=effective_end,
            status="error",
            error_message="No complete Sprout data available for the selected date range",
        )

    try:
        client = SproutClient(settings.sprout_api_token)
        prior_start, prior_end = _prior_window(effective_start, effective_end)
        cbs_group_ids = _parse_group_ids(settings.sprout_cbs_group_ids)

        profiles = client.get_profiles(group_ids=cbs_group_ids)
        profile_ids = [int(p["customer_profile_id"]) for p in profiles]
        platform_by_id, name_by_id = _profile_maps(profiles)

        if not profile_ids:
            return ChannelMetrics(
                channel=Channel.SOCIAL,
                start_date=effective_start,
                end_date=effective_end,
                status="error",
                error_message="No Columbia Business School Sprout profiles found",
            )

        if effective_end < end_date:
            logger.info(
                "Sprout: clamped end date %s → %s (%d-day sync lag)",
                end_date,
                effective_end,
                lag_days,
            )

        logger.info(
            "Sprout: fetching metrics for %d CBS profiles (groups %s)",
            len(profile_ids),
            sorted(cbs_group_ids) if cbs_group_ids else "all",
        )

        current_data = _filter_profile_rows_through(
            _fetch_profile_data(client, profile_ids, effective_start, effective_end),
            effective_end,
        )
        prior_data = _filter_profile_rows_through(
            _fetch_profile_data(client, profile_ids, prior_start, prior_end),
            prior_end,
        )

        current, current_by_platform = _extract_totals(current_data, platform_by_id)
        prior, prior_by_platform = _extract_totals(prior_data, platform_by_id)

        top_posts: List[TopPost] = []
        try:
            raw_posts = client.post_metrics(profile_ids, effective_start, effective_end)
            top_posts = _build_top_posts(raw_posts, platform_by_id, name_by_id)
        except Exception as exc:
            logger.warning("Sprout post analytics unavailable: %s", exc)

        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=effective_start,
            end_date=effective_end,
            summary=_build_summary(current, prior, current_by_platform, prior_by_platform),
            timeseries=_filter_timeseries_through(
                _build_timeseries(current_data, platform_by_id),
                effective_end,
            ),
            top_posts=top_posts,
            status="ok",
        )

    except Exception as exc:
        logger.exception("Sprout fetch failed: %s", exc)
        return ChannelMetrics(
            channel=Channel.SOCIAL,
            start_date=effective_start,
            end_date=effective_end,
            status="error",
            error_message=str(exc),
        )
