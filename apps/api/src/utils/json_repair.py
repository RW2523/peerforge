"""
JSON Repair Utility
===================
Strips LLM markdown fences and attempts to repair common JSON output issues.

Handles:
- Markdown code fences  (```json ... ```)
- Trailing commas      ({"a": 1,})
- Missing closing brackets / braces
- Single-quoted strings
- Python literals (True/False/None)
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def strip_fences(raw: str) -> str:
    """Remove ```json ... ``` and ``` ... ``` fences."""
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"^```\s*",     "", raw)
    raw = re.sub(r"```\s*$",     "", raw)
    return raw.strip()


def _repair(raw: str) -> str:
    """Best-effort JSON repair for common LLM output issues."""
    # Remove trailing commas before } or ]
    raw = re.sub(r",\s*([}\]])", r"\1", raw)

    # Replace Python literals with JSON equivalents
    raw = re.sub(r"\bTrue\b",  "true",  raw)
    raw = re.sub(r"\bFalse\b", "false", raw)
    raw = re.sub(r"\bNone\b",  "null",  raw)

    # Fix single-quoted strings (naïve — only safe for simple cases)
    # Only apply if double-quote parse fails and single-quotes are present
    if "'" in raw:
        try:
            json.loads(raw)
        except json.JSONDecodeError:
            raw = re.sub(r"(?<![\\])'", '"', raw)

    # Attempt to close unclosed brackets / braces
    open_braces  = raw.count("{") - raw.count("}")
    open_brackets = raw.count("[") - raw.count("]")
    if open_braces > 0:
        raw += "}" * open_braces
    if open_brackets > 0:
        raw += "]" * open_brackets

    return raw


def _salvage_truncated_array(raw: str) -> Optional[list]:
    """Recover the complete objects from an array that stopped mid-item.

    Walks the text tracking bracket depth and string state, remembering the
    index just past each top-level object that closed cleanly. Everything up
    to the last of those is valid JSON; the partial tail is dropped.
    """
    text = raw.lstrip()
    if not text.startswith("["):
        return None

    depth = 0
    in_string = False
    escaped = False
    last_complete = None

    for i, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if in_string and ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            # depth back to 1 after a '}' means a top-level element closed
            if depth == 1 and ch == "}":
                last_complete = i + 1

    if last_complete is None:
        return None

    try:
        items = json.loads(text[:last_complete] + "]")
    except json.JSONDecodeError:
        return None
    return items if items else None


def parse_llm_json(raw: str, stage: str = "unknown") -> Any:
    """
    Strip fences, parse JSON, and repair on failure.

    Parameters
    ----------
    raw   : raw LLM output string
    stage : label used in error messages (e.g. "research_analysis")

    Returns
    -------
    Parsed Python object (dict or list).

    Raises
    ------
    ValueError  if JSON cannot be parsed even after repair.
    """
    cleaned = strip_fences(raw)

    # First attempt — clean input
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second attempt — repair
    try:
        repaired = _repair(cleaned)
        result = json.loads(repaired)
        logger.warning("[%s] JSON repaired successfully", stage)
        return result
    except json.JSONDecodeError:
        pass

    # Third attempt — salvage a TRUNCATED ARRAY.
    #
    # Appending closing brackets cannot fix output that stopped mid-object,
    # which is exactly what hitting max_tokens produces. Observed live:
    # question generation asked for 15 detailed questions, ran out of room
    # partway through one, and the whole 65-second call failed with a 400 —
    # discarding the fourteen complete questions that came before it.
    salvaged = _salvage_truncated_array(cleaned)
    if salvaged is not None:
        logger.warning(
            "[%s] JSON was truncated; salvaged %d complete item(s)",
            stage, len(salvaged),
        )
        return salvaged

    try:
        json.loads(cleaned)
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Log first 500 chars of the bad output for diagnosis
        logger.error(
            "[%s] JSON parse failed after repair. Raw (first 500): %s",
            stage,
            cleaned[:500],
        )
        raise ValueError(
            f"LLM returned invalid JSON for stage '{stage}'. "
            f"Parse error: {exc}. "
            f"First 200 chars: {cleaned[:200]!r}"
        ) from exc
