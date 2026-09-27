"""The dormant storm occurrence ledger and its production-reachability fence."""

import ast
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from squatch.journal import Event, Journal, render_ts
from squatch.storm import OccurrenceWindow, StormLedger, THRESHOLD, WINDOW, fold


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parent.parent


def _clock(when):
    return lambda: when


def _event(*, signature, occurrence_id, when, emitting_stage=None):
    return {
        "v": 1,
        "type": "signal",
        "ts": render_ts(when),
        "ticket": None,
        "key": f"storm-occurrence/{signature}/{occurrence_id}",
        "body": {"kind": "storm_occurrence", "signature": signature,
                 "occurrence_id": occurrence_id, "emitting_stage": emitting_stage},
    }


def _seed_segment(state, name, events):
    directory = state / "journal"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("".join(json.dumps(event) + "\n" for event in events))


def test_records_the_exact_identity_and_body_once_on_replay(tmp_path):
    with Journal(tmp_path, clock=_clock(NOW)) as journal:
        ledger = StormLedger(journal=journal)
        assert ledger.record(signature="provider-timeout", occurrence_id="arrival-7",
                             emitting_stage="implement")
        assert not ledger.record(signature="provider-timeout", occurrence_id="arrival-7",
                                 emitting_stage="implement")
        [event] = tuple(journal.read())

    assert (event.type, event.key, event.body) == (
        "signal", "storm-occurrence/provider-timeout/arrival-7",
        {"kind": "storm_occurrence", "signature": "provider-timeout",
         "occurrence_id": "arrival-7", "emitting_stage": "implement"})


def test_window_spans_immutable_and_active_segments_in_journal_order(tmp_path):
    _seed_segment(tmp_path, "000001-20260927.jsonl", [
        _event(signature="provider-timeout", occurrence_id="immutable", when=NOW - timedelta(minutes=50)),
    ])
    _seed_segment(tmp_path, "000002-20260927.jsonl", [
        _event(signature="provider-timeout", occurrence_id="active", when=NOW - timedelta(minutes=10)),
        _event(signature="other", occurrence_id="other-arrival", when=NOW),
    ])
    with Journal(tmp_path, clock=_clock(NOW)) as journal:
        windows = StormLedger(journal=journal).window(now=NOW)

    assert windows == {
        "provider-timeout": OccurrenceWindow(("immutable", "active"), 2, False),
        "other": OccurrenceWindow(("other-arrival",), 1, False),
    }


def test_window_is_strictly_greater_than_threshold_and_expires_lower_boundary(tmp_path):
    events = [
        _event(signature="timeout", occurrence_id="expired", when=NOW - WINDOW),
        *[_event(signature="timeout", occurrence_id=f"live-{n}",
                 when=NOW - timedelta(minutes=THRESHOLD - n)) for n in range(THRESHOLD)],
        _event(signature="timeout", occurrence_id="crossing", when=NOW),
    ]
    windows = fold((Event(**event) for event in events), now=NOW)

    assert windows["timeout"].occurrence_ids == tuple([f"live-{n}" for n in range(THRESHOLD)] + ["crossing"])
    assert windows["timeout"].count == THRESHOLD + 1
    assert windows["timeout"].over_threshold
    strict = fold((Event(**event) for event in events[1:-1]), now=NOW)
    assert strict["timeout"] == OccurrenceWindow(tuple(f"live-{n}" for n in range(THRESHOLD)), THRESHOLD, False)


def test_production_import_closure_does_not_reach_the_dormant_ledger():
    reachable, pending = set(), ["squatch.__main__"]
    while pending:
        module = pending.pop()
        if module in reachable:
            continue
        reachable.add(module)
        spec = importlib.util.find_spec(module)
        assert spec is not None and spec.origin is not None
        tree = ast.parse(Path(spec.origin).read_text())
        for node in ast.walk(tree):
            names = ()
            if isinstance(node, ast.Import):
                names = (alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = (node.module,)
                if node.module == "squatch":
                    names = (*names, *(f"squatch.{alias.name}" for alias in node.names))
            for name in names:
                if name == "squatch" or name.startswith("squatch."):
                    pending.append(name)
    assert "squatch.storm" not in reachable
