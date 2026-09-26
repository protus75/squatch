"""Direct proofs for the dormant provider threshold runtime."""

from datetime import datetime, timedelta, timezone

import pytest

from squatch.config import parse
from squatch.providers import FailureFact
from squatch.thresh import BreakerState, ThresholdRuntime


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 26, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, **parts):
        self.now += timedelta(**parts)


def runtime(*, concurrency=2, quota_window_minutes=60, k=3, cooldown_minutes=10):
    config = parse({
        "schema_version": 1,
        "state_dir": ".state",
        "providers": [{
            "name": "agent-cli",
            "kind": "cli",
            "models_by_tier": {tier: f"model-{tier}"
                               for tier in ("low", "medium", "high", "max")},
            "limits": {
                "concurrency": concurrency,
                "est_cost_per_call_usd": 1.0,
                "quota_window_minutes": quota_window_minutes,
            },
        }],
        "routing": [],
        "circuit_breaker": {"k": k, "cooldown_minutes": cooldown_minutes},
    }, source="test")
    clock = Clock()
    return ThresholdRuntime(config, clock=clock), clock


def test_flat_subscription_quota_holds_and_allows_at_the_exact_window_boundary():
    thresholds, clock = runtime(quota_window_minutes=45, k=2)

    configured = thresholds.threshold("agent-cli")
    assert configured.flat_subscription is True
    assert configured.quota_window_minutes == 45
    state = thresholds.record_failure(FailureFact("agent-cli", "quota_exhausted"))
    deadline = clock.now + timedelta(minutes=45)
    assert state == BreakerState(0, "quota_exhausted")
    assert thresholds.quota_until("agent-cli") == deadline
    held = thresholds.decide("agent-cli")
    assert (held.kind, held.provider, held.reason, held.retry_at) == (
        "hold", "agent-cli", "quota_cooldown", deadline)

    clock.advance(minutes=45, microseconds=-1)
    assert thresholds.decide("agent-cli").reason == "quota_cooldown"
    clock.advance(microseconds=1)
    assert thresholds.decide("agent-cli").kind == "allow"
    assert thresholds.quota_until("agent-cli") is None
    assert thresholds.breaker("agent-cli").consecutive_failures == 0


def test_provider_concurrency_allows_and_holds_at_the_exact_cap():
    thresholds, _ = runtime(concurrency=2)

    assert thresholds.acquire("agent-cli").kind == "allow"
    assert thresholds.acquire("agent-cli").kind == "allow"
    held = thresholds.acquire("agent-cli")
    assert (held.kind, held.reason, held.retry_at) == (
        "hold", "provider_concurrency", None)
    assert thresholds.active("agent-cli") == 2

    thresholds.release("agent-cli")
    assert thresholds.acquire("agent-cli").kind == "allow"


def test_release_without_an_active_call_is_refused():
    thresholds, _ = runtime()
    with pytest.raises(ValueError, match="no active call"):
        thresholds.release("agent-cli")


@pytest.mark.parametrize("failure_class", ["auth_error", "rate_limited", "model_error"])
def test_non_breaker_classifications_do_not_change_breaker_count(failure_class):
    thresholds, _ = runtime(k=2)

    state = thresholds.record_failure(FailureFact("agent-cli", failure_class))
    assert state == BreakerState(0, failure_class)
    assert thresholds.decide("agent-cli").kind == "allow"


def test_classified_outage_and_unclassified_failure_feed_the_same_breaker():
    thresholds, _ = runtime(k=3)

    classified = thresholds.record_failure(FailureFact("agent-cli", "outage"))
    assert classified == BreakerState(1, "outage")
    unclassified = thresholds.record_failure(FailureFact("agent-cli", "unclassified"))
    assert unclassified == BreakerState(2, "unclassified")
    assert thresholds.decide("agent-cli").kind == "allow"


def test_breaker_trips_and_cools_down_at_the_exact_configured_boundaries():
    thresholds, clock = runtime(k=3, cooldown_minutes=10)

    for expected in (1, 2):
        state = thresholds.record_failure(FailureFact("agent-cli", "unclassified"))
        assert state.consecutive_failures == expected
        assert state.open_until is None
        assert thresholds.decide("agent-cli").kind == "allow"

    state = thresholds.record_failure(FailureFact("agent-cli", "outage"))
    deadline = clock.now + timedelta(minutes=10)
    assert state == BreakerState(3, "outage", deadline)
    assert thresholds.decide("agent-cli").kind == "hold"
    assert thresholds.decide("agent-cli").retry_at == deadline

    clock.advance(minutes=10, microseconds=-1)
    assert thresholds.decide("agent-cli").kind == "hold"
    clock.advance(microseconds=1)
    assert thresholds.decide("agent-cli").kind == "allow"
    assert thresholds.breaker("agent-cli") == BreakerState()


def test_success_resets_the_consecutive_failure_count():
    thresholds, _ = runtime(k=2)
    thresholds.record_failure(FailureFact("agent-cli", "unclassified"))
    assert thresholds.record_success("agent-cli") == BreakerState()
    assert thresholds.record_failure(
        FailureFact("agent-cli", "unclassified")).open_until is None


def test_unknown_provider_is_refused_fail_closed():
    thresholds, _ = runtime()
    with pytest.raises(ValueError, match="unknown provider"):
        thresholds.decide("missing")
