"""watchdog.py: dormant normalized event construction only."""

from pathlib import Path

import pytest

from squatch.watchdog import EventCollector, WatchdogDetector, WatchdogEvent


def test_collector_preserves_normalized_events_in_arrival_order():
    collector = EventCollector()
    first = WatchdogEvent("claude", "tool_call", input_tokens=10, output_tokens=2)
    second = WatchdogEvent("codex", "start", usd=1.0)
    collector(first)
    collector(second)
    assert collector.events == [first, second]


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def detector(clock, *, expected=10, stuck=20, scope_fence=("squatch",)):
    return WatchdogDetector(
        clock=clock, expected=expected, stuck=stuck, scope_fence=scope_fence,
        cost_basis_usd=2.0, provider_reports_metered_usage={"claude": True, "codex": False},
        flat_usd_estimates={"codex": 1.0})


def test_detector_counts_usd_strictly_and_resets_only_component_bounded_mutations():
    clock = Clock()
    subject = detector(clock, scope_fence=("squatch", "tests/unit"))
    clock.now = 15
    subject.observe_event(WatchdogEvent("claude", "tool_call", 500, 20, 6.0))
    assert subject.assess(ticket="t", run_seq=1).decision is None
    subject.observe_event(WatchdogEvent("claude", "tool_call", 1, 1, 0.01))
    assert subject.assess(ticket="t", run_seq=1).decision == "soft_trip"
    assert (subject.input_tokens, subject.output_tokens) == (501, 21)
    assert not subject.observe_mutation("squatchery/result.py")
    assert not subject.observe_mutation("tests/unitish/result.py")
    assert not subject.observe_mutation("squatch/../README.md")
    assert subject.assess(ticket="t", run_seq=1).spend_usd == 6.01
    assert subject.observe_mutation("squatch/result.py")
    assert subject.assess(ticket="t", run_seq=1).spend_usd == 0.0


def test_detector_uses_one_flat_estimate_per_unmetered_invocation_without_double_charge():
    clock = Clock()
    tokens_only = detector(clock)
    tokens_only.observe_event(WatchdogEvent("codex", "start", input_tokens=100))
    tokens_only.observe_event(WatchdogEvent(
        "codex", "tool_call", input_tokens=900, output_tokens=50))
    assert tokens_only.assess(ticket="t", run_seq=1).spend_usd == 1.0
    assert (tokens_only.input_tokens, tokens_only.output_tokens) == (1000, 50)

    subject = detector(clock)
    subject.observe_event(WatchdogEvent("codex", "start", usd=1.0))
    subject.observe_event(WatchdogEvent("codex", "tool_call"))
    assert subject.assess(ticket="t", run_seq=1).spend_usd == 1.0


@pytest.mark.parametrize(("expected", "stuck", "at", "region"), [
    (10, 10, 9, "healthy"), (10, 10, 10, "stuck"), (10, 10, 15, "stuck"),
    (8, 10, 9, "healthy"), (8, 10, 10, "stuck"), (8, 10, 12, "stuck"),
    (10, 20, 14, "healthy"), (10, 20, 15, "soft"),
    (10, 20, 19, "soft"), (10, 20, 20, "stuck"),
])
def test_detector_time_boundaries_and_cap_waits(expected, stuck, at, region):
    clock = Clock()
    subject = detector(clock, expected=expected, stuck=stuck)
    clock.now = at + 3
    subject.observe_cap_wait(3)
    assessment = subject.assess(ticket="t", run_seq=1)
    assert assessment.region == region
    assert assessment.decision == ("hard_timeout" if region == "stuck" else None)


def test_detector_soft_trip_is_once_per_ticket_run_and_has_no_action_hook():
    clock = Clock()
    subject = detector(clock)
    clock.now = 15
    subject.observe_event(WatchdogEvent("claude", "tool_call", usd=6.01))
    assert subject.assess(ticket="t", run_seq=1).decision == "soft_trip"
    assert subject.assess(ticket="t", run_seq=1).decision is None
    assert subject.assess(ticket="t", run_seq=2).decision == "soft_trip"


def test_watchdog_construction_has_no_production_callback_consumer():
    package = Path(__file__).resolve().parent.parent / "squatch"
    sources = {path.name: path.read_text() for path in package.glob("*.py")}
    assert {name for name, source in sources.items() if "on_event" in source} == {"providers.py"}
    assert {name for name, source in sources.items() if "on_stdout_line" in source} == {
        "providers.py", "seams.py"}
    assert {name for name, source in sources.items() if "EventCollector" in source} == {"watchdog.py"}
