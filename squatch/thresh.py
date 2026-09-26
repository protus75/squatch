"""Dormant provider threshold state and decisions (plan section 6 via section 20).

The dispatcher does not import this module yet. It owns the directly testable
state that the later admission boundary will compose: flat-subscription quota
cooldowns, active-call concurrency, and per-provider circuit breakers.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from squatch.config import Config
from squatch.providers import FailureClass, FailureFact
from squatch.seams import Clock

DecisionKind = Literal["allow", "hold"]
HoldReason = Literal["quota_cooldown", "provider_concurrency", "circuit_open"]

# Only provider-health failures feed the breaker. Other classified failures
# have separate policies; unknown CLI exits share the outage bound.
BREAKER_FAILURES: frozenset[FailureClass] = frozenset({"outage", "unclassified"})


@dataclass(frozen=True)
class ProviderThreshold:
    flat_subscription: bool
    concurrency: int
    quota_window_minutes: int


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    provider: str
    reason: HoldReason | None = None
    retry_at: datetime | None = None

    @property
    def allowed(self) -> bool:
        return self.kind == "allow"


@dataclass(frozen=True)
class BreakerState:
    consecutive_failures: int = 0
    last_failure_class: FailureClass | None = None
    open_until: datetime | None = None


class ThresholdRuntime:
    """Own provider quota, concurrency, and breaker state without dispatch wiring."""

    def __init__(self, config: Config, *, clock: Clock):
        self._clock = clock
        self._providers = {provider.name: provider for provider in config.providers}
        self._active = {provider.name: 0 for provider in config.providers}
        self._quota_until: dict[str, datetime | None] = {
            provider.name: None for provider in config.providers}
        self._breakers = {provider.name: BreakerState() for provider in config.providers}
        self._breaker_k = config.circuit_breaker.k
        self._breaker_cooldown = timedelta(
            minutes=config.circuit_breaker.cooldown_minutes)

    def threshold(self, provider: str) -> ProviderThreshold:
        configured = self._provider(provider)
        return ProviderThreshold(
            flat_subscription=configured.kind == "cli",
            concurrency=configured.limits.concurrency,
            quota_window_minutes=configured.limits.quota_window_minutes,
        )

    def decide(self, provider: str) -> Decision:
        """Return the pre-call verdict without reserving a provider slot."""
        self._provider(provider)
        breaker = self._refresh_breaker(provider)
        if breaker.open_until is not None:
            return Decision("hold", provider, "circuit_open", breaker.open_until)
        quota_until = self._refresh_quota(provider)
        if quota_until is not None:
            return Decision("hold", provider, "quota_cooldown", quota_until)
        if self._active[provider] >= self.threshold(provider).concurrency:
            return Decision("hold", provider, "provider_concurrency")
        return Decision("allow", provider)

    def acquire(self, provider: str) -> Decision:
        """Reserve one provider slot when the current verdict allows it."""
        decision = self.decide(provider)
        if decision.allowed:
            self._active[provider] += 1
        return decision

    def release(self, provider: str) -> None:
        self._provider(provider)
        if self._active[provider] == 0:
            raise ValueError(f"provider `{provider}` has no active call to release")
        self._active[provider] -= 1

    def record_failure(self, failure: FailureFact) -> BreakerState:
        """Fold one completed CLI failure into the provider's threshold state."""
        configured = self._provider(failure.provider)
        state = self._refresh_breaker(failure.provider)
        consecutive = state.consecutive_failures
        open_until = state.open_until
        if failure.failure_class == "quota_exhausted":
            self._quota_until[failure.provider] = self._clock() + timedelta(
                minutes=configured.limits.quota_window_minutes)
        elif failure.failure_class in BREAKER_FAILURES:
            consecutive += 1
            if consecutive >= self._breaker_k:
                open_until = self._clock() + self._breaker_cooldown
        state = BreakerState(consecutive, failure.failure_class, open_until)
        self._breakers[failure.provider] = state
        return state

    def record_success(self, provider: str) -> BreakerState:
        self._provider(provider)
        state = BreakerState()
        self._breakers[provider] = state
        return state

    def breaker(self, provider: str) -> BreakerState:
        self._provider(provider)
        return self._refresh_breaker(provider)

    def quota_until(self, provider: str) -> datetime | None:
        self._provider(provider)
        return self._refresh_quota(provider)

    def active(self, provider: str) -> int:
        self._provider(provider)
        return self._active[provider]

    def _provider(self, provider: str):
        try:
            return self._providers[provider]
        except KeyError:
            raise ValueError(f"unknown provider `{provider}`") from None

    def _refresh_breaker(self, provider: str) -> BreakerState:
        state = self._breakers[provider]
        if state.open_until is not None and self._clock() >= state.open_until:
            state = BreakerState()
            self._breakers[provider] = state
        return state

    def _refresh_quota(self, provider: str) -> datetime | None:
        deadline = self._quota_until[provider]
        if deadline is not None and self._clock() >= deadline:
            self._quota_until[provider] = None
            return None
        return deadline
