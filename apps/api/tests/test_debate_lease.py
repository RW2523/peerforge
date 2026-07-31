"""The lease that stops two instances driving one session — and stops neither.

A pause longer than LEASE_TTL_SECONDS used to let the claim lapse silently.
The next renew then read the absent key as "somebody took it", the loop broke,
and because the debate was still in `running_debates` the first resume started
nothing. The session sat marked 'running' with no driver behind it.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.services import debate_lease
from src.services.debate_lease import DebateLease, LEASE_TTL_SECONDS
from src.services.broadcast_bus import INSTANCE_ID


class FakeRedis:
    """Just enough Redis to exercise the lease, with a manual clock."""

    def __init__(self):
        self.store = {}      # key -> (value, expires_at)
        self.now = 0.0

    def _live(self, key):
        entry = self.store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and self.now >= expires_at:
            del self.store[key]
            return None
        return value

    def get(self, key):
        return self._live(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and self._live(key) is not None:
            return None
        self.store[key] = (value, None if ex is None else self.now + ex)
        return True

    def expire(self, key, seconds):
        if self._live(key) is None:
            return False
        value, _ = self.store[key]
        self.store[key] = (value, self.now + seconds)
        return True

    def delete(self, key):
        self.store.pop(key, None)

    def ping(self):
        return True


@pytest.fixture
def lease_with_redis():
    lease = DebateLease()
    fake = FakeRedis()
    lease._redis = fake
    lease._retry_after = 0.0
    return lease, fake


def test_acquire_is_exclusive(lease_with_redis):
    """A second instance cannot claim a debate this one holds."""
    lease, fake = lease_with_redis
    assert lease.acquire('d1') is True

    other = DebateLease()
    other._redis = fake
    # Simulate the other process by rewriting the recorded holder.
    fake.store['peerforge:debate-lease:d1'] = ('some-other-instance', None)
    assert other.acquire('d1') is False


def test_acquire_is_reentrant_for_the_holder(lease_with_redis):
    """Resuming must not be blocked by this instance's own live claim."""
    lease, _ = lease_with_redis
    assert lease.acquire('d1') is True
    assert lease.acquire('d1') is True


def test_renew_reclaims_a_lapsed_lease(lease_with_redis):
    """
    A pause outlasting the TTL is recoverable, not fatal.

    Reading an absent key as "lost" stopped loops that had no competitor,
    and the session was left marked running with nothing driving it.
    """
    lease, fake = lease_with_redis
    assert lease.acquire('d1') is True

    fake.now += LEASE_TTL_SECONDS + 1  # a long pause
    assert fake.get('peerforge:debate-lease:d1') is None, 'precondition: lease expired'

    assert lease.renew('d1') is True, 'loop should reclaim an uncontested lease'
    assert fake.get('peerforge:debate-lease:d1') == INSTANCE_ID


def test_renew_yields_when_another_instance_took_over(lease_with_redis):
    """If someone else genuinely holds it, this loop must stop."""
    lease, fake = lease_with_redis
    lease.acquire('d1')
    fake.store['peerforge:debate-lease:d1'] = ('some-other-instance', None)
    assert lease.renew('d1') is False


def test_renew_extends_the_deadline(lease_with_redis):
    """Renewing pushes expiry out so a slow turn does not lose the claim."""
    lease, fake = lease_with_redis
    lease.acquire('d1')

    fake.now += LEASE_TTL_SECONDS - 1
    assert lease.renew('d1') is True
    fake.now += LEASE_TTL_SECONDS - 1
    assert fake.get('peerforge:debate-lease:d1') == INSTANCE_ID, 'renew did not extend'


def test_release_frees_it_for_another_instance(lease_with_redis):
    lease, fake = lease_with_redis
    lease.acquire('d1')
    lease.release('d1')
    assert fake.get('peerforge:debate-lease:d1') is None


def test_release_does_not_steal_someone_elses_claim(lease_with_redis):
    lease, fake = lease_with_redis
    fake.store['peerforge:debate-lease:d1'] = ('some-other-instance', None)
    lease.release('d1')
    assert fake.get('peerforge:debate-lease:d1') == 'some-other-instance'


def test_without_redis_every_claim_is_granted():
    """A single instance must keep working when Redis is absent."""
    lease = DebateLease()
    lease._redis = None
    lease._retry_after = float('inf')  # pretend the connection already failed
    assert lease.acquire('d1') is True
    assert lease.renew('d1') is True
    lease.release('d1')  # must not raise


def test_redis_is_retried_rather_than_disabled_forever(monkeypatch):
    """
    One failed connection must not turn double-run protection off for good.

    The flag used to be sticky, so Redis being down for a moment at boot left
    the process unprotected for its whole life and said so only once.
    """
    lease = DebateLease()
    attempts = {'n': 0}

    class Boom:
        @staticmethod
        def from_url(*a, **k):
            attempts['n'] += 1
            raise ConnectionError('redis down')

    monkeypatch.setitem(sys.modules, 'redis', Boom)

    # Advance a fake clock rather than writing to the object's own state -
    # poking the field under test would pass against a permanently-off flag too.
    clock = {'t': 1000.0}
    monkeypatch.setattr(debate_lease.time, 'monotonic', lambda: clock['t'])

    assert lease._client() is None
    assert attempts['n'] == 1

    # Inside the retry window: no second attempt.
    clock['t'] += debate_lease.RECONNECT_INTERVAL_SECONDS / 2
    assert lease._client() is None
    assert attempts['n'] == 1

    # Past it: tries again rather than staying off permanently.
    clock['t'] += debate_lease.RECONNECT_INTERVAL_SECONDS
    assert lease._client() is None
    assert attempts['n'] == 2, 'connection was disabled for the process lifetime'
