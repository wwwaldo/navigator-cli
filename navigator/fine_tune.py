"""Build a fine-tuning dataset from preferences and conversations.

Exports prompt-completion pairs in JSONL format for open-weights model fine-tuning
(Unsloth, Axolotl, LLaMA-Factory, etc.). Uses behavioral corrections from the
evaluator: when the assistant gave a suboptimal response, we use the user's
message as prompt and the preferred alternative as completion.
"""

import json
from pathlib import Path

from .config import CONVERSATIONS_PATH, PREFERENCES_PATH, ensure_navigator_dir


def _get_message_content(msg: dict) -> str:
    """Extract plain text from a message."""
    content = msg.get("content", "")
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
        )
    return str(content) if content else ""


def _load_conversations_jsonl(path: Path) -> dict[str, dict]:
    """Load Navigator conversations.jsonl. Returns dict by conversation_id."""
    if not path.exists():
        return {}
    result = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                conv = json.loads(line)
                cid = conv.get("conversation_id", "")
                if cid:
                    result[cid] = conv
            except json.JSONDecodeError:
                continue
    return result


def _load_conversations_json(path: Path) -> dict[str, dict]:
    """Load external conversations.json (array format). Returns dict by uuid."""
    if not path.exists():
        return {}
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, list):
        return {}
    result = {}
    for conv in data:
        cid = conv.get("uuid", "")
        if not cid:
            continue
        # Convert to internal format
        chat_messages = conv.get("chat_messages", [])
        messages = []
        for m in chat_messages:
            sender = m.get("sender", "")
            role = "user" if sender == "human" else "assistant"
            text = m.get("text", "")
            if not text and "content" in m:
                content = m["content"]
                if isinstance(content, list):
                    text = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
                    )
                else:
                    text = str(content)
            messages.append({"role": role, "content": text})
        result[cid] = {"conversation_id": cid, "messages": messages}
    return result


def _load_preferences(path: Path) -> list[dict]:
    """Load preferences from JSONL file."""
    if not path.exists():
        return []
    prefs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                prefs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return prefs


def _find_user_message_before(messages: list[dict], assistant_text: str) -> str | None:
    """Find the last user message before an assistant message matching assistant_text.
    Returns the user message content, or None if not found.
    """
    want = (assistant_text or "").strip().lower()
    if not want:
        return None
    want_prefix = want[:150]
    last_user = None
    for msg in messages:
        role = msg.get("role", "")
        content = _get_message_content(msg)
        if role == "user":
            last_user = content
        elif role == "assistant":
            got = content.strip().lower()
            # Match if issue text overlaps with conversation assistant message
            if want_prefix in got or (len(got) > 50 and got[:150] in want):
                return last_user
            last_user = None
    return None


def _format_example(
    user_content: str,
    assistant_content: str,
    fmt: str,
) -> dict:
    """Format a single example for the target format."""
    if fmt == "messages":
        return {
            "messages": [
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": assistant_content},
            ]
        }
    if fmt == "sharegpt":
        return {
            "conversations": [
                {"from": "human", "value": user_content},
                {"from": "gpt", "value": assistant_content},
            ]
        }
    if fmt == "alpaca":
        return {
            "instruction": user_content,
            "input": "",
            "output": assistant_content,
        }
    raise ValueError(
        f"Unknown format: {fmt}. Use messages, sharegpt, or alpaca."
    )


def build_dataset(
    preferences_path: Path,
    conversations_path: Path | None,
    output_path: Path,
    *,
    use_json_conversations: bool = False,
    output_format: str = "messages",
) -> int:
    """Build fine-tuning JSONL from preferences and conversations.

    Supports formats for open-weights fine-tuning:
    - messages: {"messages": [...]} — LLaMA-Factory, Axolotl, Unsloth (default)
    - sharegpt: {"conversations": [{"from": "human", "value": "..."}, ...]}
    - alpaca: {"instruction": "...", "input": "", "output": "..."}

    Returns the number of examples written.
    """
    if output_format not in ("messages", "sharegpt", "alpaca"):
        raise ValueError(
            f"Invalid format: {output_format}. Use messages, sharegpt, or alpaca."
        )
    ensure_navigator_dir()
    prefs = _load_preferences(preferences_path)
    if not prefs:
        return 0

    conversations: dict[str, dict] = {}
    if conversations_path and conversations_path.exists():
        if use_json_conversations:
            conversations = _load_conversations_json(conversations_path)
        else:
            conversations = _load_conversations_jsonl(conversations_path)

    examples: list[dict] = []

    for pref in prefs:
        issues = pref.get("issues", [])
        source_cid = pref.get("source_conversation_id", "")
        conv = conversations.get(source_cid) if source_cid else None

        for issue in issues:
            alt = (issue.get("alternative_response") or "").strip()
            if not alt:
                continue

            user_content: str | None = None
            if conv:
                messages = conv.get("messages", [])
                assistant_msg = issue.get("assistant_message", "")
                user_content = _find_user_message_before(messages, assistant_msg)

            if not user_content:
                lesson = issue.get("lesson", "") or alt[:200]
                user_content = f"[Apply this correction: {lesson}]"

            examples.append(_format_example(user_content, alt, output_format))

        # Also add example_pairs as synthetic examples when we have no conversation match
        if not conv:
            for pair in pref.get("example_pairs", []):
                instead_of = pair.get("instead_of", "")
                do_this = pair.get("do_this", "")
                if instead_of and do_this:
                    user_content = f"[When you would: {instead_of}. Instead do: {do_this}]"
                    examples.append(_format_example(user_content, do_this, output_format))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    return len(examples)
