import json
import re
from typing import Any, Dict


def _unwrap_once(text: str) -> str:
    """
    Mirrors the n8n unwrapOnce logic:
    - If JSON-encoded string → unwrap
    - If object with `text` field → unwrap
    """
    if not text:
        return text

    text = text.strip()

    if not (text.startswith("{") or text.startswith("[") or text.startswith('"')):
        return text

    try:
        parsed = json.loads(text)
        if isinstance(parsed, str):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("text"), str):
            return parsed["text"]
    except Exception:
        pass

    return text


def extract_json_from_gemini(raw_text: str) -> Dict[str, Any]:
    """
    Python equivalent of your full n8n parsing pipeline.
    """
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)

    text = raw_text.strip()

    # unwrap JSON-inside-JSON up to 2 levels
    text = _unwrap_once(text)
    text = _unwrap_once(text)

    # remove leading "text:"
    if text.lower().startswith("text:"):
        text = text[5:].strip()

    # remove code fences
    text = (
        text.replace("```json", "")
        .replace("```diff", "")
        .replace("```", "")
        .strip()
    )

    # first attempt: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # fallback: slice between first { and last }
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:
        chunk = text[start : end + 1]
        try:
            return json.loads(chunk)
        except json.JSONDecodeError as e:
            return {
                "rawText": raw_text,
                "jsonChunk": chunk,
                "parseError": str(e),
            }

    return {
        "rawText": raw_text,
        "jsonChunk": None,
        "parseError": "No JSON object found",
    }
