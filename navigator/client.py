"""Claude Agent SDK client with preference injection."""

import os
import sys
from collections.abc import Callable
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from .config import get_auth_env, get_model, is_debug
from .store import format_preferences_for_prompt, load_preferences


def _stderr_callback(line: str) -> None:
    """Log CLI stderr (API errors, etc.)."""
    prefix = "[navigator debug] " if is_debug() else ""
    print(f"{prefix}{line}", file=sys.stderr, flush=True)


def build_chat_options(cwd: Path | None = None) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with preferences injected and tools enabled."""
    preferences = load_preferences()
    preferences_block = format_preferences_for_prompt(preferences)

    env = get_auth_env()
    if is_debug() and "ANTHROPIC_CUSTOM_HEADERS" in env:
        print("[navigator debug] Passing ANTHROPIC_CUSTOM_HEADERS to CLI", file=sys.stderr, flush=True)

    options_dict = {
        "allowed_tools": ["Read", "Edit", "Write", "Bash", "Glob", "Grep"],
        "permission_mode": "acceptEdits",
        "model": get_model(),
        "cwd": str(cwd) if cwd else os.getcwd(),
        "env": {**env},
        "include_partial_messages": True,  # Enables streaming text via StreamEvent
    }
    # Always capture stderr so API errors (e.g. Invalid API key) are visible
    options_dict["stderr"] = _stderr_callback
    if is_debug():
        options_dict["extra_args"] = {"debug-to-stderr": None}

    if preferences_block:
        options_dict["system_prompt"] = {
            "type": "preset",
            "preset": "claude_code",
            "append": "\n\n" + preferences_block,
        }
    else:
        options_dict["system_prompt"] = {"type": "preset", "preset": "claude_code"}

    return ClaudeAgentOptions(**options_dict)


def extract_text_from_message(message) -> str:
    """Extract plain text from an AssistantMessage or similar."""
    if isinstance(message, AssistantMessage):
        parts = []
        for block in message.content:
            if isinstance(block, TextBlock):
                parts.append(block.text)
        return "\n".join(parts)
    if hasattr(message, "result"):
        return str(message.result)
    return str(message)


def _format_tool_result(content: str | list | None, is_error: bool | None) -> str:
    """Format tool result for display."""
    if content is None:
        return "(no output)"
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, dict):
                parts.append(str(block))
        return "\n".join(parts) if parts else str(content)
    return str(content)


async def chat_turn(
    client: ClaudeSDKClient,
    user_message: str,
    *,
    on_chunk: Callable[[str], None] | None = None,
    on_tool: Callable[[str, dict, str], None] | None = None,
) -> tuple[list[dict], str | None]:
    """Send a user message and collect the full response.
    Returns (messages_for_log, final_result_text).
    on_chunk: called for each AssistantMessage text chunk (streaming).
    on_tool: called for each tool use with (name, input, result).
    """
    await client.query(user_message)

    messages_for_log: list[dict] = [
        {"role": "user", "content": user_message},
    ]

    assistant_content = ""
    streamed_parts: list[str] = []
    tool_use_by_id: dict[str, tuple[str, dict]] = {}  # id -> (name, input)

    async for msg in client.receive_response():
        if isinstance(msg, ResultMessage) and msg.result:
            assistant_content = msg.result.strip()
        elif isinstance(msg, StreamEvent):
            # Anthropic content_block_delta: event.delta.type=="text_delta" has streaming text
            ev = msg.event or {}
            if ev.get("type") == "content_block_delta":
                delta = ev.get("delta") or {}
                if delta.get("type") == "text_delta":
                    text = delta.get("text") or ""
                    if text:
                        streamed_parts.append(text)
                        if on_chunk:
                            on_chunk(text)
        elif isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    if block.text:
                        # Only stream from AssistantMessage if we didn't get StreamEvent chunks
                        if not streamed_parts:
                            streamed_parts.append(block.text)
                            if on_chunk:
                                on_chunk(block.text)
                        # else: already streamed via StreamEvent, don't duplicate
                elif isinstance(block, ToolUseBlock):
                    tool_use_by_id[block.id] = (block.name, block.input)
                elif isinstance(block, ToolResultBlock):
                    name, inp = tool_use_by_id.get(block.tool_use_id, ("?", {}))
                    result_str = _format_tool_result(block.content, block.is_error)
                    if on_tool:
                        on_tool(name, inp, result_str)
        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, ToolResultBlock):
                    name, inp = tool_use_by_id.get(block.tool_use_id, ("?", {}))
                    result_str = _format_tool_result(block.content, block.is_error)
                    if on_tool:
                        on_tool(name, inp, result_str)
    if not assistant_content and streamed_parts:
        assistant_content = "\n".join(streamed_parts).strip()
    if assistant_content:
        messages_for_log.append({"role": "assistant", "content": assistant_content})

    return messages_for_log, assistant_content or None
