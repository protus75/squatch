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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from squatch.artifacts import Artifact, ClosedModel, Finding, StageResult
from squatch.config import Config, ConfigError, Tier, load
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Journal
from squatch.llm import LLM
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
    verdict: Literal["NO-GO"]
    tiers: tuple[Tier, ...]
    identity: dict[str, dict[str, Identity]]
    spec_version: dict[str, str | None]
    spec_major: dict[str, int | None]
    fixture_authors: tuple[AuthorIdentity, ...]
    summary: Summary
    scores: tuple[Score, ...]
    produced_at_sha: str
    spool: str


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
        run_seq = sum(1 for e in journal.read()
                      if e.type == "signal" and e.body.get("kind") == SIGNAL_KIND)
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
    args = parser.parse_args(argv)
    try:
        config = load(args.config, cwd=ROOT)
        asyncio.run(run(config=config, seams=production_seams(), fixtures_dir=args.fixtures))
    except (ConfigError, RoutingError, Unscored) as e:
        print(f"review-baseline: refused -- {e}", file=sys.stderr)
        print("no verdict recorded; continue with: uv run python -m eval.harness",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
