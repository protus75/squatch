"""The section 15 journal invariant auditor."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
from test_stages import Agent, WIDGET, answer, env, implementer, repo, review  # noqa: F401
from test_terminal import Drive, author, rejected_at_review, ticket

from squatch.audit import INVARIANTS, Violation, audit, audit_journal
from squatch.journal import Event, JournalCorruption, render_ts

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)


def event(type, *, n=0, ticket="stem", key=None, **body):
    return Event(v=1, type=type, ts=render_ts(T0 + timedelta(seconds=n)),
                 ticket=ticket, key=key, body=body)


def run(to, *, ticket="stem", run_seq=0, start=0, effects=(), **terminal):
    events = [event("state_transition", n=start, ticket=ticket,
                    to="running", run_seq=run_seq)]
    for offset, (type, key) in enumerate(effects, start=1):
        events.append(event(type, n=start + offset, ticket=ticket, key=key))
    events.append(event("state_transition", n=start + len(effects) + 1, ticket=ticket,
                        to=to, run_seq=run_seq, **terminal))
    return events


def test_invariant_registry_is_closed_ordered_and_documents_each_law():
    assert [invariant.name for invariant in INVARIANTS] == [
        "one_terminal_per_run", "declared_caps", "effects_paired_at_merged",
        "merged_carries_commit", "closed_run_states", "closed_event_types", "ts_monotone"]
    assert all(invariant.law for invariant in INVARIANTS)


@pytest.mark.parametrize(("name", "segments"), [
    ("one_terminal_per_run", [[
        event("state_transition", to="running", run_seq=0),
        event("state_transition", n=1, to="gate_failed", run_seq=0),
        event("state_transition", n=2, to="abandoned", run_seq=0),
    ]]),
    ("declared_caps", [[event("cap_consumed", cap="bottomless", run_seq=0)]]),
    ("effects_paired_at_merged", [[*run(
        "merged", effects=(("effect_intent", "missing"),),
        commit="abc", reviewed_sha="def")]]),
    ("merged_carries_commit", [[*run("merged", reviewed_sha="def")]]),
    ("closed_run_states", [[event("state_transition", to="sleeping", run_seq=0)]]),
    ("closed_event_types", [[event("debug_chatter")]]),
    ("ts_monotone", [[event("signal", n=1), event("signal", n=0)]]),
])
def test_each_invariant_flags_its_refusal_fixture_once(name, segments):
    invariant = next(item for item in INVARIANTS if item.name == name)
    violations = invariant.check(segments)
    assert len(violations) == 1
    assert isinstance(violations[0], Violation)
    assert violations[0].invariant == name


def test_green_fixture_covers_merged_failed_orphan_and_noop_runs():
    stream = [
        *run("merged", ticket="merged", effects=(
            ("effect_intent", "paired"), ("effect_completion", "paired")),
             commit="abc", reviewed_sha="def"),
        *run("gate_failed", ticket="failed", start=10,
             effects=(("effect_intent", "exempt"),)),
        event("state_transition", n=20, ticket="orphan", to="running", run_seq=0),
        *run("merged", ticket="noop", start=30, commit=None, reviewed_sha=None),
    ]
    assert audit([stream]) == ()


@pytest.mark.parametrize("terminal", [
    "timeout", "abandoned", "rejected", "gate_failed", "premise_failed"])
def test_unpaired_effect_is_exempt_for_every_non_ok_terminal(terminal):
    assert audit([run(terminal, effects=(("effect_intent", "unpaired"),))]) == ()


def test_timestamp_monotonicity_resets_at_segment_boundaries():
    assert audit([[event("signal", n=10)], [event("signal", n=0)]]) == ()


def test_audit_journal_surfaces_corruption_in_a_rolled_segment(tmp_path):
    jd = tmp_path / "journal"
    jd.mkdir()
    (jd / "000001-20260804.jsonl").write_text("not json\n")
    (jd / "000002-20260805.jsonl").write_text("")
    with pytest.raises(JournalCorruption):
        audit_journal(tmp_path)


async def test_audit_is_green_over_full_runner_merge_and_gate_failure(repo, env):
    author(repo, ticket(), stem="failed")
    failed = Drive(repo, env, rejected_at_review(env))
    assert await failed.run("failed") == 1
    assert audit_journal(failed.state) == ()

    author(repo, ticket())
    failed._llm = Agent(answer("implemented"), review("approve"),
                        actions=[implementer(env, WIDGET)])
    assert await failed.run() == 0
    assert audit_journal(failed.state) == ()


def write_event(state, value):
    jd = state / "journal"
    jd.mkdir(parents=True)
    (jd / "000001-20260804.jsonl").write_text(json.dumps(value) + "\n")


def cli(state):
    return subprocess.run([sys.executable, "-m", "squatch.audit", "--state", str(state)],
                          capture_output=True, text=True)


def test_module_entry_exit_codes_and_paved_road(tmp_path):
    green = tmp_path / "green"
    write_event(green, event("signal").__dict__)
    assert cli(green).returncode == 0

    red = tmp_path / "red"
    write_event(red, event("state_transition", to="unknown", run_seq=0).__dict__)
    result = cli(red)
    assert result.returncode == 1 and "closed_run_states" in result.stdout

    result = cli(tmp_path / "missing")
    assert result.returncode == 2 and "paved road:" in result.stderr
