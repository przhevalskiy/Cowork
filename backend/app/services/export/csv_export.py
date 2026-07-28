"""
CSV export — flatten ReportArtifact or ChannelMetrics into CSV rows.

All numbers come from the artifact/metric model — never from a separate fetch.
Invariant: CSV rows ≡ the metric rows in the report artifact.
"""
from __future__ import annotations

import csv
import io
from typing import List

from app.models.cosight_metric import ChannelMetrics, NormalizedMetric
from app.models.cosight_report import ReportArtifact


def metrics_to_csv(metrics: List[NormalizedMetric]) -> str:
    """Convert a flat list of NormalizedMetric to CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["channel", "metric_key", "label", "value", "prior_value",
                    "delta_pct", "date_bucket", "unit", "dimension"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for m in metrics:
        writer.writerow({
            "channel": m.channel.value,
            "metric_key": m.metric_key,
            "label": m.label or "",
            "value": m.value,
            "prior_value": m.prior_value if m.prior_value is not None else "",
            "delta_pct": m.delta_pct if m.delta_pct is not None else "",
            "date_bucket": str(m.date_bucket) if m.date_bucket else "",
            "unit": m.unit.value,
            "dimension": m.dimension or "",
        })
    return output.getvalue()


def channel_metrics_to_csv(channel_metrics: ChannelMetrics) -> str:
    """Export a full ChannelMetrics (summary + timeseries) to CSV."""
    return metrics_to_csv(channel_metrics.summary + channel_metrics.timeseries)


def report_to_csv(artifact: ReportArtifact) -> str:
    """Export all KPI rows from a ReportArtifact to CSV."""
    all_metrics: List[NormalizedMetric] = []
    for section in artifact.sections:
        all_metrics.extend(section.kpis)
    return metrics_to_csv(all_metrics)
