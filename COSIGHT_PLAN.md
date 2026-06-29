# CoSight Build Plan
Cross-channel data reporting + agentic conversation for CBS Marketing & Communications

---

## CP0 — Key Architecture Decisions (resolve before writing code)
These forks shape everything downstream. Defaults are chosen below; the unchecked ones still need a confirming sign-off.

- [x] **Charting library: Recharts.** Declarative React components, matches Cowork's frontend style, covers line / multi-series / dual-axis needs. Chart.js rejected (imperative canvas, no porting benefit). One library for all chart types in CP8.
- [ ] **Data strategy: on-demand fetch + shared persistent cache.** Connectors fetch live per request but write results to a `cosight_metric_cache` Supabase table (15-min TTL) so the cache survives Render restarts and is shared across instances. A nightly pre-warm cron primes the common ranges (7d / 30d / 90d). Full warehouse/ingest pipeline deferred to v2.
- [ ] **Canonical metric model.** All four connectors (Social, Email, Web, Search) normalize into one internal `NormalizedMetric` schema: `(channel, metric_key, value, prior_value, delta_pct, date_bucket, unit)`. Dashboard components and AI tools consume only this shape — never raw vendor JSON.
- [ ] **Agentic tool-use loop.** CoSight chat runs a real multi-turn loop (model calls tool → backend executes → result fed back into context → repeat until final answer), NOT Cowork's single-shot intercept-and-emit pattern. Tool outputs are pre-aggregated before entering context to bound tokens/cost.
- [ ] **Role source: `app_metadata` or a `profiles.role` column — never `user_metadata`.** Roles must be server-set and uneditable by users; RLS and route gating read only from the trusted source.
- [ ] **Metrics dictionary defined first.** Pin the canonical KPI list per channel and define what the cross-channel "executive summary" actually compares (you cannot sum impressions + email opens + sessions) before building any dashboard. See Appendix A.

---

## CP1 — Project Setup & Monorepo Structure
- [ ] Create `/apps/cosight/` directory alongside `/apps/cowork/` (or scaffold as sibling repo)
- [ ] Scaffold CoSight frontend with Vite + React + TypeScript (copy Cowork's vite.config, tsconfig, tailwind/CSS setup)
- [ ] Copy shared theme CSS variables + UI shell into CoSight, but **do NOT bring over chibi avatars** — CoSight uses its own analyst identity (see CP9). Keep the same UI grammar (avatar slot, modal layout) so the apps read as siblings; swap only the content.
- [ ] Copy Modal, Sidebar shell, AuthModal, Button styles into CoSight
- [ ] Set up `VITE_API_URL` pointing to shared backend
- [ ] Install charting + dashboard deps: `recharts` (charts), and confirm bundle-size impact
- [ ] Add CoSight router to shared FastAPI backend (`backend/app/api/routes/cosight/`)
- [ ] Register CoSight routers in `backend/app/main.py`
- [ ] Create Render static site for CoSight frontend
- [ ] Verify CoSight frontend deploys and loads with Cowork branding

---

## CP2 — API Credentials & Data Connectors
- [ ] Obtain Sprout Social API key + verify endpoint access (`GET /v1/analytics/...`)
- [ ] Obtain Emma API key + verify endpoint access (campaigns, opens, clicks)
- [x] **Verify GA4 API access — DONE & smoke-tested (2026-06-29).** Live `runReport` returned real data (~12k activeUsers/day). Concrete setup:
  - GCP project: `atomic-bird-438919-a3` (display name "Cosight"); **Google Analytics Data API** (`analyticsdata.googleapis.com`) enabled
  - Service account: `cosight-ga4-reader@atomic-bird-438919-a3.iam.gserviceaccount.com`, JSON key downloaded
  - Granted **Viewer** on the GA4 property via Property Access Management
  - **Property: `288367390`** — "CBS Main Website (Root) - GA4" (numeric ID, NOT the `G-XXXX` measurement ID)
  - Library: `google-analytics-data` (installed in backend venv — **add to `requirements.txt`**)
  - Auth scope: `https://www.googleapis.com/auth/analytics.readonly`
- [x] **Verify Google Search Console API access — DONE & smoke-tested (2026-06-29).** Live `searchanalytics.query` returned real keyword data (e.g. "columbia business school" — 3,994 clicks, pos 1.2). Reuses the SAME GCP project + service account + JSON key as GA4:
  - **Google Search Console API** (`searchconsole.googleapis.com`) enabled in `atomic-bird-438919-a3`
  - Granted **Full** to `cosight-ga4-reader@...` via Search Console → Users and permissions
  - **Site (URL-prefix property): `https://business.columbia.edu/`** (GSC identifies by site URL, not a numeric ID)
  - Library: `google-api-python-client` (installed in backend venv — **add to `requirements.txt`**)
  - Auth scope: `https://www.googleapis.com/auth/webmasters.readonly`
  - Provides exactly what GA4 cannot: keyword **queries, impressions, CTR, average position** (replaces BrightEdge rank-tracking, first-party + free)
- [ ] Obtain Sprout / Emma credentials (GA4 + Search Console confirmed; Sprout + Emma still outstanding)
- [ ] Store all credentials in `backend/.env` and Render environment variables
  - [ ] Google APIs: move the JSON out of `~/Downloads` and load it as `GOOGLE_CREDENTIALS_JSON` (full JSON string, shared by GA4 + GSC) + `GA4_PROPERTY_ID=288367390` + `GSC_SITE_URL=https://business.columbia.edu/` — never commit the key file
- [ ] Add all keys to `backend/app/core/config.py` Settings model
- [ ] Document each vendor's rate limits, quota, and pagination behavior (drives CP3 retry/paging design)
- [ ] Note credential expiry / rotation requirements per vendor (esp. GA4 service-account key)

---

## CP3 — Backend Data Services
- [ ] Create `backend/app/services/sprout_service.py` — fetch social metrics (impressions, engagement, reach, follower growth) per platform (LinkedIn, Instagram, Twitter)
- [ ] Create `backend/app/services/emma_service.py` — fetch email metrics (sends, opens, clicks, unsubscribes) per campaign
- [ ] Create `backend/app/services/ga4_service.py` — fetch web metrics (sessions, pageviews, conversions, bounce rate, top pages) **plus organic-search traffic** (sessions/users from the Organic Search channel, top organic landing pages)
  - Auth pattern **verified working**: `service_account.Credentials.from_service_account_info(json.loads(GOOGLE_CREDENTIALS_JSON), scopes=[".../analytics.readonly"])` → `BetaAnalyticsDataClient` → `run_report(property="properties/288367390", ...)`
  - Reference smoke test (working): `scratchpad/ga4_smoke.py` — graduate it into this service
  - `run_report` with `Dimension(name="date")` + `Metric(name="activeUsers"/"sessions"/...)` confirmed returning rows
- [ ] Create `backend/app/services/gsc_service.py` — fetch search metrics (top queries, impressions, clicks, CTR, average position) from Google Search Console
  - Auth pattern **verified working**: same shared key with scope `.../webmasters.readonly` → `build("searchconsole", "v1", credentials=creds)` → `searchanalytics().query(siteUrl="https://business.columbia.edu/", body={...})`
  - Reference smoke test (working): `scratchpad/gsc_smoke.py` — graduate it into this service
  - Note GSC's ~2–3 day data lag: default the window to end ~3 days back
- [ ] Each service exposes a `get_metrics(start_date, end_date)` async method
- [ ] **Normalization layer:** each connector maps its raw response into the canonical `NormalizedMetric` schema (CP0); define the model in `backend/app/models/cosight_metric.py`
- [ ] **Prior-period support:** `get_metrics` fetches both the requested window and the immediately-prior equal-length window, computing `prior_value` + `delta_pct` per metric (powers KPI deltas and the agent's trend claims)
- [ ] **Rate limits / pagination / retry:** handle vendor pagination, exponential backoff on 429/5xx, and per-vendor concurrency caps (esp. Sprout, GA4, GSC)
- [ ] **Time-zone alignment:** normalize all date buckets to one canonical TZ so "last month" means the same window across all four channels (mind GSC's 2–3 day reporting lag)
- [ ] **Caching backend (resolves CP0 data strategy):** read-through cache in a `cosight_metric_cache` Supabase table keyed on `(channel, metric_key, date_range)`, 15-min TTL — survives Render restarts and is shared across instances (in-memory dict is NOT sufficient)
- [ ] Write **fixture/mocked** unit tests per connector (recorded sample payloads) — primary test path
- [ ] Add a thin live smoke test per connector, run manually / nightly (quota-aware), not in CI

---

## CP4 — CoSight API Routes
- [ ] `GET /api/cosight/social` — returns Sprout metrics for date range
- [ ] `GET /api/cosight/email` — returns Emma metrics for date range
- [ ] `GET /api/cosight/web` — returns GA4 metrics (incl. organic-search traffic) for date range
- [ ] `GET /api/cosight/seo` — returns Google Search Console metrics (queries, impressions, CTR, position) for date range
- [ ] `GET /api/cosight/overview` — aggregates all four channels into a single payload
- [ ] **Partial-failure semantics for `/overview`:** return per-channel `status` (`ok` / `stale` / `error`) and serve the channels that succeeded rather than failing the whole payload when one connector is down/slow
- [ ] All routes require auth (`get_current_user` dependency)
- [ ] Add role check — only `admin` / `leadership` roles can access CoSight routes; read role from the trusted source (CP0), not `user_metadata`
- [ ] Add date range query params (`?start=2025-01-01&end=2025-03-31`) to all routes
- [ ] Validate/clamp date ranges (reject empty/inverted ranges; cap max span to protect quota)

---

## CP5 — AI Agent Tools
- [ ] Define CoSight tools in `backend/app/core/cosight_tools.py`:
  - `get_social_metrics` — pulls Sprout data for a given date range and platform
  - `get_email_metrics` — pulls Emma data for a given date range and campaign
  - `get_web_metrics` — pulls GA4 data (incl. organic-search traffic) for a given date range and page/goal
  - `get_seo_metrics` — pulls Google Search Console data (queries, impressions, CTR, position) for a given date range
  - `generate_report` — compiles all channel data into a structured report object
- [ ] Create `backend/app/api/routes/cosight/chat.py` — SSE streaming route for agentic conversation
- [ ] **Accept optional scoped context** in the request (`{ channel, metric_key, date_range, value, delta }`) and inject it into the first turn so a KPI drill-in (CP8/CP9) starts grounded — the agent never re-asks which metric or timeframe
- [ ] **Implement a multi-turn tool-use loop** (NOT Cowork's single-shot intercept): model emits tool call → backend executes connector → result appended to context → loop until the model returns a final text answer. Cap max iterations.
- [ ] **Pre-aggregate tool results before they enter context** (summary stats / top-N, not raw rows) to bound token usage and cost; set a per-conversation token/iteration budget
- [ ] **Numeric grounding:** tools return data only via structured tool results; system prompt forbids citing any figure not present in a tool result, so leadership-facing numbers can't be hallucinated
- [ ] Write CoSight system prompt: analyst persona, use tools to answer, cite specific numbers (grounded only), surface trends, flag anomalies
- [ ] Wire tools into Claude (primary) with Mistral fallback (same overload pattern as Cowork)
- [ ] Persist CoSight conversations to Supabase (separate `cosight_discussions` table or `type` column)

---

## CP6 — Supabase Schema for CoSight
- [ ] Create `cosight_discussions` table (id, user_id, title, created_at)
- [ ] Create `cosight_messages` table (id, discussion_id, role, content, timestamp)
- [ ] Create `cosight_reports` table (id, user_id, title, payload JSONB, date_range, created_at) — saved report snapshots
- [ ] Create `cosight_metric_cache` table (channel, metric_key, date_range, payload JSONB, fetched_at) — shared connector cache (CP3)
- [ ] **Role storage:** add `role` to `profiles` (`staff` / `admin` / `leadership`) or set via `app_metadata` — server-controlled only, NOT user-editable `user_metadata`
- [ ] Set RLS policies: users read only their own discussions; admins read all (policy reads the trusted role source)
- [ ] **Idempotent migration:** guard every `CREATE POLICY` with a preceding `DROP POLICY IF EXISTS` so the schema file can be re-run safely
- [ ] (Optional) `cosight_access_log` table — audit who queried which channel/date-range, for leadership-data governance
- [ ] Run migration SQL and update `supabase_schema.sql`

---

## CP7 — Frontend Dashboard Pages
- [ ] Set up React Router with routes: `/`, `/social`, `/email`, `/web`, `/seo`, `/reports`, `/chat`
- [ ] Build `<Sidebar>` with CoSight nav links (reuse Cowork Sidebar shell, swap nav items)
- [ ] Build `<DateRangePicker>` component (presets: 7d, 30d, 90d, custom)
- [ ] Build `<KPICard>` component — metric name, value, delta vs prior period, trend arrow (delta/`prior_value` come from the connector layer per CP3, not computed in the component)
- [ ] Build `<TrendChart>` component — line chart using **Recharts**; support multi-series and dual-axis (for cross-channel overlays)
- [ ] Build `<DataTable>` component — sortable, filterable, paginated
- [ ] Build `<InsightsPanel>` component — Mistral/Claude narrative summary (static, refreshable)
- [ ] Build shared **loading skeleton, empty-state, and error-state** components, plus a per-channel "stale data" badge (consumes the `status` from `/overview`)

---

## CP8 — Dashboard Pages (Data-Wired)
- [ ] **Overview page** — KPI bar (all 4 channels), cross-channel trend chart, AI executive summary
- [ ] **Social Media page** — per-platform KPI cards, engagement trend, top posts table
- [ ] **Email page** — campaign KPI cards, open/click trend, campaign performance table
- [ ] **Web page** — GA4 KPI cards, sessions trend, top pages + conversion table, plus an **organic-search** section (organic sessions trend, top organic landing pages)
- [ ] **SEO / Search page** — Search Console KPI cards (clicks, impressions, CTR, avg position), top-queries table, position/CTR trend
- [ ] **Reports page** — list of saved report snapshots, export to PDF/DOCX (reuse Cowork export services)
- [ ] Every page handles loading / empty-range / connector-error states and renders the stale-data badge per channel (no blank or hung dashboards)
- [ ] **"Ask about this" affordance** on KPI cards (and ideally chart segments / table rows) that opens a contextual agentic chat scoped to that metric — see CP9 "Drill-in: KPI → contextual chat"

---

## CP9 — Conversational AI Interface
- [ ] Build `<CoSightChat>` page at `/chat` — same chat UI pattern as Cowork (reuse ChatArea, ChatInput, MessageBubble)
- [ ] Connect to `POST /api/cosight/chat/stream` SSE endpoint
- [ ] **Assistant identity = CoSight glyph, not a chibi character.** Design a minimal "lens / aperture / sight" mark (on-brand for "co-sight" = seeing the data together) as the assistant marker — conveys analytical authority, not cuteness. Reasoning: leadership-facing numbers need a trusted-analyst tone; a cute mascot undercuts data credibility.
- [ ] **Glyph as a state indicator** — design + build its three states: `loading/active` (animates while the agent is querying, e.g. "Querying GA4… analyzing 28 days…"), and `done` (steady mark). The agent visibly showing its work builds trust in the numbers.
- [ ] **Provenance chips are the primary marker.** Promote data-source chips ("Sprout" / "GA4" / "Search Console") from a side-detail to the lead identity on each assistant message — the agent's "face" is its citations. Chips reflect which tools were actually called.
- [ ] Support follow-up questions in the same conversation thread
- [ ] Add "Export this answer" button on assistant messages (PDF/DOCX)
- [ ] Add quick-action prompts on empty state (e.g. "Summarize last month", "What's trending?", "Compare channels")

### Drill-in: KPI → contextual chat
The feature that links the dashboards (CP8) to the chat — click any KPI to interrogate it agentically, pre-grounded so the agent never re-asks which metric or timeframe.
- [ ] Seed the chat with **scoped context** on drill-in: `{ channel, metric_key, date_range, value, delta }` (reuse Cowork's nav-state pattern — `navigate('/chat', { state: { ... } })`, as in `Sidebar.tsx` `handleSampleQuestionSelect`)
- [ ] **Carry over the dashboard's active date range** into the conversation, so "last month" in the chat matches the card the user clicked (a different window would silently mislead — trust-killer)
- [ ] Agent opens grounded in that KPI, then uses the CP5 tool loop for the deeper cut (per-campaign / per-query breakdown that explains the number)
- [ ] **MVP:** drill-in navigates to the full `/chat` page, pre-seeded (low cost, reuses existing pattern)
- [ ] **v2:** inline side-drawer chat that slides over the dashboard, so the user can interrogate a KPI without losing sight of the chart

---

## CP10 — Auth & Role Gating
- [ ] Add `role` to Supabase user metadata on signup (default: `staff`)
- [ ] Admin panel or Supabase dashboard to assign `admin` / `leadership` roles
- [ ] Backend middleware checks role before serving CoSight routes
- [ ] Frontend gates CoSight nav/pages — redirects non-admins to Cowork
- [ ] CoSight AuthModal reuses Cowork's modal layout + branding, but leads with the **CoSight glyph** (CP9), not the chibi — same design language, analyst identity

---

## CP11 — Reporting & Export
- [ ] "Save Report" button on Overview page — snapshots current metrics to `cosight_reports` table
- [ ] Reports page lists saved snapshots with date, title, channel summary
- [ ] Export any report to PDF (reuse `pdfExport.ts` with CoSight branding)
- [ ] Export any report to DOCX (reuse `docxExport.ts` with CoSight branding)
- [ ] Scheduled reports (optional): emails weekly PDF summary to configured recipients via Resend
  - [ ] Provision the scheduler — Render Cron Job (repo currently has no scheduler, only `start.sh`); the same cron also runs the CP0 nightly cache pre-warm

---

## CP12 — Deployment
- [ ] Add `VITE_API_URL` to CoSight Render static site environment
- [ ] Add all data connector API keys to Render backend environment
- [ ] Verify CORS allows CoSight frontend origin in backend `CORS_ORIGINS`
- [ ] Verify Supabase RLS policies work in production
- [ ] Smoke test all 4 data connectors in production
- [ ] Smoke test agentic chat with tool calls end-to-end in production
- [ ] Smoke test PDF/DOCX export in production
- [ ] Add monitoring/alerting for connector failures and rate-limit breaches (log + notify on repeated errors)
- [ ] Share CoSight URL with CBS MarComm team for UAT

---

## Dependencies (must resolve before build)
- [ ] Sprout Social API access confirmed
- [ ] Emma API access confirmed
- [x] **GA4 service account + property ID confirmed** (property `288367390`, smoke-tested 2026-06-29 — see CP2)
- [x] **Google Search Console access confirmed** (site `https://business.columbia.edu/`, smoke-tested 2026-06-29 — see CP2; same credential as GA4)
- [ ] User role assignments decided (who gets `leadership` vs `admin` vs `staff`)
- [ ] Scheduled report recipients list confirmed
- [ ] CP0 data strategy signed off (on-demand + shared cache vs. full ingest)
- [ ] Metrics dictionary (Appendix A) filled in and approved by MarComm stakeholders

---

## Appendix A — Metrics Dictionary (define before CP7/CP8)
The canonical KPI list each dashboard renders and each AI tool reports. Fill in before building dashboards.

- [ ] **Social (Sprout):** impressions, engagement rate, reach, follower growth, top posts — per platform (LinkedIn / Instagram / Twitter)
- [ ] **Email (Emma):** sends, open rate, click rate, unsubscribe rate — per campaign
- [ ] **Web (GA4):** sessions, pageviews, conversions, bounce rate, top pages, **organic-search traffic** (organic sessions/users, top organic landing pages)
- [ ] **Search (Google Search Console):** clicks, impressions, CTR, average position, top queries, top landing pages — the keyword/ranking side GA4 can't provide (replaces BrightEdge)
- [ ] **Cross-channel "executive summary":** define what it actually compares — NOT a sum across channels (impressions + opens + sessions is meaningless). Decide the few normalized indicators (e.g. period-over-period % change per channel, goal attainment) the Overview surfaces.
- [ ] **Goals / benchmarks:** target values per KPI so deltas have meaning (is 5% engagement good?) — optional v1, but decide now
