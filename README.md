# Cowork — Marketing & Communications Intake Assistant

Cowork is a conversational intake assistant for the **CBS (Columbia Business School) Marketing & Communications** team. Instead of filling out a static service-request form, requesters chat with Cowork in natural language. The assistant gathers everything the MarComms team needs, shows a confirmation checklist, and — once confirmed — files a structured task into the correct **Hive** sub-project automatically.

It is built on Claude tool use, with real-time SSE streaming, Supabase auth, and a React frontend.

> **Note on naming:** the repository folder is still named *Qodex*, the project's original name. The shipping product is **Cowork**.

---

## How It Works

```
User describes a request
        │
        ▼
Intent classifier  ──►  tags the conversation (research / social_media / event / media / other)
        │               zero-latency regex; steers the system prompt
        ▼
Claude (tool use)  ──►  collects required fields through natural conversation,
        │               one or two questions at a time
        ▼
show_checklist     ──►  frontend renders a structured summary for the user to review
        │
        ▼
User confirms
        │
        ▼
submit_to_hive     ──►  backend creates a Hive action in the correct MarComms sub-project
        │               + emails a copy of the submission (Resend)
        ▼
"Submitted to the marketing team"  +  Hive task ID
```

If Claude is overloaded (HTTP 529), the stream transparently falls back to **Mistral** with the same system prompt and tools.

---

## Key Features

### Conversational Intake (Claude tool use)
- Single streaming endpoint drives the whole flow — collect → confirm → submit
- **Required fields** collected through conversation: contact name, role (Staff / Faculty / Student / External), Columbia UNI, department, whether it's event-related, service type, and a project brief; plus optional free-form details
- Two Claude tools (`backend/app/core/tools.py`):
  - **`show_checklist`** — emits a structured summary the user reviews before submission
  - **`submit_to_hive`** — files the confirmed request into Hive
- The system prompt includes a routing guide so Claude maps each request to the right one of the 10 MarComms services

### Intent Classification (zero-latency)
Regex-based classifier (`backend/app/services/intent_classifier.py`) tags the conversation on the first message and steers the intake prompt. No LLM call.

| Intent | Label | Steers toward |
|--------|-------|---------------|
| `research` | Research | media_outreach / web_article (press, op-eds, PR) |
| `social_media` | Social Media | social_media (checked before `event` so "social posts for an event" routes here) |
| `event` | Event | event_promotion / event_coverage / social_media |
| `media` | Media | media_outreach / photo (press kits, brand assets) |
| `other` | General | fallback, no specialization |

### Hive Integration
- `backend/app/services/hive_service.py` posts to the Hive `/actions` API
- Routes each request to the correct **MarComms Service Requests** sub-project based on `service_type`:

  | `service_type` | Sub-project |
  |----------------|-------------|
  | `web_services` | Web Services / Digital Marketing |
  | `media_outreach` | Media Outreach |
  | `photo` | Photo Request |
  | `digital_screens` | Digital Screens |
  | `web_article` | Web Article |
  | `event_coverage` | Event Coverage |
  | `youtube` | YouTube / Video |
  | `social_media` | Social Media |
  | `event_promotion` | Event Promotion |
  | `consultation` | MarComms Consultation |

- Collected fields are formatted into structured HTML matching the team's Hive form layout
- **UAT mode**: set `HIVE_UAT_PROJECT_ID` to route *all* submissions to a single test project

### Email Copy (Resend)
On every submission, a formatted copy of the intake (with the Hive task ID) is emailed to `EMAIL_CC_ADDRESS` via Resend — a paper trail for the team. Silently skipped if Resend isn't configured.

### Reference Attachments
- Users can upload reference documents to a conversation (PDF, DOCX, TXT, MD, CSV, JSON)
- Text is extracted in-memory (`attachment_service.py`) and injected into the system prompt to inform Cowork's intake questions
- **In-memory only** — attachments are scoped to the server process, not persisted to the database

### Conversations & Auth
- **Supabase Auth**: email/password with JWT verification; profiles auto-created on signup via DB trigger
- **Discussions**: create, rename, delete; auto-titled from the first message; intent stored per discussion
- **Row-Level Security**: discussions and messages scoped to their owner
- Persistent message history with per-message latency and intent

### Streaming & UX
- **SSE** streaming via `sse-starlette`; typed events: `discussion_title` → `intent` → `chunk` (repeated) → `checklist` / `submitted` → `done`
- React frontend with Zustand state, voice input (Web Speech API), and PDF/DOCX export of conversations
- Mobile-first responsive layout

---

## Architecture

### Backend (Python 3.11 + FastAPI)
- **FastAPI** + uvicorn, SSE streaming (`sse-starlette`)
- **Supabase (PostgreSQL)** for auth, profiles, discussions, messages — all with RLS
- **AI providers** (`backend/app/providers/`):
  - **Claude** (`claude-sonnet-4-6`, configurable) — Anthropic SDK, async streaming, tool use — the primary provider
  - **Mistral** (`mistral-large-latest`) — async streaming fallback used only when Claude is overloaded
- **Services** (`backend/app/services/`):
  - `discussion_service` — Supabase-backed CRUD for discussions and messages
  - `hive_service` — Hive `/actions` API client + sub-project routing (singleton via `get_hive_service()`)
  - `email_service` — Resend submission-copy email
  - `attachment_service` — in-memory per-discussion text extraction and context assembly
  - `intent_classifier` — regex intent detection
- **Auth** (`backend/app/auth/`): Supabase JWT verification injected via the `get_current_user` FastAPI dependency

**API routes**

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat/stream` | SSE intake conversation (drives tools → Hive) |
| `GET` | `/api/discussions` | List the user's discussions |
| `POST` | `/api/discussions` | Create a discussion |
| `GET` | `/api/discussions/{id}` | Get a discussion with messages |
| `PUT` | `/api/discussions/{id}` | Update title / active / intent |
| `DELETE` | `/api/discussions/{id}` | Delete a discussion |
| `POST` | `/api/discussions/{id}/attachments` | Upload a reference attachment |
| `GET` | `/api/discussions/{id}/attachments` | List attachments |
| `DELETE` | `/api/discussions/{id}/attachments/{att_id}` | Delete an attachment |
| `POST` | `/api/hive/submit` | Direct Hive submission proxy |
| `GET` | `/health` | Health check (reports Claude config status) |

### Frontend (React + TypeScript + Vite)
- React + TypeScript, Vite, React Router, Zustand
- **Feature folders** (`frontend/src/features/`): `chat`, `discussions`, `auth`, `attachments` — each with a Zustand `store.ts` and components
- **Shared services** (`frontend/src/shared/services/`): `api.ts` (fetch wrapper with Supabase bearer token), `sse.ts` (async-generator SSE client), `supabase.ts`, `voice.ts`, `pdfExport.ts`, `docxExport.ts`
- **Hooks** (`frontend/src/shared/hooks/`): `useSSE` (send orchestration), `useVoice`
- **Routes**: `/` → `/chat`, `/chat`, `/chat/:discussionId`

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React, TypeScript, Vite, React Router, Zustand, plain CSS (CSS variables / CSS Modules), Lucide, jsPDF/html2canvas, docx/file-saver |
| **Backend** | Python 3.11+, FastAPI, uvicorn, sse-starlette |
| **AI** | Anthropic SDK (Claude, primary + tool use), Mistral SDK (fallback) |
| **Database / Auth** | Supabase (PostgreSQL + RLS, JWT), PyJWT |
| **Integrations** | Hive API (task creation), Resend (email) |
| **Document parsing** | pypdf, python-docx |

---

## Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Supabase account** (auth + database)
- **Anthropic API key** (required — primary provider)
- **Hive API credentials** (to actually file requests; without them, submissions return a synthetic task ID and still email a copy)
- Optional: **Mistral API key** (overload fallback), **Resend API key** (email copies)

### Quick Start (Automated)

```bash
./start.sh   # starts backend (:8000) and frontend (:5173)
./stop.sh    # stops both
```

`start.sh` creates the Python venv and installs dependencies, starts the backend with `PYTHONUNBUFFERED=1`, installs frontend deps, starts Vite, logs to `logs/`, and stores PIDs in `.pids/`.

### Manual Setup

**Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then edit — see Environment Variables
uvicorn app.main:app --reload     # API: http://localhost:8000  ·  docs: /docs
```

Initialize the database by pasting `backend/supabase_schema.sql` into the Supabase SQL Editor and running it. This creates `profiles`, `discussions`, and `messages` with RLS policies and the signup trigger.

**Frontend**
```bash
cd frontend
npm install
cp .env.example .env              # then edit
npm run dev                       # App: http://localhost:5173
```

---

## Environment Variables

### Backend (`backend/.env`)

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret           # Dashboard → Settings → API → JWT Secret

# Anthropic (primary provider — required)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6             # optional override

# Hive integration
HIVE_API_KEY=...
HIVE_USER_ID=...
HIVE_WORKSPACE_ID=...                          # optional; service has a default
HIVE_UAT_PROJECT_ID=...                        # optional; routes all submissions to one test project

# Mistral (optional — overload fallback)
MISTRAL_API_KEY=...
MISTRAL_MODEL=mistral-large-latest

# Email copies (optional — Resend)
RESEND_API_KEY=...
EMAIL_CC_ADDRESS=team@example.com

# Application
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
DEBUG=true
LOG_LEVEL=INFO
```

### Frontend (`frontend/.env`)

```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

---

## Database Schema (Supabase)

Run `backend/supabase_schema.sql` in the Supabase SQL Editor.

- **`profiles`** — `id` (FK `auth.users` ON DELETE CASCADE), `email`, `display_name`, `created_at`. Auto-created on signup. RLS: users read/update their own profile.
- **`discussions`** — `id`, `user_id` (FK `profiles`), `title` (default `'New Chat'`), `is_active`, `intent`, `created_at`, `updated_at`. RLS: owner full CRUD.
- **`messages`** — `id`, `discussion_id` (FK `discussions` ON DELETE CASCADE), `role` (user/assistant/system), `content`, `tokens_used`, `response_time_ms`, `intent`, `user_display_name`, `user_email`, `created_at`. RLS: scoped to discussion ownership.

**Trigger:** `on_auth_user_created` auto-creates a `profiles` row on signup.

> `backend/migrations/` contains older SQL (`document_formatted_chunks`, `research_mode`) from the previous RAG product. These tables are **not used** by Cowork.

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   │   ├── chat.py            # SSE intake endpoint (tool use → Hive)
│   │   │   ├── discussions.py     # Discussion CRUD
│   │   │   ├── attachments.py     # Reference attachment upload/list/delete
│   │   │   └── hive.py            # Hive submission proxy
│   │   ├── auth/                  # Supabase JWT verification + get_current_user
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic settings / env vars
│   │   │   └── tools.py           # Claude tool defs: show_checklist, submit_to_hive
│   │   ├── database/              # Supabase client
│   │   ├── models/                # discussion.py, message.py (Pydantic)
│   │   ├── providers/             # claude_provider.py, mistral_provider.py
│   │   ├── services/
│   │   │   ├── discussion_service.py
│   │   │   ├── hive_service.py    # Hive API client + sub-project routing
│   │   │   ├── email_service.py   # Resend submission copy
│   │   │   ├── attachment_service.py
│   │   │   └── intent_classifier.py
│   │   └── main.py                # FastAPI app + lifespan
│   ├── requirements.txt
│   └── supabase_schema.sql        # Run once in Supabase SQL Editor
├── frontend/
│   ├── src/
│   │   ├── app/                   # App.tsx — routing + auth gate
│   │   ├── components/            # ui/ and layout/ shared components
│   │   ├── features/              # chat, discussions, auth, attachments (each with store.ts)
│   │   └── shared/                # services/, hooks/, types/, utils/
│   ├── package.json
│   └── vite.config.ts
├── start.sh / stop.sh / status.sh / logs.sh
└── render.yaml                    # Render deployment blueprint
```

---

## Deployment (Render)

A `render.yaml` blueprint defines a Python web service (backend) and a static site (frontend).

1. Push to GitHub and create a Blueprint from `render.yaml` in Render.
2. Set environment variables (see above) in the Render dashboard for each service.
3. Render auto-deploys on every push.

---

## Acknowledgments

- Anthropic — Claude (primary provider, tool use)
- Mistral AI — Mistral (fallback provider)
- Supabase — authentication and PostgreSQL
- Hive — task management API
- Resend — transactional email
- FastAPI and React communities
