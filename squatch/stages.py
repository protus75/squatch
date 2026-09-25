"""The Implement, Check, and Review stages (SQUATCH_PLAN.md sections 4, 5, 7,
9, 10; section 19, Phase 1).

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
from squatch.artifacts import OUTCOMES, Artifact, ClosedModel, Cost, Finding, StageResult
from squatch.config import Config, Severity
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects, effect_key
from squatch.enginelog import EngineLog
from squatch.gates import GateReport, GateRun, run_gates
from squatch.git import Git, GitError
from squatch.journal import Journal
from squatch.llmeffect import LLMEffect
from squatch.providers import CliClient, Registry, child_env
from squatch.redact import Redactor
from squatch.seams import Clock, Filesystem, ProcessExec
from squatch.specs import DataBlock, RenderRefused, Spec, load_spec
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, Ticket, parse_frontmatter

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


class CheckEntry(ClosedModel):
    code: str
    verdict: Literal["pass", "fail"]
    severity: Severity
    # A failing code the ticket's gate_bypass valve named: recorded, never hidden.
    bypassed: bool = False
    findings: tuple[Finding, ...] = ()


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
    """The ticket's own `## Verification` commands on the committed branch;
    Phase 1 runs WITHOUT base-diff attribution (any red fails)."""

    code = "verification"
    paved_road = "make every `## Verification` command exit 0 on the committed branch"

    def __init__(self, git: Git, repo: Path, process: ProcessExec, ticket: Ticket,
                 env: Mapping[str, str], redact: Redactor):
        self._git, self._repo, self._process, self._ticket = git, repo, process, ticket
        self._env, self._redact = env, redact

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
        if slip.verdict != "already_satisfied" and not names:
            findings.append(Finding(
                code=self.code, message="the branch carries no committed diff",
                paved_road="commit the work on the branch before answering; only the "
                           "committed diff is checked and reviewed"))
        timeout = self._ticket.stuck_minutes * 60
        for argv in self._ticket.verification:
            rc, out, err = await self._process.run(list(argv), cwd=workspace, env=self._env,
                                                   timeout=timeout)
            # Scrubbed once at receipt (section 6): the tail becomes a Finding
            # that the check completion journals and the checks.json lift commits.
            out, err = self._redact(out), self._redact(err)
            if rc != 0:
                tail = (err or out)[-2000:].strip()
                findings.append(Finding(
                    code=self.code, paved_road=self.paved_road,
                    message=f"verification command exit {rc}: `{' '.join(argv)}`"
                            + (f"\n{tail}" if tail else "")))
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=tuple(findings))


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
                  bypassed: set[str], version: str) -> Invoice:
    """One gate run as the structured check report; Check and the merge
    admission's re-run persist the same shape."""
    return Invoice(
        stem=slip.stem, branch=slip.branch, base=slip.base, head=slip.head,
        changed_files=tuple(names),
        checks=tuple(CheckEntry(
            code=r.report.code, verdict=r.report.verdict, severity=r.severity,
            bypassed=r.failed and r.report.code in bypassed,
            findings=r.report.findings) for r in run.results),
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
        # Inherit-minus-secrets: a verification command never sees a provider key.
        self._child_env = child_env(env, {p.auth for p in config.providers if p.auth})
        self.implement_spec = load_spec(Path(specs_dir) / "implement.md")
        self.review_spec = load_spec(Path(specs_dir) / "review.md")
        state = self._repo / config.state_dir
        self._driver = Driver(llm=llm, spool=Spool(state, fs=fs, redact=redact), log=log,
                              clock=clock, retry_cap=config.caps.retry,
                              severity=config.review.gate_severity)

    async def run(self, ticket: Ticket, *, run_seq: int) -> Delivery:
        stem = ticket.stem
        self._llm.stuck_seconds = ticket.stuck_minutes * 60
        ws = await self._workspace(stem, run_seq)
        worktree, base = Path(ws["path"]), ws["base"]

        result = await self._implement(ticket, worktree, base, run_seq)
        await self._lift(stem, run_seq, "run-record", worktree=worktree)
        if result.outcome != "ok":
            return Delivery(result.outcome, result.findings, None, None, None, worktree)
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
                slip, None, None, worktree)

        invoice = await self._check(ticket, slip, worktree, run_seq)
        await self._lift(stem, run_seq, "checks",
                         files={CHECKS: invoice.model_dump_json(indent=2).encode()})
        soft = list(invoice.soft_findings)
        if not invoice.passed:
            return Delivery("gate_failed", list(invoice.hard_findings) + soft, slip, invoice,
                            None, worktree)
        if slip.verdict == "already_satisfied":
            return Delivery("already_satisfied", soft, slip, invoice, None, worktree)

        result = await self._review(ticket, slip, invoice, worktree, run_seq)
        if result.outcome != "ok":
            return Delivery(result.outcome, result.findings + soft, slip, invoice, None, worktree)
        report: ReviewReport = result.artifact
        verdict = REVIEW_EMITS[report.verdict](
            stem=stem, verdict=report.verdict, summary=report.summary, findings=report.findings,
            reviewed_sha=head, provider=result.cost.provider, model=result.cost.model,
            produced_by_spec_version=report.produced_by_spec_version, produced_at_sha=head)
        await self._lift(stem, run_seq, "review", files={REVIEW: render_review(verdict).encode()})
        return Delivery(REVIEW_OUTCOMES[verdict.verdict], list(verdict.findings) + soft, slip,
                        invoice, verdict, worktree)

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

    async def _implement(self, ticket: Ticket, worktree: Path, base: str,
                         run_seq: int) -> StageResult:
        stem = ticket.stem
        spec = self.implement_spec
        plan_path = self._repo / PLAN_FILE
        plan = plan_path.read_text() if ticket.plan_sections and plan_path.is_file() else None
        workspace = f"stem: {stem}\nbranch: {stem}\nrun record: {TICKETS_DIR}/{stem}/{RUN_RECORD}\n"

        def render(inputs: ImplementInput, findings) -> str:
            context = "".join(f"### {path}\n{content}\n" for path, content in inputs.context)
            return spec.render({
                "workspace": DataBlock("engine", workspace),
                "ticket": DataBlock("host", inputs.ticket),
                "context": DataBlock("host", context or "(no Context files)\n"),
            }, findings=findings, plan=plan, plan_sections=inputs.plan_sections)

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

    # -- Check --

    async def _check(self, ticket: Ticket, slip: PackingSlip, worktree: Path,
                     run_seq: int) -> Invoice:
        stem = ticket.stem
        bypassed = {code for code, _ in ticket.gate_bypass}

        async def action() -> dict:
            gates = (ScopeFence(self._git, self._repo, ticket),
                     Verification(self._git, self._repo, self._process, ticket, self._child_env,
                                  self._redact),
                     RunRecord(), DiffBudget(self._git, self._repo))
            # The one valve (section 7): a bypassed code fails soft, recorded forever.
            severity = {**self._config.review.gate_severity,
                        **{code: "soft" for code in bypassed}}
            run = await run_gates(gates, slip, worktree, severity=severity)
            names = await self._git.diff_names(self._repo, slip.base, slip.branch)
            invoice = build_invoice(run, slip, names, bypassed=bypassed, version=CHECK_VERSION)
            self._log.event("check", stage="check", ticket=stem, run_seq=run_seq,
                            passed=invoice.passed,
                            findings=[f.model_dump() for f in invoice.hard_findings])
            return invoice.model_dump(mode="json")

        data = await self._effects.run(action, key=effect_key("check", stem, run_seq), ticket=stem)
        return Invoice.model_validate(data)

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
                "diff": DataBlock("untrusted", diff),
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
        canonical = self._repo / TICKETS_DIR / stem

        async def action() -> dict:
            paths: list[str] = []
            outbox = worktree / TICKETS_DIR / stem if worktree is not None else None
            if outbox is not None and outbox.is_dir():
                for p in sorted(outbox.rglob("*")):
                    rel = p.relative_to(outbox)
                    if p.is_file() and rel != Path(TICKET_FILE):
                        data = p.read_bytes()
                        # The run record is Implement's text stream into the
                        # ticket plane; the one child holding a provider key
                        # wrote it, so it crosses the redactor (section 6).
                        if rel == Path(RUN_RECORD):
                            data = self._redact(data.decode(errors="replace")).encode()
                        self._fs.write(canonical / rel, data)
                        paths.append(f"{TICKETS_DIR}/{stem}/{rel.as_posix()}")
            for rel, data in (files or {}).items():
                self._fs.write(canonical / rel, data)
                paths.append(f"{TICKETS_DIR}/{stem}/{rel}")
            # Porcelain collapses a wholly-untracked directory to one `dir/`
            # entry, so a path is dirty when an entry names it or a parent.
            dirty = [e.path for e in await self._git.status(self._repo)]
            if not any(p == d or (d.endswith("/") and p.startswith(d)) for p in paths
                       for d in dirty):
                return {"commit": None, "paths": paths}
            await self._git.add(self._repo, paths)
            sha = await self._git.commit(self._repo, f"squatch({stem}): {kind}", paths)
            return {"commit": sha, "paths": paths}

        return await self._effects.run(action, key=effect_key("lift", stem, run_seq, kind),
                                       ticket=stem)


def compose(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,
            clock: Clock, process: ProcessExec, fs: Filesystem, git: Git) -> Stages:
    """The production composition: the routed `cli` client behind the LLM
    effect, the redactor wired into every captured-stream writer."""
    repo = Path(repo)
    state = repo / config.state_dir
    redact = Redactor.from_config(config, env)
    client = CliClient(Registry(config), process=process, fs=fs, env=env, redact=redact,
                       state_dir=state, cwd=repo)
    llm = LLMEffect(llm=client, effects=Effects(journal), redact=redact)
    return Stages(repo=repo, config=config, git=git, process=process, fs=fs, llm=llm,
                  log=EngineLog(state, clock=clock, redact=redact), redact=redact, clock=clock,
                  env=env)
