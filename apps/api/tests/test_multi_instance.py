"""Running more than one API process.

WebSocket connections and autonomous-debate loops both lived in process
memory, so a second instance would show divergent transcripts and could
double-drive a session. These cover the mechanisms that fix that.
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import src.services.debate_lease as dl
from src.services.debate_lease import DebateLease
from src.services.broadcast_bus import BroadcastBus, INSTANCE_ID


@pytest.fixture
def debate_id():
    return str(uuid.uuid4())


@pytest.fixture
def as_another_process():
    """Swap the identity the lease writes, standing in for a second instance."""
    original = dl.INSTANCE_ID

    def _switch(name='another-instance'):
        dl.INSTANCE_ID = name
        return DebateLease()

    yield _switch
    dl.INSTANCE_ID = original


# ── Ownership ───────────────────────────────────────────────────────────────

def test_only_one_instance_can_drive_a_debate(debate_id, as_another_process):
    """Two loops on the same session double every turn and its cost."""
    holder = DebateLease()
    assert holder.acquire(debate_id) is True

    stranger = as_another_process()
    assert stranger.acquire(debate_id) is False

    dl.INSTANCE_ID = INSTANCE_ID
    holder.release(debate_id)


def test_the_holder_can_reacquire_its_own_lease(debate_id):
    """Resume must not be blocked by a claim this instance already holds."""
    holder = DebateLease()
    assert holder.acquire(debate_id) is True
    assert holder.acquire(debate_id) is True
    holder.release(debate_id)


def test_renewal_reports_a_lost_claim(debate_id, as_another_process):
    """The loop stops when it no longer owns the session."""
    holder = DebateLease()
    holder.acquire(debate_id)
    assert holder.renew(debate_id) is True

    stranger = as_another_process()
    assert stranger.renew(debate_id) is False

    dl.INSTANCE_ID = INSTANCE_ID
    holder.release(debate_id)


def test_releasing_hands_the_debate_over(debate_id, as_another_process):
    """A clean shutdown frees the session without waiting for expiry."""
    holder = DebateLease()
    holder.acquire(debate_id)
    holder.release(debate_id)

    stranger = as_another_process()
    assert stranger.acquire(debate_id) is True
    stranger.release(debate_id)


def test_a_stranger_cannot_release_someone_elses_lease(debate_id, as_another_process):
    holder = DebateLease()
    holder.acquire(debate_id)

    stranger = as_another_process()
    stranger.release(debate_id)

    dl.INSTANCE_ID = INSTANCE_ID
    # Still held, so the real owner keeps driving.
    assert holder.renew(debate_id) is True
    holder.release(debate_id)


# ── Fan-out ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast_falls_back_to_local_when_redis_is_absent():
    """A single instance must keep working with no Redis at all."""
    bus = BroadcastBus()
    from src.config import settings

    original = settings.redis_url
    settings.redis_url = 'redis://127.0.0.1:59999/0'  # nothing listening
    try:
        await bus.start(lambda *_: None)
        assert bus.degraded is True
        # Publishing is a no-op rather than an error.
        await bus.publish('some-debate', {'type': 'agent_message'})
    finally:
        settings.redis_url = original
        await bus.stop()


def test_each_process_has_a_distinct_identity():
    """Instances must be distinguishable or they re-deliver their own messages."""
    assert INSTANCE_ID
    assert '-' in INSTANCE_ID
