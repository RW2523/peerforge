"""
Ownership of a running autonomous debate.

`running_debates` is a dictionary in one process. Two API instances can each
start a loop for the same session — doubling the turns and the spend — and
after a restart a session still marked `running` in the database has nothing
driving it at all.

A lease fixes both. An instance holds a short, renewable claim on a debate;
only the holder drives it. If that instance dies the claim expires by itself
and another can take over, so nothing has to detect the death.

With Redis unavailable this grants every claim, which is correct for a single
instance and no worse than the behaviour it replaces.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from ..config import settings
from .broadcast_bus import INSTANCE_ID

logger = logging.getLogger(__name__)

# Long enough to survive a slow turn, short enough that a crashed instance
# frees its debates promptly. Renewed every iteration, so the practical
# ceiling is one turn's duration.
LEASE_TTL_SECONDS = 180

# How long to wait before trying Redis again after a failed connection.
RECONNECT_INTERVAL_SECONDS = 30


def _key(debate_id: str) -> str:
    return f"peerforge:debate-lease:{debate_id}"


class DebateLease:
    def __init__(self) -> None:
        self._redis = None
        self._retry_after = 0.0

    def _client(self):
        # Retried on a timer rather than disabled for the life of the process:
        # Redis being briefly down at boot used to leave double-run protection
        # off permanently, and nothing said so again after the first warning.
        if self._redis is None and time.monotonic() >= self._retry_after:
            try:
                import redis

                client = redis.from_url(settings.redis_url, decode_responses=True)
                client.ping()
                self._redis = client
            except Exception as exc:
                self._retry_after = time.monotonic() + RECONNECT_INTERVAL_SECONDS
                logger.warning(
                    "Debate leases unavailable (%s); a second instance could "
                    "double-run a session. Retrying in %ss",
                    exc, RECONNECT_INTERVAL_SECONDS
                )
        return self._redis

    def acquire(self, debate_id: str) -> bool:
        """Claim this debate, or report that someone else holds it."""
        client = self._client()
        if client is None:
            return True  # single instance: nobody to conflict with

        try:
            if client.set(_key(debate_id), INSTANCE_ID, nx=True, ex=LEASE_TTL_SECONDS):
                return True
            # Re-entrant for the holder: resume must not be blocked by its own
            # still-valid claim.
            return client.get(_key(debate_id)) == INSTANCE_ID
        except Exception as exc:
            logger.warning("Lease acquire failed for %s: %s", debate_id, exc)
            return True

    def renew(self, debate_id: str) -> bool:
        """Extend the claim. False means someone else has it and we should stop."""
        client = self._client()
        if client is None:
            return True
        try:
            holder = client.get(_key(debate_id))
            if holder is None:
                # Expired rather than taken — a long pause can outlive the TTL.
                # Reclaim it, unless another instance got there first. Treating
                # an absent key as "lost" stopped loops nobody was competing for.
                return bool(client.set(_key(debate_id), INSTANCE_ID,
                                       nx=True, ex=LEASE_TTL_SECONDS))
            if holder != INSTANCE_ID:
                return False
            client.expire(_key(debate_id), LEASE_TTL_SECONDS)
            return True
        except Exception as exc:
            logger.warning("Lease renew failed for %s: %s", debate_id, exc)
            return True

    def release(self, debate_id: str) -> None:
        """Give the claim up so another instance can take over immediately."""
        client = self._client()
        if client is None:
            return
        try:
            if client.get(_key(debate_id)) == INSTANCE_ID:
                client.delete(_key(debate_id))
        except Exception as exc:
            logger.debug("Lease release failed for %s: %s", debate_id, exc)


lease = DebateLease()
