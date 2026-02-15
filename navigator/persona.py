"""Persona summarization via API."""

from anthropic import Anthropic

from .config import get_model, get_token


SUMMARY_PROMPT = """Summarize the following behavioral guidelines or persona instructions in one concise paragraph (2-4 sentences). Capture the main themes and how the user prefers to be assisted.

<persona>
{content}
</persona>"""


def summarize_persona(content: str) -> str | None:
    """Summarize persona content via API. Returns paragraph string or None on failure."""
    if not content or not content.strip():
        return None

    api_key = get_token()
    if not api_key:
        return None

    client = Anthropic(api_key=api_key)
    model = get_model()

    # Truncate if very long to avoid token limits
    max_chars = 16_000
    truncated = content[:max_chars] + "..." if len(content) > max_chars else content

    try:
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(content=truncated)}],
        )
    except Exception:
        return None

    text = response.content[0].text if response.content else ""
    return text.strip() if text else None
