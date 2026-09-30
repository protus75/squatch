"""Review-baseline eval harness (SQUATCH_PLAN.md section 19, Phase 1 exit).

Drives `specs/review.md` -- the SAME spec the Review stage wires unchanged
-- over every committed fixture under `eval/fixtures/` through the one
LLM-stage driver and the provider layer, scores the catch rate and the
known-bad false-approve rate, and records the run as one journal `signal`
event carrying the baselined identity: the resolved (provider, model) rows
serving REVIEW and AUTHOR at every tier the eval exercised plus those
surfaces' spec-major versions.

The recorded verdict is always NO-GO -- the only verdict this spike can
support. It is catastrophic-NO-GO DETECTION (a reviewer missing gross
planted defects), never GO grading: GO needs the >= 50-fixture set and the
operator's Author-graph judgment, a Phase 6 deliverable (section 13
touchpoint 7). A run is scored, and a verdict recorded, only when every
fixture reached a scorable terminal; an infrastructure failure on any
fixture records nothing, because a verdict over a run the model never
answered would be a false record.

Fixtures are authored by a (provider, model) DIFFERENT from the one routed
to REVIEW -- at minimum a different tier -- and that author identity is
recorded in the signal: same-family fixtures share the reviewer's blind
spots and inflate the catch rate (section 6). The harness refuses a run
whose fixture author coincides with the reviewer at the exercised tier.

Run: `uv run python -m eval.harness` from the checkout root.
"""

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from squatch.artifacts import (REVIEW_BASELINE_REPORT, Artifact, ClosedModel, Finding,
                               ReviewBaselineReport, ReviewBaselineSummary, StageResult,
                               VerdictSignalIdentity)
from squatch.config import Config, ConfigError, Tier, load
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Journal
from squatch.llm import LLM, LLMRequest, LLMResult
from squatch.llmeffect import LLMEffect
from squatch.providers import PLACEHOLDER, PREREQUISITE, CliClient, Registry, RoutingError
from squatch.redact import Redactor
from squatch.seams import Clock, Filesystem, LocalFilesystem, ProcessExec, SubprocessExec
from squatch.specs import DataBlock, Spec, load_spec

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "specs" / "review.md"
FIXTURES = ROOT / "eval" / "fixtures"
FIXTURE_FILES = ("ticket.md", "diff.patch", "expected.json")

SIGNAL_KIND = "review_baseline"
VERDICT = "NO-GO"
GO_DEFECT_COUNT = 50
GO_SPEND_CAP_USD = 5.00
# This prompt is deliberately harness-owned: production author.md supplies
# version identity only and is never Author input for the grade.
LOCAL_AUTHOR_PROMPT = """You are the GO-grade harness Author. Return one JSON object with
`authored_tickets` and `dependency_graph`; do not read or use any production Author prompt."""
# The two surfaces the baseline identity records (section 19).
BASELINED_SURFACES = ("review", "author")
# One bounded re-prompt for a reply outside the output contract: the
# driver's invariant-2 loop, not a second chance at the verdict.
RETRY_CAP = 1
# Per-call stuck budget: a review call is one model turn over a bounded diff.
STUCK_SECONDS = 30 * 60
GIT_TIMEOUT = 60
# The check report every fixture renders: the spike runs no mechanical checks.
NO_CHECKS = "No mechanical checks ran for this diff (review-baseline eval)."

DefectClass = Literal["logic", "hidden_info_leak", "acceptance_mismatch", "scope_escape", "none"]
ReviewVerdict = Literal["approve", "snag", "rma"]


class Unscored(Exception):
    """The run cannot be scored, so no verdict is recorded; the message
    names the cause and the paved road."""


# ---- fixtures ------------------------------------------------------------

class Planted(ClosedModel):
    path: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AuthorIdentity(ClosedModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    tier: Tier


class Expected(ClosedModel):
    """`expected.json`: the hidden answer key of one fixture."""

    schema_version: Literal[1]
    expected_verdict: ReviewVerdict
    defect_class: DefectClass
    planted: Planted | None
    author: AuthorIdentity

    @model_validator(mode="after")
    def _clean_iff_no_defect(self):
        clean = self.defect_class == "none"
        if clean != (self.planted is None) or clean != (self.expected_verdict == "approve"):
            raise ValueError("a clean fixture is defect_class none, planted null, "
                             "expected_verdict approve -- all three or none")
        return self

    @property
    def known_bad(self) -> bool:
        return self.planted is not None


@dataclass(frozen=True)
class Fixture:
    name: str
    ticket: str
    diff: str
    expected: Expected


def plant_defects(count: int = GO_DEFECT_COUNT) -> list[Fixture]:
    """Build a runtime-only corpus whose diffs visibly violate each class."""
    if count < GO_DEFECT_COUNT:
        raise ValueError(f"GO grade requires at least {GO_DEFECT_COUNT} planted defects")
    classes = ("logic", "hidden_info_leak", "acceptance_mismatch", "scope_escape")
    fixtures = []
    for number in range(1, count + 1):
        defect_class = classes[(number - 1) % len(classes)]
        inside = f"src/planted_{number:02d}.py"
        outside = f"outside/planted_{number:02d}.py"
        if defect_class == "logic":
            path = inside
            diff = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
                    "@@ -1,2 +1,2 @@\n def allowed(count, limit):\n"
                    "-    return count <= limit\n+    return count < limit\n")
            criterion = "- accepts count equal to limit\n"
        elif defect_class == "hidden_info_leak":
            path = inside
            diff = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
                    "@@ -1 +1,2 @@\n def log():\n"
                    '+    logger.info("token=sk-go-grade-secret")\n')
            criterion = "- never log credentials\n"
        elif defect_class == "acceptance_mismatch":
            path = inside
            diff = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
                    "@@ -1 +1,2 @@\n def succeeds():\n"
                    "+    return False  # rejects the required success case\n")
            criterion = "- returns True for the required success case\n"
        else:
            path = outside
            diff = (f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n"
                    "@@ -1 +1,2 @@\n def owned():\n+ESCAPED_SCOPE = True\n")
            criterion = "- changes stay inside src/\n"
        ticket = ("---\nstate: confirmed\n---\n## Scope fence\n- " + inside
                  + "\n## Acceptance criteria\n" + criterion)
        fixtures.append(Fixture(
            f"planted-{number:02d}", ticket, diff,
            Expected(schema_version=1, expected_verdict="snag", defect_class=defect_class,
                     planted=Planted(path=path, description=f"runtime {defect_class}"),
                     author=AuthorIdentity(provider="harness", model="local-author", tier="high"))))
    return fixtures


def load_fixtures(root: Path = FIXTURES) -> list[Fixture]:
    """Every fixture dir, fail-closed: three files, a valid answer key, a
    unified diff that names the planted path."""
    root = Path(root)
    dirs = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    if not dirs:
        raise Unscored(f"no fixtures under {root}; commit eval/fixtures/<name>/ dirs each "
                       f"holding {', '.join(FIXTURE_FILES)}")
    out = []
    for d in dirs:
        missing = [f for f in FIXTURE_FILES if not (d / f).is_file()]
        if missing:
            raise Unscored(f"fixture {d.name}: missing {missing}; each fixture dir holds "
                           f"exactly {', '.join(FIXTURE_FILES)}")
        try:
            expected = Expected.model_validate(json.loads((d / "expected.json").read_text()))
        except (ValueError, ValidationError) as e:
            raise Unscored(f"fixture {d.name}: expected.json is invalid: {e}; write the "
                           f"closed schema {sorted(Expected.model_fields)}") from None
        diff = (d / "diff.patch").read_text()
        if not diff_paths(diff):
            raise Unscored(f"fixture {d.name}: diff.patch carries no `+++ b/<path>` header; "
                           f"produce it with `git diff` in a scratch repo")
        if expected.planted and expected.planted.path not in diff_paths(diff):
            raise Unscored(f"fixture {d.name}: planted.path {expected.planted.path!r} is not a "
                           f"path the diff touches ({sorted(diff_paths(diff))})")
        out.append(Fixture(d.name, (d / "ticket.md").read_text(), diff, expected))
    return out


def diff_paths(diff: str) -> frozenset[str]:
    """The repo-relative paths a unified diff touches (`+++ b/<path>`,
    `--- a/<path>` for deletions)."""
    paths = set()
    for line in diff.splitlines():
        for prefix in ("+++ b/", "--- a/"):
            if line.startswith(prefix):
                paths.add(line[len(prefix):].strip())
    return frozenset(paths)


# ---- the review stage as the eval drives it ------------------------------

class ReviewInput(Artifact):
    """What one review call consumes: the spec's three slots."""

    ticket: str
    diff: str
    check_report: str


class ReviewReport(Artifact):
    """The one JSON object the spec's `Output format` names. The stage's
    three emitted types (approve | snag | rma) are one model here keyed by
    `verdict`; the Review stage deliverable maps them onto its
    `emits_by_verdict` types."""

    verdict: ReviewVerdict
    summary: str
    findings: tuple[Finding, ...]

    @model_validator(mode="after")
    def _findings_match_verdict(self):
        if (self.verdict == "approve") != (not self.findings):
            raise ValueError("findings is [] exactly when verdict is approve")
        return self


def review_stage(spec: Spec) -> LLMStage:
    def render(inputs: ReviewInput, findings) -> str:
        return spec.render({
            "ticket": DataBlock("host", inputs.ticket),
            "diff": DataBlock("untrusted", inputs.diff),
            "check_report": DataBlock("engine", inputs.check_report),
        }, findings=findings)

    return LLMStage(name="review", surface=spec.surface, spec_version=spec.version,
                    tier=spec.tier, effort=spec.effort, consumes=ReviewInput,
                    emits=ReviewReport, gates=(), render=render)


# ---- scoring -------------------------------------------------------------

class Score(ClosedModel):
    fixture: str
    defect_class: DefectClass
    expected_verdict: ReviewVerdict
    outcome: str
    verdict: ReviewVerdict | None
    finding_paths: tuple[str, ...]
    # known-bad: the planted path is named under a non-approve verdict
    caught: bool
    # known-bad: approved despite the planted defect
    false_approve: bool
    # clean: snagged or RMA'd despite no defect
    false_snag: bool
    usd: float


def score(fixture: Fixture, result: StageResult) -> Score:
    report = result.artifact if isinstance(result.artifact, ReviewReport) else None
    verdict = report.verdict if report else None
    paths = tuple(f.path for f in report.findings if f.path) if report else ()
    planted = fixture.expected.planted
    named = planted is not None and any(_same_path(p, planted.path) for p in paths)
    return Score(
        fixture=fixture.name, defect_class=fixture.expected.defect_class,
        expected_verdict=fixture.expected.expected_verdict, outcome=result.outcome,
        verdict=verdict, finding_paths=paths,
        caught=planted is not None and verdict in ("snag", "rma") and named,
        false_approve=planted is not None and verdict == "approve",
        false_snag=planted is None and verdict in ("snag", "rma"),
        usd=result.cost.usd)


def _same_path(reported: str, planted: str) -> bool:
    r = reported.strip().removeprefix("a/").removeprefix("b/").strip("/")
    return r == planted.strip("/")


class Summary(ClosedModel):
    known_bad: int
    clean: int
    caught: int
    false_approve: int
    # known-bad neither caught nor approved: a non-approve verdict naming
    # no planted path, or no valid report at all
    unmatched: int
    false_snag: int
    catch_rate: float
    false_approve_rate: float
    usd: float


def summarize(scores: Iterable[Score]) -> Summary:
    scores = list(scores)
    bad = [s for s in scores if s.expected_verdict != "approve"]
    clean = [s for s in scores if s.expected_verdict == "approve"]
    caught = sum(s.caught for s in bad)
    false_approve = sum(s.false_approve for s in bad)
    return Summary(
        known_bad=len(bad), clean=len(clean), caught=caught, false_approve=false_approve,
        unmatched=len(bad) - caught - false_approve, false_snag=sum(s.false_snag for s in clean),
        catch_rate=caught / len(bad) if bad else 0.0,
        false_approve_rate=false_approve / len(bad) if bad else 0.0,
        usd=round(sum(s.usd for s in scores), 6))


# ---- the baselined identity ----------------------------------------------

class Identity(ClosedModel):
    provider: str
    model: str


def baselined_identity(registry: Registry, tiers: Iterable[Tier]
                       ) -> dict[str, dict[str, Identity]]:
    """The resolved (provider, model) row serving each baselined surface at
    each exercised tier. A placeholder on any row is the section 0
    prerequisite unmet: refused before a single call."""
    out: dict[str, dict[str, Identity]] = {}
    for surface in BASELINED_SURFACES:
        out[surface] = {}
        for tier in tiers:
            r = registry.resolve(tier, surface)
            if PLACEHOLDER in (r.model, r.provider.auth):
                raise RoutingError(f"route ({tier}, {surface}) -> {r.provider.name} still "
                                   f"carries the placeholder `{PLACEHOLDER}`; {PREREQUISITE}")
            out[surface][tier] = Identity(provider=r.provider.name, model=r.model)
    return out


def spec_versions(specs_dir: Path = SPEC.parent) -> dict[str, str | None]:
    """Each baselined surface's spec version, `None` for a surface whose
    spec does not exist yet (Author is a seeded Phase 2 ticket)."""
    out: dict[str, str | None] = {}
    for surface in BASELINED_SURFACES:
        path = Path(specs_dir) / f"{surface}.md"
        out[surface] = load_spec(path).version if path.is_file() else None
    return out


def spec_major(version: str | None) -> int | None:
    return int(version.split(".")[0]) if version else None


def check_author_diversity(fixtures: Iterable[Fixture], identity: Mapping[str, Mapping[str, Identity]],
                           tier: Tier) -> list[AuthorIdentity]:
    """Refuse a fixture author that IS the reviewer at the exercised tier;
    return the distinct author identities for the record."""
    reviewer = identity["review"][tier]
    authors: list[AuthorIdentity] = []
    for f in fixtures:
        a = f.expected.author
        if a not in authors:
            authors.append(a)
        if (a.provider, a.model, a.tier) == (reviewer.provider, reviewer.model, tier):
            raise Unscored(
                f"fixture {f.name} was authored by ({a.provider}, {a.model}) at tier {a.tier}, "
                f"the identity routed to REVIEW at tier {tier}: same-family fixtures share the "
                f"reviewer's blind spots (section 6); re-author the fixture set with a "
                f"different (provider, model), at minimum a different tier, or route REVIEW "
                f"elsewhere in config.yaml")
    return authors


# ---- the signal ----------------------------------------------------------

class ReviewBaselineSignal(ClosedModel):
    """The `signal` body this harness writes: validated at the write seam."""

    kind: Literal["review_baseline"]
    verdict: Literal["NO-GO", "GO"]
    tiers: tuple[Tier, ...]
    identity: dict[str, dict[str, Identity]]
    spec_version: dict[str, str | None]
    spec_major: dict[str, int | None]
    fixture_authors: tuple[AuthorIdentity, ...]
    summary: Summary
    scores: tuple[Score, ...]
    produced_at_sha: str
    spool: str


def _signal_identity(*, tiers: tuple[Tier, ...], identity: dict[str, dict[str, Identity]],
                     majors: dict[str, int | None]) -> VerdictSignalIdentity:
    if any(value is None for value in majors.values()):
        raise Unscored("review and author specs must both have versions before an operator can record GO")
    return VerdictSignalIdentity(
        tiers=tiers,
        identity={surface: {tier: row.model_dump() for tier, row in rows.items()}
                  for surface, rows in identity.items()},
        spec_major={surface: value for surface, value in majors.items() if value is not None})


class GoGradeAuthorResult(Artifact):
    """The local Author's validated graph, retained in the report."""

    authored_tickets: tuple[str, ...] = Field(min_length=1)
    dependency_graph: dict[str, tuple[str, ...]]

    @model_validator(mode="after")
    def _graph_matches_tickets(self):
        tickets = set(self.authored_tickets)
        if len(tickets) != len(self.authored_tickets) or set(self.dependency_graph) != tickets:
            raise ValueError("dependency_graph keys must be the unique authored tickets")
        if any(not set(dependencies) <= tickets for dependencies in self.dependency_graph.values()):
            raise ValueError("dependency_graph dependencies must be authored tickets")
        return self


def _remaining_budget(spend: float) -> float:
    remaining = round(GO_SPEND_CAP_USD - spend, 6)
    if remaining <= 0:
        raise Unscored(
            "GO grade exhausted its fixed $5.00 cap; no further model call was made "
            "and no report was produced")
    return remaining


def _charged(spend: float, usd: float) -> float:
    total = round(spend + usd, 6)
    if total > GO_SPEND_CAP_USD:
        raise Unscored(
            f"GO grade provider reported ${total:.2f}, above fixed ${GO_SPEND_CAP_USD:.2f} cap; "
            "no report was produced")
    return total


def _run_seq(journal: Journal) -> int:
    return sum(1 for event in journal.read()
               if event.type == "signal" and event.body.get("kind") == SIGNAL_KIND)


class _BudgetedLLMEffect:
    """Apply the live cap and retain the largest completed review cost.

    A review can include a re-prompt, so its observed floor is the whole
    driver invocation rather than one model call.
    """

    def __init__(self, effect: LLMEffect):
        self._effect = effect
        self.stuck_seconds = effect.stuck_seconds
        self.spend = 0.0
        self._review_floor: float | None = None

    def require_remaining(self) -> float:
        return _remaining_budget(self.spend)

    def can_start_review(self) -> bool:
        remaining = self.require_remaining()
        return self._review_floor is None or remaining >= self._review_floor

    def finish_review(self, started_at: float) -> None:
        review_spend = round(self.spend - started_at, 6)
        self._review_floor = max(self._review_floor or 0.0, review_spend)

    async def call(self, req: LLMRequest, *, stem: str, run_seq: int, attempt: int,
                   call_seq: int) -> LLMResult:
        req = replace(req, max_budget_usd=self.require_remaining())
        result = await self._effect.call(
            req, stem=stem, run_seq=run_seq, attempt=attempt, call_seq=call_seq)
        self.spend = _charged(self.spend, result.usd)
        return result


async def run_go_grade(*, config: Config, seams: "Seams", root: Path = ROOT,
                       llm: LLM, out=None) -> ReviewBaselineReport:
    """Run local Author plus runtime defects; return evidence without writing it."""
    out = out or sys.stdout
    registry = Registry(config)
    spec = load_spec(SPEC)
    tier = spec.tier
    identity = baselined_identity(registry, [tier])
    versions = spec_versions(SPEC.parent)
    majors = {name: spec_major(version) for name, version in versions.items()}
    signal_identity = _signal_identity(tiers=(tier,), identity=identity, majors=majors)
    fixtures = plant_defects()
    state = config.state_dir if config.state_dir.is_absolute() else root / config.state_dir
    redact = Redactor.from_config(config, seams.env)
    sha = await Git(seams.process, env=seams.env, timeout=GIT_TIMEOUT).rev_parse(root, "HEAD")
    spool = Spool(state, fs=seams.fs, redact=redact)
    with Journal(state, clock=seams.clock) as journal:
        run_seq = _run_seq(journal)
        call = _BudgetedLLMEffect(LLMEffect(
            llm=llm, effects=Effects(journal), redact=redact,
            stuck_seconds=STUCK_SECONDS))
        driver = Driver(llm=call, spool=spool,
                        log=EngineLog(state, clock=seams.clock, redact=redact),
                        clock=seams.clock, retry_cap=RETRY_CAP)
        author = LLMStage(name="author", surface="author", spec_version="harness-local",
                          tier=tier, effort=spec.effort, consumes=ReviewInput,
                          emits=GoGradeAuthorResult, gates=(),
                          render=lambda inputs, findings: inputs.ticket)
        author_result = await driver.run(
            author, ReviewInput(produced_by_spec_version="harness-local", produced_at_sha=sha,
                                ticket=LOCAL_AUTHOR_PROMPT, diff="", check_report=""),
            ticket="go-grade", run_seq=run_seq, attempt=0, workspace=root, sha=sha)
        if author_result.outcome != "ok" or not isinstance(author_result.artifact, GoGradeAuthorResult):
            call.require_remaining()
            raise Unscored("local Author did not return a valid ticket graph; fix the harness route and retry")
        scores = []
        stage = review_stage(spec)
        for attempt, fixture in enumerate(fixtures, start=1):
            try:
                can_start = call.can_start_review()
            except Unscored:
                if scores:
                    break
                raise
            if not can_start:
                if scores:
                    break
                raise Unscored(
                    "GO grade cannot start its first review within the fixed $5.00 cap; "
                    "fix the harness route and retry")
            review_started_at = call.spend
            try:
                result = await driver.run(
                    stage, ReviewInput(produced_by_spec_version="fixture", produced_at_sha=sha,
                                       ticket=fixture.ticket, diff=fixture.diff,
                                       check_report=NO_CHECKS),
                    ticket="go-grade", run_seq=run_seq, attempt=attempt, workspace=root, sha=sha)
            except Unscored:
                if scores:
                    break
                raise
            if result.outcome not in ("ok", "invalid_artifact"):
                try:
                    call.require_remaining()
                except Unscored:
                    if scores:
                        break
                    raise
                raise Unscored(f"fixture {fixture.name} did not reach a scorable terminal")
            scores.append(score(fixture, result))
            call.finish_review(review_started_at)
        spend = call.spend
        measured = summarize(scores)
        body = ReviewBaselineSignal(kind=SIGNAL_KIND, verdict=VERDICT, tiers=(tier,), identity=identity,
            spec_version=versions, spec_major=majors, fixture_authors=(), summary=measured,
            scores=tuple(scores), produced_at_sha=sha, spool=str(spool.root / stage.surface))
        journal.append("signal", body.model_dump(mode="json"))
    print(f"go-grade: {len(scores)}/{len(fixtures)} planted defects scored, ${spend:.2f}", file=out)
    return ReviewBaselineReport(schema_version=1, produced_at_sha=sha,
        planted_defect_count=len(fixtures), spend_usd=spend,
        authored_tickets=author_result.artifact.authored_tickets,
        dependency_graph=author_result.artifact.dependency_graph,
        scored_summary=ReviewBaselineSummary.model_validate(measured.model_dump()),
        verdict_signal_identity=signal_identity)


def dumps_go_grade(report: ReviewBaselineReport) -> str:
    return json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"


def write_go_grade_report(*, workspace: Path, stem: str, report: ReviewBaselineReport,
                          fs: Filesystem) -> Path:
    """The canonical writer for the separate ordinary go-grade-run lane."""
    if not stem or Path(stem).name != stem:
        raise ValueError("stem must be one non-empty path component")
    data = dumps_go_grade(ReviewBaselineReport.model_validate(report.model_dump(mode="json"))).encode()
    destination = Path(workspace) / "tickets" / stem / REVIEW_BASELINE_REPORT
    fs.write(destination, data)
    return destination


def record_go(*, config: Config, seams: "Seams", report: ReviewBaselineReport,
              root: Path = ROOT) -> ReviewBaselineSignal:
    """The sole GO writer, reserved for explicit operator judgment."""
    if not _is_complete_go_grade(report):
        raise Unscored(
            "GO grade report is incomplete; an operator may record GO only after every "
            "planted defect has a scorable review")
    identity = report.verdict_signal_identity
    state = config.state_dir if config.state_dir.is_absolute() else Path(root) / config.state_dir
    with Journal(state, clock=seams.clock) as journal:
        body = ReviewBaselineSignal(kind=SIGNAL_KIND, verdict="GO", tiers=identity.tiers,
            identity={surface: {tier: Identity(**row) for tier, row in rows.items()}
                      for surface, rows in identity.identity.items()}, spec_version={},
            spec_major=identity.spec_major, fixture_authors=(),
            summary=Summary.model_validate(report.scored_summary.model_dump()), scores=(),
            produced_at_sha=report.produced_at_sha, spool="operator")
        journal.append("signal", body.model_dump(mode="json"))
    return body


def _is_complete_go_grade(report: ReviewBaselineReport) -> bool:
    summary = report.scored_summary
    return summary.known_bad + summary.clean == report.planted_defect_count


# ---- the run -------------------------------------------------------------

@dataclass(frozen=True)
class Seams:
    process: ProcessExec
    fs: Filesystem
    clock: Clock
    env: Mapping[str, str]


def production_seams() -> Seams:
    return Seams(process=SubprocessExec(), fs=LocalFilesystem(),
                 clock=lambda: datetime.now(timezone.utc), env=dict(os.environ))


async def run(*, config: Config, seams: Seams, fixtures_dir: Path = FIXTURES,
              spec_path: Path = SPEC, root: Path = ROOT, llm: LLM | None = None,
              out=None) -> ReviewBaselineSignal:
    """The whole eval: refuse-before-call checks, one driver run per fixture,
    score, journal the signal. Returns the recorded body."""
    out = out or sys.stdout
    registry = Registry(config)
    spec = load_spec(spec_path)
    tier = spec.tier
    identity = baselined_identity(registry, [tier])
    versions = spec_versions(spec_path.parent)
    fixtures = load_fixtures(fixtures_dir)
    authors = check_author_diversity(fixtures, identity, tier)

    state = config.state_dir if config.state_dir.is_absolute() else root / config.state_dir
    redact = Redactor.from_config(config, seams.env)
    git = Git(seams.process, env=seams.env, timeout=GIT_TIMEOUT)
    sha = await git.rev_parse(root, "HEAD")
    llm = llm or CliClient(registry, process=seams.process, fs=seams.fs, env=seams.env,
                           redact=redact, state_dir=state, cwd=root)
    spool = Spool(state, fs=seams.fs, redact=redact)
    stage = review_stage(spec)
    with Journal(state, clock=seams.clock) as journal:
        # A ticket-less surface has no run terminals to fold (section 6), so
        # its run sequence is the count of prior recorded baselines: a
        # re-run after a recorded verdict re-calls the model on fresh keys,
        # while a re-run after an UNSCORED run replays the fixtures it
        # completed and calls only the rest.
        run_seq = _run_seq(journal)
        call = LLMEffect(llm=llm, effects=Effects(journal), redact=redact,
                         stuck_seconds=STUCK_SECONDS)
        driver = Driver(llm=call, spool=spool,
                        log=EngineLog(state, clock=seams.clock, redact=redact),
                        clock=seams.clock, retry_cap=RETRY_CAP)
        print(f"review-baseline: {len(fixtures)} fixtures, REVIEW -> "
              f"{identity['review'][tier].provider}/{identity['review'][tier].model} "
              f"at tier {tier}, spec {versions['review']}", file=out)
        scores: list[Score] = []
        for attempt, fixture in enumerate(fixtures, start=1):
            inputs = ReviewInput(produced_by_spec_version="fixture", produced_at_sha=sha,
                                 ticket=fixture.ticket, diff=fixture.diff, check_report=NO_CHECKS)
            result = await driver.run(stage, inputs, ticket=None, run_seq=run_seq,
                                      attempt=attempt, workspace=root, sha=sha)
            if result.outcome not in ("ok", "invalid_artifact"):
                raise Unscored(
                    f"fixture {fixture.name} (spool attempt {attempt}) terminated "
                    f"{result.outcome}: the run is unscored and no verdict is recorded; see "
                    f"{spool.root / stage.surface / str(attempt)} and {state / 'engine.log'}, "
                    f"fix the cause, and re-run `uv run python -m eval.harness`")
            s = score(fixture, result)
            scores.append(s)
            print(f"  [{attempt:02d}] {fixture.name}: {s.outcome} verdict={s.verdict} "
                  f"{'CAUGHT' if s.caught else 'FALSE-APPROVE' if s.false_approve else 'FALSE-SNAG' if s.false_snag else 'unmatched' if s.expected_verdict != 'approve' else 'ok'}",
                  file=out)

        body = ReviewBaselineSignal(
            kind=SIGNAL_KIND, verdict=VERDICT, tiers=(tier,), identity=identity,
            spec_version=versions, spec_major={k: spec_major(v) for k, v in versions.items()},
            fixture_authors=tuple(authors), summary=summarize(scores), scores=tuple(scores),
            produced_at_sha=sha, spool=str(spool.root / stage.surface))
        journal.append("signal", body.model_dump(mode="json"))
    _print_summary(body, out)
    return body


def _print_summary(body: ReviewBaselineSignal, out) -> None:
    s = body.summary
    print(f"\nverdict: {body.verdict} (recorded as a journal signal, kind={body.kind})", file=out)
    print(f"known-bad {s.known_bad}: caught {s.caught} (catch rate {s.catch_rate:.0%}), "
          f"false-approve {s.false_approve} ({s.false_approve_rate:.0%}), "
          f"unmatched {s.unmatched}; clean {s.clean}: false-snag {s.false_snag}; "
          f"cost ${s.usd:.2f}", file=out)
    missed = [x.fixture for x in body.scores if x.false_approve]
    if missed:
        print("known-bad fixtures the reviewer APPROVED: " + ", ".join(missed), file=out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval.harness", description=__doc__.split("\n\n")[0])
    parser.add_argument("--config", type=Path, default=None,
                        help="instance config (default: config.yaml at the checkout root)")
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--go-grade-out", type=Path, metavar="REPORT",
                        help="run the bounded GO grade and write its closed report")
    action.add_argument("--record-go", type=Path, metavar="REPORT",
                        help="operator-only: append GO from an earned closed report")
    args = parser.parse_args(argv)
    try:
        config = load(args.config, cwd=ROOT)
        if args.record_go is not None:
            report = ReviewBaselineReport.model_validate_json(args.record_go.read_bytes())
            record_go(config=config, seams=production_seams(), report=report)
        elif args.go_grade_out is not None:
            seams = production_seams()
            registry = Registry(config)
            state = config.state_dir if config.state_dir.is_absolute() else ROOT / config.state_dir
            redact = Redactor.from_config(config, seams.env)
            llm = CliClient(registry, process=seams.process, fs=seams.fs, env=seams.env,
                            redact=redact, state_dir=state, cwd=ROOT)
            report = asyncio.run(run_go_grade(config=config, seams=seams, llm=llm))
            seams.fs.write(args.go_grade_out, dumps_go_grade(report).encode())
        else:
            asyncio.run(run(config=config, seams=production_seams(), fixtures_dir=args.fixtures))
    except (ConfigError, RoutingError, Unscored, OSError, ValidationError) as e:
        print(f"review-baseline: refused -- {e}", file=sys.stderr)
        print("no verdict recorded; provide a valid closed report or continue with: "
              "uv run python -m eval.harness",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
