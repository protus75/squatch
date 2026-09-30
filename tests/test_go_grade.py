"""The bounded GO-grade construction and operator-only GO handoff."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eval import harness
from eval.harness import (GO_DEFECT_COUNT, GO_SPEND_CAP_USD, ReviewBaselineReport,
                          dumps_go_grade, plant_defects, record_go, run, run_go_grade,
                          write_go_grade_report)
from squatch.artifacts import REVIEW_BASELINE_REPORT
from squatch.baseline import GO, resolve_baseline
from squatch.journal import Journal
from squatch.llm import FakeLLM, LLMResult
from squatch.seams import LocalFilesystem
from squatch.specs import load_spec
from squatch.stages import KNOWN_ARTIFACTS
from test_eval_harness import TickingClock, config, fixtures_dir, reply, seams


def _result(text, usd):
    return LLMResult(text=text, input_tokens=1, output_tokens=1,
                     provider="fake", model="fake", usd=usd)


def _report() -> ReviewBaselineReport:
    return ReviewBaselineReport(
        schema_version=1, produced_at_sha="deadbeef", planted_defect_count=50, spend_usd=5,
        authored_tickets=("a",), dependency_graph={"a": ()},
        scored_summary={"known_bad": 50, "clean": 0, "caught": 50, "false_approve": 0,
                        "unmatched": 0, "false_snag": 0, "catch_rate": 1,
                        "false_approve_rate": 0, "usd": 5},
        verdict_signal_identity={"tiers": ("high",), "identity": {
            "review": {"high": {"provider": "claude", "model": "c-max"}},
            "author": {"high": {"provider": "claude", "model": "c-high"}}},
            "spec_major": {"review": 1, "author": 1}})


def test_runtime_planting_has_real_defects_in_each_class_and_no_fixture_files():
    fixtures = plant_defects()
    assert len(fixtures) == GO_DEFECT_COUNT >= 50
    by_class = {fixture.expected.defect_class: fixture for fixture in fixtures[:4]}
    assert "return count < limit" in by_class["logic"].diff
    assert "sk-go-grade-secret" in by_class["hidden_info_leak"].diff
    assert "return False" in by_class["acceptance_mismatch"].diff
    escaped = by_class["scope_escape"]
    assert escaped.expected.planted.path.startswith("outside/")
    assert escaped.expected.planted.path not in escaped.ticket.split("## Scope fence", 1)[1].split("##", 1)[0]


async def test_go_grade_runs_local_author_under_cap_and_records_graph(tmp_path):
    cfg = config(tmp_path)
    tickets = ["authored-0", "authored-1"]
    author = json.dumps({"authored_tickets": tickets,
                         "dependency_graph": {tickets[0]: [], tickets[1]: [tickets[0]]}})
    llm = FakeLLM(_result(author, 0.05), *[_result(reply("snag", "src/planted_01.py"), 0.05)] * GO_DEFECT_COUNT)
    report = await run_go_grade(config=cfg, seams=seams(tmp_path), root=tmp_path, llm=llm)

    assert [request.surface for request in llm.requests] == ["author"] + ["review"] * GO_DEFECT_COUNT
    assert [request.max_budget_usd for request in llm.requests] == pytest.approx(
        [GO_SPEND_CAP_USD - 0.05 * number for number in range(GO_DEFECT_COUNT + 1)])
    assert harness.LOCAL_AUTHOR_PROMPT in llm.requests[0].rendered
    assert "specs/author.md" not in llm.requests[0].rendered
    assert report.planted_defect_count == GO_DEFECT_COUNT
    assert report.spend_usd == pytest.approx((GO_DEFECT_COUNT + 1) * 0.05)
    assert report.spend_usd <= GO_SPEND_CAP_USD
    assert report.authored_tickets == tuple(tickets)
    assert report.dependency_graph[tickets[1]] == (tickets[0],)
    assert not list(tmp_path.rglob(REVIEW_BASELINE_REPORT))
    assert {event.body["verdict"] for event in Journal(cfg.state_dir, clock=TickingClock()).read()
            if event.type == "signal"} == {"NO-GO"}


async def test_running_cap_counts_author_and_refuses_before_another_review(tmp_path):
    cfg = config(tmp_path)
    author = json.dumps({"authored_tickets": ["a"], "dependency_graph": {"a": []}})
    llm = FakeLLM(_result(author, 5.00))
    with pytest.raises(harness.Unscored, match="no further model call was made"):
        await run_go_grade(config=cfg, seams=seams(tmp_path), root=tmp_path, llm=llm)
    assert [request.surface for request in llm.requests] == ["author"]
    charged = sum(event.body["cost"]["usd"]
                  for event in Journal(cfg.state_dir, clock=TickingClock()).read()
                  if event.type == "effect_completion")
    assert charged == 5.00 <= GO_SPEND_CAP_USD
    assert not list(tmp_path.rglob(REVIEW_BASELINE_REPORT))


async def test_author_reprompt_gets_budget_remaining_after_first_call(tmp_path):
    cfg = config(tmp_path)
    author = json.dumps({"authored_tickets": ["a"], "dependency_graph": {"a": []}})
    llm = FakeLLM(
        _result("{}", 0.10), _result(author, 0.20),
        *[_result(reply("snag", "src/planted_01.py"), 0.01)] * GO_DEFECT_COUNT)

    report = await run_go_grade(config=cfg, seams=seams(tmp_path), root=tmp_path, llm=llm)

    assert [request.surface for request in llm.requests[:3]] == ["author", "author", "review"]
    assert [request.max_budget_usd for request in llm.requests[:3]] == pytest.approx(
        [5.00, 4.90, 4.70])
    assert report.spend_usd == pytest.approx(0.80)
    assert report.spend_usd <= GO_SPEND_CAP_USD


async def test_review_reprompt_gets_budget_remaining_after_first_call(tmp_path):
    cfg = config(tmp_path)
    author = json.dumps({"authored_tickets": ["a"], "dependency_graph": {"a": []}})
    llm = FakeLLM(
        _result(author, 0.10), _result("{}", 0.20),
        _result(reply("snag", "src/planted_01.py"), 0.30),
        *[_result(reply("snag", "src/planted_01.py"), 0.01)] * (GO_DEFECT_COUNT - 1))

    report = await run_go_grade(config=cfg, seams=seams(tmp_path), root=tmp_path, llm=llm)

    assert [request.surface for request in llm.requests[:3]] == ["author", "review", "review"]
    assert [request.max_budget_usd for request in llm.requests[:3]] == pytest.approx(
        [5.00, 4.90, 4.70])
    assert report.spend_usd == pytest.approx(1.09)
    assert report.spend_usd <= GO_SPEND_CAP_USD


async def test_go_grade_after_recorded_baseline_uses_fresh_effect_keys(tmp_path):
    cfg = config(tmp_path)
    ordinary = FakeLLM(*[reply("snag", "src/app.py")] * 3)
    await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
              root=tmp_path, llm=ordinary)
    author = json.dumps({"authored_tickets": ["a"], "dependency_graph": {"a": []}})
    graded = FakeLLM(_result(author, 0.05),
                     *[_result(reply("snag", "src/planted_01.py"), 0.05)] * GO_DEFECT_COUNT)

    await run_go_grade(config=cfg, seams=seams(tmp_path), root=tmp_path, llm=graded)

    assert [request.surface for request in graded.requests] == ["author"] + ["review"] * 50


async def test_go_grade_does_not_replay_an_unscored_ordinary_run(tmp_path):
    cfg = config(tmp_path)
    ordinary = FakeLLM(reply("snag", "src/app.py"), ConnectionError("provider gone"))
    with pytest.raises(harness.Unscored):
        await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
                  root=tmp_path, llm=ordinary)
    author = json.dumps({"authored_tickets": ["a"], "dependency_graph": {"a": []}})
    graded = FakeLLM(_result(author, 0.05),
                     *[_result(reply("snag", "src/planted_01.py"), 0.05)] * GO_DEFECT_COUNT)
    await run_go_grade(config=cfg, seams=seams(tmp_path), root=tmp_path, llm=graded)
    assert len(graded.requests) == GO_DEFECT_COUNT + 1


def test_closed_report_registration_and_canonical_ordinary_writer(tmp_path):
    report = _report()
    with pytest.raises(ValidationError):
        ReviewBaselineReport(**report.model_dump(), unknown=True)
    assert KNOWN_ARTIFACTS[REVIEW_BASELINE_REPORT](dumps_go_grade(report)) == report
    target = write_go_grade_report(workspace=tmp_path / "worktree", stem="go-grade-run",
                                   report=report, fs=LocalFilesystem())
    assert target.name == REVIEW_BASELINE_REPORT and target.read_text() == dumps_go_grade(report)


async def test_only_operator_path_writes_go_and_it_binds_the_report_identity(tmp_path):
    cfg = config(tmp_path)
    ordinary = FakeLLM(*[reply("snag", "src/app.py")] * 3)
    await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path), root=tmp_path,
              llm=ordinary)
    body = record_go(config=cfg, seams=seams(tmp_path), root=tmp_path, report=_report())
    with Journal(cfg.state_dir, clock=TickingClock()) as journal:
        events = list(journal.read())
    resolution = resolve_baseline(cfg, events, specs_dir=Path(__file__).parents[1] / "specs")
    expected = _report().verdict_signal_identity
    assert resolution.state == GO and resolution.binds is True
    assert body.tiers == expected.tiers
    assert body.model_dump(mode="json")["identity"] == expected.identity
    assert body.spec_major == expected.spec_major
    assert set(body.identity) == {"review", "author"}
    assert body.spec_major == {surface: int(load_spec(Path(__file__).parents[1] / "specs" / f"{surface}.md").version.split(".")[0])
                               for surface in ("review", "author")}
    signals = [event.body for event in events if event.type == "signal"]
    assert [signal["verdict"] for signal in signals[:-1]] == ["NO-GO"]
    assert signals[-1]["verdict"] == "GO"
    assert signals[-1]["summary"] == _report().scored_summary.model_dump(mode="json")
