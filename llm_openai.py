import os
from openai import OpenAI


# strict schema: {"description": "..."}.
SCHEMA = {
    "name": "company_description",
    "schema": {
        "type": "object",
        "properties": {
            "description": {"type": "string"}
        },
        "required": ["description"],
        "additionalProperties": False
    },
    "strict": True
}

SYSTEM = (
    "You improve company 'Solution Description' entries for a business database.\n"
    "Rules:\n"
    "- Use only the provided website text/context; do not invent facts.\n"
    "- Neutral, professional tone. No marketing fluff.\n"
    "- 1–2 sentences, max 50 words.\n"
    "- Output must be English.\n"
    "- If information is insufficient, write a cautious minimal description.\n"
)

_client: OpenAI | None = None


def _get_client() -> OpenAI | None:
    """Lazy init. Returns None if OPENAI_API_KEY is not set."""
    global _client
    if _client is not None:
        return _client

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    _client = OpenAI(api_key=api_key)
    return _client

def rewrite_description(company: str, website: str, extracted_text: str, current_description: str = "") -> str | None:
    """
    Returns improved description (string) or None if LLM is disabled/unavailable.
    """
    client = _get_client()
    if client is None:
        # LLM disabled (no API key) -> let caller fall back to scraper result
        return None
    
    prompt = f"""Company: {company}
Website: {website}
Current description: {current_description or "EMPTY"}

Website/extracted text:
{extracted_text}
"""

    # Responses API + Structured Outputs
    resp = client.responses.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "json_schema": SCHEMA
            }
        }
    )

    data = resp.output_parsed or {}  # thanks to strict schema this is parsed JSON
    desc = (data.get("description") or "").strip()
    # safety fallback
    return desc[:600] if desc else None
