"""The Implement, Check, and Review stages (SQUATCH_PLAN.md sections 4, 5, 7,
9, 10; section 19, Phase 2).

One run of `Stages.run` is Implement -> Check -> Review over one ticket in
one fresh worktree, every external action a run-scoped effect: the
worktree's teardown-and-create, each model call (the driver's LLM effect),
the mechanical check, and every ticket-plane commit. Implement is the one
surface granted the tree: the agent CLI runs inside the worktree, commits
code on the branch, and leaves its run record in the outbox
(`tickets/<stem>/` inside the worktree) that this layer lifts into the
canonical ticket dir -- one ticket-plane commit per stage terminal. Check is
the mechanical stage: the four v1 codes over the packing slip, persisted as
`checks.json`, a hard failure ending the run `gate_failed` with the invoice
durable as the re-entry's source. Review wires `specs/review.md` unchanged
over the committed diff and emits one of three artifacts by verdict; a
`snag` is `gate_failed` (the review surface is a gate) and an `rma` is
`premise_failed` (the ticket is the problem). The merge admission
(`squatch.merge`) settles what this layer delivers.

Re-entry is findings-fed (section 11.2): when the journal says the stem's
prior run ended without merging, Implement's render folds the terminal
findings artifacts already durable in the canonical ticket dir -- a
`review.md` whose verdict rejects, a `checks.json` that fails -- into the
spec's `prior_attempts` slot, placed by `specs/implement.md` right after
the ticket so the clear-these-findings block sits in criteria-position.
Rendered fresh each attempt from the artifacts, never written into
`ticket.md`; a first attempt renders no such block. Harvest extends this one
block with bounded worktree-only material, never a second path.
"""

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

import squatch
from squatch.artifacts import (DAEMON_SOAK_REPORT, OUTCOMES, Artifact, ClosedModel, Cost,
                               DaemonSoakReport, Finding, StageResult)
from squatch.box import Box
from squatch.config import Config, Severity
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects, effect_key, latest_terminal
from squatch.enginelog import EngineLog
from squatch.gates import GateReport, GateRun, run_gates
from squatch.git import Git, GitError
from squatch.harvest import HARVEST_FILE, HARVEST_RENDER_CHARS, Harvest
from squatch.journal import Journal
from squatch.llm import Effort
from squatch.llmeffect import LLMEffect
from squatch.providers import CliClient, Registry, child_env
from squatch.redact import Redactor
from squatch.seams import Clock, Filesystem, ProcessExec
from squatch.shakeout import REPORT_NAME, ShakeoutReport
from squatch.specs import DATA_MARKER, DataBlock, RenderRefused, Spec, load_spec
from squatch.seeds import (SEED_LIFT_SIGNAL, Seed, authored_seeds, blob_sha, reviewed_seeds,
                           validate_batch)
from squatch.tickets import (PLAN_FILE, TICKET_FILE, TICKETS_DIR, Intake, Ticket,
                             lint_ticket, parse_frontmatter, stamp)

SPECS_DIR = Path(squatch.__file__).resolve().parent.parent / "specs"
RUN_RECORD = "run.md"
CHECKS = "checks.json"
REVIEW = "review.md"
# The closed section set the run_record gate validates (section 13).
RUN_RECORD_SECTIONS: tuple[str, ...] = (
    "Outcome", "Surprises / judgment calls", "Dead ends", "Second problems filed",
    "Resolved engine/model", "Predicted vs actual")
# The Check stage's gate set: the v1 hard codes that validate the packing
# slip (section 7), in run order. Check has no prompt spec; this is its version.
CHECK_CODES: tuple[str, ...] = ("scope_fence", "verification", "run_record", "diff_budget")
CHECK_VERSION = "1.0"
# Engine constants, not config: the reviewable-diff cap (section 7).
DIFF_BUDGET_FILES = 30
DIFF_BUDGET_LINES = 1500
SPLIT_ROAD = "split the ticket (diagnosis verdict `split`, section 11)"

# Names in this registry are validated before any bytes from an outbox are
# written. Unregistered evidence remains intentionally open as section 10's
# ordinary ticket-plane lane requires.
KNOWN_ARTIFACTS = {
    REPORT_NAME: ShakeoutReport.model_validate_json,
    DAEMON_SOAK_REPORT: DaemonSoakReport.model_validate_json,
}

ImplementVerdict = Literal["implemented", "already_satisfied", "premise_failed"]
ReviewVerdictName = Literal["approve", "snag", "rma"]

_H2 = re.compile(r"^## (.+?)\s*$")


# ---- artifacts ----------------------------------------------------------------

class ImplementInput(Artifact):
    """What Implement consumes: the ticket and its read-first material at
    the base commit."""

    stem: str
    ticket: str
    context: tuple[tuple[str, str], ...]
    plan_sections: tuple[str, ...]


class ImplementReport(Artifact):
    """The one JSON object the implement spec's Output format names."""

    verdict: ImplementVerdict
    summary: str = Field(min_length=1)


class PackingSlip(Artifact):
    """Implement's emitted artifact: the branch plus the run record in the
    outbox, stamped at the branch head."""

    stem: str
    verdict: ImplementVerdict
    summary: str
    branch: str
    base: str
    head: str


class VerificationCommand(ClosedModel):
    argv: tuple[str, ...]
    attribution: Literal["base", "branch"] | None = None
    filed: str | None = None


class CheckEntry(ClosedModel):
    code: str
    verdict: Literal["pass", "fail"]
    severity: Severity
    path: str | None = None
    sha: str | None = None
    # A failing code the ticket's gate_bypass valve named: recorded, never hidden.
    bypassed: bool = False
    findings: tuple[Finding, ...] = ()
    commands: tuple[VerificationCommand, ...] = ()


class Invoice(Artifact):
    """Check's emitted artifact: the structured check report (`checks.json`)."""

    stem: str
    branch: str
    base: str
    head: str
    changed_files: tuple[str, ...]
    checks: tuple[CheckEntry, ...]

    @property
    def passed(self) -> bool:
        return not self.hard_findings

    @property
    def hard_findings(self) -> tuple[Finding, ...]:
        return self._findings("hard")

    @property
    def soft_findings(self) -> tuple[Finding, ...]:
        return self._findings("soft")

    def _findings(self, severity: Severity) -> tuple[Finding, ...]:
        return tuple(f for c in self.checks if c.verdict == "fail" and c.severity == severity
                     for f in c.findings)


class ReviewReport(Artifact):
    """The one JSON object `specs/review.md`'s Output format names."""

    verdict: ReviewVerdictName
    summary: str
    findings: tuple[Finding, ...]

    @model_validator(mode="after")
    def _findings_match_verdict(self):
        if (self.verdict == "approve") != (not self.findings):
            raise ValueError("findings is [] exactly when verdict is approve")
        return self


class ReviewVerdict(Artifact):
    """Review's emitted artifact, pinned to the reviewed SHA; one concrete
    type per verdict (`emits_by_verdict`, section 5)."""

    stem: str
    verdict: ReviewVerdictName
    summary: str
    findings: tuple[Finding, ...]
    reviewed_sha: str
    provider: str | None
    model: str | None


class ApprovedInvoice(ReviewVerdict):
    verdict: Literal["approve"]


class SnagList(ReviewVerdict):
    verdict: Literal["snag"]


class RMA(ReviewVerdict):
    verdict: Literal["rma"]


REVIEW_EMITS: Mapping[str, type[ReviewVerdict]] = {
    "approve": ApprovedInvoice, "snag": SnagList, "rma": RMA}
# A snag is a gate failure (the review surface is a gate, section 11.1); an
# RMA says the ticket is the problem, the premise_failed route to Requisition.
REVIEW_OUTCOMES: Mapping[str, str] = {
    "approve": "ok", "snag": "gate_failed", "rma": "premise_failed"}


def _add_cost(*costs: Cost) -> Cost:
    return Cost(tokens=sum(c.tokens for c in costs), seconds=sum(c.seconds for c in costs),
                attempts=sum(c.attempts for c in costs), usd=sum(c.usd for c in costs),
                provider=next((c.provider for c in reversed(costs) if c.provider), None),
                model=next((c.model for c in reversed(costs) if c.model), None))


def _terminal_reason(result: StageResult) -> str | None:
    """Findings carry their own detail; empty terminal results still name their wall."""
    return None if result.findings else result.outcome


def render_review(v: ReviewVerdict) -> str:
    """`review.md`: the pinned verdict in frontmatter (the merge gate's
    on-disk input), the summary and findings as the body."""
    head = {"verdict": v.verdict, "reviewed_sha": v.reviewed_sha,
            "produced_by_spec_version": v.produced_by_spec_version,
            "produced_at_sha": v.produced_at_sha, "provider": v.provider, "model": v.model,
            "artifact_schema_version": v.artifact_schema_version}
    findings = "".join(f"- {f.code}{_where(f)}: {f.message} (paved road: {f.paved_road})\n"
                       for f in v.findings) or "- none\n"
    return ("---\n" + yaml.safe_dump(head, sort_keys=False) + "---\n"
            f"## Summary\n{v.summary}\n\n## Findings\n{findings}")


def load_review(text: str) -> dict:
    """The frontmatter of a `review.md`: verdict, reviewed_sha, provenance."""
    meta, _ = parse_frontmatter(text)
    return meta


def _where(f: Finding) -> str:
    return (f" at {f.path}" + (f":{f.line}" if f.line else "")) if f.path else ""



# ---- the Check gates ----------------------------------------------------------

def _outside_fence(path: str, stem: str, fence: Sequence[str]) -> bool:
    outbox = f"{TICKETS_DIR}/{stem}/"
    if path.startswith(outbox):
        return path == f"{outbox}{TICKET_FILE}"  # the no-self-editing rule
    return not any(path == p or path.startswith(p if p.endswith("/") else p + "/")
                   for p in fence)


class ScopeFence:
    code = "scope_fence"
    paved_road = ("edit only paths under the ticket's `## Scope fence` prefixes; a criterion "
                  "that forces an out-of-fence edit is an authoring defect (answer "
                  "premise_failed), and a genuine surprise takes the gate_bypass valve")

    def __init__(self, git: Git, repo: Path, ticket: Ticket):
        self._git, self._repo, self._ticket = git, repo, ticket

    async def check(self, slip: PackingSlip, workspace: Path) -> GateReport:
        names = await self._git.diff_names(self._repo, slip.base, slip.branch)
        findings = tuple(
            Finding(code=self.code, path=p, paved_road=self.paved_road,
                    message=f"{p} is outside the scope fence {list(self._ticket.scope_fence)}")
            for p in names if _outside_fence(p, slip.stem, self._ticket.scope_fence))
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=findings)


class Verification:
    """The ticket's own `## Verification` commands on the committed branch."""

    code = "verification"
    paved_road = "make every `## Verification` command exit 0 on the committed branch"

    def __init__(self, git: Git, repo: Path, process: ProcessExec, ticket: Ticket,
                 env: Mapping[str, str], redact: Redactor, *, box: Box | None = None,
                 base_worktree: Path | None = None, run_seq: int | None = None,
                 allow_empty: bool = False):
        self._git, self._repo, self._process, self._ticket = git, repo, process, ticket
        self._env, self._redact = env, redact
        self._box, self._base_worktree, self._run_seq = box, base_worktree, run_seq
        self._allow_empty = allow_empty
        self.commands: tuple[VerificationCommand, ...] = ()

    async def check(self, slip: PackingSlip, workspace: Path) -> GateReport:
        findings = []
        names = await self._git.diff_names(self._repo, slip.base, slip.branch)
        # The one sanctioned empty-diff settlement is a PROVEN already_satisfied.
        if slip.verdict == "already_satisfied" and names:
            findings.append(Finding(
                code=self.code, paved_road="an already_satisfied answer commits nothing; "
                "answer implemented for a diff",
                message=f"already_satisfied claimed but the branch carries a committed diff: "
                        f"{', '.join(names)}"))
        if slip.verdict != "already_satisfied" and not names and not self._allow_empty:
            findings.append(Finding(
                code=self.code, message="the branch carries no committed diff",
                paved_road="commit the work on the branch before answering; only the "
                           "committed diff is checked and reviewed"))
        timeout = self._ticket.stuck_minutes * 60
        base_created = False
        base_create_error: Exception | None = None
        commands: list[VerificationCommand] = []
        attribution_enabled = bool(names and self._box is not None and self._base_worktree
                                   is not None and self._run_seq is not None)
        try:
            for argv in self._ticket.verification:
                rc, out, err = await self._process.run(
                    list(argv), cwd=workspace, env=self._env, timeout=timeout)
                # Scrubbed once at receipt (section 6): the tail becomes a Finding
                # that the check completion journals and the checks.json lift commits.
                out, err = self._redact(out), self._redact(err)
                if rc == 0:
                    commands.append(VerificationCommand(argv=tuple(argv)))
                    continue
                finding = self._finding(argv, rc, out, err)
                if not attribution_enabled:
                    findings.append(finding)
                    commands.append(VerificationCommand(
                        argv=tuple(argv), attribution="branch" if names else None))
                    continue
                if base_create_error is not None:
                    findings.append(self._attribution_failure(finding, base_create_error))
                    commands.append(VerificationCommand(argv=tuple(argv), attribution="branch"))
                    continue
                try:
                    if not base_created:
                        await self._git.worktree_add_detached(
                            self._repo, self._base_worktree, slip.base)
                        base_created = True
                except Exception as e:
                    base_create_error = e
                    findings.append(self._attribution_failure(finding, e))
                    commands.append(VerificationCommand(argv=tuple(argv), attribution="branch"))
                    continue
                try:
                    base_rc, base_out, base_err = await self._process.run(
                        list(argv), cwd=self._base_worktree, env=self._env, timeout=timeout)
                    base_out, base_err = self._redact(base_out), self._redact(base_err)
                except Exception as e:
                    findings.append(self._attribution_failure(finding, e))
                    commands.append(VerificationCommand(argv=tuple(argv), attribution="branch"))
                    continue
                if base_rc == 0:
                    findings.append(finding)
                    commands.append(VerificationCommand(argv=tuple(argv), attribution="branch"))
                    continue
                reason = self._finding(argv, base_rc, base_out, base_err).message
                filed = self._file_base_red(slip, reason)
                commands.append(VerificationCommand(
                    argv=tuple(argv), attribution="base", filed=filed))
        finally:
            self.commands = tuple(commands)
            if base_created:
                await self._git.worktree_remove(self._repo, self._base_worktree)
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=tuple(findings))

    def _finding(self, argv: Sequence[str], rc: int, out: str, err: str) -> Finding:
        tail = (err or out)[-2000:].strip()
        return Finding(
            code=self.code, paved_road=self.paved_road,
            message=f"verification command exit {rc}: `{' '.join(argv)}`"
                    + (f"\n{tail}" if tail else ""))

    def _attribution_failure(self, finding: Finding, error: Exception) -> Finding:
        detail = self._redact(f"{type(error).__name__}: {error}")
        return finding.model_copy(update={
            "message": f"{finding.message}\nbase attribution failed: {detail}"})

    def _file_base_red(self, slip: PackingSlip, reason: str) -> str:
        assert self._box is not None and self._run_seq is not None
        result = self._box.enqueue(
            message_class="failure_report", summary="Pre-existing verification failure",
            detail=reason, origin=slip.stem, stage="check", outcome="base_red",
            run_seq=self._run_seq)
        return result.id


def lint_run_record(text: str) -> list[str]:
    """The `run.md` schema: the six sections present, `## Outcome` in the
    closed vocabulary; prose quality is Review's."""
    seen: list[str] = []
    outcome: list[str] = []
    current = None
    fenced = False
    for line in text.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (h := _H2.match(line)):
            current = h.group(1)
            seen.append(current)
        elif current == "Outcome" and line.strip():
            outcome.append(line.strip())
    defects = [f"section `## {name}` is missing" for name in RUN_RECORD_SECTIONS
               if name not in seen]
    defects += [f"section `## {name}` is not a run-record section" for name in seen
                if name not in RUN_RECORD_SECTIONS]
    if "Outcome" in seen and (len(outcome) != 1 or outcome[0] not in OUTCOMES):
        defects.append(f"`## Outcome` must be exactly one of {sorted(OUTCOMES)}, "
                       f"got {' '.join(outcome)!r}")
    return defects


class RunRecord:
    code = "run_record"
    paved_road = (f"write {TICKETS_DIR}/<stem>/{RUN_RECORD} in the worktree with exactly the "
                  "sections " + ", ".join(f"## {s}" for s in RUN_RECORD_SECTIONS)
                  + "; ## Outcome carries one Outcome value")

    async def check(self, slip: PackingSlip, workspace: Path) -> GateReport:
        rel = f"{TICKETS_DIR}/{slip.stem}/{RUN_RECORD}"
        path = workspace / rel
        if not path.is_file():
            defects = [f"run record {rel} is missing from the worktree"]
        else:
            defects = [f"{rel}: {d}" for d in lint_run_record(path.read_text(errors="replace"))]
        findings = tuple(Finding(code=self.code, path=rel, message=d, paved_road=self.paved_road)
                         for d in defects)
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=findings)


class DiffBudget:
    code = "diff_budget"
    paved_road = SPLIT_ROAD

    def __init__(self, git: Git, repo: Path):
        self._git, self._repo = git, repo

    async def check(self, slip: PackingSlip, workspace: Path) -> GateReport:
        names = await self._git.diff_names(self._repo, slip.base, slip.branch)
        diff = await self._git.diff(self._repo, slip.base, slip.branch)
        inserted = sum(1 for line in diff.splitlines()
                       if line.startswith("+") and not line.startswith("+++"))
        if len(names) <= DIFF_BUDGET_FILES and inserted <= DIFF_BUDGET_LINES:
            return GateReport(code=self.code, verdict="pass")
        return GateReport(code=self.code, verdict="fail", findings=(Finding(
            code=self.code, paved_road=self.paved_road,
            message=f"diff is {len(names)} files / {inserted} inserted lines, over the budget "
                    f"of {DIFF_BUDGET_FILES} files / {DIFF_BUDGET_LINES} inserted lines"),))


def build_invoice(run: GateRun, slip: PackingSlip, names: Sequence[str], *,
                  bypassed: set[str], version: str,
                  verification: Verification | None = None) -> Invoice:
    """One gate run as the structured check report; Check and the merge
    admission's re-run persist the same shape."""
    return Invoice(
        stem=slip.stem, branch=slip.branch, base=slip.base, head=slip.head,
        changed_files=tuple(names),
        checks=tuple(CheckEntry(
            code=r.report.code, verdict=r.report.verdict, severity=r.severity,
            bypassed=r.failed and r.report.code in bypassed,
            findings=r.report.findings,
            commands=(verification.commands
                      if verification is not None and r.report.code == verification.code
                      else ())) for r in run.results),
        produced_by_spec_version=version, produced_at_sha=slip.head)


# ---- the stages ---------------------------------------------------------------

@dataclass(frozen=True)
class Delivery:
    """What one run delivered: the outcome, the findings behind it, and every
    artifact that reached its terminal (merge consumes slip + invoice + an
    approved review)."""

    outcome: str
    findings: list[Finding]
    slip: PackingSlip | None
    invoice: Invoice | None
    review: ReviewVerdict | None
    worktree: Path
    base: str
    stage: str
    reason: str | None
    cost: Cost


class Stages:
    def __init__(self, *, repo: Path, config: Config, git: Git, process: ProcessExec,
                 fs: Filesystem, llm: LLMEffect, log: EngineLog, redact: Redactor,
                 clock: Clock, env: Mapping[str, str], specs_dir: Path = SPECS_DIR):
        self._repo = Path(repo)
        self._config = config
        self._git = git
        self._process = process
        self._fs = fs
        self._llm = llm
        self._effects: Effects = llm.effects
        self._log = log
        self._redact = redact
        self._clock = clock
        self._specs_dir = Path(specs_dir)
        # Inherit-minus-secrets: a verification command never sees a provider key.
        self._child_env = child_env(env, {p.auth for p in config.providers if p.auth})
        self.implement_spec = load_spec(self._specs_dir / "implement.md")
        self.review_spec = load_spec(self._specs_dir / "review.md")
        state = self._repo / config.state_dir
        self._box = Box(state, fs=fs, clock=clock)
        self._spool = Spool(state, fs=fs, redact=redact)
        self._driver = Driver(llm=llm, spool=self._spool, log=log,
                              clock=clock, retry_cap=config.caps.retry,
                              severity=config.review.gate_severity)

    async def abort_active(self) -> None:
        """Abort and observe the Driver invocation currently owned by these stages."""
        await self._driver.abort_active()

    async def run(self, ticket: Ticket, *, run_seq: int) -> Delivery:
        stem = ticket.stem
        self._llm.stuck_seconds = ticket.stuck_minutes * 60
        ws = await self._workspace(stem, run_seq)
        worktree, base = Path(ws["path"]), ws["base"]

        result = await self._implement(ticket, worktree, base, run_seq)
        run_cost = result.cost
        try:
            await self._lift(stem, run_seq, "run-record", worktree=worktree)
        except LiftRefused as error:
            return Delivery("invalid_artifact", [error.finding], None, None, None,
                            worktree, base, "implement", "invalid_artifact", result.cost)
        if result.outcome != "ok":
            return Delivery(result.outcome, result.findings, None, None, None, worktree, base,
                            "implement", _terminal_reason(result), result.cost)
        report: ImplementReport = result.artifact
        head = await self._git.rev_parse(worktree, "HEAD")
        slip = PackingSlip(stem=stem, verdict=report.verdict, summary=report.summary,
                           branch=stem, base=base, head=head,
                           produced_by_spec_version=report.produced_by_spec_version,
                           produced_at_sha=head)
        if slip.verdict == "premise_failed":
            return Delivery("premise_failed", [Finding(
                code="premise_failed", message=slip.summary,
                paved_road="fix the ticket (or the plan it renders) and re-run; the "
                           "implementer answered the ticket as written")],
                slip, None, None, worktree, base, "implement", slip.summary, result.cost)

        invoice, reviewed = await self._check(ticket, slip, worktree, run_seq)
        seeds, seed_findings = ((await reviewed_seeds(
            worktree, stem, self._git, reviewed)) if invoice.passed else ((), []))
        if seed_findings:
            invoice = invoice.model_copy(update={"checks": invoice.checks + (CheckEntry(
                code="requisition_review", verdict="fail", severity="hard",
                findings=tuple(seed_findings)),)})
        await self._lift(stem, run_seq, "checks",
                         files={CHECKS: invoice.model_dump_json(indent=2).encode()})
        soft = list(invoice.soft_findings)
        if not invoice.passed:
            return Delivery("gate_failed", list(invoice.hard_findings) + soft, slip, invoice,
                            None, worktree, base, "check", None, result.cost)
        if seeds:
            lift_report = await self._lift_seeds(stem, run_seq, reviewed, worktree)
            if lift_report.verdict == "fail":
                return Delivery("gate_failed", list(lift_report.findings) + soft, slip, invoice,
                                None, worktree, base, "check", None, result.cost)
        if slip.verdict == "already_satisfied":
            return Delivery("already_satisfied", soft, slip, invoice, None, worktree, base,
                            "check", None, result.cost)

        result = await self._review(ticket, slip, invoice, worktree, run_seq)
        if result.outcome != "ok":
            return Delivery(result.outcome, result.findings + soft, slip, invoice, None, worktree,
                            base, "review", _terminal_reason(result),
                            _add_cost(run_cost, result.cost))
        report: ReviewReport = result.artifact
        verdict = REVIEW_EMITS[report.verdict](
            stem=stem, verdict=report.verdict, summary=report.summary, findings=report.findings,
            reviewed_sha=head, provider=result.cost.provider, model=result.cost.model,
            produced_by_spec_version=report.produced_by_spec_version, produced_at_sha=head)
        await self._lift(stem, run_seq, "review", files={REVIEW: render_review(verdict).encode()})
        return Delivery(REVIEW_OUTCOMES[verdict.verdict], list(verdict.findings) + soft, slip,
                        invoice, verdict, worktree, base, "review", None,
                        _add_cost(run_cost, result.cost))

    # -- workspace --

    async def _workspace(self, stem: str, run_seq: int) -> dict:
        """Teardown-and-create: a fresh worktree on a fresh `<stem>` branch
        off main, clearing whatever a dead run left (section 11.2)."""
        path = self._repo / self._config.worktree_root / stem

        async def action() -> dict:
            if path.exists():
                await self._git.worktree_remove(self._repo, path)
            else:
                await self._git.worktree_prune(self._repo)
            if await self._branch_exists(stem):
                await self._git.branch_delete(self._repo, stem)
            base = await self._git.rev_parse(self._repo, "main")
            await self._git.worktree_add(self._repo, path, stem, "main")
            return {"path": str(path), "branch": stem, "base": base}

        return await self._effects.run(action, key=effect_key("worktree", stem, run_seq),
                                       ticket=stem)

    async def _branch_exists(self, name: str) -> bool:
        try:
            await self._git.rev_parse(self._repo, f"refs/heads/{name}")
        except GitError:
            return False
        return True

    # -- Implement --

    def render_implement(self, ticket: Ticket, *, effort: Effort,
                         ticket_text: str | None = None) -> str:
        """Render Implement's standing, first-attempt prompt without making a call."""
        inputs = ImplementInput(
            stem=ticket.stem,
            ticket=(ticket_text if ticket_text is not None else
                    (self._repo / TICKETS_DIR / ticket.stem / TICKET_FILE).read_text()),
            context=tuple(
                (path, (self._repo / path).read_text(errors="replace"))
                for path in ticket.context),
            plan_sections=ticket.plan_sections,
            produced_by_spec_version="ticket", produced_at_sha="standing")
        return self._render_implement(
            ticket, inputs, effort=effort, prior=None, findings=())

    def _render_implement(self, ticket: Ticket, inputs: ImplementInput, *,
                          effort: Effort | None,
                          prior: str | None, findings: Sequence[Finding]) -> str:
        plan_path = self._repo / PLAN_FILE
        plan = plan_path.read_text() if ticket.plan_sections and plan_path.is_file() else None
        workspace = (f"stem: {ticket.stem}\nbranch: {ticket.stem}\n"
                     f"run record: {TICKETS_DIR}/{ticket.stem}/{RUN_RECORD}\n")
        context = "".join(f"### {path}\n{content}\n" for path, content in inputs.context)
        blocks = {
            "workspace": DataBlock("engine", workspace),
            "ticket": DataBlock("host", inputs.ticket),
            "context": DataBlock("host", context or "(no Context files)\n"),
        }
        if prior is not None:
            blocks["prior_attempts"] = DataBlock(
                "untrusted", prior.replace(DATA_MARKER, "[squatch-data:"))
        return self.implement_spec.render(
            blocks, findings=findings, plan=plan,
            plan_sections=inputs.plan_sections, effort=effort)

    async def _implement(self, ticket: Ticket, worktree: Path, base: str,
                         run_seq: int) -> StageResult:
        stem = ticket.stem
        spec = self.implement_spec
        prior = self._prior_attempts(stem, run_seq)

        def render(inputs: ImplementInput, findings) -> str:
            return self._render_implement(
                ticket, inputs, effort=None,
                prior=prior, findings=findings)

        stage = LLMStage(name="implement", surface=spec.surface, spec_version=spec.version,
                         tier=ticket.agent_tier, effort=ticket.agent_effort,
                         consumes=ImplementInput, emits=ImplementReport, gates=(), render=render)
        inputs = ImplementInput(
            stem=stem, ticket=(self._repo / TICKETS_DIR / stem / TICKET_FILE).read_text(),
            context=tuple((p, (worktree / p).read_text(errors="replace")) for p in ticket.context),
            plan_sections=ticket.plan_sections,
            produced_by_spec_version="ticket", produced_at_sha=base)
        return await self._call(stage, inputs, stem=stem, run_seq=run_seq, workspace=worktree,
                                sha=base)

    def _prior_attempts(self, stem: str, run_seq: int) -> str | None:
        """The re-entry fold (section 11.2): None on a first attempt; otherwise
        the prior run's terminal and whichever durable findings artifacts
        reject -- itemized with their paved roads, untrusted like all data."""
        ended = latest_terminal(self._effects.journal, stem)
        if ended is None:
            return None
        canonical = self._repo / TICKETS_DIR / stem
        lines = [f"Prior attempts (informational, unverified, not reviewed; scoped to this "
                 f"attempt {run_seq}, never acceptance criteria)",
                 f"attempt {run_seq - 1} of {stem} ended `{ended}`; clear every finding "
                 f"below as well as the ticket's criteria"]
        review = canonical / REVIEW
        if review.is_file():
            meta, body = parse_frontmatter(review.read_text(errors="replace"))
            if meta.get("verdict") != "approve":
                lines.append(f"\nreview.md (verdict `{meta.get('verdict')}` at "
                             f"{meta.get('reviewed_sha')}):")
                lines.append("\n".join(body).strip("\n"))
        checks = canonical / CHECKS
        if checks.is_file():
            invoice = Invoice.model_validate_json(checks.read_text(errors="replace"))
            if not invoice.passed:
                lines.append(f"\nchecks.json (failing at {invoice.head}):")
                lines.extend(f"- {f.code}{_where(f)}: {f.message} (paved road: {f.paved_road})"
                             for f in invoice.hard_findings)
        phase_one_count = len(lines)
        diagnoses = {
            event.body.get("run_seq"): (event.body, event.body["diagnosis"])
            for event in self._effects.journal.read()
            if event.type == "state_transition" and event.ticket == stem
            and isinstance(event.body.get("diagnosis"), dict)
            and event.body["diagnosis"].get("verdict") is not None
        }
        artifacts: dict[int, tuple[Path, Harvest]] = {}
        attempts = canonical / "attempts"
        if attempts.is_dir():
            for attempt in sorted((p for p in attempts.iterdir()
                                   if p.is_dir() and p.name.isdigit()),
                                  key=lambda p: int(p.name)):
                artifact_path = attempt / HARVEST_FILE
                if not artifact_path.is_file():
                    continue
                artifact = Harvest.model_validate_json(
                    artifact_path.read_text(errors="replace"))
                artifacts[artifact.run_seq] = (attempt, artifact)
        harvest_summaries: list[str] = []
        for attempt_seq in sorted(artifacts.keys() | diagnoses.keys()):
            pair = artifacts.get(attempt_seq)
            terminal_and_diagnosis = diagnoses.get(attempt_seq)
            if terminal_and_diagnosis is not None:
                terminal, diagnosis = terminal_and_diagnosis
                reason = ((pair[1].reason or "(findings carried separately)")
                          if pair is not None else terminal["to"])
                harvest_summaries.append(
                    f"attempt {attempt_seq}: terminal reason `{reason}`; diagnosis "
                    f"verdict `{diagnosis['verdict']}`")
                harvest_summaries.extend(
                    f"- lesson: {lesson}" for lesson in diagnosis.get("lessons", ()))
            elif pair is not None:
                attempt, artifact = pair
                changed = " / ".join(artifact.diff_stat.strip().splitlines())
                harvest_summaries.append(
                    f"harvest attempt {artifact.run_seq}: outcome `{artifact.outcome}`; "
                    f"reason: {artifact.reason or '(findings carried separately)'}; "
                    f"files changed: {changed or '(no changed files)'}")
        latest = artifacts[max(artifacts)][0] if artifacts else None
        if latest is not None and max(artifacts) in diagnoses:
            latest = None
        harvest_details: list[str] = []
        if latest is not None:
            run_record = latest / RUN_RECORD
            if run_record.is_file():
                harvest_details.append("latest run.md:")
                harvest_details.append(run_record.read_text(errors="replace"))
            artifact = Harvest.model_validate_json(
                (latest / HARVEST_FILE).read_text(errors="replace"))
            tails = [(name, tail) for name, tail in artifact.spool_tails.items()
                     if not name.endswith("-prompt.md")]
            if tails:
                harvest_details.append("latest non-prompt spool tails:")
                for name, tail in tails:
                    harvest_details.extend((f"[{name}]", tail))
        summary_text = "\n".join(harvest_summaries)
        detail_text = "\n".join(harvest_details)
        harvest_text = "\n".join(
            part for part in (summary_text, detail_text) if part)[:HARVEST_RENDER_CHARS]
        if harvest_text:
            lines.append(harvest_text)
        if len(lines) == phase_one_count and phase_one_count == 2:
            lines.append("\n(no rejecting review.md or failing checks.json is on the ticket "
                         "plane; the terminal's detail is in the engine log)")
        return "\n".join(lines) + "\n"

    # -- Check --

    async def _check(self, ticket: Ticket, slip: PackingSlip, worktree: Path,
                     run_seq: int) -> tuple[Invoice, dict[str, str]]:
        stem = ticket.stem
        bypassed = {code for code, _ in ticket.gate_bypass}

        async def action() -> dict:
            seeds = await authored_seeds(worktree, stem, self._git)
            seed_entries = await self._seed_checks(ticket, slip, worktree, run_seq, seeds)
            verification = Verification(
                self._git, self._repo, self._process, ticket, self._child_env, self._redact,
                box=self._box,
                base_worktree=(self._repo / self._config.worktree_root
                               / f"{stem}-base-{run_seq}"),
                run_seq=run_seq, allow_empty=bool(seeds))
            gates = (ScopeFence(self._git, self._repo, ticket), verification,
                     RunRecord(), DiffBudget(self._git, self._repo))
            # The one valve (section 7): a bypassed code fails soft, recorded forever.
            severity = {**self._config.review.gate_severity,
                        **{code: "soft" for code in bypassed}}
            run = await run_gates(gates, slip, worktree, severity=severity)
            names = await self._git.diff_names(self._repo, slip.base, slip.branch)
            invoice = build_invoice(run, slip, names, bypassed=bypassed, version=CHECK_VERSION,
                                    verification=verification)
            if seed_entries:
                invoice = invoice.model_copy(
                    update={"checks": tuple(seed_entries) + invoice.checks})
            self._log.event("check", stage="check", ticket=stem, run_seq=run_seq,
                            passed=invoice.passed,
                            findings=[f.model_dump() for f in invoice.hard_findings])
            reviewed = {
                seed.stem: seed.sha for seed in seeds
                if any(entry.code == "requisition_review" and entry.verdict == "pass"
                       and entry.path == seed.path and entry.sha == seed.sha
                       for entry in seed_entries)
            }
            return {"invoice": invoice.model_dump(mode="json"),
                    "reviewed_seeds": reviewed}

        data = await self._effects.run(action, key=effect_key("check", stem, run_seq), ticket=stem)
        return Invoice.model_validate(data["invoice"]), dict(data["reviewed_seeds"])

    async def _seed_checks(self, ticket: Ticket, slip: PackingSlip, worktree: Path,
                           run_seq: int, seeds: tuple[Seed, ...]) -> list[CheckEntry]:
        if not seeds:
            return []
        plan_path = worktree / PLAN_FILE
        findings = validate_batch(
            seeds, repo=self._repo,
            plan=plan_path.read_text() if plan_path.is_file() else None,
            config=self._config, events=self._effects.journal.read(), seeder=ticket.stem)
        if findings:
            return [CheckEntry(code="requisition_review", verdict="fail", severity="hard",
                               findings=tuple(findings))]

        # Imported here because requisition owns Stages' standing-render seam.
        from squatch.requisition import RequisitionGate, RequisitionReview

        review = RequisitionReview(
            repo=worktree, git=self._git,
            stages=_SeedRenderStages(self, worktree),
            llm=self._llm, spool=self._spool, log=self._log, clock=self._clock)
        entries = []
        for seed in seeds:
            gate = RequisitionGate(
                review, lambda artifact, workspace, seed=seed: ((seed.stem, seed.text),),
                run_seq=run_seq)
            report = (await run_gates((gate,), slip, worktree)).results[0].report
            path = seed.path
            decorated = tuple(finding.model_copy(update={"path": path})
                              for finding in report.findings)
            entries.append(CheckEntry(
                code=report.code, verdict=report.verdict, severity="hard", path=path,
                sha=seed.sha,
                findings=decorated))
        return entries

    # -- Review --

    async def _review(self, ticket: Ticket, slip: PackingSlip, invoice: Invoice,
                      worktree: Path, run_seq: int) -> StageResult:
        stem = ticket.stem
        spec = self.review_spec
        ticket_text = (self._repo / TICKETS_DIR / stem / TICKET_FILE).read_text()
        diff = await self._git.diff(self._repo, slip.base, slip.branch)

        def render(inputs: Invoice, findings) -> str:
            return spec.render({
                "ticket": DataBlock("host", ticket_text),
                "diff": DataBlock("untrusted", diff.replace(DATA_MARKER, "[squatch-data:")),
                "check_report": DataBlock("engine", inputs.model_dump_json(indent=2)),
            }, findings=findings)

        stage = LLMStage(name="review", surface=spec.surface, spec_version=spec.version,
                         tier=ticket.agent_tier, effort=ticket.agent_effort,
                         consumes=Invoice, emits=ReviewReport, gates=(), render=render)
        return await self._call(stage, invoice, stem=stem, run_seq=run_seq, workspace=worktree,
                                sha=slip.head)

    async def _call(self, stage: LLMStage, inputs: Artifact, *, stem: str, run_seq: int,
                    workspace: Path, sha: str) -> StageResult:
        """One LLM stage under the driver; the attempt IS the run sequence
        (section 11.2), so spools and keys never collide across runs."""
        try:
            return await self._driver.run(stage, inputs, ticket=stem, run_seq=run_seq,
                                          attempt=run_seq, workspace=workspace, sha=sha)
        except RenderRefused as e:
            # A mechanical pre-call short-circuit (section 8): ticket-text
            # arithmetic, never implementer failure -- no call, no cap draw.
            self._log.event("terminal", stage=stage.name, surface=stage.surface, ticket=stem,
                            attempt=run_seq, outcome="premise_failed", reason=str(e))
            return StageResult(outcome="premise_failed", artifact=None, cost=Cost(0, 0.0, 0),
                               findings=[Finding(code="render_refused", message=str(e),
                                                 paved_road=e.paved_road)])

    # -- the outbox lift + ticket-plane commit --

    async def _lift(self, stem: str, run_seq: int, kind: str, *, worktree: Path | None = None,
                    files: Mapping[str, bytes] | None = None) -> dict:
        """ONE ticket-plane commit per stage terminal: the worktree outbox
        (everything under `tickets/<stem>/` but `ticket.md`) and/or the
        engine-written artifacts, into the canonical ticket dir."""
        return await lift_ticket_files(
            repo=self._repo, git=self._git, fs=self._fs, effects=self._effects,
            redact=self._redact, stem=stem, run_seq=run_seq, kind=kind,
            worktree=worktree, files=files)

    async def _lift_seeds(self, stem: str, run_seq: int, reviewed: dict[str, str],
                          worktree: Path) -> GateReport:
        """One effect, using Intake's one ticket-plane lane for every seed."""
        seeds, findings = await reviewed_seeds(worktree, stem, self._git, reviewed)
        if findings:
            return GateReport(code="requisition_review", verdict="fail",
                              findings=tuple(findings))

        async def action() -> dict:
            intake = Intake(repo=self._repo, git=self._git,
                            journal=self._effects.journal, fs=self._fs)
            batch = {seed.stem for seed in seeds}
            resolve = lambda candidate: (candidate in batch or (
                self._repo / TICKETS_DIR / candidate / TICKET_FILE).is_file())
            plan_path = self._repo / PLAN_FILE
            plan = plan_path.read_text() if plan_path.is_file() else None
            replayed: dict[str, str] = {}
            prepared: dict[str, str] = {}

            # Nothing fallible about schema or reviewed-byte identity remains
            # after the first ticket-plane commit.
            for seed in seeds:
                text = stamp(seed.text, source="seed", state="confirmed")
                lint_ticket(text, stem=seed.stem, repo=self._repo,
                            plan=plan, resolve_stem=resolve)
                if blob_sha(text) != seed.sha:
                    raise ValueError(f"{seed.path}: intake would change the reviewed seed bytes")
                prepared[seed.stem] = text
                try:
                    current = await self._git.rev_parse(self._repo, f"HEAD:{seed.path}")
                except GitError:
                    current = None
                if current == seed.sha:
                    commit = next((event.body.get("commit")
                                   for event in reversed(tuple(self._effects.journal.read()))
                                   if event.type == "signal" and event.ticket == seed.stem
                                   and event.body.get("kind") == "ticket_intake"
                                   and event.body.get("source") == "seed"), None)
                    if not isinstance(commit, str):
                        raise ValueError(f"{seed.path}: prior seed bytes have no intake commit")
                    replayed[seed.stem] = commit

            commits = {}
            for seed in seeds:
                if seed.stem in replayed:
                    commits[seed.stem] = replayed[seed.stem]
                    continue
                path = self._repo / seed.path
                original = path.read_bytes() if path.is_file() else None
                self._fs.write(path, prepared[seed.stem].encode())
                try:
                    committed = await intake.commit(
                        seed.stem, resolve_stem=resolve, seeder=stem,
                        source="seed", state="confirmed")
                except Exception:
                    dirty = next((entry for entry in await self._git.status(self._repo)
                                  if entry.path.split(" -> ")[-1] == seed.path), None)
                    if dirty is not None and dirty.code != "??":
                        await self._git.restore(self._repo, [seed.path], source="HEAD")
                    elif original is None:
                        self._fs.unlink(path)
                    else:
                        self._fs.write(path, original)
                    raise
                commits[seed.stem] = committed.sha
            lifted = {seed.stem: seed.sha for seed in seeds}
            self._effects.journal.append(
                "signal", {"kind": SEED_LIFT_SIGNAL, "seeder": stem,
                           "run_seq": run_seq, "seeds": lifted}, ticket=stem)
            return {"commits": commits, "seeds": lifted}

        await self._effects.run(
            action, key=effect_key("lift", stem, run_seq, "seeds"), ticket=stem)
        return GateReport(code="requisition_review", verdict="pass")


class _SeedRenderStages:
    """Render a seed's standing Implement prompt from its authoring worktree."""

    def __init__(self, stages: Stages, worktree: Path):
        self._stages = stages
        self._worktree = worktree

    def render_implement(self, ticket: Ticket, *, effort: Effort,
                         ticket_text: str | None = None) -> str:
        inputs = ImplementInput(
            stem=ticket.stem,
            ticket=ticket_text if ticket_text is not None else (
                self._worktree / TICKETS_DIR / ticket.stem / TICKET_FILE).read_text(),
            context=tuple((path, (self._worktree / path).read_text(errors="replace"))
                          for path in ticket.context),
            plan_sections=ticket.plan_sections,
            produced_by_spec_version="ticket", produced_at_sha="standing")
        return self._stages._render_implement(
            ticket, inputs, effort=effort, prior=None, findings=())


class LiftRefused(Exception):
    """A known outbox artifact failed its closed schema before the lift wrote."""

    def __init__(self, finding: Finding):
        self.finding = finding
        super().__init__(finding.message)


async def lift_ticket_files(*, repo: Path, git: Git, fs: Filesystem, effects: Effects,
                            redact: Redactor, stem: str, run_seq: int, kind: str,
                            worktree: Path | None = None,
                            files: Mapping[str, bytes] | None = None) -> dict:
    """The sole ticket-plane lift path, shared by stages and terminal harvests."""
    canonical = repo / TICKETS_DIR / stem

    async def action() -> dict:
        paths: list[str] = []
        outbox = worktree / TICKETS_DIR / stem if worktree is not None else None
        candidates: list[tuple[Path, Path, bytes]] = []
        if outbox is not None and outbox.is_dir():
            for path in sorted(outbox.rglob("*")):
                rel = path.relative_to(outbox)
                # Attempt custody is engine-owned and closed to harvest.json
                # plus run.md; an agent cannot smuggle extra attempt files
                # through the otherwise-open outbox lift.
                if (path.is_file() and rel != Path(TICKET_FILE)
                        and (not rel.parts or rel.parts[0] != "attempts")):
                    data = path.read_bytes()
                    if rel == Path(RUN_RECORD):
                        data = redact(data.decode(errors="replace")).encode()
                    candidates.append((rel, canonical / rel, data))
        for rel, destination, data in candidates:
            validator = KNOWN_ARTIFACTS.get(rel.name)
            if validator is None:
                continue
            try:
                validator(data)
            except Exception as error:
                path = f"{TICKETS_DIR}/{stem}/{rel.as_posix()}"
                raise LiftRefused(Finding(
                    code="invalid_artifact", path=path,
                    message=f"{rel.name} failed schema validation: {error}",
                    paved_road=(f"regenerate {rel.name} through its report runner with the "
                                "closed schema, then re-run the ticket"))) from None
        for rel, destination, data in candidates:
            fs.write(destination, data)
            paths.append(f"{TICKETS_DIR}/{stem}/{rel.as_posix()}")
        for rel, data in (files or {}).items():
            if Path(rel).name == RUN_RECORD:
                data = redact(data.decode(errors="replace")).encode()
            fs.write(canonical / rel, data)
            paths.append(f"{TICKETS_DIR}/{stem}/{rel}")
        dirty = [entry.path for entry in await git.status(repo)]
        if not any(path == entry or (entry.endswith("/") and path.startswith(entry))
                   for path in paths for entry in dirty):
            return {"commit": None, "paths": paths}
        await git.add(repo, paths)
        sha = await git.commit(repo, f"squatch({stem}): {kind}", paths)
        return {"commit": sha, "paths": paths}

    return await effects.run(action, key=effect_key("lift", stem, run_seq, kind), ticket=stem)


def compose(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,
            clock: Clock, process: ProcessExec, fs: Filesystem, git: Git) -> Stages:
    """The production composition: the routed `cli` client behind the LLM
    effect, the redactor wired into every captured-stream writer."""
    repo = Path(repo)
    state = repo / config.state_dir
    redact = Redactor.from_config(config, env)
    client = CliClient(Registry(config), process=process, fs=fs, env=env, redact=redact,
                       state_dir=state, cwd=repo)
    llm = LLMEffect(llm=client, effects=Effects(journal), redact=redact, clock=clock)
    return Stages(repo=repo, config=config, git=git, process=process, fs=fs, llm=llm,
                  log=EngineLog(state, clock=clock, redact=redact), redact=redact, clock=clock,
                  env=env)
