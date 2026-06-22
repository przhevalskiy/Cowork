# CoSight Build Plan
Cross-channel data reporting + agentic conversation for CBS Marketing & Communications

---

## CP1 — Project Setup & Monorepo Structure
- [ ] Create `/apps/cosight/` directory alongside `/apps/cowork/` (or scaffold as sibling repo)
- [ ] Scaffold CoSight frontend with Vite + React + TypeScript (copy Cowork's vite.config, tsconfig, tailwind/CSS setup)
- [ ] Copy shared theme CSS variables, chibi sprite sheet, ChibiAvatars component into CoSight
- [ ] Copy Modal, Sidebar shell, AuthModal, Button styles into CoSight
- [ ] Set up `VITE_API_URL` pointing to shared backend
- [ ] Add CoSight router to shared FastAPI backend (`backend/app/api/routes/cosight/`)
- [ ] Register CoSight routers in `backend/app/main.py`
- [ ] Create Render static site for CoSight frontend
- [ ] Verify CoSight frontend deploys and loads with Cowork branding

---

## CP2 — API Credentials & Data Connectors
- [ ] Obtain Sprout Social API key + verify endpoint access (`GET /v1/analytics/...`)
- [ ] Obtain Emma API key + verify endpoint access (campaigns, opens, clicks)
- [ ] Obtain BrightEdge API credentials + verify endpoint access (keyword rankings, SEO metrics)
- [ ] Verify GA4 API access (Google service account JSON, property ID)
- [ ] Store all credentials in `backend/.env` and Render environment variables
- [ ] Add all keys to `backend/app/core/config.py` Settings model

---

## CP3 — Backend Data Services
- [ ] Create `backend/app/services/sprout_service.py` — fetch social metrics (impressions, engagement, reach, follower growth) per platform (LinkedIn, Instagram, Twitter)
- [ ] Create `backend/app/services/emma_service.py` — fetch email metrics (sends, opens, clicks, unsubscribes) per campaign
- [ ] Create `backend/app/services/brightedge_service.py` — fetch SEO metrics (keyword rankings, organic traffic, page performance)
- [ ] Create `backend/app/services/ga4_service.py` — fetch web metrics (sessions, pageviews, conversions, bounce rate, top pages)
- [ ] Each service exposes a `get_metrics(start_date, end_date)` async method
- [ ] Add response caching (TTL 15 min) to avoid hammering external APIs on every request
- [ ] Write smoke tests for each connector against live APIs

---

## CP4 — CoSight API Routes
- [ ] `GET /api/cosight/social` — returns Sprout metrics for date range
- [ ] `GET /api/cosight/email` — returns Emma metrics for date range
- [ ] `GET /api/cosight/seo` — returns BrightEdge metrics for date range
- [ ] `GET /api/cosight/web` — returns GA4 metrics for date range
- [ ] `GET /api/cosight/overview` — aggregates all four channels into a single payload
- [ ] All routes require auth (`get_current_user` dependency)
- [ ] Add role check — only `admin` / `leadership` roles can access CoSight routes
- [ ] Add date range query params (`?start=2025-01-01&end=2025-03-31`) to all routes

---

## CP5 — AI Agent Tools
- [ ] Define CoSight tools in `backend/app/core/cosight_tools.py`:
  - `get_social_metrics` — pulls Sprout data for a given date range and platform
  - `get_email_metrics` — pulls Emma data for a given date range and campaign
  - `get_seo_metrics` — pulls BrightEdge data for a given date range and keyword set
  - `get_web_metrics` — pulls GA4 data for a given date range and page/goal
  - `generate_report` — compiles all channel data into a structured report object
- [ ] Create `backend/app/api/routes/cosight/chat.py` — SSE streaming route for agentic conversation
- [ ] Write CoSight system prompt: analyst persona, instructs model to use tools to answer questions, cite specific numbers, surface trends, flag anomalies
- [ ] Wire tools into Claude (primary) with Mistral fallback (same overload pattern as Cowork)
- [ ] Persist CoSight conversations to Supabase (separate `cosight_discussions` table or `type` column)

---

## CP6 — Supabase Schema for CoSight
- [ ] Create `cosight_discussions` table (id, user_id, title, created_at)
- [ ] Create `cosight_messages` table (id, discussion_id, role, content, timestamp)
- [ ] Create `cosight_reports` table (id, user_id, title, payload JSONB, date_range, created_at) — saved report snapshots
- [ ] Add `role` column to Supabase `auth.users` metadata (`staff`, `admin`, `leadership`)
- [ ] Set RLS policies: users can only read their own discussions; admins can read all
- [ ] Run migration SQL and update `supabase_schema.sql`

---

## CP7 — Frontend Dashboard Pages
- [ ] Set up React Router with routes: `/`, `/social`, `/email`, `/seo`, `/web`, `/reports`, `/chat`
- [ ] Build `<Sidebar>` with CoSight nav links (reuse Cowork Sidebar shell, swap nav items)
- [ ] Build `<DateRangePicker>` component (presets: 7d, 30d, 90d, custom)
- [ ] Build `<KPICard>` component — metric name, value, delta vs prior period, trend arrow
- [ ] Build `<TrendChart>` component — line chart (use Recharts or Chart.js)
- [ ] Build `<DataTable>` component — sortable, filterable, paginated
- [ ] Build `<InsightsPanel>` component — Mistral/Claude narrative summary (static, refreshable)

---

## CP8 — Dashboard Pages (Data-Wired)
- [ ] **Overview page** — KPI bar (all 4 channels), cross-channel trend chart, AI executive summary
- [ ] **Social Media page** — per-platform KPI cards, engagement trend, top posts table
- [ ] **Email page** — campaign KPI cards, open/click trend, campaign performance table
- [ ] **SEO page** — keyword ranking cards, organic traffic trend, top pages table
- [ ] **Web page** — GA4 KPI cards, sessions trend, top pages + conversion table
- [ ] **Reports page** — list of saved report snapshots, export to PDF/DOCX (reuse Cowork export services)

---

## CP9 — Conversational AI Interface
- [ ] Build `<CoSightChat>` page at `/chat` — same chat UI pattern as Cowork (reuse ChatArea, ChatInput, MessageBubble)
- [ ] Connect to `POST /api/cosight/chat/stream` SSE endpoint
- [ ] Display chibi avatar on assistant messages (same ChibiAvatars component)
- [ ] Show data source chips on messages (e.g. "Sprout", "GA4") based on which tools were called
- [ ] Support follow-up questions in the same conversation thread
- [ ] Add "Export this answer" button on assistant messages (PDF/DOCX)
- [ ] Add quick-action prompts on empty state (e.g. "Summarize last month", "What's trending?", "Compare channels")

---

## CP10 — Auth & Role Gating
- [ ] Add `role` to Supabase user metadata on signup (default: `staff`)
- [ ] Admin panel or Supabase dashboard to assign `admin` / `leadership` roles
- [ ] Backend middleware checks role before serving CoSight routes
- [ ] Frontend gates CoSight nav/pages — redirects non-admins to Cowork
- [ ] CoSight AuthModal shows same chibi + branding as Cowork

---

## CP11 — Reporting & Export
- [ ] "Save Report" button on Overview page — snapshots current metrics to `cosight_reports` table
- [ ] Reports page lists saved snapshots with date, title, channel summary
- [ ] Export any report to PDF (reuse `pdfExport.ts` with CoSight branding)
- [ ] Export any report to DOCX (reuse `docxExport.ts` with CoSight branding)
- [ ] Scheduled reports (optional): cron job emails weekly PDF summary to configured recipients via Resend

---

## CP12 — Deployment
- [ ] Add `VITE_API_URL` to CoSight Render static site environment
- [ ] Add all data connector API keys to Render backend environment
- [ ] Verify CORS allows CoSight frontend origin in backend `CORS_ORIGINS`
- [ ] Verify Supabase RLS policies work in production
- [ ] Smoke test all 4 data connectors in production
- [ ] Smoke test agentic chat with tool calls end-to-end in production
- [ ] Smoke test PDF/DOCX export in production
- [ ] Share CoSight URL with CBS MarComm team for UAT

---

## Dependencies (must resolve before build)
- [ ] Sprout Social API access confirmed
- [ ] Emma API access confirmed
- [ ] BrightEdge API access confirmed
- [ ] GA4 service account + property ID confirmed
- [ ] User role assignments decided (who gets `leadership` vs `admin` vs `staff`)
- [ ] Scheduled report recipients list confirmed
