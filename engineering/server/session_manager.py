"""
session_manager.py — In-memory session management for Aego Cyber Cafe.

UUID-based sessions with TTL auto-purge. Thread-safe via asyncio lock.
No persistent customer data — everything is ephemeral by design.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from models import SessionState

logger = logging.getLogger("aego.sessions")


class Session:
    """A single customer session."""

    __slots__ = (
        "session_id", "state", "service_type", "data",
        "created_at", "expires_at", "last_accessed",
    )

    def __init__(
        self,
        session_id: str,
        service_type: str,
        ttl_seconds: int = 1800,  # 30 minutes
    ):
        self.session_id = session_id
        self.state = SessionState.COLLECTING
        self.service_type = service_type
        self.data: dict[str, Any] = {}
        self.created_at = time.time()
        self.expires_at = self.created_at + ttl_seconds
        self.last_accessed = self.created_at

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Update last access time."""
        self.last_accessed = time.time()

    def set(self, key: str, value: Any) -> None:
        """Store data in session."""
        self.data[key] = value
        self.touch()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve data from session."""
        self.touch()
        return self.data.get(key, default)


class SessionManager:
    """
    Manages in-memory sessions with automatic TTL-based cleanup.

    Thread-safe: all mutations go through an asyncio.Lock.
    Purge runs on every create/get operation if enough time has passed.
    """

    def __init__(self, ttl_seconds: int = 1800, purge_interval: int = 60):
        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()
        self._ttl = ttl_seconds
        self._purge_interval = purge_interval
        self._last_purge = time.time()

    async def create(
        self,
        service_type: str,
        session_id: Optional[str] = None,
    ) -> Session:
        """Create a new session. Returns the session object."""
        sid = session_id or str(uuid.uuid4())
        session = Session(sid, service_type, self._ttl)

        async with self._lock:
            self._sessions[sid] = session
            logger.info(f"Session created: {sid} (service={service_type})")
            await self._maybe_purge()

        return session

    async def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID. Returns None if not found or expired."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if session.is_expired:
                del self._sessions[session_id]
                logger.info(f"Session expired: {session_id}")
                return None
            session.touch()
            return session

    async def update_state(
        self,
        session_id: str,
        state: SessionState,
    ) -> bool:
        """Update session state."""
        async with self._lock:
            session = self._sessions.get(session_id)
            if session is None or session.is_expired:
                return False
            session.state = state
            session.touch()
            return True

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Session deleted: {session_id}")
                return True
            return False

    async def count_active(self) -> int:
        """Count non-expired sessions."""
        async with self._lock:
            now = time.time()
            return sum(
                1 for s in self._sessions.values()
                if s.expires_at > now
            )

    async def cleanup(self) -> int:
        """Remove all expired sessions. Returns count removed."""
        async with self._lock:
            return await self._purge_locked()

    async def _maybe_purge(self) -> None:
        """Purge expired sessions if enough time has passed."""
        now = time.time()
        if now - self._last_purge > self._purge_interval:
            await self._purge_locked()

    async def _purge_locked(self) -> int:
        """Purge expired sessions. Must hold lock."""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if s.expires_at <= now
        ]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.info(f"Purged {len(expired)} expired sessions")
        self._last_purge = now
        return len(expired)
