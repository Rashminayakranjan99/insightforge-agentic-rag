# src/memory/short_term.py
"""Short-term conversation memory — per-session message history."""

from typing import List, Dict
from collections import defaultdict


class ShortTermMemory:
    """In-memory conversation history per session. Thread-safe for Flask."""

    def __init__(self, max_messages: int = 50):
        self._store: Dict[str, List[dict]] = defaultdict(list)
        self._max = max_messages

    def add(self, session_id: str, role: str, content: str):
        """Add a message to session history."""
        self._store[session_id].append({"role": role, "content": content})
        # Trim to keep last N messages
        if len(self._store[session_id]) > self._max:
            self._store[session_id] = self._store[session_id][-self._max:]

    def get(self, session_id: str) -> List[dict]:
        """Get full conversation history for a session."""
        return self._store[session_id].copy()

    def clear(self, session_id: str):
        """Clear session history."""
        self._store[session_id] = []

    def get_last_n(self, session_id: str, n: int = 6) -> List[dict]:
        """Get last N messages for context window."""
        return self._store[session_id][-n:]
