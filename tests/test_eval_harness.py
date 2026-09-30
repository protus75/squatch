"""eval/harness.py: the review-baseline eval (plan section 19, Phase 1 exit).

The contract under test, offline against the scripted fake LLM: the
committed fixture set is valid and spans the four defect classes; the real
`specs/review.md` lints and renders every fixture; scoring separates caught
/ false-approve / unmatched / false-snag; a run is refused BEFORE any call
on a placeholder row or a fixture author that is the reviewer; an
infrastructure failure on any fixture records NO verdict; and a scored run
writes exactly one `signal` event carrying the baselined identity, the
spec-major versions, the fixture authors, and the NO-GO verdict.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from eval import harness
from eval.harness import (
    FIXTURES, SPEC, AuthorIdentity, Expected, Fixture, ReviewReport, Score, Seams, Unscored,
    diff_paths, load_fixtures, run, score, summarize)
from squatch.artifacts import Cost, Finding, StageResult
from squatch.config import parse
from squatch.journal import Journal
from squatch.llm import FakeLLM
from squatch.providers import PLACEHOLDER, RoutingError
from squatch.seams import LocalFilesystem
from squatch.specs import DATA_MARKER, DataBlock, load_spec

T0 = datetime(2026, 9, 24, 12, 0, 0, tzinfo=timezone.utc)
DEFECT_CLASSES = {"logic", "hidden_info_leak", "acceptance_mismatch", "scope_escape"}
AUTHOR = {"provider": "claude", "model": "c-author", "tier": "medium"}

DIFF = """\
diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,4 @@
 import os
+TOKEN = "sk-test-FAKE"
 def main():
     return 0
"""
TICKET = "---\nstate: confirmed\n---\n# t\n## Scope fence\n- src/app.py\n## Acceptance criteria\n- exits 0\n"


class TickingClock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class GitStub:
    """The only process the offline run may spawn: `git rev-parse HEAD`."""

    def __init__(self):
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        self.calls.append(list(argv))
        assert argv[0] == "git" and "rev-parse" in argv, argv
        return 0, "deadbeef\n", ""


def config(tmp_path, *, review_model="c-max", author_provider="claude"):
    return parse({
        "schema_version": 1, "state_dir": str(tmp_path / "state"),
        "providers": [
            {"name": "claude", "kind": "cli",
             "models_by_tier": {"low": "c-low", "medium": "c-med", "high": "c-high", "max": "c-max"},
             "limits": {"concurrency": 1}},
            {"name": "codex", "kind": "cli",
             "models_by_tier": {"low": "x-low", "medium": "x-med", "high": "x-high", "max": "x-max"},
             "limits": {"concurrency": 1, "est_cost_per_call_usd": 1.0}}],
        "routing": [
            {"tier": "high", "surface": "review",
             "candidates": [{"provider": "claude", "model": review_model}]},
            {"tier": "high", "surface": "author", "candidates": [{"provider": author_provider}]},
            {"tier": "high", "surface": "implement", "candidates": [{"provider": "codex"}]}],
    }, source="test")


def write_fixture(root: Path, name: str, *, defect_class="logic", planted_path="src/app.py",
                  author=AUTHOR, diff=DIFF):
    d = root / name
    d.mkdir(parents=True)
    (d / "ticket.md").write_text(TICKET)
    (d / "diff.patch").write_text(diff)
    clean = defect_class == "none"
    (d / "expected.json").write_text(json.dumps({
        "schema_version": 1, "expected_verdict": "approve" if clean else "snag",
        "defect_class": defect_class,
        "planted": None if clean else {"path": planted_path, "description": "planted"},
        "author": author}))
    return d


def fixtures_dir(tmp_path):
    root = tmp_path / "fixtures"
    write_fixture(root, "a-logic")
    write_fixture(root, "b-leak", defect_class="hidden_info_leak")
    write_fixture(root, "c-clean", defect_class="none")
    return root


def reply(verdict, path=None):
    findings = [] if verdict == "approve" else [{
        "code": "correctness_review", "path": path, "line": 2,
        "message": "wrong", "paved_road": "fix it"}]
    return json.dumps({"verdict": verdict, "summary": "s", "findings": findings})


def seams(tmp_path, git=None):
    return Seams(process=git or GitStub(), fs=LocalFilesystem(), clock=TickingClock(),
                 env={"PATH": "/usr/bin"})


def signals(state: Path):
    with Journal(state, clock=TickingClock()) as j:
        return [e for e in j.read() if e.type == "signal"]


# --- the committed spec and fixture set ------------------------------------


def test_review_spec_lints_and_renders_the_three_slots_in_data_blocks():
    spec = load_spec(SPEC)
    assert (spec.surface, spec.version, spec.slots) == (
        "review", "1.0", ("ticket", "diff", "check_report"))
    assert spec.emits == {"approve": "ApprovedInvoice", "snag": "SnagList", "rma": "RMA"}
    text = spec.render({"ticket": DataBlock("host", TICKET), "diff": DataBlock("untrusted", DIFF),
                        "check_report": DataBlock("engine", harness.NO_CHECKS)})
    assert f'{DATA_MARKER}data name="ticket" origin="host"' in text
    assert f'{DATA_MARKER}data name="diff" origin="untrusted"' in text
    assert f'{DATA_MARKER}data name="check_report" origin="engine"' in text


def _hunks_are_consistent(diff: str) -> list[str]:
    """Every `@@ -a,b +c,d @@` hunk's line counts match its body."""
    defects = []
    lines = diff.splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@", lines[i])
        if not m:
            i += 1
            continue
        want_old = int(m.group(1)) if m.group(1) is not None else 1
        want_new = int(m.group(2)) if m.group(2) is not None else 1
        old = new = 0
        i += 1
        while i < len(lines) and not lines[i].startswith(("@@", "diff --git")):
            tag = lines[i][:1]
            if tag == "\\":
                pass  # "\ No newline at end of file"
            elif tag == "-":
                old += 1
            elif tag == "+":
                new += 1
            elif tag in (" ", ""):
                old += 1
                new += 1
            i += 1
        if (old, new) != (want_old, want_new):
            defects.append(f"{m.group(0)}: body is -{old} +{new}")
    return defects


def test_committed_fixture_set_is_valid_and_spans_every_defect_class():
    fixtures = load_fixtures(FIXTURES)
    bad = [f for f in fixtures if f.expected.known_bad]
    assert 15 <= len(bad) <= 20, [f.name for f in bad]
    assert {f.expected.defect_class for f in bad} == DEFECT_CLASSES
    assert len({f.name for f in fixtures}) == len(fixtures)
    for f in fixtures:
        assert f.name == f.name.lower() and re.fullmatch(r"[a-z0-9][a-z0-9-]+", f.name)
        assert "## Scope fence" in f.ticket and "## Acceptance criteria" in f.ticket, f.name
        assert _hunks_are_consistent(f.diff) == [], f.name
        assert f.expected.author.provider and f.expected.author.model
    # Every fixture renders through the real spec inside the render bound.
    spec = load_spec(SPEC)
    stage = harness.review_stage(spec)
    for f in fixtures:
        stage.render(harness.ReviewInput(produced_by_spec_version="fixture", produced_at_sha="x",
                                         ticket=f.ticket, diff=f.diff,
                                         check_report=harness.NO_CHECKS), ())


# --- fixture loading refuses fail-closed -----------------------------------


def test_load_fixtures_refuses_a_missing_file(tmp_path):
    d = write_fixture(tmp_path / "fx", "a-logic")
    (d / "ticket.md").unlink()
    with pytest.raises(Unscored, match=r"a-logic: missing \['ticket.md'\]"):
        load_fixtures(tmp_path / "fx")


def test_load_fixtures_refuses_an_answer_key_outside_the_schema(tmp_path):
    d = write_fixture(tmp_path / "fx", "a-logic")
    data = json.loads((d / "expected.json").read_text())
    data["defect_class"] = "style"
    (d / "expected.json").write_text(json.dumps(data))
    with pytest.raises(Unscored, match="a-logic: expected.json is invalid"):
        load_fixtures(tmp_path / "fx")


def test_load_fixtures_refuses_a_planted_path_the_diff_never_touches(tmp_path):
    write_fixture(tmp_path / "fx", "a-logic", planted_path="src/other.py")
    with pytest.raises(Unscored, match="planted.path 'src/other.py' is not a path the diff"):
        load_fixtures(tmp_path / "fx")


def test_expected_refuses_a_half_clean_answer_key():
    with pytest.raises(ValueError, match="all three or none"):
        Expected(schema_version=1, expected_verdict="approve", defect_class="logic",
                 planted=None, author=AuthorIdentity(**AUTHOR))


def test_diff_paths_reads_both_headers_without_prefixes():
    assert diff_paths(DIFF) == {"src/app.py"}
    assert diff_paths("--- a/gone.py\n+++ /dev/null\n") == {"gone.py"}
    assert diff_paths("not a diff") == frozenset()


# --- scoring ---------------------------------------------------------------


def fixture(name="fx", defect_class="logic", path="src/app.py") -> Fixture:
    clean = defect_class == "none"
    return Fixture(name, TICKET, DIFF, Expected(
        schema_version=1, expected_verdict="approve" if clean else "snag",
        defect_class=defect_class,
        planted=None if clean else {"path": path, "description": "d"}, author=AUTHOR))


def result(verdict=None, path=None, outcome="ok") -> StageResult:
    artifact = None
    if verdict is not None:
        findings = () if verdict == "approve" else (Finding(
            code="correctness_review", path=path, message="m", paved_road="r"),)
        artifact = ReviewReport(produced_by_spec_version="1.0", produced_at_sha="x",
                                verdict=verdict, summary="s", findings=findings)
    return StageResult(outcome=outcome, artifact=artifact, findings=[],
                       cost=Cost(tokens=1, seconds=1, attempts=1, usd=0.25))


def test_score_separates_caught_false_approve_unmatched_and_false_snag():
    caught = score(fixture(), result("snag", "b/src/app.py"))
    assert (caught.caught, caught.false_approve, caught.false_snag) == (True, False, False)
    assert score(fixture(), result("rma", "src/app.py")).caught
    approved = score(fixture(), result("approve"))
    assert (approved.caught, approved.false_approve) == (False, True)
    wrong_path = score(fixture(), result("snag", "src/other.py"))
    assert (wrong_path.caught, wrong_path.false_approve) == (False, False)
    invalid = score(fixture(), result(None, outcome="invalid_artifact"))
    assert (invalid.verdict, invalid.caught, invalid.false_approve) == (None, False, False)
    snagged_clean = score(fixture(defect_class="none"), result("snag", "src/app.py"))
    assert (snagged_clean.false_snag, snagged_clean.caught) == (True, False)
    assert not score(fixture(defect_class="none"), result("approve")).false_snag


def test_summarize_counts_and_rates():
    s = summarize([
        score(fixture("a"), result("snag", "src/app.py")),
        score(fixture("b"), result("approve")),
        score(fixture("c"), result("snag", "src/x.py")),
        score(fixture("d", "none"), result("snag", "src/app.py")),
    ])
    assert (s.known_bad, s.clean, s.caught, s.false_approve, s.unmatched, s.false_snag) == (
        3, 1, 1, 1, 1, 1)
    assert (s.catch_rate, s.false_approve_rate, s.usd) == (1 / 3, 1 / 3, 1.0)


# --- the run ---------------------------------------------------------------


async def test_run_scores_every_fixture_and_journals_the_no_go_signal(tmp_path, capsys):
    llm = FakeLLM(reply("snag", "src/app.py"), reply("approve"), reply("approve"))
    cfg = config(tmp_path)

    body = await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
                     root=tmp_path, llm=llm)

    assert [r.surface for r in llm.requests] == ["review"] * 3
    assert all(r.tier == "high" and r.ticket is None and r.worktree is None
               for r in llm.requests)
    assert "sk-test-FAKE" in llm.requests[0].rendered
    assert body.verdict == "NO-GO" and body.kind == "review_baseline" and body.tiers == ("high",)
    assert body.model_dump()["identity"] == {
        "review": {"high": {"provider": "claude", "model": "c-max"}},
        "author": {"high": {"provider": "claude", "model": "c-high"}}}
    assert body.spec_version == {"review": "1.0", "author": "1.0"}
    assert body.spec_major == {"review": 1, "author": 1}
    assert body.fixture_authors == (AuthorIdentity(**AUTHOR),)
    assert body.produced_at_sha == "deadbeef"
    s = body.summary
    assert (s.known_bad, s.clean, s.caught, s.false_approve, s.false_snag) == (2, 1, 1, 1, 0)
    assert [x.fixture for x in body.scores] == ["a-logic", "b-leak", "c-clean"]

    [event] = signals(cfg.state_dir)
    assert event.ticket is None and event.key is None
    assert event.body == body.model_dump(mode="json")
    assert event.body["summary"]["catch_rate"] == 0.5
    out = capsys.readouterr().out
    assert "verdict: NO-GO" in out and "APPROVED: b-leak" in out
    # The attempt spool holds each fixture's prompt and reply under its attempt number.
    assert sorted(p.name for p in (cfg.state_dir / "spools" / "review").iterdir()) == ["1", "2", "3"]


async def test_run_refuses_a_placeholder_row_before_any_call(tmp_path):
    llm = FakeLLM()
    cfg = config(tmp_path, review_model=PLACEHOLDER)
    with pytest.raises(RoutingError, match=f"carries the placeholder `{PLACEHOLDER}`"):
        await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
                  root=tmp_path, llm=llm)
    assert llm.requests == [] and not (cfg.state_dir / "journal").exists()


async def test_run_refuses_a_fixture_author_that_is_the_reviewer(tmp_path):
    llm = FakeLLM()
    cfg = config(tmp_path)
    root = fixtures_dir(tmp_path)
    write_fixture(root, "d-same", author={"provider": "claude", "model": "c-max", "tier": "high"})
    with pytest.raises(Unscored, match="d-same was authored by .claude, c-max. at tier high"):
        await run(config=cfg, seams=seams(tmp_path), fixtures_dir=root, root=tmp_path, llm=llm)
    assert llm.requests == []
    # Same model at a DIFFERENT tier is the plan's minimum diversity: accepted.
    (root / "d-same").rename(root / "d-other-tier")
    (root / "d-other-tier" / "expected.json").write_text(json.dumps({
        **json.loads((root / "d-other-tier" / "expected.json").read_text()),
        "author": {"provider": "claude", "model": "c-max", "tier": "low"}}))
    llm = FakeLLM(*[reply("snag", "src/app.py")] * 4)
    body = await run(config=cfg, seams=seams(tmp_path), fixtures_dir=root, root=tmp_path, llm=llm)
    assert len(body.fixture_authors) == 2


async def test_infra_error_on_any_fixture_records_no_verdict(tmp_path):
    llm = FakeLLM(reply("snag", "src/app.py"), ConnectionError("provider gone"))
    cfg = config(tmp_path)
    with pytest.raises(Unscored, match="b-leak .* terminated infra_error"):
        await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
                  root=tmp_path, llm=llm)
    assert signals(cfg.state_dir) == []


async def test_rerun_after_an_unscored_run_replays_completed_fixtures_and_calls_the_rest(tmp_path):
    cfg = config(tmp_path)
    first = FakeLLM(reply("snag", "src/app.py"), ConnectionError("provider gone"))
    with pytest.raises(Unscored):
        await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
                  root=tmp_path, llm=first)
    second = FakeLLM(reply("approve"), reply("approve"))
    root = tmp_path / "fixtures"
    body = await run(config=cfg, seams=seams(tmp_path), fixtures_dir=root, root=tmp_path,
                     llm=second)
    assert len(second.requests) == 2  # a-logic replays; b-leak and c-clean are called
    assert [s.verdict for s in body.scores] == ["snag", "approve", "approve"]


async def test_rerun_after_a_recorded_verdict_takes_a_fresh_sequence_and_calls_again(tmp_path):
    cfg = config(tmp_path)
    root = fixtures_dir(tmp_path)
    for n in range(2):
        llm = FakeLLM(*[reply("snag", "src/app.py")] * 3)
        await run(config=cfg, seams=seams(tmp_path), fixtures_dir=root, root=tmp_path, llm=llm)
        assert len(llm.requests) == 3
    with Journal(cfg.state_dir, clock=TickingClock()) as j:
        keys = [e.key for e in j.read() if e.type == "effect_completion"]
    assert keys == [f"llm/review/{n}/review/{a}/1" for n in range(2) for a in (1, 2, 3)]
    assert len(signals(cfg.state_dir)) == 2


async def test_a_reply_outside_the_contract_is_reprompted_once_then_scored_unmatched(tmp_path):
    llm = FakeLLM("not json", "```json\n{}\n```",           # a-logic: two bad replies
                  reply("snag", "src/app.py"), reply("approve"))
    cfg = config(tmp_path)
    body = await run(config=cfg, seams=seams(tmp_path), fixtures_dir=fixtures_dir(tmp_path),
                     root=tmp_path, llm=llm)
    assert len(llm.requests) == 4
    assert f'{DATA_MARKER}data name="findings"' in llm.requests[1].rendered
    first = body.scores[0]
    assert (first.outcome, first.verdict, first.caught, first.false_approve) == (
        "invalid_artifact", None, False, False)
    assert (body.summary.unmatched, body.summary.caught) == (1, 1)
    assert len(signals(cfg.state_dir)) == 1


def test_main_reports_a_refusal_and_exits_one_without_a_verdict(tmp_path, capsys):
    cfg = tmp_path / "config.yaml"
    text = (Path(harness.ROOT) / "config.yaml").read_text()
    text = text.replace("state_dir: .squatch/state", f"state_dir: {tmp_path / 'state'}")
    text = text.replace("model: sonnet", "model: OPERATOR-SETS-THIS", 1)
    cfg.write_text(text)
    assert harness.main(["--config", str(cfg), "--fixtures", str(fixtures_dir(tmp_path))]) == 1
    err = capsys.readouterr().err
    assert "refused" in err and "no verdict recorded" in err
    assert not (tmp_path / "state").exists()
