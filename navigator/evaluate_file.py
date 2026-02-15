"""Evaluate an external conversations.json file (e.g. from Claude desktop export).

Expects JSON array of conversations with:
  - uuid, name, created_at, updated_at, chat_messages
  - chat_messages: [{ sender: "human"|"assistant", text: "..." }]

Outputs evaluation results to a JSONL file.
"""

import json
import sys
from pathlib import Path

from anthropic import Anthropic

from .config import MIN_CONVERSATION_MESSAGES, get_model, get_token
from .evaluator import (
    _is_system_error_conversation,
    evaluate_conversation,
)


def _get_text(msg: dict) -> str:
    """Extract text from a chat message (supports content blocks)."""
    text = msg.get("text", "")
    if text:
        return str(text)
    content = msg.get("content", [])
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
        )
    return str(content) if content else ""


def convert_conversation(raw: dict) -> dict:
    """Convert external format to evaluator format."""
    chat_messages = raw.get("chat_messages", [])
    messages = []
    for m in chat_messages:
        sender = m.get("sender", "")
        role = "user" if sender == "human" else "assistant"
        text = _get_text(m)
        messages.append({"role": role, "content": text})
    return {
        "conversation_id": raw.get("uuid", ""),
        "timestamp": raw.get("updated_at", raw.get("created_at", "")),
        "messages": messages,
    }


def run_evaluate_file(
    input_path: Path,
    output_path: Path | None = None,
    limit: int | None = None,
) -> tuple[int, int]:
    """Evaluate conversations from a JSON file. Returns (evaluated_count, total_with_issues)."""
    api_key = get_token()
    if not api_key:
        raise ValueError(
            "No API key configured. Run: navigator config --api-key sk-ant-... (from console.anthropic.com)"
        )

    print("[navigator] Loading conversations (may take a moment for large files)...", file=sys.stderr)
    sys.stderr.flush()
    with open(input_path) as f:
        raw_conversations = json.load(f)

    if not isinstance(raw_conversations, list):
        raise ValueError("Expected JSON array of conversations")

    conversations = [convert_conversation(c) for c in raw_conversations]
    # Pre-filter to get eligible count
    eligible = [
        c
        for c in conversations
        if len(c.get("messages", [])) >= MIN_CONVERSATION_MESSAGES
        and not _is_system_error_conversation(c)
    ]
    to_process = eligible[:limit] if limit else eligible
    total = len(to_process)

    # ~15–30 sec per API call for typical conversation length
    est_min = total * 15 // 60
    est_max = total * 30 // 60
    if total > 0:
        print(
            f"[navigator] {total} conversation(s) to evaluate (~{est_min}–{est_max} min estimated)",
            file=sys.stderr,
        )
        sys.stderr.flush()

    client = Anthropic(api_key=api_key)
    model = get_model()

    out_path = output_path or input_path.with_suffix(".evaluated.jsonl")
    out_path.write_text("")

    evaluated = 0
    with_issues = 0
    eligible_iter = iter(to_process)

    for conv in eligible_iter:
        try:
            pref = evaluate_conversation(conv, client, model)
        except Exception as e:
            print(
                f"[navigator] Error evaluating conv {conv.get('conversation_id', '?')}: {e}",
                file=sys.stderr,
            )
            continue

        evaluated += 1
        if pref:
            with_issues += 1
            with open(out_path, "a") as f:
                f.write(json.dumps(pref) + "\n")

        print(
            f"[navigator] {evaluated}/{total} evaluated ({with_issues} with issues)",
            file=sys.stderr,
        )
        sys.stderr.flush()

    return evaluated, with_issues
