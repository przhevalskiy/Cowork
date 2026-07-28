# CoSight Build Plan
Cross-channel data reporting + agentic conversation for CBS Marketing & Communications

---

> **Review checkpoints (RC):** between each phase sits a checkpoint — a code-review gate that verifies the phase's **invariants** hold and sweeps for gaps / discrepancies / holes before the next phase begins. Do not advance a CP until its checkpoint passes.

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

### ✅ Checkpoint RC0 — review after CP0 (before CP1)
- [ ] **Invariant:** every CP0 decision is resolved or has a named sign-off owner — no blocking "TBD" leaks into build
- [ ] **Consistency:** decisions don't contradict each other — role source is identical in CP4/CP6/CP10; the data strategy (CP0) matches the cache backend (CP3); the channel set (4: Social/Email/Web/Search) is the same everywhere
- [ ] **Gap:** the Metrics Dictionary (Appendix A) is filled and stakeholder-approved before any dashboard work

---

## CP1 — Project Setup & Monorepo Structure
- [ ] Create `/apps/cosight/` directory alongside `/apps/cowork/` (or scaffold as sibling repo)
- [ ] Scaffold CoSight frontend with Vite + React + TypeScript (copy Cowork's vite.config, tsconfig, tailwind/CSS setup)
- [ ] Copy shared theme CSS variables + UI shell into CoSight, but **do NOT bring over chibi avatars** — CoSight uses its own analyst identity (see CP9). Keep the same UI grammar (avatar slot, modal layout) so the apps read as siblings; swap only the content.
- [ ] Copy Modal, Sidebar shell, AuthModal, Button styles into CoSight
- [ ] Set up `VITE_API_URL` pointing to shared backend
- [ ] Frontend deps: `recharts` (charts), `html-to-image` (chart PNG export), a CSV util (`papaparse` or native); confirm bundle-size impact
- [x] **Slides target decided: `python-pptx`** (server-side `.pptx` generation). Free, in the backend's Python stack, full layout control, no extra auth — chosen over Google Slides (avoids the Drive/Slides write-scope + OAuth setup) and over Aspose/SaaS (cost/dependency). Backend dep — **add `python-pptx` to `requirements.txt`**. Tradeoff: we own the layout, so a branded deck **template/style must be defined** (next item).
- [ ] Add CoSight router to shared FastAPI backend (`backend/app/api/routes/cosight/`)
- [ ] Register CoSight routers in `backend/app/main.py`
- [ ] Create Render static site for CoSight frontend
- [ ] Verify CoSight frontend deploys and loads with Cowork branding

---

### ✅ Checkpoint RC1 — review after CP1 (before CP2)
- [ ] **Invariant (no regression):** Cowork still builds and runs unchanged — adding CoSight routers + CORS broke none of its existing routes
- [ ] **Invariant:** no route-prefix collision (`/api/chat/*` vs `/api/cosight/*`); CORS allows the CoSight dev port (5174) and the prod origin
- [ ] **Gap:** zero chibi assets/components leaked into CoSight; dev ports don't clash (5173 vs 5174)

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

### ✅ Checkpoint RC2 — review after CP2 (before CP3)
- [ ] **Invariant:** each connector's credential is proven by a live smoke test *before* its service is built (GA4 ✓, GSC ✓; Sprout/Emma pending)
- [ ] **Invariant (security):** all secrets live in env vars — grep the diff to confirm no key file or token is committed
- [ ] **Gap:** each vendor's rate limits / pagination / quota are documented (feeds CP3 retry & paging design)

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
- [ ] **Export pipeline (one artifact → many formats)** — a report artifact (CP5) is rendered by per-format services so the formats aren't five one-off builds:
  - `backend/app/services/export/pdf_export.py` + `docx_export.py` — reuse Cowork's existing exporters with CoSight branding
  - `backend/app/services/export/slides_export.py` — `.pptx` via **`python-pptx`** (CP1); pours the report artifact into a branded CBS deck template (see CP11 styling task)
  - `backend/app/services/export/csv_export.py` — flatten `NormalizedMetric` rows to CSV (nearly free since the canonical model is already tabular)
  - chart-image export is **client-side** (Recharts SVG → PNG via `html-to-image`); add a server-side headless render only if charts must be embedded into Slides/PDF
- [ ] **Normalization layer:** each connector maps its raw response into the canonical `NormalizedMetric` schema (CP0); define the model in `backend/app/models/cosight_metric.py`
- [ ] **Prior-period support:** `get_metrics` fetches both the requested window and the immediately-prior equal-length window, computing `prior_value` + `delta_pct` per metric (powers KPI deltas and the agent's trend claims)
- [ ] **Rate limits / pagination / retry:** handle vendor pagination, exponential backoff on 429/5xx, and per-vendor concurrency caps (esp. Sprout, GA4, GSC)
- [ ] **Time-zone alignment:** normalize all date buckets to one canonical TZ so "last month" means the same window across all four channels (mind GSC's 2–3 day reporting lag)
- [ ] **Caching backend (resolves CP0 data strategy):** read-through cache in a `cosight_metric_cache` Supabase table keyed on `(channel, metric_key, date_range)`, 15-min TTL — survives Render restarts and is shared across instances (in-memory dict is NOT sufficient)
- [ ] Write **fixture/mocked** unit tests per connector (recorded sample payloads) — primary test path
- [ ] Add a thin live smoke test per connector, run manually / nightly (quota-aware), not in CI

---

### ✅ Checkpoint RC3 — review after CP3 (before CP4)
- [ ] **Invariant (the big one):** all four connectors emit an *identical* `NormalizedMetric` shape — diff their outputs field-by-field; nothing downstream may branch on which vendor produced a metric
- [ ] **Invariant:** `prior_value` + `delta_pct` are computed in the service layer (not downstream); all date buckets are in one canonical TZ; GSC's 2–3 day lag is handled
- [ ] **Invariant:** the cache is shared + persistent (Supabase) and survives a restart — a cache hit and a cache miss return byte-identical data
- [ ] **Gap:** every connector has fixture tests and a partial-failure path

---

## CP4 — CoSight API Routes
- [ ] `GET /api/cosight/social` — returns Sprout metrics for date range
- [ ] `GET /api/cosight/email` — returns Emma metrics for date range
- [ ] `GET /api/cosight/web` — returns GA4 metrics (incl. organic-search traffic) for date range
- [ ] `GET /api/cosight/seo` — returns Google Search Console metrics (queries, impressions, CTR, position) for date range
- [ ] `GET /api/cosight/overview` — aggregates all four channels into a single payload
- [ ] `POST /api/cosight/reports` — save a report artifact; `GET /api/cosight/reports` / `GET /api/cosight/reports/{id}` — list/fetch
- [ ] `GET /api/cosight/reports/{id}/export?format=pdf|docx|slides|csv` — render the saved artifact to the requested format (CP3 export pipeline)
- [ ] `GET /api/cosight/{channel}/export.csv` — direct CSV download of a channel's metrics for a date range
- [ ] **Partial-failure semantics for `/overview`:** return per-channel `status` (`ok` / `stale` / `error`) and serve the channels that succeeded rather than failing the whole payload when one connector is down/slow
- [ ] All routes require auth (`get_current_user` dependency)
- [ ] Add role check — only `admin` / `leadership` roles can access CoSight routes; read role from the trusted source (CP0), not `user_metadata`
- [ ] Add date range query params (`?start=2025-01-01&end=2025-03-31`) to all routes
- [ ] Validate/clamp date ranges (reject empty/inverted ranges; cap max span to protect quota)

---

### ✅ Checkpoint RC4 — review after CP4 (before CP5)
- [ ] **Invariant:** every route requires auth AND the role check; date-range validation/clamping is identical across all routes (one shared validator, not per-route copies)
- [ ] **Invariant:** `/overview` never 500s when a single connector is down — it returns per-channel `status`; verify by killing one connector
- [ ] **Gap:** export routes map 1:1 onto the CP3 export pipeline; response schemas are consistent across routes

---

## CP5 — AI Agent Tools
- [ ] Define CoSight tools in `backend/app/core/cosight_tools.py`:
  - `get_social_metrics` — pulls Sprout data for a given date range and platform
  - `get_email_metrics` — pulls Emma data for a given date range and campaign
  - `get_web_metrics` — pulls GA4 data (incl. organic-search traffic) for a given date range and page/goal
  - `get_seo_metrics` — pulls Google Search Console data (queries, impressions, CTR, position) for a given date range
  - `generate_report` — assembles a structured **report artifact** (sections + referenced KPIs + chart specs + data tables + narrative), NOT a flat blob — this artifact is the single source the export layer (CP11) renders to every format
  - `export_report(report_id, format)` — agent-callable export to `pdf | docx | slides | csv` (lets the user say "send me that as slides" in chat)
- [ ] Create `backend/app/api/routes/cosight/chat.py` — SSE streaming route for agentic conversation
- [ ] **Reports via agentic conversation:** when the agent calls `generate_report`, emit a new **`report` SSE event** (same pattern as Cowork's `checklist`/`submitted`) so the report renders inline in chat with an export menu; persist the artifact to `cosight_reports`
- [ ] **Accept optional scoped context** in the request (`{ channel, metric_key, date_range, value, delta }`) and inject it into the first turn so a KPI drill-in (CP8/CP9) starts grounded — the agent never re-asks which metric or timeframe
- [ ] **Implement a multi-turn tool-use loop** (NOT Cowork's single-shot intercept): model emits tool call → backend executes connector → result appended to context → loop until the model returns a final text answer. Cap max iterations.
- [ ] **Pre-aggregate tool results before they enter context** (summary stats / top-N, not raw rows) to bound token usage and cost; set a per-conversation token/iteration budget
- [ ] **Numeric grounding:** tools return data only via structured tool results; system prompt forbids citing any figure not present in a tool result, so leadership-facing numbers can't be hallucinated
- [ ] Write CoSight system prompt: analyst persona, use tools to answer, cite specific numbers (grounded only), surface trends, flag anomalies
- [ ] Wire tools into Claude (primary) with Mistral fallback (same overload pattern as Cowork)
- [ ] Persist CoSight conversations to Supabase (separate `cosight_discussions` table or `type` column)

---

### ✅ Checkpoint RC5 — review after CP5 (before CP6)
- [ ] **Invariant (numeric grounding):** every figure the agent emits traces to a tool result — adversarially prompt it to invent a number and confirm it refuses
- [ ] **Invariant:** the tool-use loop always terminates (max-iteration cap), and tool outputs are pre-aggregated within the token budget
- [ ] **Invariant:** the report artifact is the *single* source for all exports; tools key on the same `channel`/`service_type` the CP4 routes use
- [ ] **Gap:** scoped-context injection works for KPI drill-in (agent doesn't re-ask metric/timeframe)

---

## CP6 — Supabase Schema for CoSight
- [ ] Create `cosight_discussions` table (id, user_id, title, created_at)
- [ ] Create `cosight_messages` table (id, discussion_id, role, content, timestamp)
- [ ] Create `cosight_reports` table (id, user_id, title, payload JSONB, date_range, created_at) — `payload` holds the structured **report artifact** (CP5) that the export layer renders to any format
- [ ] Create `cosight_metric_cache` table (channel, metric_key, date_range, payload JSONB, fetched_at) — shared connector cache (CP3)
- [ ] **Role storage:** add `role` to `profiles` (`staff` / `admin` / `leadership`) or set via `app_metadata` — server-controlled only, NOT user-editable `user_metadata`
- [ ] Set RLS policies: users read only their own discussions; admins read all (policy reads the trusted role source)
- [ ] **Idempotent migration:** guard every `CREATE POLICY` with a preceding `DROP POLICY IF EXISTS` so the schema file can be re-run safely
- [ ] (Optional) `cosight_access_log` table — audit who queried which channel/date-range, for leadership-data governance
- [ ] Run migration SQL and update `supabase_schema.sql`

---

### ✅ Checkpoint RC6 — review after CP6 (before CP7)
- [ ] **Invariant:** the migration is idempotent — run it twice; the second run is a clean no-op with no policy errors (`DROP POLICY IF EXISTS` guards present)
- [ ] **Invariant (security):** role lives only in the trusted source — grep confirms `user_metadata` is never read for authorization anywhere
- [ ] **Invariant:** FK dependency order is valid; the cache-table key matches CP3; `cosight_reports.payload` matches the artifact schema

---

## CP7 — Frontend Dashboard Pages
- [ ] Set up React Router with routes: `/`, `/social`, `/email`, `/web`, `/seo`, `/reports`, `/chat`
- [ ] Build `<Sidebar>` with CoSight nav links (reuse Cowork Sidebar shell, swap nav items)
- [ ] Build `<DateRangePicker>` component (presets: 7d, 30d, 90d, custom)
- [ ] Build `<KPICard>` component — metric name, value, delta vs prior period, trend arrow (delta/`prior_value` come from the connector layer per CP3, not computed in the component)
- [ ] Build `<TrendChart>` component — line chart using **Recharts**; support multi-series and dual-axis (for cross-channel overlays); include a **"Download as image"** action (SVG → PNG via `html-to-image`)
- [ ] Build `<DataTable>` component — sortable, filterable, paginated; include a **"Download CSV"** action
- [ ] Build `<InsightsPanel>` component — Mistral/Claude narrative summary (static, refreshable)
- [ ] Build `<ReportArtifact>` renderer — renders the CP5 report artifact (sections, KPIs, charts, tables) with an **export menu** (PDF / DOCX / Slides / CSV); used both on the Reports page and inline in chat
- [ ] Build shared **loading skeleton, empty-state, and error-state** components, plus a per-channel "stale data" badge (consumes the `status` from `/overview`)

---

### ✅ Checkpoint RC7 — review after CP7 (before CP8)
- [ ] **Invariant:** components consume only `NormalizedMetric` — no raw vendor JSON reaches a component, and deltas come from the data layer (not computed in-component)
- [ ] **Invariant:** every data component ships loading / empty / error states; chart-image + CSV affordances are present
- [ ] **Gap:** `<ReportArtifact>` renders the *exact* artifact type the backend emits (shared/matching type, not a hand-rolled parallel shape)

---

## CP8 — Dashboard Pages (Data-Wired)
- [ ] **Overview page** — KPI bar (all 4 channels), cross-channel trend chart, AI executive summary
- [ ] **Social Media page** — per-platform KPI cards, engagement trend, top posts table
- [ ] **Email page** — campaign KPI cards, open/click trend, campaign performance table
- [ ] **Web page** — GA4 KPI cards, sessions trend, top pages + conversion table, plus an **organic-search** section (organic sessions trend, top organic landing pages)
- [ ] **SEO / Search page** — Search Console KPI cards (clicks, impressions, CTR, avg position), top-queries table, position/CTR trend
- [ ] **Reports page** — list of saved report artifacts; open any in `<ReportArtifact>` with the full export menu (PDF / DOCX / Slides / CSV)
- [ ] Every page handles loading / empty-range / connector-error states and renders the stale-data badge per channel (no blank or hung dashboards)
- [ ] **"Ask about this" affordance** on KPI cards (and ideally chart segments / table rows) that opens a contextual agentic chat scoped to that metric — see CP9 "Drill-in: KPI → contextual chat"

---

### ✅ Checkpoint RC8 — review after CP8 (before CP9)
- [ ] **Invariant:** one date-range source per page — the picker drives every query; no component silently fetches a different window
- [ ] **Invariant:** every page degrades gracefully on partial failure (stale badges), never blank or hung
- [ ] **Invariant:** "Ask about this" carries the metric + the *currently displayed* date range into chat (drill-in context matches what's on screen)

---

## CP9 — Conversational AI Interface
- [ ] Build `<CoSightChat>` page at `/chat` — same chat UI pattern as Cowork (reuse ChatArea, ChatInput, MessageBubble)
- [ ] Connect to `POST /api/cosight/chat/stream` SSE endpoint
- [ ] **Assistant identity = CoSight glyph, not a chibi character.** Design a minimal "lens / aperture / sight" mark (on-brand for "co-sight" = seeing the data together) as the assistant marker — conveys analytical authority, not cuteness. Reasoning: leadership-facing numbers need a trusted-analyst tone; a cute mascot undercuts data credibility.
- [ ] **Glyph as a state indicator** — design + build its three states: `loading/active` (animates while the agent is querying, e.g. "Querying GA4… analyzing 28 days…"), and `done` (steady mark). The agent visibly showing its work builds trust in the numbers.
- [ ] **Provenance chips are the primary marker.** Promote data-source chips ("Sprout" / "GA4" / "Search Console") from a side-detail to the lead identity on each assistant message — the agent's "face" is its citations. Chips reflect which tools were actually called.
- [ ] Support follow-up questions in the same conversation thread
- [ ] Add "Export this answer" button on assistant messages (PDF/DOCX)
- [ ] **Render report artifacts inline:** when a `report` SSE event arrives (agent called `generate_report`), render it with `<ReportArtifact>` + export menu right in the chat — this is "reports built via agentic conversation" (e.g. "build me a Q1 social report" → report appears, exportable to slides/PDF/CSV)
- [ ] Add quick-action prompts on empty state (e.g. "Summarize last month", "What's trending?", "Compare channels", "Build a monthly report")

### Drill-in: KPI → contextual chat
The feature that links the dashboards (CP8) to the chat — click any KPI to interrogate it agentically, pre-grounded so the agent never re-asks which metric or timeframe.
- [ ] Seed the chat with **scoped context** on drill-in: `{ channel, metric_key, date_range, value, delta }` (reuse Cowork's nav-state pattern — `navigate('/chat', { state: { ... } })`, as in `Sidebar.tsx` `handleSampleQuestionSelect`)
- [ ] **Carry over the dashboard's active date range** into the conversation, so "last month" in the chat matches the card the user clicked (a different window would silently mislead — trust-killer)
- [ ] Agent opens grounded in that KPI, then uses the CP5 tool loop for the deeper cut (per-campaign / per-query breakdown that explains the number)
- [ ] **MVP:** drill-in navigates to the full `/chat` page, pre-seeded (low cost, reuses existing pattern)
- [ ] **v2:** inline side-drawer chat that slides over the dashboard, so the user can interrogate a KPI without losing sight of the chart

---

### ✅ Checkpoint RC9 — review after CP9 (before CP10)
- [ ] **Invariant (cross-surface consistency):** for the same metric + range, the number on the dashboard equals the number the chat cites — verify equality on 3 metrics
- [ ] **Invariant:** provenance chips reflect the tools actually called; an inline report artifact renders identically to the Reports page
- [ ] **Gap:** drill-in date-range carry-over confirmed end-to-end (dashboard → chat → answer all on the same window)

---

## CP10 — Auth & Role Gating
- [ ] Add `role` to Supabase user metadata on signup (default: `staff`)
- [ ] Admin panel or Supabase dashboard to assign `admin` / `leadership` roles
- [ ] Backend middleware checks role before serving CoSight routes
- [ ] Frontend gates CoSight nav/pages — redirects non-admins to Cowork
- [ ] CoSight AuthModal reuses Cowork's modal layout + branding, but leads with the **CoSight glyph** (CP9), not the chibi — same design language, analyst identity

---

### ✅ Checkpoint RC10 — review after CP10 (before CP11)
- [ ] **Invariant (security):** no CoSight route or page is reachable by a `staff` token — test the **backend** gate and the **frontend** gate independently (defense in depth)
- [ ] **Invariant:** a user cannot self-escalate role — the authz path never trusts user-writable metadata
- [ ] **Gap:** non-admin redirect works; RLS admin-read tested with a real admin vs. non-admin account

---

## CP11 — Reporting & Export (reports · slides · CSV · chart images)
All outputs render from the one **report artifact** (CP5) via the **export pipeline** (CP3) — build the spine once, the formats are renderers on it.
- [ ] "Save Report" button on Overview page — snapshots current metrics into a report artifact in `cosight_reports`
- [ ] Reports page lists saved artifacts with date, title, channel summary
- [ ] **Reports via agentic conversation** — the agent assembles a report mid-chat (`generate_report`) and the user can refine it conversationally before exporting (see CP5/CP9)
- [ ] **Export to PDF** (reuse `pdfExport.ts` w/ CoSight branding)
- [ ] **Export to DOCX** (reuse `docxExport.ts` w/ CoSight branding)
- [ ] **Export to Slides** — generate a `.pptx` deck via `python-pptx`; map report sections → slide layouts
  - [ ] **Define the deck styling/template first** (the work `python-pptx` requires): CBS-branded slide master(s), color palette + fonts, the CoSight glyph, and reusable layouts — title slide, KPI-grid slide, single-chart slide, data-table slide, narrative/insights slide. Build `slides_export.py` against these so every report renders on-brand.
- [ ] **Export to CSV** — spreadsheet download of the underlying metric rows (per-report and per-channel/table)
- [ ] **Chart image export** — download any `<TrendChart>` as PNG (client-side SVG→PNG)
- [ ] Scheduled reports (optional): emails weekly PDF summary to configured recipients via Resend
  - [ ] Provision the scheduler — Render Cron Job (repo currently has no scheduler, only `start.sh`); the same cron also runs the CP0 nightly cache pre-warm
- [ ] _Deferred: shareable preview links — intentionally out of scope (leadership data exposure); revisit with a tokenized, expiring, snapshot-based design if needed_

---

### ✅ Checkpoint RC11 — review after CP11 (before CP12)
- [ ] **Invariant (export fidelity):** every format renders from the single artifact — none bypasses the pipeline; numbers in PDF / DOCX / Slides / CSV match the dashboard exactly
- [ ] **Invariant:** every export is CBS-branded; the `python-pptx` template covers all layout types real reports use (title / KPI-grid / chart / table / narrative)
- [ ] **Gap:** the scheduled report uses the same pipeline; CSV rows match the underlying metric rows

---

## CP12 — Deployment
- [ ] Add `VITE_API_URL` to CoSight Render static site environment
- [ ] Add all data connector API keys to Render backend environment
- [ ] Verify CORS allows CoSight frontend origin in backend `CORS_ORIGINS`
- [ ] Verify Supabase RLS policies work in production
- [ ] Smoke test all 4 data connectors in production
- [ ] Smoke test agentic chat with tool calls end-to-end in production
- [ ] Smoke test all export formats in production — PDF, DOCX, Slides, CSV, chart-image
- [ ] Add monitoring/alerting for connector failures and rate-limit breaches (log + notify on repeated errors)
- [ ] Share CoSight URL with CBS MarComm team for UAT

---

### ✅ Checkpoint RC12 — review after CP12 (final gate)
- [ ] **Invariant (prod parity):** all 4 connectors, the agentic chat, every export format, the role gate, RLS, and CORS are verified live in production
- [ ] **Invariant:** every prior checkpoint RC0–RC11 passed — no gate was skipped
- [ ] **Gap:** nothing in Dependencies / Appendix A remains unresolved that a shipped feature relies on

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
