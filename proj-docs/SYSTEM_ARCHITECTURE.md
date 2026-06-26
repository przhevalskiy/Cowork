# Cowork — System Architecture

Cowork is a conversational intake assistant for the **CBS Marketing & Communications** team. A user chats in natural language; Claude (with tool use) collects the right fields, shows a confirmation checklist, and on confirmation files a task into the correct **Hive** sub-project. There are **two intake flows** — MarComms **service requests** and VDR **research-impact submissions** — both driven by the same streaming endpoint and the same tool-call → SSE → Hive plumbing.

This document maps the components and shows exactly **what triggers what**.

---

## 1. Component overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React)                            │
│  ChatInput ── useSSE ──► SSEClient (EventSource/async generator)       │
│      ▲                                   │ SSE events                  │
│      │                                   ▼                             │
│  ChecklistMessage ◄── chat store (addChecklistMessage / setSubmitted)  │
└───────────────────────────────────│──────────────────────────────────┘
                                     │ POST /api/chat/stream (Bearer JWT)
                                     ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          BACKEND (FastAPI)                             │
│                                                                        │
│  routes/chat.py  ──► system prompt = BASE + intent suffix + attachments│
│       │                                                                │
│       ├─ intent_classifier.classify_intent()   (regex, first msg only) │
│       ├─ ClaudeProvider.stream_completion(tools=COWORK_TOOLS)          │
│       │        └─ on 529/overloaded → MistralProvider (fallback)       │
│       │                                                                │
│       └─ tool-call interception ──┬─ show_checklist     → SSE checklist │
│                                   ├─ show_vdr_checklist → SSE checklist │
│                                   ├─ submit_to_hive  → HiveService      │
│                                   └─ submit_vdr      → HiveService      │
│                                                                        │
│  services/                                                             │
│   • hive_service.py     → POST app.hive.com/api/v2/actions             │
│   • email_service.py    → Resend submission copy                       │
│   • discussion_service  → Supabase (discussions, messages)             │
│   • attachment_service  → in-memory per-discussion text                │
└───────────────────────────────│──────────────────────────────────────┘
                                 ▼
        Supabase (auth + Postgres)      Hive API        Resend (email)
```

**Providers:** Claude `claude-sonnet-4-6` is primary (tool use); Mistral `mistral-large-latest` is the overload fallback only.

---

## 2. End-to-end request lifecycle (the trigger sequence)

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend (useSSE)
    participant API as chat.py /stream
    participant IC as IntentClassifier
    participant LLM as Claude (Mistral fallback)
    participant HV as HiveService
    participant H as Hive API

    U->>FE: types message, hits send
    FE->>API: POST /api/chat/stream (JWT, discussion_id, message)
    API->>API: persist user msg; auto-title if "New Chat"
    alt first message in discussion
        API->>IC: classify_intent(message)
        IC-->>API: intent + prompt_suffix
        API-->>FE: SSE intent
    end
    API->>API: system_prompt = BASE + suffix + attachment_context
    API->>LLM: stream_completion(messages, system_prompt, tools=COWORK_TOOLS)
    LLM-->>API: text chunks (questions to the user)
    API-->>FE: SSE chunk (repeated)
    Note over LLM: once all required fields gathered,<br/>model emits a tool_use block (no text)
    LLM-->>API: tool_call show_checklist / show_vdr_checklist
    API-->>FE: SSE checklist {fields, intent}
    FE-->>U: render ChecklistMessage (Edit / Submit)
    U->>FE: clicks "Submit"
    FE->>API: POST /stream ("...please submit")
    API->>LLM: stream_completion(...)
    LLM-->>API: tool_call submit_to_hive / submit_vdr
    API->>HV: create_action / create_vdr_action(fields)
    HV->>H: POST /actions {workspaceId, projectId, title, description}
    H-->>HV: { id }
    API->>API: send_submission_copy (Resend, optional)
    API-->>FE: SSE submitted {hive_task_id}
    API-->>FE: SSE done
```

**Key point:** submission is a **two-round-trip** conversation. Round 1 ends with a `checklist` tool call; the user confirms in the UI, which sends a new message that triggers Round 2 ending in a `submit_*` tool call. The backend never auto-submits — the human confirm is required.

---

## 3. Flow selection — how the agent decides which intake to run

The system prompt ([chat.py](../backend/app/api/routes/chat.py) `BASE_SYSTEM_PROMPT`) defines two flows and instructs Claude to pick one from the **first message**:

```
                         ┌─────────────────────────────┐
   user's first message  │  Is this a request for the  │
 ───────────────────────►│  team to DO work, or a      │
                         │  report of an achievement?  │
                         └───────────┬─────────────────┘
                                     │
            ┌────────────────────────┴────────────────────────┐
            ▼                                                  ▼
   FLOW A — Service Request                        FLOW B — VDR Impact Submission
   "I need a press release"                        "My paper was covered in the NYT"
   "Can you shoot our event?"                      "I won an award / published a book"
            │                                                  │
   tools: show_checklist                           tools: show_vdr_checklist
          submit_to_hive                                  submit_vdr
            │                                                  │
   route by service_type                           route by impact_type
            ▼                                                  ▼
   MarComms Service Requests project               VDR Impact Submissions project
```

If genuinely ambiguous (e.g. *"I had a media mention and want social posts about it"*), the prompt tells the agent to ask **one** clarifying question. The regex `intent` hint (see §6) only steers Flow A service-type routing and is explicitly ignored for VDR.

---

## 4. Tool calls → triggers (the dispatch table)

All four tools are registered in `COWORK_TOOLS` ([tools.py](../backend/app/core/tools.py)). The backend inspects `stream_metadata["tool_calls"]` after the stream and dispatches:

| Tool call (emitted by Claude) | Backend action | Emits SSE | Side effect |
|---|---|---|---|
| `show_checklist` | echo fields | `checklist` `{fields, intent}` | — |
| `show_vdr_checklist` | echo fields | `checklist` `{fields, intent:'vdr'}` | — |
| `submit_to_hive` | `HiveService.create_action(fields)` | `submitted` `{hive_task_id}` | POST to MarComms sub-project + Resend email |
| `submit_vdr` | `HiveService.create_vdr_action(fields)` | `submitted` `{hive_task_id}` | POST to VDR sub-project + Resend email |

Both checklist tools reuse the **same** `checklist` SSE event, so the frontend renders both flows with one component ([ChecklistMessage.tsx](../frontend/src/features/chat/components/chat/ChecklistMessage.tsx)) — fields are rendered generically from `Object.entries`.

---

## 5. Hive routing — the mappings

**Workspace:** `MvJ2A7jmTiCJcheoM` (constant). **UAT override:** if `HIVE_UAT_PROJECT_ID` is set, *all* submissions route there regardless of type.

### 5a. Flow A — `service_type` → MarComms sub-project
Parent project: **Marcomms Service Requests** (`YzWwuHSKwqri9z8QS`).

| `service_type` | Hive sub-project | project ID |
|---|---|---|
| `web_services` | Web Services Requests | `46u9tbXY28SyHXxty` |
| `media_outreach` | Media Outreach Requests | `Nq9yjjP6MTRh33Pbs` |
| `photo` | Photo Requests | `9Pkm2bSg7hMWNs4Jy` |
| `digital_screens` | Digital Screens Requests | `n2pgMprEkoSTSXA6f` |
| `web_article` | Web Article Requests | `WJJfzensshDySmwfs` |
| `event_coverage` | Event Coverage Requests | `ouLeGxMQriFRFsYsW` |
| `youtube` | YouTube Requests | `mfTJrGj6FrTaBnviz` |
| `social_media` | Social Media Requests | `GNPJiJnFMuzD54CvH` |
| `event_promotion` | Event Promotion Requests | `Xov2Fcmcdm5cktzje` |
| `consultation` | MarComms Consultation | `qT3WRqYtoyqLLAkJG` |

Unknown `service_type` → falls back to `consultation`.

### 5b. Flow B — `impact_type` → VDR sub-project
Parent project: **VDR Impact Submissions** (`Ha2kdQfm8v5CSd3hp`), a sibling of the MarComms parent in the same workspace.

| `impact_type` | Hive sub-project | project ID |
|---|---|---|
| `Award` | VDR Awards Submissions | `y3PEd49oAfrjG3MPL` |
| `Media mention` | VDR Media Mention Submissions | `ttf3zbwo2jKBoexHn` |
| `Book`, `Case Study`, `Grant`, `Notable Service`, `Research article`, `Speaking Engagement/Major event appearance`, `Other` | VDR_Research and Impact Submissions (default) | `W2ChxFDWE8WhFbuE5` |

Any `impact_type` not explicitly mapped → defaults to **Research and Impact**.

### 5c. Action payload
`create_action` / `create_vdr_action` build:
```json
{
  "workspaceId": "MvJ2A7jmTiCJcheoM",
  "projectId":   "<resolved from table above>",
  "title":       "<summary/brief> - <type> - <name> <UTC timestamp>",
  "description": "<fields rendered as sectioned HTML>"
}
```
POSTed to `https://app.hive.com/api/v2/actions` with headers `api_key` + `user_id`.

---

## 6. Intent classifier (Flow A hint only)

[intent_classifier.py](../backend/app/services/intent_classifier.py) runs **once**, on the first message of a discussion, via zero-latency regex. It does **not** call an LLM and does **not** decide the flow — it only appends a `prompt_suffix` that nudges Flow A service-type selection, and is stored on the discussion for display.

| intent key | matches (examples) | nudges toward |
|---|---|---|
| `research` | press release, op-ed, pitch, journalist | `media_outreach` / `web_article` |
| `social_media` | instagram, linkedin, reels, caption | `social_media` |
| `event` | conference, webinar, panel, launch | `event_promotion` / `event_coverage` |
| `media` | press kit, headshot, boilerplate, logo | `media_outreach` / `photo` |
| `other` | (fallback) | none |

---

## 7. Resilience — provider fallback

```
ClaudeProvider.stream_completion(tools=COWORK_TOOLS)
        │
        ├─ success ──────────────► stream chunks + tool calls
        │
        └─ APIStatusError 529 / "overloaded"
                 │
                 ▼  (only if MISTRAL_API_KEY set)
        MistralProvider.stream_completion(tools=COWORK_TOOLS)  ← same prompt + tools
                 │
                 └─ failure ─────► SSE error "Service temporarily unavailable"
```

The fallback clears any partial output and `stream_metadata` first, so a half-streamed Claude response is not mixed with Mistral's.

---

## 8. SSE event reference

Emitted by `chat.py` `generate()` in this order:

| Event | When | Payload | Frontend handler (`useSSE`) |
|---|---|---|---|
| `discussion_title` | first message only | `{discussion_id, title}` | `updateDiscussionTitle` |
| `intent` | first message only | `{intent, label}` | `setStreamIntent` |
| `chunk` | each token batch | `{content, provider}` | `appendToStream` |
| `checklist` | on `show_*_checklist` | `{fields, intent}` | `addChecklistMessage` → `ChecklistMessage` |
| `submitted` | on `submit_*` | `{hive_task_id, message}` | `setSubmitted` |
| `error` | stream failure | `{error, provider}` | append + finalize |
| `done` | end of turn | `{provider}` | `finalizeStream` |

---

## 9. Persistence & context

| Concern | Store | Notes |
|---|---|---|
| Auth | Supabase Auth (JWT) | `get_current_user` dependency on protected routes |
| Discussions / messages | Supabase Postgres (RLS) | `discussion_service`; `intent` stored per discussion |
| Conversation context | last 20 messages | `get_context_messages(limit=20)` injected into the LLM |
| Reference attachments | **in-memory** (process-local) | `attachment_service`; text extracted (PDF/DOCX/TXT/MD/CSV/JSON) and appended to the system prompt; **not** persisted to DB |

System prompt assembled per turn:
```
system_prompt = BASE_SYSTEM_PROMPT + intent_result.prompt_suffix + attachment_context
```

---

## 10. External services & configuration

| Service | Env vars | Used for |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | primary chat + tool use |
| Mistral | `MISTRAL_API_KEY`, `MISTRAL_MODEL` | overload fallback |
| Hive | `HIVE_API_KEY`, `HIVE_USER_ID`, `HIVE_WORKSPACE_ID`, `HIVE_UAT_PROJECT_ID` | task creation |
| Resend | `RESEND_API_KEY`, `EMAIL_CC_ADDRESS` | submission-copy email (optional) |
| Supabase | `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | auth + data |

---

## 11. File map (where each responsibility lives)

| Responsibility | File |
|---|---|
| Streaming endpoint, flow selection prompt, tool dispatch | `backend/app/api/routes/chat.py` |
| Tool definitions + field schemas (both flows) | `backend/app/core/tools.py` |
| Hive routing + action creation | `backend/app/services/hive_service.py` |
| Submission-copy email | `backend/app/services/email_service.py` |
| Intent regex classifier | `backend/app/services/intent_classifier.py` |
| Discussions/messages CRUD | `backend/app/services/discussion_service.py` |
| Attachment text extraction | `backend/app/services/attachment_service.py` |
| Provider streaming (Claude/Mistral) | `backend/app/providers/` |
| SSE consumption + store | `frontend/src/shared/hooks/useSSE.ts`, `frontend/src/features/chat/store.ts` |
| Checklist rendering | `frontend/src/features/chat/components/chat/ChecklistMessage.tsx` |

---

## 12. Known edges / things to watch

- **Flow disambiguation** lives entirely in the system prompt; requests that span both flows (e.g. a media mention you also want promoted) rely on the agent asking a clarifying question.
- **Unmapped MarComms dropdown items** (Audio/Podcast Recording, Videography, Video editing, MMG Consultation) have no dedicated Hive sub-project; they are not yet routable and currently fall back to `consultation` if selected.
- **Attachments are process-local** — they do not survive a backend restart and are not shared across instances.
- **UAT mode** (`HIVE_UAT_PROJECT_ID`) overrides *both* flows' routing, so it validates the end-to-end path but not the per-type project mapping.
