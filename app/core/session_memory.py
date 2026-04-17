"""Conversation memory with file-backed persistence.

Each session is stored as data/sessions/{session_id}.json.
In-memory cache avoids disk reads on every turn.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

SESSIONS_DIR = Path(__file__).parent.parent.parent / "data" / "sessions"
MAX_HISTORY_TURNS = 3  # pairs (user + assistant) — giữ 3 lượt gần nhất để tiết kiệm tokens


def _session_path(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    return SESSIONS_DIR / f"{safe}.json"


def _load_from_disk(session_id: str) -> list[dict]:
    path = _session_path(session_id)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("history", [])
        except Exception:
            return []
    return []


def _save_to_disk(session_id: str, history: list[dict]) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _session_path(session_id)
    payload = {"session_id": session_id, "updated_at": time.time(), "history": history}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class SessionMemory:
    """Thread-safe (GIL) in-process session store with file persistence."""

    def __init__(self) -> None:
        self._cache: dict[str, list[dict]] = {}

    def get_history(self, session_id: str) -> list[dict]:
        if session_id not in self._cache:
            self._cache[session_id] = _load_from_disk(session_id)
        return self._cache[session_id]

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self.get_history(session_id)
        history.append({"role": role, "content": content})
        # Trim to keep within token budget
        max_msgs = MAX_HISTORY_TURNS * 2
        if len(history) > max_msgs:
            self._cache[session_id] = history[-max_msgs:]
        _save_to_disk(session_id, self._cache[session_id])

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        """Convenience: add a full user+assistant turn at once."""
        history = self.get_history(session_id)
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        max_msgs = MAX_HISTORY_TURNS * 2
        if len(history) > max_msgs:
            self._cache[session_id] = history[-max_msgs:]
        _save_to_disk(session_id, self._cache[session_id])

    def clear(self, session_id: str) -> None:
        self._cache[session_id] = []
        path = _session_path(session_id)
        if path.exists():
            path.unlink()

    def list_sessions(self) -> list[str]:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        return [p.stem for p in SESSIONS_DIR.glob("*.json")]


# Singleton used across the app
memory = SessionMemory()
