"""Anthropic Claude provider — standalone, supports tool use."""
import json
import logging
from typing import AsyncGenerator, Dict, List, Optional

from anthropic import AsyncAnthropic

from app.models.message import Message, MessageRole

logger = logging.getLogger(__name__)


class ClaudeProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def stream_completion(
        self,
        messages: List[Message],
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[List[Dict]] = None,
        stream_metadata: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text from Claude, capturing any tool_use blocks in stream_metadata."""
        formatted_messages = []
        for msg in messages:
            if not msg.content or not msg.content.strip():
                continue
            if msg.role == MessageRole.SYSTEM:
                continue

            # Reconstruct tool_use + tool_result turns from the __checklist__ sentinel.
            # The DB stores checklist messages as plain assistant text (no schema migration
            # needed). We expand them back into the two-turn structure Anthropic requires
            # so Claude knows it already called show_checklist and moves on to submit_to_hive.
            if msg.role == MessageRole.ASSISTANT and msg.content.startswith("__checklist__"):
                # Parse the stored field lines back into a dict
                lines = msg.content.split("\n")[1:]  # drop the __checklist__ header
                fields: Dict[str, str] = {}
                for line in lines:
                    # Format is "**key**: value"
                    if line.startswith("**") and "**: " in line:
                        key = line[2:line.index("**", 2)]
                        value = line[line.index("**: ") + 4:]
                        fields[key] = value

                synthetic_tool_id = "toolu_checklist_synthetic"
                # Assistant turn: the tool_use block
                formatted_messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": synthetic_tool_id,
                            "name": "show_checklist",
                            "input": {"fields": fields, "intent": msg.intent or "other"},
                        }
                    ],
                })
                # User turn: the tool_result (checklist was displayed successfully)
                formatted_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": synthetic_tool_id,
                            "content": "Checklist displayed to user. Awaiting confirmation.",
                        }
                    ],
                })
                continue

            formatted_messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        if not formatted_messages:
            formatted_messages = [{"role": "user", "content": "Hello"}]

        kwargs: Dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": formatted_messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools

        tool_calls: List[Dict] = []
        current_tool_name: str = ""
        current_tool_id: str = ""
        current_tool_input: str = ""

        async with self.client.messages.stream(**kwargs) as stream:
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
                        yield delta.text
                    elif delta.type == "input_json_delta":
                        current_tool_input += delta.partial_json

                elif etype == "content_block_stop":
                    if current_tool_name:
                        try:
                            tool_input = json.loads(current_tool_input) if current_tool_input else {}
                        except Exception:
                            tool_input = {}
                        tool_calls.append({
                            "id": current_tool_id,
                            "name": current_tool_name,
                            "input": tool_input,
                        })
                        current_tool_name = ""
                        current_tool_id = ""
                        current_tool_input = ""

        if stream_metadata is not None and tool_calls:
            stream_metadata["tool_calls"] = tool_calls
