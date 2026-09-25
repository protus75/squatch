"""Offline contract tests for the production diagnosis evaluation harness."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval import diagnose
from eval.diagnose import (FIXTURES, SPEC, CLASS_VERDICT, STUCK_SECONDS, USD_CAP,
                           DiagnosisEvalReport, Expected, FixtureEnvelope, Refused, Seams,
                           load_fixtures, run)
from squatch.config import parse
from squatch.diagnose import VERDICTS, DiagnosisInput, diagnose_stage
from squatch.journal import Journal
from squatch.llm import FakeLLM, Hang, LLMResult
from squatch.providers import PLACEHOLDER, RoutingError
from squatch.seams import LocalFilesystem
from squatch.specs import DATA_MARKER, load_spec

T0 = datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc)


class TickingClock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class GitStub:
    """The only process the offline harness may spawn is git rev-parse."""

    def __init__(self):
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        self.calls.append(list(argv))
        assert argv[0] == "git" and argv[-3:] == ["rev-parse", "--verify", "HEAD"]
        return 0, "deadbeef\n", ""


def config(tmp_path, *, model="diagnoser"):
    return parse({
        "schema_version": 1,
        "state_dir": str(tmp_path / "instance-state"),
        "providers": [{
            "name": "claude", "kind": "cli",
            "models_by_tier": {
                "low": "small", "medium": model, "high": "large", "max": "largest"},
            "limits": {"concurrency": 1, "est_cost_per_call_usd": 2.0},
        }],
        "routing": [{
            "tier": "medium", "surface": "review",
            "candidates": [{"provider": "claude", "model": model}],
        }],
    }, source="test")


def seams(git=None):
    return Seams(process=git or GitStub(), fs=LocalFilesystem(), clock=TickingClock(),
                 env={"PATH": "/usr/bin"})


def reply(verdict):
    return json.dumps({
        "verdict": verdict,
        "lessons": [f"Use the evidence supporting {verdict}."],
        "reason": f"The evidence supports {verdict}.",
    })


def metered(verdict, usd):
    return LLMResult(text=reply(verdict), input_tokens=10, output_tokens=5,
                     provider="fake", model="fake-1", usd=usd)


def events(state):
    with Journal(state, clock=TickingClock()) as journal:
        return list(journal.read())


def copy_fixture_set(tmp_path, names):
    root = tmp_path / "fixtures"
    root.mkdir(parents=True)
    for name in names:
        source = FIXTURES / f"{name}.json"
        root.joinpath(source.name).write_bytes(source.read_bytes())
    return root


def test_committed_fixtures_are_valid_and_span_every_verdict_twice():
    fixtures = load_fixtures(FIXTURES)
    assert len(fixtures) >= 12
    assert {item.expected.expected_verdict for item in fixtures} == VERDICTS
    for verdict in VERDICTS:
        assert sum(item.expected.expected_verdict == verdict for item in fixtures) >= 2
    for fixture in fixtures:
        assert fixture.harvest.outcome
        assert fixture.harvest.reason
        assert fixture.harvest.findings
        assert fixture.harvest.spool_tails
        assert fixture.expected.expected_verdict == CLASS_VERDICT[fixture.expected.failure_class]


def test_load_fixtures_refuses_missing_invalid_harvest_and_mismatched_pair(tmp_path):
    root = copy_fixture_set(tmp_path, ["oversight-inverted-guard"])
    path = root / "oversight-inverted-guard.json"
    envelope = json.loads(path.read_text())
    del envelope["ticket"]
    path.write_text(json.dumps(envelope))
    with pytest.raises(Refused, match="oversight-inverted-guard: envelope is invalid"):
        load_fixtures(root)

    root = copy_fixture_set(tmp_path / "unknown-field", ["oversight-inverted-guard"])
    path = root / "oversight-inverted-guard.json"
    envelope = json.loads(path.read_text())
    envelope["unknown"] = True
    path.write_text(json.dumps(envelope))
    with pytest.raises(Refused, match="oversight-inverted-guard: envelope is invalid"):
        load_fixtures(root)

    root = copy_fixture_set(tmp_path / "bad-harvest", ["oversight-inverted-guard"])
    path = root / "oversight-inverted-guard.json"
    envelope = json.loads(path.read_text())
    envelope["harvest"] = {}
    path.write_text(json.dumps(envelope))
    with pytest.raises(Refused, match="oversight-inverted-guard: envelope is invalid"):
        load_fixtures(root)

    root = copy_fixture_set(tmp_path / "bad-pair", ["oversight-inverted-guard"])
    path = root / "oversight-inverted-guard.json"
    envelope = json.loads(path.read_text())
    envelope["expected"]["expected_verdict"] = "reject"
    path.write_text(json.dumps(envelope))
    with pytest.raises(Refused, match="oversight-inverted-guard: envelope is invalid"):
        load_fixtures(root)


def test_production_spec_renders_every_fixture_in_data_blocks():
    spec = load_spec(SPEC)
    stage = diagnose_stage(spec, tier=spec.tier, effort=spec.effort)
    for fixture in load_fixtures(FIXTURES):
        rendered = stage.render(DiagnosisInput(
            stem=fixture.name, ticket=fixture.ticket, harvest=fixture.harvest_text,
            run_record=fixture.run_record, produced_by_spec_version="fixture",
            produced_at_sha="x"), ())
        assert f'{DATA_MARKER}data name="ticket" origin="host"' in rendered
        assert f'{DATA_MARKER}data name="harvest" origin="untrusted"' in rendered
        if fixture.run_record is not None:
            assert f'{DATA_MARKER}data name="run_record" origin="untrusted"' in rendered


async def test_every_expected_verdict_is_reachable_and_completed_run_signals(tmp_path):
    fixtures = load_fixtures(FIXTURES)
    llm = FakeLLM(*(reply(item.expected.expected_verdict) for item in fixtures))
    report_path = tmp_path / "report.json"
    state = tmp_path / "harness-state"
    report = await run(config=config(tmp_path), seams=seams(), report_path=report_path,
                       state_dir=state, root=tmp_path, llm=llm, usd_cap=100.0)

    loaded = DiagnosisEvalReport.model_validate_json(report_path.read_text())
    assert loaded == report
    assert report.summary.agreement_rate == 1.0
    assert report.summary.scored == len(fixtures)
    assert all(item.agreed for item in report.scores)
    assert report.stopped is None
    assert all(request.ticket is None and request.worktree is None for request in llm.requests)
    signal = [event for event in events(state) if event.type == "signal"]
    assert len(signal) == 1 and signal[0].body["kind"] == "diagnosis_eval"
    completions = [event for event in events(state) if event.type == "effect_completion"]
    assert [event.key.split("/")[1] for event in completions] == [item.name for item in fixtures]


async def test_invalid_verdict_reprompts_once_then_run_completes_unscored(tmp_path):
    fixtures_dir = copy_fixture_set(tmp_path, ["oversight-inverted-guard",
                                                "oversight-missed-callsite"])
    llm = FakeLLM(reply("invented"), reply("invented"), reply("retry"))
    report = await run(config=config(tmp_path), seams=seams(),
                       report_path=tmp_path / "report.json", state_dir=tmp_path / "state",
                       fixtures_dir=fixtures_dir, root=tmp_path, llm=llm, usd_cap=100.0)
    assert len(llm.requests) == 3
    assert (report.scores[0].outcome, report.scores[0].verdict,
            report.scores[0].agreed) == ("invalid_artifact", None, False)
    assert report.summary.unscored == 1 and report.stopped is None
    assert len([event for event in events(tmp_path / "state") if event.type == "signal"]) == 1


async def test_timeout_aborts_leaves_intent_only_and_continues(tmp_path):
    names = ["environment-auth-expired", "oversight-inverted-guard"]
    fixtures_dir = copy_fixture_set(tmp_path, names)
    llm = FakeLLM(Hang(resist=True), reply("retry"))
    state = tmp_path / "state"
    report = await run(config=config(tmp_path), seams=seams(),
                       report_path=tmp_path / "report.json", state_dir=state,
                       fixtures_dir=fixtures_dir, root=tmp_path, llm=llm,
                       usd_cap=100.0, stuck_seconds=0.01)
    assert llm.aborted == 1
    assert [(item.fixture, item.outcome, item.verdict) for item in report.scores] == [
        ("environment-auth-expired", "timeout", None),
        ("oversight-inverted-guard", "ok", "retry"),
    ]
    journal_events = events(state)
    timeout_key = "llm/environment-auth-expired/0/diagnose/1/1"
    assert any(event.type == "effect_intent" and event.key == timeout_key
               for event in journal_events)
    assert not any(event.type == "effect_completion" and event.key == timeout_key
                   for event in journal_events)


async def test_budget_stops_pre_call_and_same_state_replays_then_completes(tmp_path):
    names = ["oversight-hidden-secret", "oversight-inverted-guard",
             "oversight-missed-callsite"]
    fixtures_dir = copy_fixture_set(tmp_path, names)
    state = tmp_path / "state"
    first = FakeLLM(*(metered("retry", 2.0) for _ in range(3)))
    stopped = await run(config=config(tmp_path), seams=seams(),
                        report_path=tmp_path / "first.json", state_dir=state,
                        fixtures_dir=fixtures_dir, root=tmp_path, llm=first)
    assert len(first.requests) == 2
    assert stopped.stopped == "budget"
    assert stopped.summary.not_run == ("oversight-missed-callsite",)
    assert stopped.summary.usd <= USD_CAP
    assert not [event for event in events(state) if event.type == "signal"]

    second = FakeLLM(metered("retry", 2.0))
    completed = await run(config=config(tmp_path), seams=seams(),
                          report_path=tmp_path / "second.json", state_dir=state,
                          fixtures_dir=fixtures_dir, root=tmp_path, llm=second)
    assert len(second.requests) == 1
    assert completed.stopped is None and len(completed.scores) == 3
    assert len([event for event in events(state) if event.type == "signal"]) == 1


async def test_budget_stop_on_reprompt_reports_the_paid_first_call(tmp_path):
    fixtures_dir = copy_fixture_set(tmp_path, ["oversight-inverted-guard",
                                                "oversight-missed-callsite"])
    llm = FakeLLM(LLMResult(
        text=reply("invented"), input_tokens=10, output_tokens=5,
        provider="fake", model="fake-1", usd=3.0))

    report = await run(config=config(tmp_path), seams=seams(),
                       report_path=tmp_path / "report.json", state_dir=tmp_path / "state",
                       fixtures_dir=fixtures_dir, root=tmp_path, llm=llm)

    assert len(llm.requests) == 1
    assert report.stopped == "budget"
    assert report.summary.usd == 3.0
    assert report.summary.not_run == ("oversight-missed-callsite",)
    assert [(item.fixture, item.outcome, item.usd) for item in report.scores] == [
        ("oversight-inverted-guard", "infra_error", 3.0)]


def test_bounds_are_pinned():
    assert USD_CAP == 5.0
    assert STUCK_SECONDS == 600


async def test_placeholder_and_same_author_refuse_before_call(tmp_path):
    fixtures_dir = copy_fixture_set(tmp_path, ["oversight-inverted-guard"])
    llm = FakeLLM()
    with pytest.raises(RoutingError, match=f"placeholder `{PLACEHOLDER}`"):
        await run(config=config(tmp_path, model=PLACEHOLDER), seams=seams(),
                  report_path=tmp_path / "report.json", fixtures_dir=fixtures_dir,
                  root=tmp_path, llm=llm)
    assert llm.requests == []

    answer_path = fixtures_dir / "oversight-inverted-guard.json"
    envelope = json.loads(answer_path.read_text())
    envelope["expected"]["author"] = {
        "provider": "claude", "model": "diagnoser", "tier": "medium"}
    answer_path.write_text(json.dumps(envelope))
    with pytest.raises(Refused, match="oversight-inverted-guard was authored by"):
        await run(config=config(tmp_path), seams=seams(), report_path=tmp_path / "report.json",
                  fixtures_dir=fixtures_dir, root=tmp_path, llm=llm)
    assert llm.requests == []


async def test_check_accepts_written_report_and_refuses_extra_field(tmp_path, capsys):
    fixtures_dir = copy_fixture_set(tmp_path, ["oversight-inverted-guard"])
    report_path = tmp_path / "report.json"
    await run(config=config(tmp_path), seams=seams(), report_path=report_path,
              state_dir=tmp_path / "state", fixtures_dir=fixtures_dir, root=tmp_path,
              llm=FakeLLM(reply("retry")), usd_cap=100.0)
    assert diagnose.main(["--check", str(report_path)]) == 0
    data = json.loads(report_path.read_text())
    data["unknown"] = True
    report_path.write_text(json.dumps(data))
    assert diagnose.main(["--check", str(report_path)]) == 1
    assert "invalid report" in capsys.readouterr().err


def test_main_refuses_placeholder_route_before_model_call(tmp_path, monkeypatch, capsys):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("""\
schema_version: 1
state_dir: state
providers:
  - name: claude
    kind: cli
    models_by_tier: {low: small, medium: OPERATOR-SETS-THIS, high: large, max: largest}
    limits: {concurrency: 1, est_cost_per_call_usd: 1.0}
routing:
  - {tier: medium, surface: review, candidates: [{provider: claude}]}
""")
    called = False

    async def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("model call")

    monkeypatch.setattr(FakeLLM, "call", forbidden)
    assert diagnose.main(["--config", str(cfg), "--report", str(tmp_path / "report.json")]) == 1
    assert not called
    assert "refused" in capsys.readouterr().err

    fixtures = copy_fixture_set(tmp_path, ["oversight-inverted-guard"])
    path = fixtures / "oversight-inverted-guard.json"
    envelope = json.loads(path.read_text())
    envelope["expected"]["author"] = {
        "provider": "claude", "model": "diagnoser", "tier": "medium"}
    path.write_text(json.dumps(envelope))
    valid_cfg = tmp_path / "valid-config.yaml"
    valid_cfg.write_text(cfg.read_text().replace("OPERATOR-SETS-THIS", "diagnoser"))
    assert diagnose.main([
        "--config", str(valid_cfg), "--fixtures", str(fixtures),
        "--report", str(tmp_path / "report.json")]) == 1
    assert not called
    assert "was authored by" in capsys.readouterr().err


def test_expected_schema_is_closed():
    fixture = load_fixtures(FIXTURES)[0]
    data = fixture.expected.model_dump()
    data["extra"] = True
    with pytest.raises(ValidationError):
        Expected.model_validate(data)


def test_fixture_envelope_schema_is_closed():
    data = json.loads(next(FIXTURES.glob("*.json")).read_text())
    data["extra"] = True
    with pytest.raises(ValidationError):
        FixtureEnvelope.model_validate(data)
