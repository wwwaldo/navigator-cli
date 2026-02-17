"""Ollama chat client with tool support (Read, Edit, Write, Bash, Glob, Grep)."""

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from ollama import AsyncClient

from .config import get_ollama_model_name, get_persona_file
from .store import format_preferences_for_prompt, load_persona_from_file, load_preferences

# Tool schemas for Ollama (OpenAI function-calling format)
OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read the contents of a file. Use for inspecting code, configs, or any file.",
            "parameters": {
                "type": "object",
                "required": ["path"],
                "properties": {"path": {"type": "string", "description": "Path to the file (relative to cwd or absolute)"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Edit",
            "description": "Replace old_string with new_string in a file. Use for precise edits.",
            "parameters": {
                "type": "object",
                "required": ["path", "old_string", "new_string"],
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "old_string": {"type": "string", "description": "Exact text to find and replace"},
                    "new_string": {"type": "string", "description": "Replacement text"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write or overwrite a file with the given content.",
            "parameters": {
                "type": "object",
                "required": ["path", "content"],
                "properties": {
                    "path": {"type": "string", "description": "Path to the file"},
                    "content": {"type": "string", "description": "Content to write"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Run a shell command. Use for builds, tests, git, etc.",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {"command": {"type": "string", "description": "Shell command to run"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": "Find files matching a glob pattern.",
            "parameters": {
                "type": "object",
                "required": ["pattern"],
                "properties": {"pattern": {"type": "string", "description": "Glob pattern (e.g. **/*.py)"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": "Search for a pattern in files.",
            "parameters": {
                "type": "object",
                "required": ["pattern"],
                "properties": {
                    "pattern": {"type": "string", "description": "Regex or literal pattern to search"},
                    "path": {"type": "string", "description": "Path to search (file or directory, default: cwd)"},
                },
            },
        },
    },
]


def _resolve_path(path: str, cwd: Path) -> Path:
    """Resolve path relative to cwd."""
    p = Path(path)
    if not p.is_absolute():
        p = (cwd / p).resolve()
    return p


def _run_tool(name: str, args: dict, cwd: Path) -> str:
    """Execute a tool and return the result string."""
    try:
        if name == "Read":
            p = _resolve_path(args["path"], cwd)
            if not p.exists():
                return f"Error: file not found: {p}"
            if not p.is_file():
                return f"Error: not a file: {p}"
            return p.read_text()

        if name == "Edit":
            p = _resolve_path(args["path"], cwd)
            if not p.exists():
                return f"Error: file not found: {p}"
            content = p.read_text()
            old = args.get("old_string", "")
            new = args.get("new_string", "")
            if old not in content:
                return f"Error: old_string not found in file"
            new_content = content.replace(old, new, 1)
            p.write_text(new_content)
            return "Edit applied."

        if name == "Write":
            p = _resolve_path(args["path"], cwd)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(args.get("content", ""))
            return "File written."

        if name == "Bash":
            result = subprocess.run(
                args.get("command", ""),
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            out = result.stdout or ""
            err = result.stderr or ""
            if result.returncode != 0:
                return f"Exit code {result.returncode}\n{out}{err}".strip() or "(no output)"
            return (out + err).strip() or "(no output)"

        if name == "Glob":
            pattern = args.get("pattern", "")
            matches = sorted(cwd.glob(pattern))
            return "\n".join(str(m.relative_to(cwd)) for m in matches) if matches else "(no matches)"

        if name == "Grep":
            import re

            pattern = args.get("pattern", "")
            path_arg = args.get("path", ".")
            root = _resolve_path(path_arg, cwd)
            if not root.exists():
                return f"Error: path not found: {root}"
            try:
                pat = re.compile(pattern)
            except re.error:
                pat = re.compile(re.escape(pattern))
            lines = []
            files = [root] if root.is_file() else root.rglob("*")
            for f in files:
                if f.is_file():
                    try:
                        for i, line in enumerate(f.read_text().splitlines(), 1):
                            if pat.search(line):
                                lines.append(f"{f.relative_to(cwd)}:{i}:{line}")
                    except (OSError, UnicodeDecodeError):
                        pass
            return "\n".join(lines[:100]) if lines else "(no matches)"

    except Exception as e:
        return f"Error: {e}"
    return "Unknown tool"


def _build_system_prompt(cwd: Path) -> str:
    """Build system prompt with preferences and persona."""
    blocks = [
        "You are a helpful coding assistant. You have access to tools: Read, Edit, Write, Bash, Glob, Grep.",
        "Use them to explore the codebase, make edits, and run commands. Work in the directory: " + str(cwd),
    ]
    persona_path = get_persona_file()
    if persona_path and Path(persona_path).exists():
        blocks.append(load_persona_from_file(Path(persona_path)))
    preferences = load_preferences()
    pref_block = format_preferences_for_prompt(preferences)
    if pref_block:
        blocks.append(pref_block)
    return "\n\n".join(blocks)


async def ollama_chat_turn(
    client: AsyncClient,
    model: str,
    messages: list[dict],
    cwd: Path,
    system_prompt: str | None = None,
    *,
    on_chunk: Callable[[str], None] | None = None,
    on_tool: Callable[[str, dict, str], None] | None = None,
) -> tuple[list[dict], str | None]:
    """Run one chat turn with Ollama, handling tool calls in a loop.

    Returns (messages_for_log, final_assistant_text).
    """
    max_tool_rounds = 10
    all_messages = list(messages)
    if system_prompt:
        all_messages = [{"role": "system", "content": system_prompt}] + all_messages
    final_content = ""

    for _ in range(max_tool_rounds):
        stream = await client.chat(
            model=model,
            messages=all_messages,
            tools=OLLAMA_TOOLS,
            stream=True,
        )

        thinking = ""
        content = ""
        tool_calls: list[dict] = []
        done_thinking = False

        async for chunk in stream:
            msg = getattr(chunk, "message", chunk) or {}
            if isinstance(msg, dict):
                if msg.get("thinking"):
                    thinking += msg["thinking"]
                    if on_chunk and not done_thinking:
                        on_chunk(msg["thinking"])
                if msg.get("content"):
                    if not done_thinking:
                        done_thinking = True
                    content += msg["content"]
                    if on_chunk:
                        on_chunk(msg["content"])
                if msg.get("tool_calls"):
                    for tc in msg["tool_calls"]:
                        tool_calls.append(tc)
            else:
                if getattr(msg, "thinking", None):
                    thinking += msg.thinking or ""
                if getattr(msg, "content", None):
                    content += msg.content or ""
                    if on_chunk:
                        on_chunk(msg.content or "")
                if getattr(msg, "tool_calls", None):
                    tool_calls.extend(msg.tool_calls or [])

        final_content = content.strip()

        # Build assistant message for history
        asst_msg: dict = {"role": "assistant", "content": content}
        if thinking:
            asst_msg["thinking"] = thinking
        if tool_calls:
            asst_msg["tool_calls"] = tool_calls
        all_messages.append(asst_msg)

        if not tool_calls:
            break

        # Execute tools and append results
        for tc in tool_calls:
            fn = tc.get("function", tc) if isinstance(tc, dict) else getattr(tc, "function", tc)
            if isinstance(fn, dict):
                name = fn.get("name", "?")
                args_raw = fn.get("arguments", "{}")
            else:
                name = getattr(fn, "name", "?")
                args_raw = getattr(fn, "arguments", "{}")
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
            except json.JSONDecodeError:
                args = {}
            result = _run_tool(name, args, cwd)
            if on_tool:
                on_tool(name, args, result)
            all_messages.append({
                "role": "tool",
                "tool_name": name,
                "content": result,
            })

    # Build messages_for_log (user + assistant only, for conversation.jsonl)
    log_messages: list[dict] = []
    for m in messages:
        if m.get("role") == "user":
            log_messages.append({"role": "user", "content": m.get("content", "")})
    if final_content:
        log_messages.append({"role": "assistant", "content": final_content})

    return log_messages, final_content or None
