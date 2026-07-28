"""
CoSight agentic chat route — multi-turn tool-use loop.

Unlike Cowork's single-shot intercept pattern, CoSight runs a real loop:
  model emits tool call → backend executes connector → result fed back into
  context → repeat until model returns a final text answer.

Invariants:
- Max iterations cap prevents infinite loops.
- Tool outputs are pre-aggregated (top-N, summary stats) before entering context.
- Numeric grounding: system prompt forbids citing any figure not in a tool result.
- Optional scoped_context injects a pre-grounded KPI so drill-ins don't re-ask.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.cosight_tools import COSIGHT_SYSTEM_PROMPT, COSIGHT_TOOLS
from app.models.message import Message, MessageRole
from app.providers import get_claude_provider, get_mistral_provider
from app.services.cosight_discussion_service import get_cosight_discussion_service
from app.services import ga4_service, gsc_service, emma_service, sprout_service
from app.services.cosight_cache_service import get_cached, set_cached

router = APIRouter(prefix="/api/cosight/chat", tags=["cosight-chat"])
logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 5


# ── Request / response models ─────────────────────────────────────────────────

class ScopedContext(BaseModel):
    """Optional pre-grounded context for KPI drill-ins from the dashboard."""
    channel: Optional[str] = None
    metric_key: Optional[str] = None
    date_range: Optional[str] = None    # e.g. "2025-01-01/2025-01-31"
    value: Optional[float] = None
    delta: Optional[float] = None


class ChatRequest(BaseModel):
    discussion_id: str
    message: str
    temperature: float = 0.3            # lower = more factual for analytics
    max_tokens: int = 4096
    scoped_context: Optional[ScopedContext] = None


# ── Tool executor ─────────────────────────────────────────────────────────────

def _default_date_range() -> tuple[date, date]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=29)
    return start, end


async def _execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """
    Execute a CoSight tool call and return a pre-aggregated string result
    to inject back into the model context.
    """
    start_str = tool_input.get("start_date")
    end_str = tool_input.get("end_date")

    if start_str and end_str:
        try:
            start = date.fromisoformat(start_str)
            end = date.fromisoformat(end_str)
        except ValueError:
            return json.dumps({"error": f"Invalid date format: {start_str} / {end_str}"})
    else:
        start, end = _default_date_range()

    if tool_name == "get_web_metrics":
        cached = get_cached("web", start, end)
        result = cached or await ga4_service.get_metrics(start, end)
        if result.status == "ok" and not cached:
            set_cached(result)
    elif tool_name == "get_seo_metrics":
        cached = get_cached("search", start, end)
        result = cached or await gsc_service.get_metrics(start, end)
        if result.status == "ok" and not cached:
            set_cached(result)
    elif tool_name == "get_email_metrics":
        cached = get_cached("email", start, end)
        result = cached or await emma_service.get_metrics(start, end)
        if result.status == "ok" and not cached:
            set_cached(result)
    elif tool_name == "get_social_metrics":
        cached = get_cached("social", start, end)
        result = cached or await sprout_service.get_metrics(start, end)
        if result.status == "ok" and not cached:
            set_cached(result)
    elif tool_name == "generate_report":
        # generate_report is handled in the streaming generator (emits SSE event)
        return json.dumps({"status": "pending", "message": "Report generation handled by stream"})
    else:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    if result.status == "error":
        return json.dumps({"error": result.error_message, "channel": result.channel.value})

    # Pre-aggregate: send only summary KPIs + first 10 timeseries rows
    summary = [m.model_dump(mode="json") for m in result.summary]
    timeseries_sample = [m.model_dump(mode="json") for m in result.timeseries[:10]]

    return json.dumps({
        "channel": result.channel.value,
        "start_date": str(result.start_date),
        "end_date": str(result.end_date),
        "status": result.status,
        "cached_at": result.cached_at,
        "summary": summary,
        "timeseries_sample": timeseries_sample,
        "timeseries_total_rows": len(result.timeseries),
    })


# ── SSE streaming route ───────────────────────────────────────────────────────

@router.post("/stream")
async def stream_chat(request: ChatRequest):
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise HTTPException(status_code=400, detail="Anthropic API key not configured")

    disc_service = get_cosight_discussion_service()
    discussion = disc_service.get_discussion(request.discussion_id)
    if not discussion:
        raise HTTPException(status_code=404, detail="Discussion not found")

    # Persist user message
    user_msg = Message(
        id=str(uuid.uuid4()),
        content=request.message,
        role=MessageRole.USER,
        timestamp=datetime.utcnow(),
    )
    disc_service.add_message(request.discussion_id, user_msg)

    # Auto-title on first message
    title_updated = False
    if discussion.title == "New Chat":
        new_title = request.message[:50] + ("..." if len(request.message) > 50 else "")
        disc_service.update_discussion(request.discussion_id, title=new_title)
        title_updated = True

    # Build system prompt, injecting scoped context if provided
    system_prompt = COSIGHT_SYSTEM_PROMPT
    if request.scoped_context and request.scoped_context.metric_key:
        sc = request.scoped_context
        inject = (
            f"\n\n## Drill-in Context (pre-grounded)\n"
            f"The user clicked on a specific metric from the dashboard:\n"
            f"- Channel: {sc.channel or 'unknown'}\n"
            f"- Metric: {sc.metric_key}\n"
            f"- Date range: {sc.date_range or 'not specified'}\n"
            f"- Current value: {sc.value}\n"
            f"- Delta vs prior period: {sc.delta}%\n\n"
            f"Start your analysis grounded in these values. Do NOT re-ask which metric "
            f"or date range — you already have this context. Use tools to go deeper."
        )
        system_prompt += inject

    context_messages = disc_service.get_context_messages(request.discussion_id, limit=20)

    provider = get_claude_provider(
        api_key=settings.anthropic_api_key,
        model=settings.anthropic_model,
    )

    async def generate():
        import anthropic as anthropic_sdk

        nonlocal context_messages
        _t0 = time.time()

        if title_updated:
            yield f"data: {json.dumps({'type': 'discussion_title', 'discussion_id': request.discussion_id, 'title': discussion.title[:50]})}\n\n"

        # Multi-turn tool loop
        iteration = 0
        # anthropic_messages tracks the full context for multi-turn tool use
        anthropic_messages = [
            {"role": m.role.value, "content": m.content}
            for m in context_messages
            if m.content.strip()
        ]

        full_final_response: List[str] = []
        tools_called: List[str] = []

        while iteration < _MAX_TOOL_ITERATIONS:
            iteration += 1
            stream_metadata: dict = {}

            try:
                async for chunk in provider.stream_completion(
                    messages=context_messages,
                    system_prompt=system_prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    tools=COSIGHT_TOOLS,
                    stream_metadata=stream_metadata,
                ):
                    full_final_response.append(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"

            except Exception as e:
                is_overloaded = (
                    isinstance(e, anthropic_sdk.APIStatusError) and e.status_code == 529
                ) or "overloaded" in str(e).lower()

                if is_overloaded and settings.mistral_api_key:
                    logger.warning("Claude overloaded — falling back to Mistral for CoSight")
                    full_final_response.clear()
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
                        ):
                            full_final_response.append(chunk)
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    except Exception as me:
                        logger.error("Mistral fallback error: %s", me)
                        yield f"data: {json.dumps({'type': 'error', 'error': 'Service temporarily unavailable.'})}\n\n"
                        return
                    break  # Mistral doesn't support tool use — end loop
                else:
                    logger.error("CoSight stream error: %s", e)
                    yield f"data: {json.dumps({'type': 'error', 'error': 'Something went wrong. Please try again.'})}\n\n"
                    return

            tool_calls = stream_metadata.get("tool_calls", [])
            if not tool_calls:
                # No tools called — model gave final answer
                break

            # Execute tools and feed results back into context
            tool_results = []
            for call in tool_calls:
                tool_name = call["name"]
                tools_called.append(tool_name)

                yield f"data: {json.dumps({'type': 'tool_call', 'tool': tool_name})}\n\n"

                tool_result = await _execute_tool(tool_name, call["input"])

                # Handle generate_report specially — emit a report SSE event
                if tool_name == "generate_report":
                    inp = call["input"]
                    from app.models.cosight_report import ReportArtifact, ReportSection
                    artifact = ReportArtifact(
                        title=inp.get("title", "Marketing Report"),
                        date_range_start=inp.get("date_range_start", ""),
                        date_range_end=inp.get("date_range_end", ""),
                        executive_summary=inp.get("executive_summary"),
                        sections=[],
                    )
                    # Save to DB
                    from app.api.routes.cosight.reports import save_report
                    saved = await save_report(artifact)
                    report_id = saved["id"]
                    yield f"data: {json.dumps({'type': 'report', 'report_id': report_id, 'artifact': json.loads(artifact.model_dump_json())})}\n\n"
                    tool_result = json.dumps({"report_id": report_id, "status": "saved"})

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": call["id"],
                    "content": tool_result,
                })

            # Emit provenance chips for the tools called
            yield f"data: {json.dumps({'type': 'provenance', 'tools': tools_called})}\n\n"

            # Append assistant tool-use block + user tool-results to context
            # We reconstruct context_messages for the next iteration
            assistant_tool_content = [
                {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]}
                for c in tool_calls
            ]
            # Add to context for next turn
            context_messages = list(context_messages) + [
                Message(
                    id=str(uuid.uuid4()),
                    content="__tool_use__",  # sentinel — provider skips non-str content
                    role=MessageRole.ASSISTANT,
                    timestamp=datetime.utcnow(),
                ),
            ]
            # We need to inject as raw dicts for Claude's multi-turn format.
            # Override stream_completion call next iteration with extended messages.
            # Simpler: rebuild context_messages as raw Claude messages for the loop.
            # The provider's stream_completion accepts List[Message] — we need raw dicts
            # for tool results. Use a separate messages list.
            if not hasattr(context_messages, "_raw_override"):
                # Build a raw message list for the multi-turn tool loop
                raw_messages = [
                    {"role": m.role.value, "content": m.content}
                    for m in context_messages
                    if m.content.strip() and not m.content.startswith("__tool_use__")
                ]
                raw_messages.append({"role": "assistant", "content": assistant_tool_content})
                raw_messages.append({"role": "user", "content": tool_results})

                # Wrap in Message objects that pass through as-is
                # Since our provider expects List[Message], and tool results need raw dicts,
                # we pass a special sentinel that gets skipped, and use a direct Anthropic call.
                # Cleanest path: call Anthropic directly for subsequent iterations.
                try:
                    from anthropic import AsyncAnthropic
                    direct_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
                    full_final_response.clear()

                    async with direct_client.messages.stream(
                        model=settings.anthropic_model,
                        max_tokens=request.max_tokens,
                        system=system_prompt,
                        messages=raw_messages,
                        tools=COSIGHT_TOOLS,
                        temperature=request.temperature,
                    ) as stream:
                        current_tool_name = ""
                        current_tool_id = ""
                        current_tool_input = ""
                        next_tool_calls = []

                        async for event in stream:
                            etype = event.type
                            if etype == "content_block_start":
                                block = event.content_block
                                if block.type == "tool_use":
                                    current_tool_name = block.name
                                    current_tool_id = block.id
                                    current_tool_input = ""
                            elif etype == "content_block_delta":
                                delta = event.delta
                                if delta.type == "text_delta":
                                    full_final_response.append(delta.text)
                                    yield f"data: {json.dumps({'type': 'chunk', 'content': delta.text})}\n\n"
                                elif delta.type == "input_json_delta":
                                    current_tool_input += delta.partial_json
                            elif etype == "content_block_stop":
                                if current_tool_name:
                                    try:
                                        ti = json.loads(current_tool_input) if current_tool_input else {}
                                    except Exception:
                                        ti = {}
                                    next_tool_calls.append({
                                        "id": current_tool_id,
                                        "name": current_tool_name,
                                        "input": ti,
                                    })
                                    current_tool_name = ""
                                    current_tool_id = ""
                                    current_tool_input = ""

                        if next_tool_calls:
                            # More tool calls — continue loop with updated raw_messages
                            tool_results_next = []
                            for call in next_tool_calls:
                                tools_called.append(call["name"])
                                yield f"data: {json.dumps({'type': 'tool_call', 'tool': call['name']})}\n\n"
                                tr = await _execute_tool(call["name"], call["input"])
                                tool_results_next.append({
                                    "type": "tool_result",
                                    "tool_use_id": call["id"],
                                    "content": tr,
                                })
                            raw_messages.append({"role": "assistant", "content": [
                                {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["input"]}
                                for c in next_tool_calls
                            ]})
                            raw_messages.append({"role": "user", "content": tool_results_next})
                            # One more final pass
                            async with direct_client.messages.stream(
                                model=settings.anthropic_model,
                                max_tokens=request.max_tokens,
                                system=system_prompt,
                                messages=raw_messages,
                                temperature=request.temperature,
                            ) as final_stream:
                                async for event in final_stream:
                                    if event.type == "content_block_delta" and event.delta.type == "text_delta":
                                        full_final_response.append(event.delta.text)
                                        yield f"data: {json.dumps({'type': 'chunk', 'content': event.delta.text})}\n\n"
                        break

                except Exception as direct_err:
                    logger.error("Direct Anthropic multi-turn call failed: %s", direct_err)
                    break

        # Emit final provenance chips
        if tools_called:
            unique_tools = list(dict.fromkeys(tools_called))
            yield f"data: {json.dumps({'type': 'provenance', 'tools': unique_tools})}\n\n"

        # Persist assistant response
        response_ms = int((time.time() - _t0) * 1000)
        full_text = "".join(full_final_response).strip()
        if full_text:
            assistant_msg = Message(
                id=str(uuid.uuid4()),
                content=full_text,
                role=MessageRole.ASSISTANT,
                timestamp=datetime.utcnow(),
                response_time_ms=response_ms,
            )
            disc_service.add_message(request.discussion_id, assistant_msg)

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Discussion CRUD ───────────────────────────────────────────────────────────

@router.get("/discussions", response_model=list)
async def list_discussions():
    return [
        {"id": d.id, "title": d.title, "created_at": str(d.created_at), "updated_at": str(d.updated_at)}
        for d in get_cosight_discussion_service().list_discussions()
    ]


@router.post("/discussions", response_model=dict)
async def create_discussion():
    d = get_cosight_discussion_service().create_discussion()
    return {"id": d.id, "title": d.title}


@router.delete("/discussions/{discussion_id}", response_model=dict)
async def delete_discussion(discussion_id: str):
    ok = get_cosight_discussion_service().delete_discussion(discussion_id)
    return {"status": "deleted" if ok else "not_found"}
