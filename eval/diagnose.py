"""Real-model diagnosis evaluation harness (plan section 19, Phase 2).

The harness runs the production diagnosis stage over committed failed-attempt
fixtures.  It owns a journal separate from the squatch instance journal, so it
can safely run from an implement worktree while the instance writer lock is
held.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from squatch.artifacts import ClosedModel, StageResult
from squatch.config import Config, ConfigError, Tier, load
from squatch.diagnose import (DIAGNOSE_RETRY_CAP, VERDICTS, Diagnosis, DiagnosisInput,
                              diagnose_stage)
from squatch.driver import Driver, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.harvest import Harvest
from squatch.journal import Journal
from squatch.llm import LLM
from squatch.llmeffect import LLMEffect, llm_key
from squatch.providers import PLACEHOLDER, PREREQUISITE, CliClient, Registry, RoutingError
from squatch.redact import Redactor
from squatch.seams import Clock, Filesystem, LocalFilesystem, ProcessExec, SubprocessExec
from squatch.specs import Spec, load_spec

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "specs" / "diagnose.md"
FIXTURES = ROOT / "eval" / "diagnose_fixtures"
SIGNAL_KIND = "diagnosis_eval"
USD_CAP = 5.0
STUCK_SECONDS = 600
GIT_TIMEOUT = 60

FailureClass = Literal[
    "fixable_oversight", "under_capability", "oversized", "false_premise", "environment"]
StopReason = Literal["budget"]

CLASS_VERDICT: Mapping[FailureClass, str] = {
    "fixable_oversight": "retry",
    "under_capability": "escalate",
    "oversized": "split",
    "false_premise": "reject",
    "environment": "abandon-human",
}


class Refused(Exception):
    """A fail-closed harness refusal with an operator-actionable message."""


class BudgetRefused(Exception):
    """The pre-call run budget check refused a fresh effect."""


class AuthorIdentity(ClosedModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tier: Tier


class Expected(ClosedModel):
    schema_version: Literal[1]
    expected_verdict: str
    failure_class: FailureClass
    rationale: str = Field(min_length=1)
    author: AuthorIdentity

    @field_validator("expected_verdict")
    @classmethod
    def _closed_verdict(cls, value: str) -> str:
        if value not in VERDICTS:
            raise ValueError(f"expected_verdict must be one of {sorted(VERDICTS)}")
        return value

    @field_validator("rationale")
    @classmethod
    def _one_sentence(cls, value: str) -> str:
        if ("\n" in value or "\r" in value or not value.endswith((".", "!", "?"))
                or re.search(r"[.!?]\s+\S", value)):
            raise ValueError("rationale must be one sentence on one line")
        return value

    @model_validator(mode="after")
    def _class_matches_verdict(self):
        expected = CLASS_VERDICT[self.failure_class]
        if self.expected_verdict != expected:
            raise ValueError(
                f"failure_class {self.failure_class!r} maps to verdict {expected!r}, "
                f"not {self.expected_verdict!r}")
        return self


@dataclass(frozen=True)
class Fixture:
    name: str
    ticket: str
    harvest: Harvest
    harvest_text: str
    run_record: str | None
    expected: Expected


class FixtureEnvelope(ClosedModel):
    ticket: str = Field(min_length=1)
    harvest: Harvest
    expected: Expected
    run_record: str | None = None


def load_fixtures(root: Path = FIXTURES) -> list[Fixture]:
    root = Path(root)
    paths = sorted(root.glob("*.json")) if root.is_dir() else []
    if not paths:
        raise Refused(f"no fixtures under {root}; commit "
                      "eval/diagnose_fixtures/<name>.json envelopes")
    fixtures: list[Fixture] = []
    for path in paths:
        name = path.stem
        try:
            envelope = FixtureEnvelope.model_validate_json(path.read_text())
        except (OSError, ValueError, ValidationError) as exc:
            raise Refused(
                f"fixture {name}: envelope is invalid: {exc}; write the closed schema "
                f"{sorted(FixtureEnvelope.model_fields)} with a validated Harvest and "
                "class-verdict pair") from None
        harvest_text = envelope.harvest.model_dump_json(indent=2)
        fixtures.append(Fixture(
            name=name,
            ticket=envelope.ticket,
            harvest=envelope.harvest,
            harvest_text=harvest_text,
            run_record=envelope.run_record,
            expected=envelope.expected,
        ))
    return fixtures


class Identity(ClosedModel):
    provider: str
    model: str
    tier: Tier


class Score(ClosedModel):
    fixture: str
    failure_class: FailureClass
    expected_verdict: str
    outcome: str
    verdict: str | None
    agreed: bool
    lesson_count: int = Field(ge=0)
    usd: float = Field(ge=0)
    provider: str | None
    model: str | None

    @field_validator("expected_verdict", "verdict")
    @classmethod
    def _closed_verdict(cls, value: str | None) -> str | None:
        if value is not None and value not in VERDICTS:
            raise ValueError(f"verdict must be null or one of {sorted(VERDICTS)}")
        return value


class VerdictSummary(ClosedModel):
    fixtures: int = Field(ge=0)
    scored: int = Field(ge=0)
    agreed: int = Field(ge=0)
    agreement_rate: float = Field(ge=0, le=1)


class Summary(ClosedModel):
    fixtures: int = Field(ge=0)
    scored: int = Field(ge=0)
    agreed: int = Field(ge=0)
    agreement_rate: float = Field(ge=0, le=1)
    per_verdict: dict[str, VerdictSummary]
    unscored: int = Field(ge=0)
    usd: float = Field(ge=0)
    not_run: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _all_verdicts_present(self):
        if set(self.per_verdict) != set(VERDICTS):
            raise ValueError(f"per_verdict keys must be exactly {sorted(VERDICTS)}")
        return self


class DiagnosisEvalReport(ClosedModel):
    schema_version: Literal[1]
    produced_at_sha: str = Field(min_length=1)
    identity: Identity
    spec_version: str
    fixture_authors: tuple[AuthorIdentity, ...]
    usd_cap: float = Field(ge=0)
    stuck_seconds: float = Field(gt=0)
    stopped: StopReason | None
    scores: tuple[Score, ...]
    summary: Summary


class DiagnosisEvalSignal(ClosedModel):
    kind: Literal["diagnosis_eval"]
    summary: Summary
    identity: Identity
    report: str


def score(fixture: Fixture, result: StageResult) -> Score:
    diagnosis = result.artifact if isinstance(result.artifact, Diagnosis) else None
    verdict = diagnosis.verdict if diagnosis else None
    return Score(
        fixture=fixture.name,
        failure_class=fixture.expected.failure_class,
        expected_verdict=fixture.expected.expected_verdict,
        outcome=result.outcome,
        verdict=verdict,
        agreed=verdict == fixture.expected.expected_verdict,
        lesson_count=len(diagnosis.lessons) if diagnosis else 0,
        usd=result.cost.usd,
        provider=result.cost.provider,
        model=result.cost.model,
    )


def summarize(fixtures: Iterable[Fixture], scores: Iterable[Score],
              not_run: Iterable[str] = ()) -> Summary:
    fixtures = list(fixtures)
    scores = list(scores)
    scored = [item for item in scores if item.verdict is not None]
    per_verdict: dict[str, VerdictSummary] = {}
    for verdict in sorted(VERDICTS):
        expected = [item for item in fixtures if item.expected.expected_verdict == verdict]
        verdict_scores = [item for item in scored if item.expected_verdict == verdict]
        agreed = sum(item.agreed for item in verdict_scores)
        per_verdict[verdict] = VerdictSummary(
            fixtures=len(expected), scored=len(verdict_scores), agreed=agreed,
            agreement_rate=agreed / len(verdict_scores) if verdict_scores else 0.0)
    agreed = sum(item.agreed for item in scored)
    return Summary(
        fixtures=len(fixtures), scored=len(scored), agreed=agreed,
        agreement_rate=agreed / len(scored) if scored else 0.0,
        per_verdict=per_verdict, unscored=len(fixtures) - len(scored),
        usd=round(sum(item.usd for item in scores), 6), not_run=tuple(not_run))


@dataclass(frozen=True)
class Seams:
    process: ProcessExec
    fs: Filesystem
    clock: Clock
    env: Mapping[str, str]


def production_seams() -> Seams:
    return Seams(process=SubprocessExec(), fs=LocalFilesystem(),
                 clock=lambda: datetime.now(timezone.utc), env=dict(os.environ))


class _RunBudget:
    def __init__(self, cap: float, fallback: float):
        self.cap = cap
        self.fallback = fallback
        self.spent = 0.0
        self.largest: float | None = None

    def check(self) -> None:
        estimate = self.largest if self.largest is not None else self.fallback
        if self.spent + estimate > self.cap:
            raise BudgetRefused(
                f"spent ${self.spent:.6f} plus estimate ${estimate:.6f} exceeds "
                f"the ${self.cap:.2f} run cap")

    def observe(self, usd: float) -> None:
        self.spent += usd
        self.largest = max(self.largest or 0.0, usd)


class _FixtureEffect:
    """Give a ticket-less driver call a fixture-scoped effect-key stem."""

    def __init__(self, inner: LLMEffect, fixture: str, run_seq: int, budget: _RunBudget,
                 completed: set[str]):
        self._inner = inner
        self.fixture = fixture
        self.run_seq = run_seq
        self.budget = budget
        self.completed = completed
        self.stuck_seconds = inner.stuck_seconds

    async def call(self, req, *, stem, run_seq, attempt, call_seq):
        key = llm_key(self.fixture, self.run_seq, req.surface, attempt, call_seq)
        replay = key in self.completed
        if not replay:
            self.budget.check()
        result = await self._inner.call(
            req, stem=self.fixture, run_seq=self.run_seq, attempt=attempt, call_seq=call_seq)
        if not replay:
            self.completed.add(key)
            self.budget.observe(result.usd)
        return result


def resolved_identity(registry: Registry, spec: Spec) -> tuple[Identity, float]:
    resolved = registry.resolve(spec.tier, spec.surface)
    if PLACEHOLDER in (resolved.model, resolved.provider.auth):
        raise RoutingError(f"route ({spec.tier}, {spec.surface}) -> {resolved.provider.name} "
                           f"still carries the placeholder `{PLACEHOLDER}`; {PREREQUISITE}")
    fallback = resolved.provider.limits.est_cost_per_call_usd or 0.0
    return Identity(provider=resolved.provider.name, model=resolved.model, tier=spec.tier), fallback


def check_author_diversity(fixtures: Iterable[Fixture], identity: Identity
                           ) -> tuple[AuthorIdentity, ...]:
    authors: list[AuthorIdentity] = []
    for fixture in fixtures:
        author = fixture.expected.author
        if author not in authors:
            authors.append(author)
        if (author.provider, author.model, author.tier) == (
                identity.provider, identity.model, identity.tier):
            raise Refused(
                f"fixture {fixture.name} was authored by ({author.provider}, {author.model}) "
                f"at tier {author.tier}, the identity routed to DIAGNOSE at tier "
                f"{identity.tier}; re-author it with a different (provider, model), at "
                "minimum a different tier, or route DIAGNOSE elsewhere in config.yaml")
    return tuple(authors)


async def run(*, config: Config, seams: Seams, report_path: Path,
              state_dir: Path | None = None, fixtures_dir: Path = FIXTURES,
              spec_path: Path = SPEC, root: Path = ROOT, llm: LLM | None = None,
              usd_cap: float = USD_CAP, stuck_seconds: float = STUCK_SECONDS,
              out=None) -> DiagnosisEvalReport:
    out = out or sys.stdout
    registry = Registry(config)
    spec = load_spec(spec_path)
    identity, fallback = resolved_identity(registry, spec)
    fixtures = load_fixtures(fixtures_dir)
    authors = check_author_diversity(fixtures, identity)

    base_state = config.state_dir if config.state_dir.is_absolute() else root / config.state_dir
    state = Path(state_dir) if state_dir is not None else base_state / "eval-diagnose"
    if not state.is_absolute():
        state = root / state
    redactor = Redactor.from_config(config, seams.env)
    git = Git(seams.process, env=seams.env, timeout=GIT_TIMEOUT)
    sha = await git.rev_parse(root, "HEAD")
    llm = llm or CliClient(registry, process=seams.process, fs=seams.fs, env=seams.env,
                           redact=redactor, state_dir=state, cwd=root)
    spool = Spool(state, fs=seams.fs, redact=redactor)
    stage = diagnose_stage(spec, tier=spec.tier, effort=spec.effort)

    with Journal(state, clock=seams.clock) as journal:
        events = list(journal.read())
        run_seq = sum(event.type == "signal" and event.body.get("kind") == SIGNAL_KIND
                      for event in events)
        completed = {event.key for event in events
                     if event.type == "effect_completion" and event.key is not None}
        budget = _RunBudget(usd_cap, fallback)
        base_effect = LLMEffect(llm=llm, effects=Effects(journal), redact=redactor,
                                stuck_seconds=stuck_seconds)
        print(f"diagnosis-eval: {len(fixtures)} fixtures, DIAGNOSE -> "
              f"{identity.provider}/{identity.model} at tier {identity.tier}, "
              f"spec {spec.version}", file=out)
        scores: list[Score] = []
        stopped: StopReason | None = None
        not_run: list[str] = []
        for attempt, fixture in enumerate(fixtures, start=1):
            effect = _FixtureEffect(base_effect, fixture.name, run_seq, budget, completed)
            driver = Driver(
                llm=effect, spool=spool,
                log=EngineLog(state, clock=seams.clock, redact=redactor),
                clock=seams.clock, retry_cap=DIAGNOSE_RETRY_CAP)
            inputs = DiagnosisInput(
                stem=fixture.name, ticket=fixture.ticket, harvest=fixture.harvest_text,
                run_record=fixture.run_record, produced_by_spec_version="fixture",
                produced_at_sha=sha)
            result = await driver.run(stage, inputs, ticket=None, run_seq=run_seq,
                                      attempt=attempt, workspace=root, sha=sha)
            if result.outcome == "infra_error" and result.reason and "BudgetRefused:" in result.reason:
                stopped = "budget"
                # A refusal on the re-prompt follows a paid first call.  Keep
                # that terminal in the report so its cost cannot disappear;
                # only a refusal before call one leaves this fixture unrun.
                if result.cost.usd:
                    scores.append(score(fixture, result))
                    not_run = [item.name for item in fixtures[attempt:]]
                else:
                    not_run = [item.name for item in fixtures[attempt - 1:]]
                print(f"  [{attempt:02d}] stopped before {fixture.name}: {result.reason}", file=out)
                break
            item = score(fixture, result)
            scores.append(item)
            print(f"  [{attempt:02d}] {fixture.name}: {item.outcome} "
                  f"verdict={item.verdict} {'AGREE' if item.agreed else 'DISAGREE'}", file=out)

        summary = summarize(fixtures, scores, not_run)
        report = DiagnosisEvalReport(
            schema_version=1, produced_at_sha=sha, identity=identity,
            spec_version=spec.version, fixture_authors=authors, usd_cap=usd_cap,
            stuck_seconds=stuck_seconds, stopped=stopped, scores=tuple(scores), summary=summary)
        report_path = Path(report_path)
        seams.fs.write(report_path, (report.model_dump_json(indent=2) + "\n").encode())
        if stopped is None:
            signal = DiagnosisEvalSignal(kind=SIGNAL_KIND, summary=summary, identity=identity,
                                         report=str(report_path))
            journal.append("signal", signal.model_dump(mode="json"))
    _print_summary(report, out)
    return report


def _print_summary(report: DiagnosisEvalReport, out) -> None:
    summary = report.summary
    print(f"diagnosis-eval: scored {summary.scored}/{summary.fixtures}, "
          f"agreed {summary.agreed} ({summary.agreement_rate:.0%}), "
          f"unscored {summary.unscored}, cost ${summary.usd:.2f}", file=out)
    if report.stopped:
        print(f"stopped: {report.stopped}; not run: {', '.join(summary.not_run)}", file=out)


def check_report(path: Path, out=None) -> bool:
    out = out or sys.stdout
    try:
        report = DiagnosisEvalReport.model_validate_json(Path(path).read_text())
    except (OSError, ValueError, ValidationError) as exc:
        print(f"diagnosis-eval: invalid report {path}: {exc}", file=sys.stderr)
        return False
    _print_summary(report, out)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.diagnose", description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", type=Path, help="write the diagnosis evaluation report")
    mode.add_argument("--check", type=Path, help="validate and summarize an existing report")
    parser.add_argument("--config", type=Path, default=None,
                        help="instance config (default: config.yaml at the checkout root)")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument("--state", type=Path, default=None,
                        help="harness state (default: <config.state_dir>/eval-diagnose)")
    args = parser.parse_args(argv)
    if args.check is not None:
        return 0 if check_report(args.check) else 1
    try:
        config = load(args.config, cwd=ROOT)
        asyncio.run(run(config=config, seams=production_seams(), report_path=args.report,
                        state_dir=args.state, fixtures_dir=args.fixtures))
    except (ConfigError, RoutingError, Refused) as exc:
        print(f"diagnosis-eval: refused -- {exc}", file=sys.stderr)
        print("no model call made for the refused item; fix the named cause and re-run "
              "`uv run python -m eval.diagnose --report <path>`", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
