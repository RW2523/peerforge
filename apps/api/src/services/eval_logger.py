"""
Debate Evaluation Logger
========================
Writes a single JSON file per debate to eval_logs/{debate_id}.json.

The file captures everything end-to-end so the conversation, all LLM
request/response pairs (with model names and token counts), preflight prep
packs, and the final summary can be inspected offline.

File structure
--------------
{
  "debate_id":   "...",
  "created_at":  "...",
  "updated_at":  "...",

  "setup": {
    "title":              "...",
    "problem_statement":  "...",
    "agenda":             [...],
    "desired_outcomes":   [...],
    "participants":       [{"name": ..., "role": ..., "model_id": ...}],
    "materials":          [{"title": ..., "kind": ...}],
    "policy_config":      {...}
  },

  "lifecycle": [
    {"event": "created|started|ended", "at": "..."}
  ],

  "llm_calls": [
    {
      "call_id":       "uuid",
      "at":            "ISO timestamp",
      "stage":         "turn | preflight | summary | reasoning | ...",
      "debate_id":     "...",
      "participant":   "agent name or null",
      "model":         "openai/gpt-4o-mini",
      "request": {
        "messages":    [...],
        "temperature": 0.7,
        "max_tokens":  null
      },
      "response": {
        "content":     "...",
        "usage": {
          "prompt_tokens":     ...,
          "completion_tokens": ...,
          "total_tokens":      ...
        }
      },
      "latency_ms":    123,
      "error":         null
    }
  ],

  "turns": [
    {
      "turn_number": 1,
      "at":          "ISO timestamp",
      "participant": "...",
      "agent_id":    "...",
      "model":       "...",
      "content":     "..."
    }
  ],

  "preflight": {
    "participants": [
      {
        "participant_id": "...",
        "agent_name":     "...",
        "model":          "...",
        "prep_pack":      "..."
      }
    ]
  },

  "summary": {
    "at":           "ISO timestamp",
    "model":        "...",
    "request_prompt": "...",
    "response": {
      "summary":      "...",
      "minutes":      "...",
      "action_items": [...]
    },
    "usage": {...}
  },

  "metadata": {
    "total_llm_calls":        0,
    "total_prompt_tokens":    0,
    "total_completion_tokens":0,
    "total_turns":            0,
    "stages_seen":            []
  }
}
"""

import json
import os
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Where the log files live (relative to this file → apps/api/eval_logs/)
# ---------------------------------------------------------------------------
_EVAL_LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "eval_logs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Keys that must never appear in eval log files
_SENSITIVE_KEYS = frozenset({
    "openrouter_key", "openrouter_api_key", "api_key", "apikey",
    "secret", "password", "token", "authorization",
})


def _scrub(obj, depth: int = 0):
    """Recursively remove sensitive keys from dicts/lists."""
    if depth > 20:
        return obj
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if k.lower() in _SENSITIVE_KEYS else _scrub(v, depth + 1)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub(item, depth + 1) for item in obj]
    return obj


# One lock per debate_id so concurrent threads don't corrupt the same file
_locks: Dict[str, threading.Lock] = {}
_lock_registry = threading.Lock()


def _get_lock(debate_id: str) -> threading.Lock:
    with _lock_registry:
        if debate_id not in _locks:
            _locks[debate_id] = threading.Lock()
        return _locks[debate_id]


# ---------------------------------------------------------------------------
# DebateEvalLogger
# ---------------------------------------------------------------------------

class DebateEvalLogger:
    """
    Thread-safe, append-style JSON logger for a single debate.

    Usage
    -----
    logger = DebateEvalLogger(debate_id)
    logger.log_setup(...)
    logger.log_llm_call(...)
    logger.log_turn(...)
    logger.log_preflight_participant(...)
    logger.log_summary(...)
    logger.log_lifecycle(...)
    """

    def __init__(self, debate_id: str):
        self.debate_id = debate_id
        self._path = _EVAL_LOGS_DIR / f"{debate_id}.json"
        self._lock = _get_lock(debate_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_setup(
        self,
        title: str,
        problem_statement: str,
        participants: List[Dict],
        materials: Optional[List[Dict]] = None,
        agenda: Optional[List[str]] = None,
        desired_outcomes: Optional[List[str]] = None,
        policy_config: Optional[Dict] = None,
    ) -> None:
        self._update(lambda doc: self._set_setup(
            doc, title, problem_statement, participants,
            materials, agenda, desired_outcomes, policy_config
        ))

    def log_lifecycle(self, event: str) -> None:
        """Record debate created / started / ended."""
        self._update(lambda doc: doc["lifecycle"].append(
            {"event": event, "at": _now()}
        ))

    def log_llm_call(
        self,
        stage: str,
        model: str,
        messages: List[Dict],
        response_content: Optional[str],
        usage: Optional[Dict],
        latency_ms: int,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        participant: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        entry = {
            "call_id":    str(uuid.uuid4()),
            "at":         _now(),
            "stage":      stage,
            "debate_id":  self.debate_id,
            "participant": participant,
            "model":      model,
            "request": {
                "messages":    _scrub(messages),
                "temperature": temperature,
                "max_tokens":  max_tokens,
            },
            "response": {
                "content": response_content,
                "usage":   usage or {},
            },
            "latency_ms": latency_ms,
            "error":      error,
        }
        self._update(lambda doc: self._append_llm_call(doc, entry))

    def log_turn(
        self,
        turn_number: int,
        participant: str,
        agent_id: Optional[str],
        model: str,
        content: str,
    ) -> None:
        entry = {
            "turn_number": turn_number,
            "at":          _now(),
            "participant": participant,
            "agent_id":    agent_id,
            "model":       model,
            "content":     content,
        }
        self._update(lambda doc: (
            doc["turns"].append(entry),
            doc["metadata"].__setitem__(
                "total_turns", doc["metadata"]["total_turns"] + 1
            ),
        ))

    def log_preflight_participant(
        self,
        participant_id: str,
        agent_name: str,
        model: str,
        prep_pack: str,
    ) -> None:
        entry = {
            "participant_id": participant_id,
            "agent_name":     agent_name,
            "model":          model,
            "prep_pack":      prep_pack,
        }
        self._update(lambda doc: doc["preflight"]["participants"].append(entry))

    def log_summary(
        self,
        model: str,
        request_prompt: str,
        summary: str,
        minutes: str,
        action_items: List,
        usage: Optional[Dict] = None,
    ) -> None:
        self._update(lambda doc: doc.__setitem__("summary", {
            "at":             _now(),
            "model":          model,
            "request_prompt": request_prompt,
            "response": {
                "summary":      summary,
                "minutes":      minutes,
                "action_items": action_items,
            },
            "usage": usage or {},
        }))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _empty_doc(self) -> Dict:
        return {
            "debate_id":  self.debate_id,
            "created_at": _now(),
            "updated_at": _now(),
            "setup":      {},
            "lifecycle":  [],
            "llm_calls":  [],
            "turns":      [],
            "preflight":  {"participants": []},
            "summary":    None,
            "metadata": {
                "total_llm_calls":         0,
                "total_prompt_tokens":     0,
                "total_completion_tokens": 0,
                "total_turns":             0,
                "stages_seen":             [],
            },
        }

    def _read(self) -> Dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return self._empty_doc()

    def _write(self, doc: Dict) -> None:
        doc["updated_at"] = _now()
        _EVAL_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, default=str, ensure_ascii=False)
        tmp.replace(self._path)  # atomic on POSIX

    def _update(self, mutate_fn) -> None:
        """Read → mutate → write under per-debate lock. Never raises."""
        try:
            with self._lock:
                doc = self._read()
                mutate_fn(doc)
                self._write(doc)
        except Exception as exc:  # noqa: BLE001
            print(f"[eval_logger] WARNING: could not update log for {self.debate_id}: {exc}")

    @staticmethod
    def _set_setup(doc, title, problem_statement, participants,
                   materials, agenda, desired_outcomes, policy_config):
        doc["setup"] = {
            "title":             title,
            "problem_statement": problem_statement,
            "agenda":            agenda or [],
            "desired_outcomes":  desired_outcomes or [],
            "participants":      _scrub(participants or []),
            "materials":         materials or [],
            "policy_config":     _scrub(policy_config or {}),
        }

    @staticmethod
    def _append_llm_call(doc, entry):
        doc["llm_calls"].append(entry)
        m = doc["metadata"]
        m["total_llm_calls"] += 1
        usage = entry["response"].get("usage") or {}
        m["total_prompt_tokens"]     += usage.get("prompt_tokens", 0)
        m["total_completion_tokens"] += usage.get("completion_tokens", 0)
        stage = entry["stage"]
        if stage not in m["stages_seen"]:
            m["stages_seen"].append(stage)


# ---------------------------------------------------------------------------
# Module-level convenience: get-or-create a logger for a debate_id
# ---------------------------------------------------------------------------
_loggers: Dict[str, "DebateEvalLogger"] = {}
_logger_lock = threading.Lock()


def get_logger(debate_id: str) -> DebateEvalLogger:
    """Return (and cache) a DebateEvalLogger for the given debate."""
    with _logger_lock:
        if debate_id not in _loggers:
            _loggers[debate_id] = DebateEvalLogger(debate_id)
        return _loggers[debate_id]
