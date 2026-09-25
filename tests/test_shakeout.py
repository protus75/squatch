import json
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from eval.shakeout import registry
from eval.shakeout.__main__ import main
from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.journal import Journal
from squatch.llm import FakeLLM
from squatch.shakeout import REPORT_NAME, Entry, ShakeoutReport, dumps
from squatch.stages import KNOWN_ARTIFACTS
from test_stages import (Agent, Harness, WIDGET, answer, implementer, review,
                         run_record, env, repo)  # noqa: F401 -- shared fixtures


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 25, tzinfo=timezone.utc)

    def __call__(self):
        self.now += timedelta(microseconds=1)
        return self.now


def entry(**changes) -> Entry:
    values = {
        "member": "fixture.member", "group": "fixture", "fault": "planted",
        "observable": "terminal", "expected": "merged", "observed": "merged",
        "detail": "tickets/*/attempts/*/harvest.json", "producing_run": "ticket/0",
        "auditor": "green", "green": True,
    }
    values.update(changes)
    return Entry(**values)


def report(*entries: Entry, groups=("fixture",)) -> ShakeoutReport:
    return ShakeoutReport(schema_version=1, produced_at_sha="a" * 40,
                          groups=groups, entries=entries)


def test_schema_is_closed_and_green_is_derived():
    with pytest.raises(ValidationError):
        entry(auditor="yellow")
    with pytest.raises(ValidationError):
        entry(observed="gate_failed", green=True)
    with pytest.raises(ValidationError):
        Entry(**entry().model_dump(), surprise=True)
    with pytest.raises(ValidationError):
        ShakeoutReport(schema_version=2, produced_at_sha="a", groups=(), entries=())


def test_dumps_is_canonical_and_byte_stable():
    first = report(entry())
    second = report(Entry(**entry().model_dump()))
    assert dumps(first) == dumps(second)
    assert dumps(first).endswith("\n")
    assert dumps(first) == json.dumps(first.model_dump(mode="json"),
                                      sort_keys=True, indent=2) + "\n"


async def test_known_report_lifts_and_invalid_report_is_a_typed_terminal(repo, env):
    assert REPORT_NAME in KNOWN_ARTIFACTS
    valid = dumps(report(entry()))
    good = Agent(answer("implemented"), review("approve"), actions=[implementer(
        env, WIDGET, (f"tickets/widget-module/{REPORT_NAME}", valid))])
    harness = Harness(repo, env, good)
    delivery = await harness.run()
    assert delivery.outcome == "ok"
    assert (repo / "tickets/widget-module" / REPORT_NAME).read_text() == valid

    bad = Agent(answer("implemented"), actions=[implementer(
        env, WIDGET, (f"tickets/widget-module/{REPORT_NAME}", "{}\n"))])
    harness.llm = bad
    harness.stages._llm._llm = bad
    delivery = await harness.run(run_seq=1)
    assert delivery.outcome == "invalid_artifact"
    [finding] = delivery.findings
    assert finding.code == "invalid_artifact" and REPORT_NAME in finding.path
    assert (repo / "tickets/widget-module" / REPORT_NAME).read_text() == valid


def fixture_group(*members: Member) -> ModuleType:
    module = ModuleType("fixture_group")
    module.MEMBERS = tuple(members)
    return module


def test_runner_records_observable_and_auditor_results(tmp_path, monkeypatch):
    def duplicate(bench):
        with Journal(bench.state_dir, clock=bench.clock) as journal:
            journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket="bad")
            journal.append("state_transition", {"to": "gate_failed", "run_seq": 0},
                           ticket="bad")
            journal.append("state_transition", {"to": "timeout", "run_seq": 0}, ticket="bad")
        return "merged"

    group = fixture_group(
        Member("pass", "none", "terminal", "merged", "detail", lambda bench: "merged"),
        Member("mismatch", "wrong", "terminal", "merged", "detail",
               lambda bench: "gate_failed"),
        Member("audit", "duplicate", "terminal", "merged", "detail", duplicate),
    )
    monkeypatch.setattr(registry, "GROUPS", (("fixture", group),))
    outbox = tmp_path / "outbox"
    assert main(["run", "--outbox", str(outbox)]) == 1
    made = ShakeoutReport.model_validate_json((outbox / REPORT_NAME).read_text())
    invoking_head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    assert made.produced_at_sha == invoking_head
    assert [item.member for item in made.entries] == [
        "fixture.pass", "fixture.mismatch", "fixture.audit"]
    assert [item.green for item in made.entries] == [True, False, False]
    assert [item.auditor for item in made.entries] == ["green", "green", "red"]

    repeated = tmp_path / "repeated"
    assert main(["run", "--outbox", str(repeated)]) == 1
    repeated_report = ShakeoutReport.model_validate_json(
        (repeated / REPORT_NAME).read_text())
    assert repeated_report.produced_at_sha == made.produced_at_sha

    group.MEMBERS = (group.MEMBERS[0],)
    assert main(["run", "--outbox", str(tmp_path / "green")]) == 0


def test_double_gate_refuses_drift_and_appends_last_group(tmp_path, monkeypatch, capsys):
    first = fixture_group(Member(
        "one", "none", "terminal", "merged", "detail", lambda bench: "merged"))
    last = fixture_group(Member(
        "two", "none", "terminal", "merged", "detail", lambda bench: "merged"))
    monkeypatch.setattr(registry, "GROUPS", (("first", first), ("last", last)))
    initial = tmp_path / "initial"
    assert main(["run", "--outbox", str(initial)]) == 0
    prior_path = initial / REPORT_NAME
    prior = ShakeoutReport.model_validate_json(prior_path.read_text())

    changed = prior.model_copy(update={"entries": (
        prior.entries[0].model_copy(update={"fault": "changed"}), prior.entries[1])})
    changed_path = tmp_path / "changed.json"
    changed_path.write_text(dumps(changed))
    refused = tmp_path / "refused"
    assert main(["run", "--outbox", str(refused), "--prior", str(changed_path)]) == 1
    assert "first.one" in capsys.readouterr().out
    assert not (refused / REPORT_NAME).exists()

    appended = tmp_path / "appended"
    assert main(["run", "--outbox", str(appended), "--prior", str(prior_path)]) == 0
    cumulative = ShakeoutReport.model_validate_json((appended / REPORT_NAME).read_text())
    assert [item.member for item in cumulative.entries] == ["first.one", "last.two"]


def test_check_requires_every_registered_member_green(tmp_path, monkeypatch, capsys):
    group = fixture_group(Member(
        "one", "none", "terminal", "merged", "detail", lambda bench: "merged"))
    monkeypatch.setattr(registry, "GROUPS", (("fixture", group),))
    path = tmp_path / REPORT_NAME
    path.write_text(dumps(report(entry(member="fixture.one"))))
    assert main(["check", str(path)]) == 0
    assert "fixture.one: green" in capsys.readouterr().out

    path.write_text(dumps(report(groups=("fixture",))))
    assert main(["check", str(path)]) == 1
    path.write_text(dumps(report(entry(member="fixture.one", observed="red", green=False))))
    assert main(["check", str(path)]) == 1


def ticket(stem: str) -> str:
    python = sys.executable
    return textwrap.dedent(f"""\
        ---
        priority: P1
        kind: feature
        ---
        ## Depends on
        - none

        ## Context
        - fixture/context.txt

        ## Goal
        Land {stem}.

        ## Why
        Exercise the production composition.

        ## Scope in
        One fixture file.

        ## Scope out
        Engine code.

        ## Scope fence
        - feature/{stem}.txt

        ## Acceptance criteria
        - `feature/{stem}.txt` exists.

        ## Verification
        ```
        {python} -c "import pathlib,sys;sys.exit(not pathlib.Path('feature/{stem}.txt').is_file())"
        ```

        ## Definition of rejected
        Stop if the fixture cannot be written.

        ## Time budget
        - expected: 1m
        - stuck: 2m
        """)


class ActingFake(FakeLLM):
    def __init__(self, *script, actions=()):
        super().__init__(*script)
        self.actions = list(actions)

    async def call(self, request):
        action = self.actions.pop(0) if self.actions else None
        if action is not None:
            action(request)
        return await super().call(request)


def implement(request):
    stem = request.ticket
    path = request.worktree / "feature" / f"{stem}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("green\n")
    record = request.worktree / "tickets" / stem / "run.md"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(run_record())
    subprocess.run(["git", "-C", str(request.worktree), "add", "--", str(path)], check=True)
    subprocess.run(["git", "-C", str(request.worktree), "commit", "-q", "-m", "fixture"],
                   check=True)


def test_bench_drives_two_ticket_production_drain_to_quiescence(tmp_path):
    fake = ActingFake(
        answer("implemented"), review("approve"),
        answer("implemented"), review("approve"),
        actions=(implement, None, implement, None))
    bench = Bench.make(tmp_path / "bench", fake=fake, clock=Clock())
    for stem in ("alpha", "beta"):
        bench.write_ticket(stem, ticket(stem))
    assert bench.drain() == 0
    assert bench.terminal("alpha", 0) == "merged", bench.lines
    assert bench.terminal("beta", 0) == "merged"


def test_bench_initial_commit_is_reproducible(tmp_path):
    first = Bench.make(tmp_path / "first", fake=FakeLLM(), clock=Clock())
    second = Bench.make(tmp_path / "second", fake=FakeLLM(), clock=Clock())
    assert first.head() == second.head()
