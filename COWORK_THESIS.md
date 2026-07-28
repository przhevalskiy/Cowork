# Cowork — Thesis, Architecture & Direction

> A complete statement of what Cowork is: the core thesis, the infrastructure it runs on, the architecture that implements it, the use cases it serves, and the pivots it could become. Grounded in the actual codebase, not aspiration.

---

## Part 1 — The Thesis

### The one-sentence version

**Cowork replaces a static intake form with a conversation that ends in a structured, routed, human-confirmed write into a system of record.**

The form still exists — its job has moved from the human to the model.

### The problem it dissolves

Every organization runs on structured systems: ticketing queues, CRMs, intake forms, task managers. Every one of them is fed by a human staring at a form they didn't design, in a taxonomy they don't understand, guessing which field means what and which category their request belongs to.

The friction isn't the *work*. It's the **encoding** of the work — translating a plain human request ("we need press for our new dean") into the exact fields, required values, and correct destination the downstream system demands. Most people fill these forms in wrong, or abandon them.

Cowork moves that encoding burden off the requester. They describe what they want in their own words; Cowork does the translation, the validation, and the routing.

### The three moves that define it

**1. Conversation in, structured record out.**
The requester speaks naturally. Cowork asks for exactly the fields the downstream system needs — one or two questions at a time — and assembles messy human intent into the clean structured record the system requires. The long tail of "my request doesn't fit your dropdowns" is handled by conversation instead of abandonment.

**2. A hard boundary between "talk" and "commit."**
The conversation is fluid and forgiving. The **write is not.** There is a deliberate airlock:

```
freeform conversation → show_checklist (structured summary) → user confirms → submit (routed write)
```

The model is never trusted to silently mutate the system of record. The user reviews the exact payload before it commits. This is what makes an AI-driven write **trustworthy enough to point at a production system** — the difference between a demo and something an operations team will actually run.

**3. It routes.**
The quiet heart of the tool. Cowork encodes the organization's internal taxonomy — which service a request maps to, which sub-project it belongs in, which fields that type requires — and does the sorting a human coordinator used to do. "Social posts for an event" routes one way; "photos of the gala" routes another. The intelligence isn't the chat; it's **knowing where things belong.**

### What Cowork is NOT

- **Not a generic chatbot.** It commits to a system of record, routed correctly, with a paper trail. Chatbots just talk.
- **Not a static form with an AI skin.** The point is *removing* the encoding burden, not decorating it.
- **Not an autonomous agent.** The human-confirmed commit is the entire trust model. It drafts; the human authorizes; then it writes.

### The center of gravity

**The last mile between how people naturally describe work and how a system of record demands it be entered** — bridged by a conversation that encodes intent, routes it correctly, and commits only what a human has confirmed.

---

## Part 2 — Infrastructure

The infrastructure Cowork actually runs on (all present in the repo):

| Layer | Technology | Role |
|-------|-----------|------|
| **AI (primary)** | Anthropic Claude (tool use, async streaming) | Drives the conversation and emits tool calls |
| **AI (fallback)** | Mistral (`mistral-large-latest`) | Transparent failover when Claude is overloaded (HTTP 529) |
| **API server** | FastAPI + uvicorn | Async HTTP + SSE streaming endpoints |
| **Streaming** | `sse-starlette` | Server-Sent Events; typed event stream to the frontend |
| **Database / Auth** | Supabase (PostgreSQL + RLS + JWT) | Users, profiles, discussions, messages — all row-level-scoped |
| **Auth verification** | PyJWT | Verifies Supabase JWTs via a `get_current_user` dependency |
| **System of record** | Hive `/actions` API | The downstream target the confirmed write commits to |
| **Email** | Resend | Sends a copy of every submission (paper trail) |
| **Document parsing** | pypdf, python-docx | Extracts text from uploaded reference attachments |
| **Frontend** | React + TypeScript + Vite + Zustand | Chat UI, streaming client, PDF/DOCX export, voice input |
| **Deployment** | Render (`render.yaml` blueprint) | Backend web service + frontend static site |

**Key infrastructure properties:**

- **Provider abstraction.** Claude and Mistral sit behind a common provider interface, so overload failover is transparent to the rest of the system.
- **Streaming-first.** The whole intake flow runs over one SSE endpoint — collect → confirm → submit — with typed events so the frontend can render structured UI (a checklist, a submission result) mid-stream.
- **Stateless writes, stateful conversation.** Conversation state lives in Supabase with RLS; the write to Hive is a discrete, confirmed, side-effecting action.
- **In-memory attachments.** Reference documents are extracted in-memory and injected into the prompt — scoped to the server process, never persisted. A deliberate privacy choice.
- **Secrets in env.** All credentials (Anthropic, Hive, Supabase, Resend) live in environment variables / Render config.

---

## Part 3 — Architecture

### The intake flow (end to end)

```
User describes a request
        │
        ▼
Intent classifier ──► tags the conversation (research / social_media / event / media / other)
        │             zero-latency regex; no LLM call; steers the system prompt
        ▼
Claude (tool use) ──► collects required fields through natural conversation,
        │             one or two questions at a time
        ▼
show_checklist    ──► emits a structured summary; frontend renders it for review
        │
        ▼
User confirms
        │
        ▼
submit_to_hive    ──► backend files the action into the correct Hive sub-project
        │             + emails a copy (Resend)
        ▼
"Submitted"  +  Hive task ID
```

If Claude returns HTTP 529 (overloaded), the stream transparently falls back to **Mistral** with the same system prompt and tools.

### The typed SSE event stream

The single `/api/chat/stream` endpoint emits a typed sequence the frontend interprets:

```
discussion_title → intent → chunk (repeated) → checklist | submitted → done
```

This is how one streaming endpoint drives *structured* UI — a `checklist` event renders a review card, a `submitted` event renders the result with the task ID.

### The tools (the airlock, in code)

Defined in `backend/app/core/tools.py`:

- **`show_checklist`** — stage: emits the structured intake summary for the user to review.
- **`submit_to_hive`** — commit: files the confirmed request into Hive (only called after user confirmation).
- **`show_vdr_checklist` / `submit_vdr`** — a second stage/commit pair for a different submission type (research-impact "VDR" reports) — proof the stage→confirm→commit pattern generalizes to more than one form.

The tools share a field schema (`_INTAKE_FIELDS`) with a `service_type` enum — **the enum is the routing taxonomy encoded as data.**

### Backend module map (actual)

```
backend/app/
├── main.py                      # FastAPI app + lifespan; mounts routers, CORS
├── core/
│   ├── config.py                # Pydantic settings / env vars
│   └── tools.py                 # Claude tool defs: show_checklist, submit_to_hive, VDR pair
├── auth/                        # Supabase JWT verification → get_current_user dependency
├── providers/
│   ├── claude_provider.py       # primary — async streaming + tool use
│   └── mistral_provider.py      # fallback — overload failover
├── api/routes/
│   ├── chat.py                  # SSE intake endpoint (tools → Hive)
│   ├── discussions.py           # discussion CRUD
│   ├── attachments.py           # reference upload / list / delete
│   ├── projects.py              # project context
│   ├── templates.py             # templates
│   └── hive.py                  # direct Hive submission proxy
├── services/
│   ├── intent_classifier.py     # regex intent detection (zero-latency)
│   ├── hive_service.py          # Hive /actions client + sub-project routing (singleton)
│   ├── discussion_service.py    # Supabase-backed discussion/message CRUD
│   ├── email_service.py         # Resend submission-copy email
│   ├── attachment_service.py    # in-memory text extraction + context assembly
│   ├── field_default_service.py # remembers/pre-fills intake field defaults
│   ├── template_service.py      # template CRUD
│   ├── project_service.py       # project CRUD
│   └── project_file_service.py  # project file handling
└── models/                      # Pydantic: discussion, message, project, template, field_default
```

### Data model (Supabase)

- **`profiles`** — auto-created on signup via a DB trigger; RLS: users read/update their own.
- **`discussions`** — conversations; `title`, `is_active`, `intent`; RLS: owner-only CRUD.
- **`messages`** — per-message content, role, latency, intent; RLS: scoped to discussion ownership.

### The two architectural invariants that make it trustworthy

1. **Nothing writes to the system of record without a confirmed tool call.** The airlock (`show_checklist` → confirm → `submit_to_hive`) is not bypassable in the flow.
2. **Routing is data, not hardcoded branching.** The `service_type` enum + `hive_service` sub-project map is the taxonomy; the model selects from it, the service resolves it. Downstream code never hardcodes a destination.

---

## Part 4 — Use Cases

### The shipping use case
**University MarComms intake.** CBS staff/faculty/students file marketing & communications requests (press, social, events, photo, video, web) by chatting instead of filling a form; Cowork routes each into 1 of 10 Hive sub-projects. A second flow files research-impact ("VDR") reports.

### The generalizable class of use cases
Any situation where a **person must feed a rigid system of record through a form they find confusing**, and where the *routing/encoding* is the hard part:

- **IT / service desk intake** — "my laptop won't connect" → correctly-tiered, correctly-routed ticket with the required diagnostic fields.
- **HR / facilities requests** — time-off, onboarding, room bookings, equipment — routed to the right queue with the right fields.
- **Grant / research / IRB submissions** — high-structure, high-stakes forms where the taxonomy is opaque to the requester.
- **Sales / CRM lead entry** — turn a freeform note about a prospect into a correctly-structured CRM record in the right pipeline stage.
- **Government / civic intake** — permit applications, benefit enrollment, records requests — the archetypal "confusing form, rigid system" problem.
- **Procurement / vendor onboarding** — structured supplier records routed to the right approval workflow.

The common shape every one of these shares: **freeform human intent → interrogate for the required fields → confirm the exact record → route it to the correct destination in a system of record.** That shape is what Cowork is; the MarComms instance is one configuration of it.

---

## Part 5 — Possible Pivots

Each pivot is a different center of gravity already latent in the codebase. Ranked by defensibility.

### Pivot A — The confirmation gate as infrastructure ("trust layer for agentic writes")
Extract the airlock as a horizontal primitive: *freeform in → model drafts a structured write → human confirms the exact payload → commit, with an audit trail.* Become the mandatory chokepoint any agent calls before it writes to a production system — the "are you sure?" that's structured, diffable, and logged.
- **Strength:** it's the one thing autonomy-racing incumbents are running *away* from, and exactly what risk-averse buyers (edu / health / gov / finance) require.
- **Riskiest bet:** is "safe agentic writes" a product people buy, or a feature every agent framework ships free? Bet: it's a *compliance-grade, org-mandated* need (a control plane), not a developer checkbox.

### Pivot B — Vertical intake-ops for a segment with a shared taxonomy
Own one vertical where every org faces the *same* routing ambiguities (all university MarComms; then all IT service desks; then all clinics), so corrections from customer A sharpen routing for customer B.
- **Strength:** the only version where the correction-flywheel moat clears the volume bar — pooled edge cases instead of starving at one small team.
- **Riskiest bet:** is the segment venture-scale, and does the wedge vertical generalize to adjacent ones?

### Pivot C — Grounded reporting (the CoSight sibling, standalone)
Point the same engine at *reading* data with a hard grounding rule: *the AI may never cite a number not present in a tool result.* Leadership-facing analytics where fabrication is disqualifying.
- **Strength:** verifiability-as-a-feature; the buyer (leadership) has money and fear.
- **Riskiest bet:** BI is a graveyard; is "grounded + conversational" a real wedge against incumbents' own AI?

### Pivot D — The verifiable membrane (unify Cowork + CoSight)
Cowork gates *writes* (confirm before commit); CoSight grounds *reads* (never assert ungrounded). Same stance, two sides. The company: **AI you can put in front of your systems of record without a compliance fight** — nothing operative crosses ungrounded or unconfirmed.
- **Strength:** most defensible framing — a *stance*, not a feature; the intersection incumbents skip.
- **Riskiest bet:** requires conviction and a longer build; needs a vertical (Pivot B) to get flywheel volume.

### Pivot E — Consumer "agent for the paperwork of being alive"
Flip who's on the painful side of the form: from the *org receiving it* to the *individual filing it against institutions in their own life* (refunds, cancellations, appeals, claims, reimbursements). Same engine — gather → draft → confirm → file → track — as a ~$20/mo consumer subscription.
- **Strength:** the beneficiary becomes the payer; the confirm-gate becomes a *consumer trust* feature ("never acts as you without showing you first").
- **Riskiest bet:** a real competitor already exists (Pine AI, autonomy-first); differentiation must be trust + auditability, not reach. *(Fully developed separately in `VENTURE_THESIS.md`.)*

### Pivots explicitly rejected
- **"Conversational forms" (Typeform-with-AI)** — commoditized, no moat.
- **"Universal integration layer"** — a connector-maintenance swamp where distribution incumbents (Zapier/Workato) win.
- **"Learned defaults" as a standalone product** — too shallow; a feature of A/B, not a company.

---

## Appendix — The through-line

Every pivot runs on the same three assets Cowork already proved:

1. **The stage → confirm → commit airlock** — trustworthy writes against a real system.
2. **Routing-as-data** — an organization's taxonomy encoded so the model selects and the service resolves.
3. **Grounding discipline** — the model only commits/cites what's confirmed or retrieved, never invented.

Cowork is the smallest complete instance of a larger idea: **a trustworthy conversational membrane between people and their systems of record** — encoding intent on the way in, grounding facts on the way out, always with a confirmation gate on anything that commits or gets quoted.
