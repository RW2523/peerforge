"""
Cross-instance message fan-out.

WebSocket connections live in the process that accepted them. A message
broadcast on instance A never reaches a client attached to instance B, so with
more than one API process two people in the same review session see different
transcripts.

This publishes every broadcast to Redis and delivers what it receives to local
sockets, so any instance can originate a message and all of them show it.

Degrades to local-only when Redis is unavailable: a single instance keeps
working exactly as before rather than failing to broadcast at all.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)

CHANNEL = "peerforge:ws:broadcast"

# Reconnection backoff bounds. Starts fast so a restarting Redis is picked up
# almost immediately, and caps so a long outage does not spin.
INITIAL_RECONNECT_SECONDS = 1
MAX_RECONNECT_SECONDS = 30

# Identifies this process so it does not re-deliver its own messages: the
# originating instance has already sent them to its local sockets.
INSTANCE_ID = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"


class BroadcastBus:
    def __init__(self) -> None:
        self._redis = None
        self._pubsub = None
        self._task: Optional[asyncio.Task] = None
        self._deliver: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
        self._degraded = False

    @property
    def degraded(self) -> bool:
        """True when running local-only because Redis could not be reached."""
        return self._degraded

    async def start(self, deliver: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        """Begin listening. `deliver(debate_id, message)` sends to local sockets."""
        self._deliver = deliver
        # Try once here so the startup log reports the truth, then hand off to
        # the listener, which owns reconnection from then on. Redis down at
        # boot is a delay rather than a permanent downgrade to local-only.
        try:
            await self._connect()
        except Exception as exc:
            self._degraded = True
            logger.warning(
                "Broadcast bus unavailable, local-only for now: %s", exc
            )
        self._task = asyncio.create_task(self._listen())

    async def _connect(self) -> None:
        """Open the connection and subscribe. Raises if Redis is unreachable."""
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await self._redis.ping()
        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(CHANNEL)
        self._degraded = False
        logger.info("Broadcast bus connected (instance %s)", INSTANCE_ID)

    async def _drop(self) -> None:
        """Discard a broken connection so the next attempt starts clean."""
        for closer in (self._pubsub, self._redis):
            if closer is None:
                continue
            try:
                # aclose() on redis>=5; close() on older clients.
                aclose = getattr(closer, "aclose", None)
                await (aclose() if aclose else closer.close())
            except Exception:
                pass
        self._pubsub = None
        self._redis = None

    async def publish(self, debate_id: str, message: Dict[str, Any]) -> None:
        """Send to every other instance. Local delivery is the caller's job."""
        if self._redis is None:
            return
        try:
            await self._redis.publish(
                CHANNEL,
                json.dumps({"origin": INSTANCE_ID, "debate_id": debate_id, "message": message}),
            )
        except Exception as exc:
            # A failed fan-out must not fail the turn that produced it.
            logger.warning("Broadcast publish failed for %s: %s", debate_id, exc)

    async def _listen(self) -> None:
        """
        Receive relayed messages, reconnecting for as long as the process runs.

        Returning on the first error left the instance able to publish but
        never to receive: it broadcast its own turns outward while its clients
        silently stopped seeing everyone else's.
        """
        backoff = INITIAL_RECONNECT_SECONDS
        while True:
            try:
                if self._pubsub is None:
                    await self._connect()

                async for raw in self._pubsub.listen():
                    backoff = INITIAL_RECONNECT_SECONDS  # a live stream resets it
                    if raw.get("type") != "message":
                        continue
                    try:
                        payload = json.loads(raw["data"])
                    except Exception:
                        continue
                    if payload.get("origin") == INSTANCE_ID:
                        continue  # already delivered locally by the originator
                    if self._deliver:
                        try:
                            await self._deliver(payload["debate_id"], payload["message"])
                        except Exception as exc:
                            logger.warning(
                                "Local delivery of a relayed message failed: %s", exc
                            )
                # listen() ending without an error still means the stream is gone.
                raise ConnectionError("broadcast subscription closed")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._degraded = True
                await self._drop()
                logger.warning(
                    "Broadcast bus local-only (%s); retrying in %ss", exc, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, MAX_RECONNECT_SECONDS)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        await self._drop()


bus = BroadcastBus()
