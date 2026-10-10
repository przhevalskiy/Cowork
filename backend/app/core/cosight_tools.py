"""
CoSight AI tool definitions — consumed by the agentic chat loop.

Tools are pre-aggregated before entering context to bound token usage.
Numeric grounding invariant: every figure the agent emits must trace to a
tool result — the system prompt forbids citing any number not returned by a tool.
"""
from __future__ import annotations

COSIGHT_TOOLS = [
    {
        "name": "get_web_metrics",
        "description": (
            "Fetch Google Analytics 4 web metrics for a date range. "
            "Returns sessions, pageviews, active users, bounce rate, conversions, "
            "avg session duration, organic sessions, and daily timeseries. "
            "Use this for any question about website traffic, user behavior, or "
            "organic search channel performance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_seo_metrics",
        "description": (
            "Fetch Google Search Console SEO metrics for a date range. "
            "Returns total clicks, impressions, CTR, average position, "
            "top search queries with their individual metrics, and daily timeseries. "
            "Use this for any question about keyword rankings, organic search visibility, "
            "top queries, or search performance. Note: GSC has a ~3 day data lag."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_email_metrics",
        "description": (
            "Fetch Emma email marketing metrics for a date range. "
            "Returns total sends, open rate, click rate, and unsubscribe rate "
            "aggregated across all campaigns in the period, plus prior-period deltas. "
            "Use this for any question about email performance, campaign effectiveness, "
            "or audience engagement via email."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_social_metrics",
        "description": (
            "Fetch Sprout Social metrics for a date range. "
            "Returns impressions, engagements, reach, follower growth, top posts, "
            "and per-platform breakdowns across CBS Sprout profiles, plus prior-period deltas. "
            "Note: Sprout data excludes the most recent 2 days due to Facebook sync lag."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "end_date": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Assemble a structured report artifact from fetched metrics. "
            "Call AFTER fetching the relevant channel metrics with the other tools. "
            "The artifact is persisted and can be exported to PDF, DOCX, PPTX, or CSV. "
            "Returns the report ID and a summary of what was included."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Report title, e.g. 'Q1 2025 Marketing Performance'",
                },
                "date_range_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format",
                },
                "date_range_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format",
                },
                "channels": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["web", "search", "email", "social"]},
                    "description": "Which channels to include in the report",
                },
                "executive_summary": {
                    "type": "string",
                    "description": "2–4 sentence executive summary of the period's performance",
                },
            },
            "required": ["title", "date_range_start", "date_range_end", "channels"],
        },
    },
]

# System prompt for the CoSight analyst agent
COSIGHT_SYSTEM_PROMPT = """You are CoSight, an AI data analyst for Columbia Business School Marketing & Communications.

Your job: answer questions about marketing performance data using your tools, and generate structured reports on demand.
You have access to web analytics (Google Analytics 4), organic search performance (Google Search Console),
email marketing (Emma), and social media (Sprout Social) data across CBS's digital channels.

## CRITICAL — Numeric Grounding
You MUST ONLY cite numbers that were returned by a tool call in this conversation.
NEVER invent, estimate, or recall figures from memory. If you don't have data from
a tool result, call the appropriate tool first.

## How to answer
1. Identify which channels are relevant to the question.
2. Call the appropriate tool(s) with the correct date range.
3. Analyze the results — surface trends, compare to prior period, flag anomalies.
4. Cite specific numbers with their source (e.g. "GA4 shows 42,300 sessions in the
   past 30 days, up 8.2% from the prior period").
5. Be concise and executive-ready — lead with the most important finding.

## Date ranges
- "Last 30 days" = today minus 30 days to yesterday
- "Last month" = first to last day of the previous calendar month
- "Last quarter" = previous calendar quarter
- When the user doesn't specify a range, ask once to clarify before calling tools.

## On generate_report
Call generate_report only when the user explicitly asks for a report or summary document.
Always fetch the channel metrics first, then call generate_report with the assembled data.

## Tone
Clear, analytical, data-driven. No hedging, no filler. Lead with the number, follow
with context. Flag if data is stale (GSC has a ~3 day lag) or if a connector is unavailable."""
