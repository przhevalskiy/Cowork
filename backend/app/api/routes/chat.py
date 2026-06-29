"""Cowork chat route — streaming intake agent with tool use."""
import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.core.config import get_settings
from app.core.tools import COWORK_TOOLS
from app.models import Message, MessageRole
import anthropic as anthropic_sdk
from app.providers import get_claude_provider, get_mistral_provider
from app.services.attachment_service import build_attachment_context
from app.services.discussion_service import get_discussion_service
from app.services.project_service import get_project_service
from app.services.project_file_service import build_project_file_context
from app.services.hive_service import get_hive_service, SERVICE_LABELS
from app.services.email_service import send_submission_copy
from app.services.intent_classifier import classify_intent, get_intent_for_key
from app.services.field_default_service import get_field_default_service
from app.utils.streaming import format_sse_event
from app.auth import get_current_user, UserContext

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

BASE_SYSTEM_PROMPT = """You are Cowork, the CBS Marketing & Communications assistant. You handle two kinds of requests:

(A) MARCOMMS SERVICE REQUEST — someone wants the MarComms team to DO work for them: a press release, event promotion, photography, social media, a web article, video, digital screens, web services, etc.
(B) RESEARCH IMPACT / SUCCESS SUBMISSION (VDR) — a faculty member, or someone on their behalf, is REPORTING a completed achievement so it can be featured and promoted: an award, book, case study, grant, media mention, notable service, research article, or speaking engagement / major event appearance.

First, decide which kind of request this is from the user's first message, then follow the matching flow. If it is genuinely unclear, ask one brief clarifying question. (Any automatic "intent" hint below applies only to Flow A service-type routing — ignore it if this is a VDR submission.)

Ask only 1-2 questions at a time, never all at once. Be concise, warm, and professional.

=== FLOW A — MarComms service request ===
Required fields:
- contact_name: requester's full name
- role: Staff, Faculty, Student, or External
- uni: Columbia UNI (e.g. ap3456) — if not Columbia-affiliated say N/A
- department: their department or school
- is_event: whether the request is tied to an event (Yes / No)
- service_type: one of the 10 Marcomms services:
    web_services, media_outreach, photo, digital_screens, web_article,
    event_coverage, youtube, social_media, event_promotion, consultation
- brief: a 1-2 sentence project brief
- details: any additional context, deadlines, or notes

Routing guide — pick service_type based on the request:
- Press release, op-ed, byline, article → web_article
- Event promotion, webinar, speaker series → event_promotion
- Event photography, event recap coverage → event_coverage
- Photography for headshots, portraits → photo
- Social media posts, Instagram, LinkedIn, Twitter → social_media
- PR pitch, media list, journalist outreach → media_outreach
- Video, YouTube, reels → youtube
- Digital lobby screens, signage → digital_screens
- Website buildout, SEO, analytics, feature requests → web_services
- General question or multi-service request → consultation

Once all required fields are gathered, call show_checklist immediately — do not output any text before calling the tool.
After the user confirms, call submit_to_hive immediately — do not output any text before calling the tool.

=== FLOW B — VDR research impact / success submission ===
Required fields:
- submitter_role: "Faculty member", "PhD student", or "Staff member submitting on behalf of a faculty member"
- faculty_name: the faculty member whose achievement this is (their own name if they are the submitter)
- division: Accounting; Decision, Risk and Operations; Economics; Finance; Management; Marketing; or Other
- impact_type: Award, Book, Case Study, Grant, Media mention, Notable Service, Research article, Speaking Engagement/Major event appearance, or Other
- summary: a short title or summary of the achievement
- collaborators: CBS collaborator name(s) — faculty and current or former PhD students; use "None" if there were none
Optional fields (capture only if the user offers them — do not interrogate):
- area_of_expertise, promo_channels (where the school may promote it), details

Once all required VDR fields are gathered, call show_vdr_checklist immediately — do not output any text before calling the tool.
After the user confirms, call submit_vdr immediately — do not output any text before calling the tool."""


def _build_project_context(project) -> str:
    """System-prompt addition that locks a project's conversation to its request type."""
    parts = [
        "\n\n=== PROJECT CONTEXT ===",
        f'This conversation belongs to the project "{project.name}".',
    ]
    if project.instructions:
        parts.append(f"Project instructions to follow: {project.instructions}")

    if project.locked_service_type:
        label = SERVICE_LABELS.get(project.locked_service_type, project.locked_service_type)
        parts.append(
            f"This project is LOCKED to a MarComms service request of type "
            f'"{project.locked_service_type}" ({label}). Use Flow A. Set '
            f"service_type=\"{project.locked_service_type}\" and do NOT ask the user "
            f"which service they need — it is already decided. Still collect the other "
            f"required Flow A fields."
        )
    elif project.locked_intent == "research":
        parts.append(
            "This project is LOCKED to a Research Impact / Success (VDR) submission. "
            "Use Flow B. Do NOT ask whether this is a service request vs. a submission."
        )
    return "\n".join(parts)


# Promotion thresholds: how many consistent repeats before a learned field stops
# being asked. suggest = state it and let the user correct; silent = fill it in
# directly without mentioning it (never for always_confirm fields).
_SUGGEST_AT = 2
_SILENT_AT = 4


def _build_defaults_context(defaults) -> tuple[str, dict]:
    """Turn a user's learned field defaults into a system-prompt block plus the dict
    of values we are pre-filling (used later to diff against what they submit)."""
    silent, suggest = [], []
    for d in defaults:
        if d.confidence >= _SILENT_AT and not d.always_confirm:
            silent.append(d)
        elif d.confidence >= _SUGGEST_AT:
            suggest.append(d)
    if not silent and not suggest:
        return "", {}

    block = ["\n\n=== KNOWN DEFAULTS FOR THIS USER ==="]
    if silent:
        block.append(
            "Treat these as already provided. Do NOT ask for them; fill them into "
            "the checklist directly:"
        )
        block += [f"- {d.field}: {d.value}" for d in silent]
    if suggest:
        block.append(
            "State these as assumptions the user can correct; do not interrogate. "
            "Use the value unless the user says otherwise:"
        )
        block += [f"- {d.field}: {d.value}" for d in suggest]
    injected = {d.field: d.value for d in silent + suggest}
    return "\n".join(block), injected


class ChatRequest(BaseModel):
    discussion_id: str
    message: str
    temperature: float = 0.7
    max_tokens: int = 4096


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    current_user: UserContext = Depends(get_current_user),
):
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")

    disc_service = get_discussion_service()
    user_id = current_user.user_id

    discussion = disc_service.get_discussion(request.discussion_id, user_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Add user message
    user_message = Message(
        id=str(uuid.uuid4()),
        content=request.message,
        role=MessageRole.USER,
        timestamp=datetime.utcnow(),
    )
    disc_service.add_message(
        request.discussion_id, user_message,
        user_display_name=current_user.display_name,
        user_email=current_user.email,
    )

    # Auto-title on first message
    title_updated = False
    if discussion.title == "New Chat":
        new_title = request.message[:50] + ("..." if len(request.message) > 50 else "")
        disc_service.update_discussion(request.discussion_id, user_id, title=new_title)
        discussion.title = new_title
        title_updated = True

    # Load the owning project (if filed), to lock the request type and add context.
    project = None
    if discussion.project_id:
        project = get_project_service().get_project(discussion.project_id, user_id)

    # Intent: classify once on first message, reuse on subsequent turns.
    # A project's locked_intent takes precedence over the classifier.
    emit_intent = False
    if not discussion.intent:
        if project and project.locked_intent:
            intent_result = get_intent_for_key(project.locked_intent)
        else:
            intent_result = classify_intent(request.message)
        logger.info(f"Intent for '{request.message[:60]}' → {intent_result.intent}")
        disc_service.update_discussion(request.discussion_id, user_id, intent=intent_result.intent)
        discussion.intent = intent_result.intent
        emit_intent = True
    else:
        intent_result = get_intent_for_key(discussion.intent)

    # Build system prompt — include attachment text, plus project context/files when filed.
    attachment_context = build_attachment_context(request.discussion_id)
    system_prompt = BASE_SYSTEM_PROMPT + intent_result.prompt_suffix + attachment_context
    if project:
        system_prompt += _build_project_context(project)
        system_prompt += build_project_file_context(project.id)

    # Pre-fill from this user's learned defaults for the request type, so recurring
    # tickets stop re-asking predictable fields. Keyed on the locked service_type
    # when filed under a hubspace, otherwise on the classified intent.
    injected_defaults: dict = {}
    if discussion.intent and discussion.intent != "vdr":
        default_key = (project.locked_service_type if project else None) or discussion.intent
        try:
            defaults = get_field_default_service().get_defaults(
                user_id, default_key, project.id if project else None,
            )
            defaults_block, injected_defaults = _build_defaults_context(defaults)
            system_prompt += defaults_block
        except Exception as e:
            logger.warning(f"Could not load field defaults: {e}")

    # Get conversation context
    context_messages = disc_service.get_context_messages(request.discussion_id, limit=20)

    provider = get_claude_provider(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )

    async def generate():
        _t0 = time.time()
        full_response: list[str] = []

        if title_updated:
            yield f"data: {json.dumps({'type': 'discussion_title', 'discussion_id': request.discussion_id, 'title': discussion.title})}\n\n"

        if emit_intent:
            yield f"data: {json.dumps({'type': 'intent', 'intent': intent_result.intent, 'label': intent_result.label})}\n\n"

        stream_metadata: dict = {}

        try:
            async for chunk in provider.stream_completion(
                messages=context_messages,
                system_prompt=system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                tools=COWORK_TOOLS,
                stream_metadata=stream_metadata,
            ):
                full_response.append(chunk)
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'provider': 'claude'})}\n\n"

        except Exception as e:
            is_overloaded = (
                isinstance(e, anthropic_sdk.APIStatusError) and e.status_code == 529
            ) or "overloaded" in str(e).lower()

            if is_overloaded and settings.mistral_api_key:
                logger.warning("Claude overloaded — falling back to Mistral")
                full_response.clear()
                stream_metadata.clear()
                try:
                    mistral = get_mistral_provider(
                        api_key=settings.mistral_api_key,
                        model=settings.mistral_model,
                    )
                    async for chunk in mistral.stream_completion(
                        messages=context_messages,
                        system_prompt=system_prompt,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        tools=COWORK_TOOLS,
                        stream_metadata=stream_metadata,
                    ):
                        full_response.append(chunk)
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk, 'provider': 'mistral'})}\n\n"
                except Exception as me:
                    logger.error(f"Mistral fallback error: {me}")
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Service temporarily unavailable. Please try again.', 'provider': 'mistral'})}\n\n"
                    return
            else:
                logger.error(f"Stream error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'error': 'Something went wrong. Please try again.', 'provider': 'claude'})}\n\n"
                return

        # Intercept tool calls
        tool_calls = stream_metadata.get("tool_calls", [])
        for call in tool_calls:
            name = call.get("name")
            inp = call.get("input", {})

            if name == "show_checklist":
                yield f"data: {json.dumps({'type': 'checklist', 'fields': inp.get('fields', {}), 'intent': discussion.intent or 'other'})}\n\n"

            elif name == "show_vdr_checklist":
                yield f"data: {json.dumps({'type': 'checklist', 'fields': inp.get('fields', {}), 'intent': 'vdr'})}\n\n"

            elif name == "submit_to_hive":
                fields = inp.get("fields", {})
                # A locked project decides the service_type — enforce it regardless
                # of what the model produced, so routing always matches the project.
                if project and project.locked_service_type:
                    fields["service_type"] = project.locked_service_type
                hive_task_id = f"HIVE-{uuid.uuid4().hex[:8].upper()}"
                if settings.hive_api_key:
                    try:
                        hive = get_hive_service()
                        result = await hive.create_action(fields=fields)
                        hive_task_id = str(result.get("id") or result.get("_id") or hive_task_id)
                    except Exception as hive_err:
                        logger.error(f"Hive API error: {hive_err}")
                send_submission_copy(fields, hive_task_id)
                # Learn from this submission: unchanged pre-fills gain confidence,
                # edited values overwrite. Must use the SAME key as the injection
                # above, or the next lookup won't find what we stored.
                learn_key = (project.locked_service_type if project else None) or discussion.intent
                get_field_default_service().learn(
                    user_id, learn_key, submitted=fields, injected=injected_defaults,
                    hubspace_id=project.id if project else None,
                )
                yield f"data: {json.dumps({'type': 'submitted', 'hive_task_id': hive_task_id, 'message': 'Your request has been submitted to the marketing team.'})}\n\n"

            elif name == "submit_vdr":
                hive_task_id = f"HIVE-{uuid.uuid4().hex[:8].upper()}"
                if settings.hive_api_key:
                    try:
                        hive = get_hive_service()
                        result = await hive.create_vdr_action(fields=inp.get("fields", {}))
                        hive_task_id = str(result.get("id") or result.get("_id") or hive_task_id)
                    except Exception as hive_err:
                        logger.error(f"Hive API error (VDR): {hive_err}")
                send_submission_copy(inp.get("fields", {}), hive_task_id)
                yield f"data: {json.dumps({'type': 'submitted', 'hive_task_id': hive_task_id, 'message': 'Your research impact submission has been sent to the MarComms team.'})}\n\n"

        # Persist text-only assistant message — skip when a tool was called (tool events are the canonical message)
        response_ms = int((time.time() - _t0) * 1000)
        full_text = "".join(full_response).strip()
        if full_text and not tool_calls:
            assistant_message = Message(
                id=str(uuid.uuid4()),
                content=full_text,
                role=MessageRole.ASSISTANT,
                timestamp=datetime.utcnow(),
                response_time_ms=response_ms,
                intent=intent_result.intent,
            )
            disc_service.add_message(request.discussion_id, assistant_message)

        yield f"data: {json.dumps({'type': 'done', 'provider': 'claude'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
