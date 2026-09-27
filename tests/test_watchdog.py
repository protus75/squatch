"""watchdog.py: dormant normalized event construction only."""

from pathlib import Path

from squatch.watchdog import EventCollector, WatchdogEvent


def test_collector_preserves_normalized_events_in_arrival_order():
    collector = EventCollector()
    first = WatchdogEvent("claude", "tool_call", input_tokens=10, output_tokens=2)
    second = WatchdogEvent("codex", "start", usd=1.0)
    collector(first)
    collector(second)
    assert collector.events == [first, second]


def test_watchdog_construction_has_no_production_callback_consumer():
    package = Path(__file__).resolve().parent.parent / "squatch"
    sources = {path.name: path.read_text() for path in package.glob("*.py")}
    assert {name for name, source in sources.items() if "on_event" in source} == {"providers.py"}
    assert {name for name, source in sources.items() if "on_stdout_line" in source} == {
        "providers.py", "seams.py"}
    assert {name for name, source in sources.items() if "EventCollector" in source} == {"watchdog.py"}
