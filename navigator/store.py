"""JSONL storage for conversations and preferences."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    CONVERSATIONS_PATH,
    PREFERENCES_PATH,
    ensure_navigator_dir,
)


def _ensure_file(path: Path) -> None:
    ensure_navigator_dir()
    if not path.exists():
        path.touch()


def append_conversation(conversation_id: str, messages: list[dict]) -> None:
    """Append a conversation to conversations.jsonl."""
    _ensure_file(CONVERSATIONS_PATH)
    record = {
        "conversation_id": conversation_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messages": messages,
    }
    with open(CONVERSATIONS_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_conversations() -> list[dict]:
    """Load all conversations from conversations.jsonl."""
    if not CONVERSATIONS_PATH.exists():
        return []
    conversations = []
    with open(CONVERSATIONS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                conversations.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return conversations


def load_unevaluated_conversations(last_evaluated: str | None) -> list[dict]:
    """Load conversations that haven't been evaluated yet.
    If last_evaluated is None, return all. Otherwise return those after that timestamp.
    """
    all_convos = load_conversations()
    if not last_evaluated:
        return all_convos
    return [c for c in all_convos if c.get("timestamp", "") > last_evaluated]


def append_preference(preference: dict) -> None:
    """Append a preference record to preferences.jsonl."""
    _ensure_file(PREFERENCES_PATH)
    if "id" not in preference:
        preference["id"] = str(uuid.uuid4())
    if "created_at" not in preference:
        preference["created_at"] = datetime.now(timezone.utc).isoformat()
    with open(PREFERENCES_PATH, "a") as f:
        f.write(json.dumps(preference) + "\n")


def load_preferences() -> list[dict]:
    """Load all preferences from preferences.jsonl."""
    if not PREFERENCES_PATH.exists():
        return []
    preferences = []
    with open(PREFERENCES_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                preferences.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return preferences


def clear_preferences() -> None:
    """Clear all preferences."""
    _ensure_file(PREFERENCES_PATH)
    PREFERENCES_PATH.write_text("")


def format_preferences_for_prompt(preferences: list[dict]) -> str:
    """Format preferences into the system prompt block."""
    if not preferences:
        return ""

    guidelines: list[str] = []
    example_pairs: list[tuple[str, str]] = []

    for pref in preferences:
        if pref.get("behavioral_guidelines"):
            guidelines.append(pref["behavioral_guidelines"])
        for pair in pref.get("example_pairs", []):
            instead_of = pair.get("instead_of", "")
            do_this = pair.get("do_this", "")
            if instead_of and do_this:
                example_pairs.append((instead_of, do_this))

    if not guidelines and not example_pairs:
        return ""

    lines = [
        "<user_preferences>",
        "The following behavioral guidelines have been learned from previous conversations with this user. Follow them closely:",
        "",
        "\n".join(guidelines),
    ]

    if example_pairs:
        lines.extend([
            "",
            "Examples of preferred behavior:",
        ])
        for instead_of, do_this in example_pairs:
            lines.append(f"- Instead of: {instead_of} → Do this: {do_this}")

    lines.append("</user_preferences>")
    return "\n".join(lines)
