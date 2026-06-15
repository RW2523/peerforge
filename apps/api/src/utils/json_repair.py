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
from typing import Any

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
