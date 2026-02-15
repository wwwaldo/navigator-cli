"""Evaluator: analyzes conversations and extracts behavioral preferences."""

import json
import re
import sys
import uuid
from datetime import datetime, timezone

from anthropic import Anthropic
from anthropic._exceptions import APIError, APIStatusError

from .config import (
    MIN_CONVERSATION_MESSAGES,
    PREFERENCE_COMPRESSION_THRESHOLD,
    get_last_evaluated,
    get_model,
    get_token,
    set_last_evaluated,
)
from .store import (
    append_preference,
    clear_preferences,
    load_preferences,
    load_unevaluated_conversations,
)


EVALUATOR_PROMPT = """You are a conversation evaluator. Analyze the following conversation between a user and an AI assistant.

Identify moments where the user expressed dissatisfaction, frustration, or disengagement. This includes:
- Explicit negative feedback ("that's not what I meant", "stop doing that")
- Implicit signals (user repeating themselves, ignoring suggestions, changing topic abruptly, shorter responses indicating disengagement)
- Mismatches between what the user asked for and what the assistant provided

For each issue found, generate an alternative response the assistant should have given instead.

Output a JSON object with:
{{
  "issues": [
    {{
      "assistant_message": "the original assistant response that caused the problem",
      "trigger": "what specifically was wrong with it",
      "user_reaction": "how the user responded",
      "alternative_response": "what the assistant should have said instead",
      "lesson": "the general principle to follow in future"
    }}
  ],
  "behavioral_guidelines": "Concise instructions for future conversations with this user, written as direct rules.",
  "example_pairs": [
    {{
      "instead_of": "short summary of bad pattern",
      "do_this": "short summary of good pattern"
    }}
  ]
}}

If there are no issues, return:
{{"issues": [], "behavioral_guidelines": "", "example_pairs": []}}

IMPORTANT: Skip entirely (return empty issues/guidelines) if:
- The assistant's response is a system or API error (e.g. "No API key configured", "Invalid API key", "Authentication failed", "run: navigator config"). These are infrastructure errors, not assistant behavior.
- The conversation is too short to show meaningful user-assistant interaction.

<conversation>
{conversation}
</conversation>"""


COMPRESSION_PROMPT = """You are a preference manager. Below is a list of behavioral guidelines extracted from a user's conversation history.

Consolidate these into a concise set of rules:
- Merge duplicates and similar guidelines
- Remove guidelines that contradict each other (keep the most recent)
- Drop guidelines that seem one-off or low-priority
- Keep the total under 20 rules

Output the consolidated guidelines as a JSON array of strings. Each string is one rule. Example: ["Rule 1", "Rule 2"].

<guidelines>
{guidelines}
</guidelines>"""


# Phrases that indicate the "assistant" content is actually a system/API error, not real assistant output
_SYSTEM_ERROR_PHRASES = (
    "no api key",
    "api key configured",
    "invalid api key",
    "authentication",
    "oauth authentication",
    "navigator config",
    "console.anthropic.com",
    "run:",
    "rate limit",
    "billing",
)


def _get_message_content(msg: dict) -> str:
    """Extract plain text from a message."""
    content = msg.get("content", "")
    if isinstance(content, list):
        return " ".join(
            b.get("text", "") for b in content if isinstance(b, dict) and "text" in b
        )
    return str(content) if content else ""


def _is_system_error_conversation(conversation: dict) -> bool:
    """True if the conversation appears to be system/API errors rather than real assistant output."""
    messages = conversation.get("messages", [])
    assistant_text = " ".join(
        _get_message_content(m) for m in messages if m.get("role") == "assistant"
    ).lower()
    if not assistant_text.strip():
        return False
    return any(phrase in assistant_text for phrase in _SYSTEM_ERROR_PHRASES)


def _format_conversation_for_eval(conversation: dict) -> str:
    """Format a conversation for the evaluator prompt."""
    messages = conversation.get("messages", [])
    lines = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = _get_message_content(msg)
        lines.append(f"{role.upper()}: {content}")
    return "\n\n".join(lines)


def _extract_json_from_response(text: str) -> dict | None:
    """Extract JSON from model response, handling markdown code blocks."""
    text = text.strip()
    # Try to find ```json ... ``` block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    # Try raw JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find {...} in text
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _log_api_error(e: Exception) -> None:
    """Log full API error details."""
    print("[navigator] API error details:", file=sys.stderr)
    print(f"  type: {type(e).__name__}", file=sys.stderr)
    print(f"  message: {e}", file=sys.stderr)
    if isinstance(e, APIStatusError):
        print(f"  status_code: {e.status_code}", file=sys.stderr)
        print(f"  request_id: {getattr(e, 'request_id', None)}", file=sys.stderr)
    if isinstance(e, APIError) and e.body is not None:
        print(f"  response body: {e.body}", file=sys.stderr)
    sys.stderr.flush()


def evaluate_conversation(conversation: dict, client: Anthropic, model: str) -> dict | None:
    """Run evaluator on a single conversation. Returns preference dict or None."""
    formatted = _format_conversation_for_eval(conversation)
    prompt = EVALUATOR_PROMPT.format(conversation=formatted)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as e:
        _log_api_error(e)
        raise

    text = response.content[0].text if response.content else ""
    data = _extract_json_from_response(text)
    if not data:
        return None

    issues = data.get("issues", [])
    guidelines = data.get("behavioral_guidelines", "")
    example_pairs = data.get("example_pairs", [])

    if not guidelines and not example_pairs and not issues:
        return None

    return {
        "id": str(uuid.uuid4()),
        "source_conversation_id": conversation.get("conversation_id", ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "behavioral_guidelines": guidelines,
        "example_pairs": example_pairs,
        "issues": issues,
    }


def run_compression(client: Anthropic, model: str) -> list[str]:
    """Compress preferences into fewer rules. Returns list of guideline strings."""
    prefs = load_preferences()
    guidelines_text = "\n".join(
        p.get("behavioral_guidelines", "")
        for p in prefs
        if p.get("behavioral_guidelines")
    )
    if not guidelines_text.strip():
        return []

    prompt = COMPRESSION_PROMPT.format(guidelines=guidelines_text)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as e:
        _log_api_error(e)
        raise

    text = response.content[0].text if response.content else ""
    data = _extract_json_from_response(text)
    if not data:
        return []

    if isinstance(data, list):
        return [str(r) for r in data if r]
    if isinstance(data, dict) and "guidelines" in data:
        return [str(r) for r in data["guidelines"] if r]
    return []


def run_learn() -> tuple[int, bool]:
    """Process unevaluated conversations and update preferences.
    Returns (num_conversations_processed, compression_ran).
    """
    api_key = get_token()
    if not api_key:
        raise ValueError(
            "No API key configured. Run: navigator config --api-key sk-ant-... (from console.anthropic.com)"
        )

    client = Anthropic(api_key=api_key)
    model = get_model()
    last_evaluated = get_last_evaluated()
    conversations = load_unevaluated_conversations(last_evaluated)

    if not conversations:
        return 0, False

    latest_timestamp = last_evaluated or ""
    existing_guidelines: set[str] = {g.strip().lower() for g in (p.get("behavioral_guidelines", "") for p in load_preferences()) if g and g.strip()}

    for conv in conversations:
        messages = conv.get("messages", [])
        if len(messages) < MIN_CONVERSATION_MESSAGES:
            ts = conv.get("timestamp", "")
            if ts > latest_timestamp:
                latest_timestamp = ts
            continue
        if _is_system_error_conversation(conv):
            ts = conv.get("timestamp", "")
            if ts > latest_timestamp:
                latest_timestamp = ts
            continue
        pref = evaluate_conversation(conv, client, model)
        if pref:
            # Deduplicate: skip if we already have this guideline (normalized)
            new_guidelines = (pref.get("behavioral_guidelines") or "").strip()
            if new_guidelines:
                normalized = new_guidelines.lower()
                if normalized in existing_guidelines:
                    ts = conv.get("timestamp", "")
                    if ts > latest_timestamp:
                        latest_timestamp = ts
                    continue
                existing_guidelines.add(normalized)
            append_preference(pref)
        ts = conv.get("timestamp", "")
        if ts > latest_timestamp:
            latest_timestamp = ts

    if latest_timestamp:
        set_last_evaluated(latest_timestamp)

    # Compression if needed
    prefs = load_preferences()
    compression_ran = False
    if len(prefs) >= PREFERENCE_COMPRESSION_THRESHOLD:
        consolidated = run_compression(client, model)
        if consolidated:
            clear_preferences()
            for g in consolidated:
                append_preference({
                    "id": str(uuid.uuid4()),
                    "source_conversation_id": "",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "behavioral_guidelines": g,
                    "example_pairs": [],
                    "issues": [],
                })
            compression_ran = True

    return len(conversations), compression_ran
