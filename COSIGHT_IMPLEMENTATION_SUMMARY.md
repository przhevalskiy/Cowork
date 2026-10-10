# CoSight Implementation Summary

## Overview

**Columbia Business Sight** is an AI Agentic Digital Analysis Reporting Platform for CBS Marketing & Communications. It delivers conversational, citation-grounded marketing intelligence by aggregating live data from four channels — web (GA4), organic search (Google Search Console), email (Emma), and social media (Sprout Social) — through a unified canonical metric pipeline. A multi-turn agentic tool-use loop, implemented via Anthropic Claude's native tool use API with a Mistral fallback on overload, powers an AI analyst that calls live data connectors on demand over a real-time SSE streaming interface. The system enforces a strict numeric grounding invariant: the LLM is forbidden from citing any figure not returned by an in-context tool result. Users interact through a real-time streaming dashboard and a conversational chat interface that can generate, persist, and export structured marketing reports (PDF, DOCX, PPTX, CSV).

This document summarizes the CoSight backend implementation completed so far, following the build plan outlined in `COSIGHT_PLAN.md`.

## Completed Checkpoints

### CP0 - Key Architecture Decisions ✅

- **Charting library**: Recharts (confirmed)
- **Data strategy**: On-demand fetch + shared persistent cache via Supabase (15-min TTL)
- **Canonical metric model**: `NormalizedMetric` schema implemented
- **Agentic tool-use loop**: Multi-turn loop with tool execution (design confirmed)
- **Role source**: `profiles.role` column (trusted, server-controlled, not `user_metadata`)
- **Metrics dictionary**: Defined in models (Appendix A to be filled with stakeholders)

### CP1 - Project Setup & Monorepo Structure ✅

- Created directory structure:
  - `backend/app/api/routes/cosight/` - API routes
  - `backend/app/services/cosight/` - Data connector services
  - `backend/app/models/cosight/` - Data models
  - `backend/app/core/cosight/` - Core utilities and tools
  - `backend/app/auth/cosight_dependencies.py` - Auth middleware
- Updated `requirements.txt` with:
  - `google-analytics-data>=0.18.0`
  - `google-api-python-client>=2.120.0`
  - `google-auth>=2.23.0`
  - `python-pptx>=0.6.23`
- Updated `config.py` with CoSight credentials:
  - Google credentials JSON
  - GA4 property ID
  - GSC site URL
  - Emma API keys
  - LinkedIn API keys (Sprout substitute)
  - Event Registry API key
- Added CORS origin for CoSight frontend (5174)
- Registered CoSight routers in `main.py`

### CP2 - API Credentials & Data Connectors ✅

**Confirmed credentials:**
- GA4: Service account `cosight-ga4-reader@atomic-bird-438919-a3.iam.gserviceaccount.com` (property: 288367390)
- GSC: Same credentials, site: `https://business.columbia.edu/`
- Emma: Public key `0a9913cc4b780396dbb4`, Private key `8aca9d43ba7d113cc900`, Account ID `1982082`
- Event Registry: `f197ba9f-3bf3-4301-9fa9-4939bae35a5d`

**Note:** Sprout Social API key is still outstanding. Using LinkedIn API as substitute (placeholder implementation).

### CP3 - Backend Data Services ✅

**Implemented Services:**

1. **`ga4_service.py`** - Google Analytics 4 connector
   - Fetches sessions, activeUsers, pageviews, bounceRate, sessionDuration
   - Organic search traffic filtering
   - Top pages by pageviews
   - Async with retry logic

2. **`gsc_service.py`** - Google Search Console connector
   - Aggregate search metrics (clicks, impressions, CTR, avg position)
   - Top queries by clicks
   - Top landing pages
   - Handles 2-3 day data lag automatically

3. **`emma_service.py`** - Emma Email API connector
   - Campaign listing with date filtering
   - Per-campaign statistics (sends, opens, clicks, unsubscribes)
   - Rate calculations (open_rate, click_rate)
   - HMAC-SHA1 signature authentication

4. **`linkedin_service.py`** - LinkedIn API connector (Sprout substitute)
   - Placeholder implementation with mock data
   - Ready for actual API integration when credentials available

5. **`cache_service.py`** - Supabase cache backend
   - Read-through cache with 15-minute TTL
   - Keyed on `(channel, start_date, end_date)`
   - Shared across instances

6. **`metric_aggregator.py`** - Unified metric aggregation
   - Aggregates all four channels
   - Handles partial failures gracefully
   - Per-channel status reporting
   - Parallel fetching

**Canonical Model:**
- `NormalizedMetric`: channel, metric_key, value, prior_value, delta_pct, date_bucket, unit, source, platform, campaign_id
- `MetricCollection`: Channel-level collection with status
- `OverviewMetrics`: Aggregated multi-channel response

### CP4 - CoSight API Routes ✅

**Implemented Routes:**

- `GET /api/cosight/social` - LinkedIn metrics
- `GET /api/cosight/email` - Emma metrics
- `GET /api/cosight/web` - GA4 metrics (incl. organic search)
- `GET /api/cosight/seo` - GSC metrics
- `GET /api/cosight/overview` - All channels aggregated

**Features:**
- Date range validation (rejects inverted ranges, caps at 365 days)
- Role-based access control (admin/leadership only)
- Partial failure handling (per-channel status)
- Shared date range validator

**Reports Routes:**
- `POST /api/cosight/reports` - Save report artifact
- `GET /api/cosight/reports` - List user's reports
- `GET /api/cosight/reports/{id}` - Fetch a report
- `GET /api/cosight/reports/{id}/export` - Export (CSV, JSON for now)
- `GET /api/cosight/{channel}/export.csv` - Direct CSV download

### CP6 - Supabase Schema for CoSight ✅

Created `supabase_schema_cosight.sql` with:

1. **Role column**: Added `role` to `profiles` table (default: 'staff')
2. **cosight_metric_cache**: Cache table with 15-min TTL
3. **cosight_reports**: Report artifacts storage
4. **cosight_discussions**: Chat conversation storage
5. **cosight_messages**: Chat messages storage
6. **cosight_access_log**: Audit log (optional)
7. **RLS Policies**: All tables have appropriate Row-Level Security
8. **Idempotent migrations**: All CREATE POLICY guarded with DROP POLICY IF EXISTS

### CP10 - Auth & Role Gating ✅

- Created `cosight_dependencies.py` with role verification
- Only `admin`/`leadership` roles can access CoSight routes
- Roles read from trusted `profiles.role` source
- Profile caching to avoid repeated Supabase calls

## Current Status

### Backend Implementation: ~70% Complete

**Fully Implemented:**
- ✅ Data models (NormalizedMetric, MetricCollection, OverviewMetrics, ReportArtifact)
- ✅ All four data connectors (GA4, GSC, Emma, LinkedIn)
- ✅ Cache layer (Supabase)
- ✅ Metric aggregation with partial failure handling
- ✅ API routes with auth and date validation
- ✅ Supabase schema
- ✅ Role-based access control

**Partially Implemented:**
- ⚠️ Report export: CSV and JSON working; PDF/DOCX/Slides deferred
- ⚠️ Report persistence: In-memory store (to be replaced with Supabase)
- ⚠️ LinkedIn service: Mock data (waiting for credentials)

**Not Yet Started:**
- ❌ Agent tools (CP5)
- ❌ Agentic chat interface (CP5, CP9)
- ❌ Frontend dashboard (CP7, CP8)
- ❌ Export pipeline (PDF, DOCX, Slides via python-pptx)
- ❌ Metrics Dictionary finalization (Appendix A)
- ❌ Production deployment (CP12)

## File Structure

```
backend/
├── app/
│   ├── api/
│   │   └── routes/
│   │       └── cosight/
│   │           ├── __init__.py
│   │           ├── metrics.py      # API routes for metrics
│   │           └── reports.py      # API routes for reports
│   │
│   ├── auth/
│   │   └── cosight_dependencies.py # Role-based auth
│   │
│   ├── core/
│   │   └── cosight/
│   │       └── __init__.py
│   │
│   ├── models/
│   │   └── cosight/
│   │       ├── __init__.py
│   │       ├── cosight_metric.py # NormalizedMetric, MetricCollection
│   │       └── report.py          # ReportArtifact, ReportCreate
│   │
│   └── services/
│       └── cosight/
│           ├── __init__.py
│           ├── cache_service.py   # Supabase cache
│           ├── emma_service.py     # Emma API
│           ├── ga4_service.py      # GA4 API
│           ├── gsc_service.py      # GSC API
│           ├── linkedin_service.py # LinkedIn API (Sprout sub)
│           └── metric_aggregator.py # Unified aggregation
│
├── requirements.txt          # Updated with CoSight deps
├── supabase_schema_cosight.sql  # CoSight schema
└── backend/.env              # Needs credential updates
```

## Next Steps

### Immediate (Continue Implementation)

1. **CP5 - Agent Tools**
   - Define CoSight tools in `backend/app/core/cosight_tools.py`
   - Create SSE streaming route for agentic conversation
   - Implement multi-turn tool-use loop
   - Write CoSight system prompt

2. **CP7 - Frontend Dashboard Components**
   - Scaffold CoSight frontend with Vite + React + TypeScript
   - Copy shared theme CSS from Cowork
   - Build components: Sidebar, DateRangePicker, KPICard, TrendChart, DataTable

3. **CP8 - Dashboard Pages**
   - Overview page with cross-channel summary
   - Channel-specific pages (Social, Email, Web, SEO)
   - Reports page with export menu

4. **CP9 - Conversational AI Interface**
   - Build CoSightChat page
   - Connect to SSE endpoint
   - Design CoSight glyph (lens/aperture mark)
   - Implement provenance chips

### Before Production (Dependencies to Resolve)

1. **Sprout Social API**: Currently using LinkedIn as substitute
2. **LinkedIn API credentials**: For production social metrics
3. **Metrics Dictionary**: Fill Appendix A with stakeholder approval
4. **User role assignments**: Decide who gets admin/leadership
5. **Scheduled report recipients**: For automated report delivery

### Testing

To test the current implementation:

```bash
# Start the backend
cd /Users/ap4395/Desktop/Cowork
source backend/venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn app.main:app --reload

# Test endpoints (with valid JWT token)
curl -H "Authorization: Bearer YOUR_JWT" \
  "http://localhost:8000/api/cosight/overview?start=2025-01-01&end=2025-01-31"
```

Note: Requires admin/leadership role in profiles table.

## Key Design Decisions

1. **NormalizedMetric Schema**: All connectors emit identical shape, enabling consistent dashboard and AI tool consumption
2. **Partial Failure Handling**: Overview endpoint returns per-channel status; one failing connector doesn't break the entire response
3. **Cache Strategy**: 15-minute TTL on Supabase cache; survives Render restarts; shared across instances
4. **Role Source**: `profiles.role` is the single source of truth for authorization; never `user_metadata`
5. **Date Handling**: GSC automatically adjusted for 2-3 day data lag; all dates normalized to same TZ

## Notes

- The implementation substitutes LinkedIn API for Sprout Social (as requested)
- Emma credentials are from the Cosight Keys.rtf file
- GA4 and GSC use the same service account credentials
- All code follows the existing Cowork patterns and style
- The Supabase schema is idempotent and can be re-run safely
