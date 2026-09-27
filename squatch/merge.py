"""Bootstrap and daemon merge admission (SQUATCH_PLAN.md sections 7, 9, 10, 20).

One admission settles one delivered run, everything BEFORE main moves: the
pinned approval for the head being admitted (`correctness_review` at merge is
that check, never a re-executed model call); the code-lane check on the
delivered diff; the branch worktree's ticket plane restored and the branch
rebased onto main (a refused rebase is aborted and the branch left at its
own head); the mechanical hard set re-run against the rebased candidate --
the tree the squash will put on main, so a semantic conflict (green alone,
red together) is caught while main stays green; then the squash-merge with
its two identity trailers, the branch and worktree retired, and the run's
`to: merged` transition journaled. A red candidate is never admitted: main
is untouched, the findings become the run's `gate_failed` terminal, and the
branch stays in place, re-runnable. Bootstrap runs this admission inline.
Serve selects daemon admission, which keeps the immutable delivery checks
here and delegates rebase through integration to the serial MergeQueue.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from squatch.artifacts import Finding
from squatch.box import Box
from squatch.config import Config
from squatch.control import ControlInbox
from squatch.diagnose import Diagnoser, DiagnosisRecord
from squatch.effects import Effects, effect_key
from squatch.enginelog import EngineLog
from squatch.gates import GateReport, run_gates
from squatch.git import Git, GitError, RebaseConflict
from squatch.journal import Journal
from squatch.mergequeue import AdmissionHold, Candidate, MergeQueue
from squatch.providers import child_env
from squatch.redact import Redactor
from squatch.runner import SETTLED
from squatch.seeds import SEED_LIFT_SIGNAL, blob_sha
from squatch.seams import Clock, Filesystem, ProcessExec
from squatch.stages import (REVIEW, Delivery, DiffBudget, Invoice, PackingSlip, RunRecord,
                            ScopeFence, Stages, Verification, build_invoice, compose, load_review)
from squatch.tickets import PLAN_FILE, TICKET_FILE, TICKETS_DIR, Ticket, lint_ticket

MERGE_VERSION = "1.0"
REGATE = "post_rebase_regate"
APPROVAL = "correctness_review"
TICKET_TRAILER = "squatch-ticket"
REVIEWED_TRAILER = "squatch-reviewed-sha"
CODE_LANE_ROAD = "leave outbox files uncommitted; the driver lifts them"
REBASE_ROAD = ("re-run the stem: the refused rebase was aborted, so the branch sits at its own "
               "head and a fresh run re-implements against the moved main")
APPROVAL_ROAD = ("an admission needs an `approve` verdict pinned to the branch head it admits; "
                 "re-run the stem so Review approves the current head")
SEED_SAFETY_ROAD = ("re-run the stem: a lifted seed has no recorded approval for the bytes "
                    "on main")
REWORK_ROAD = ("let the daemon Rework consumer revise or split the ticket from the published "
               "conflict handoff, then dispatch the resulting ticket")



def _entries_below(path: Path) -> list[Path]:
    """The unlink list under an untracked ticket-plane entry, never following
    a symlink: a link is one entry (the link itself), whatever it points at,
    so an agent-planted link out of the worktree can never delete its target."""
    if path.is_symlink() or not path.is_dir():
        return [path]
    return [p for child in sorted(path.iterdir()) for p in _entries_below(child)]


@dataclass(frozen=True)
class Admission:
    """What one admission settled: the delivered outcome on success (or
    `gate_failed`), the findings behind it, the squash commit (None when
    nothing was integrated), and the SHA the carried approval pinned."""

    outcome: str
    findings: list[Finding]
    commit: str | None
    reviewed_sha: str | None


class CodeLane:
    """`tickets/**` reaches main only through ticket-plane commits (section
    10); a branch committing its outbox is refused on the delivered diff,
    before any rebase can fold an identical lifted copy out of it."""

    code = REGATE
    paved_road = CODE_LANE_ROAD

    def __init__(self, git: Git, repo: Path):
        self._git, self._repo = git, repo

    async def check(self, slip: PackingSlip, workspace: Path) -> GateReport:
        names = await self._git.diff_names(self._repo, slip.base, slip.branch)
        findings = tuple(
            Finding(code=self.code, path=p, paved_road=self.paved_road,
                    message=f"{p} is committed on the branch; tickets/** never rides the code lane")
            for p in names if p.startswith(f"{TICKETS_DIR}/"))
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=findings)


class SeedSafety:
    """The lifted bytes on main still match this run's per-seed approvals."""

    code = "requisition_review"
    paved_road = SEED_SAFETY_ROAD

    def __init__(self, git: Git, repo: Path, journal: Journal, invoice: Invoice | None, *,
                 run_seq: int):
        self._git, self._repo, self._journal = git, Path(repo), journal
        self._invoice = invoice
        self._run_seq = run_seq

    async def check(self, slip: PackingSlip, workspace: Path) -> GateReport:
        signal = next((event for event in reversed(tuple(self._journal.read()))
                       if event.type == "signal" and event.ticket == slip.stem
                       and event.body.get("kind") == SEED_LIFT_SIGNAL
                       and event.body.get("run_seq") == self._run_seq), None)
        if signal is None:
            return GateReport(code=self.code, verdict="pass")
        seeds = signal.body.get("seeds")
        if not isinstance(seeds, dict):
            return self._failed(None, "seed_lift signal has no seed map")
        checks_rel = f"{TICKETS_DIR}/{slip.stem}/checks.json"
        try:
            checks_sha = await self._git.rev_parse(self._repo, f"main:{checks_rel}")
        except GitError:
            return self._failed(checks_rel, "seed checks are not committed on main")
        if self._invoice is None:
            return self._failed(checks_rel, "the seeding delivery carries no seed checks")
        recorded_sha = blob_sha(self._invoice.model_dump_json(indent=2))
        if checks_sha != recorded_sha:
            return self._failed(
                checks_rel,
                f"committed seed checks blob {checks_sha} does not match this run's "
                f"invoice blob {recorded_sha}")
        findings = []
        for stem, expected in sorted(seeds.items()):
            path = f"{TICKETS_DIR}/{stem}/ticket.md"
            try:
                actual = await self._git.rev_parse(self._repo, f"main:{path}")
            except GitError:
                actual = None
            approved = any(entry.code == self.code and entry.path == path
                           and entry.sha == expected
                           and entry.verdict == "pass" for entry in self._invoice.checks)
            if actual != expected or not approved:
                findings.append(Finding(
                    code=self.code, path=path, paved_road=self.paved_road,
                    message=(f"lifted seed approval is stale: main blob {actual or 'missing'}, "
                             f"lifted blob {expected}, passing check {approved}")))
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=tuple(findings))

    def _failed(self, path: str | None, message: str) -> GateReport:
        return GateReport(code=self.code, verdict="fail", findings=(Finding(
            code=self.code, path=path, paved_road=self.paved_road, message=message),))


class Merge:
    def __init__(self, *, repo: Path, config: Config, git: Git, process: ProcessExec,
                 fs: Filesystem, effects: Effects, journal: Journal, log: EngineLog,
                 redact: Redactor, clock: Clock, env: Mapping[str, str]):
        self._repo = Path(repo)
        self._config = config
        self._git = git
        self._process = process
        self._fs = fs
        self._effects = effects
        self._journal = journal
        self._log = log
        self._redact = redact
        self._box = Box(self._repo / config.state_dir, fs=fs, clock=clock)
        # Inherit-minus-secrets: a verification command never sees a provider key.
        self._child_env = child_env(env, {p.auth for p in config.providers if p.auth})

    async def admit(self, ticket: Ticket, delivery: Delivery, *, run_seq: int) -> Admission:
        stem = ticket.stem
        slip, worktree = delivery.slip, delivery.worktree
        reviewed, findings = await self._precheck(ticket, delivery, run_seq=run_seq)
        if findings:
            return self._blocked(stem, run_seq, findings)

        rebase = await self._rebase(stem, worktree, run_seq)
        if rebase["refused"] is not None:
            return self._blocked(stem, run_seq, [Finding(
                code=REGATE, paved_road=REBASE_ROAD,
                message=f"rebase onto main refused (aborted; the branch sits at its own head): "
                        f"{rebase['refused']}")])
        candidate = PackingSlip(
            stem=stem, verdict=slip.verdict, summary=slip.summary, branch=stem,
            base=rebase["base"], head=rebase["head"],
            produced_by_spec_version=MERGE_VERSION, produced_at_sha=rebase["head"])
        invoice = await self._regate(ticket, candidate, worktree, run_seq)
        soft = list(invoice.soft_findings)
        if not invoice.passed:
            return self._blocked(stem, run_seq, list(invoice.hard_findings) + soft)

        commit = None
        if reviewed is not None and invoice.changed_files:
            commit = (await self._squash(ticket, invoice, reviewed, run_seq))["commit"]
        await self._retire(stem, worktree, run_seq)
        self._journal.append("state_transition", {
            "to": "merged", "run_seq": run_seq, "commit": commit, "reviewed_sha": reviewed},
            ticket=stem)
        self._log.event("merge", ticket=stem, run_seq=run_seq, outcome=delivery.outcome,
                        commit=commit, reviewed_sha=reviewed,
                        findings=[f.model_dump() for f in soft])
        return Admission(delivery.outcome, soft, commit, reviewed)

    async def admit_daemon(self, ticket: Ticket, delivery: Delivery, *, run_seq: int,
                           queue: "_ReviewedMergeQueue") -> Admission:
        """Run immutable delivery checks, then hand all moving-main work to the queue."""
        stem = ticket.stem
        reviewed, findings = await self._precheck(ticket, delivery, run_seq=run_seq)
        if findings:
            return self._blocked(stem, run_seq, findings)

        await self._restore_ticket_plane(delivery.worktree)
        candidate = Candidate(stem=stem, branch=stem, worktree=delivery.worktree,
                              run_seq=run_seq)
        queued, commit, soft = await queue.admit_delivery(
            candidate, ticket=ticket, delivery=delivery, reviewed_head=reviewed)
        if queued.outcome != "integrated":
            findings = list(queued.findings)
            if queued.outcome == "rework":
                paths = queued.conflict_facts.paths
                findings.append(Finding(
                    code=REGATE, path=paths[0] if len(paths) == 1 else None,
                    paved_road=REWORK_ROAD,
                    message=(f"unresolved rebase conflicts require Rework"
                             f"{': ' + ', '.join(paths) if paths else ''}")))
            self._log.event("merge", ticket=stem, run_seq=run_seq,
                            outcome="gate_failed",
                            findings=[finding.model_dump() for finding in findings])
            return Admission("gate_failed", findings, None, reviewed)

        await self._retire(stem, delivery.worktree, run_seq)
        self._journal.append("state_transition", {
            "to": "merged", "run_seq": run_seq, "commit": commit,
            "reviewed_sha": reviewed}, ticket=stem)
        self._log.event("merge", ticket=stem, run_seq=run_seq, outcome=delivery.outcome,
                        commit=commit, reviewed_sha=reviewed,
                        findings=[finding.model_dump() for finding in soft])
        return Admission(delivery.outcome, soft, commit, reviewed)

    async def _precheck(self, ticket: Ticket, delivery: Delivery, *,
                        run_seq: int) -> tuple[str | None, list[Finding]]:
        stem = ticket.stem
        slip, worktree = delivery.slip, delivery.worktree
        if delivery.outcome not in SETTLED or slip is None:
            raise ValueError(f"{stem}: only a settled delivery is admitted, not {delivery.outcome!r}")
        head = await self._git.rev_parse(self._repo, f"refs/heads/{stem}")
        # An already_satisfied run settles on Check's proof alone (section 5):
        # nothing was implemented, so nothing is reviewed or integrated.
        reviewed = None if slip.verdict == "already_satisfied" else head
        findings = self._approval(stem, head) if reviewed else []
        safety = (CodeLane(self._git, self._repo),
                  SeedSafety(self._git, self._repo, self._journal, delivery.invoice,
                             run_seq=run_seq))
        findings += (await run_gates(safety, slip, worktree,
                                     severity=self._severity(ticket))).hard_failures
        return reviewed, findings

    # -- the pinned approval --

    def _approval(self, stem: str, head: str) -> list[Finding]:
        """The on-disk verdict (`tickets/<stem>/review.md`, the ticket-plane
        record) must be an `approve` pinned to the head being admitted."""
        rel = f"{TICKETS_DIR}/{stem}/{REVIEW}"
        path = self._repo / rel
        if not path.is_file():
            return [Finding(code=APPROVAL, path=rel, paved_road=APPROVAL_ROAD,
                            message=f"no review verdict at {rel}")]
        try:
            meta = load_review(path.read_text())
        except ValueError as e:
            return [Finding(code=APPROVAL, path=rel, paved_road=APPROVAL_ROAD,
                            message=f"{rel} does not parse: {e}")]
        verdict, pinned = meta.get("verdict"), meta.get("reviewed_sha")
        if verdict != "approve" or pinned != head:
            return [Finding(code=APPROVAL, path=rel, paved_road=APPROVAL_ROAD,
                            message=f"{rel} is `{verdict}` pinned to {str(pinned)[:12]}, but the "
                                    f"branch head is {head[:12]}")]
        return []

    def _severity(self, ticket: Ticket) -> dict:
        # The one valve (section 7): a bypassed code fails soft at merge too.
        return {**self._config.review.gate_severity,
                **{code: "soft" for code, _ in ticket.gate_bypass}}

    # -- restore + rebase --

    async def _rebase(self, stem: str, worktree: Path, run_seq: int) -> dict:
        async def action() -> dict:
            await self._restore_ticket_plane(worktree)
            base = await self._git.rev_parse(self._repo, "main")
            try:
                await self._git.rebase(worktree, "main")
            except RebaseConflict as e:
                refused = self._redact((e.stderr or e.stdout)[-2000:].strip())
                return {"base": base, "head": None, "refused": refused}
            return {"base": base, "head": await self._git.rev_parse(worktree, "HEAD"),
                    "refused": None}

        return await self._effects.run(action, key=effect_key("rebase", stem, run_seq), ticket=stem)

    async def _restore_ticket_plane(self, worktree: Path) -> None:
        """Clear the worktree's `tickets/**` so the rebase can carry it to
        main's content: the lifted outbox copies (untracked here, tracked on
        main) would refuse the checkout, and a modified or deleted tracked
        copy would refuse the rebase. Restored to the BRANCH head, not main:
        a rebase needs index == HEAD, and main's versions land with it."""
        for entry in await self._git.status(worktree):
            if entry.code != "??" or not entry.path.startswith(f"{TICKETS_DIR}/"):
                continue
            # Porcelain collapses a wholly-untracked directory to one `dir/` entry.
            for p in _entries_below(worktree / entry.path):
                self._fs.unlink(p)
        await self._git.restore(worktree, [TICKETS_DIR], source="HEAD")

    # -- the mechanical hard set, re-run on the rebased candidate --

    async def _regate(self, ticket: Ticket, candidate: PackingSlip, worktree: Path,
                      run_seq: int) -> Invoice:
        stem = ticket.stem
        bypassed = {code for code, _ in ticket.gate_bypass}

        async def action() -> dict:
            verification = Verification(
                self._git, self._repo, self._process, ticket, self._child_env, self._redact,
                box=self._box,
                base_worktree=(self._repo / self._config.worktree_root
                               / f"{stem}-base-{run_seq}"),
                run_seq=run_seq, allow_empty=self._seed_lift(stem, run_seq) is not None)
            gates = (ScopeFence(self._git, self._repo, ticket), RunRecord(),
                     DiffBudget(self._git, self._repo), verification)
            run = await run_gates(gates, candidate, worktree, severity=self._severity(ticket))
            names = await self._git.diff_names(self._repo, candidate.base, candidate.branch)
            invoice = build_invoice(run, candidate, names, bypassed=bypassed,
                                    version=MERGE_VERSION, verification=verification)
            self._log.event("merge_check", stage="merge", ticket=stem, run_seq=run_seq,
                            passed=invoice.passed,
                            findings=[f.model_dump() for f in invoice.hard_findings])
            return invoice.model_dump(mode="json")

        data = await self._effects.run(action, key=effect_key("regate", stem, run_seq), ticket=stem)
        return Invoice.model_validate(data)

    def _seed_lift(self, stem: str, run_seq: int):
        return next((event for event in reversed(tuple(self._journal.read()))
                     if event.type == "signal" and event.ticket == stem
                     and event.body.get("kind") == SEED_LIFT_SIGNAL
                     and event.body.get("run_seq") == run_seq), None)

    # -- squash + trailers, then retire the branch --

    async def _squash(self, ticket: Ticket, invoice: Invoice, reviewed: str, run_seq: int) -> dict:
        stem = ticket.stem
        message = (f"squatch({stem}): {ticket.goal}\n\n"
                   f"{TICKET_TRAILER}: {stem}\n{REVIEWED_TRAILER}: {reviewed}")

        async def action() -> dict:
            await self._git.merge_squash(self._repo, stem)
            # Pathspec commit: only the candidate's own paths, so bytes an
            # operator pre-staged in the main checkout never ride the squash.
            sha = await self._git.commit(self._repo, message, invoice.changed_files)
            return {"commit": sha}

        return await self._effects.run(action, key=effect_key("merge", stem, run_seq), ticket=stem)

    async def _retire(self, stem: str, worktree: Path, run_seq: int) -> dict:
        async def action() -> dict:
            # The worktree first: git refuses to delete a branch a worktree holds.
            if worktree.exists():
                await self._git.worktree_remove(self._repo, worktree)
            else:
                await self._git.worktree_prune(self._repo)
            try:
                await self._git.branch_delete(self._repo, stem)
            except GitError as error:
                try:
                    await self._git.rev_parse(self._repo, f"refs/heads/{stem}")
                except GitError:
                    pass
                else:
                    raise error
            return {"branch": stem}

        return await self._effects.run(action, key=effect_key("retire", stem, run_seq), ticket=stem)

    def _blocked(self, stem: str, run_seq: int, findings: list[Finding]) -> Admission:
        # Phase 1's named detail location for a non-ok terminal is the engine log.
        self._log.event("merge", ticket=stem, run_seq=run_seq, outcome="gate_failed",
                        findings=[f.model_dump() for f in findings])
        return Admission("gate_failed", findings, None, None)


AdmissionMode = Literal["inline", "daemon"]


class Pipeline:
    """Implement -> Check -> Review -> selected admission behind the runner seam."""

    def __init__(self, stages: Stages, merge: Merge, merge_queue: MergeQueue | None = None):
        self.stages = stages
        self.merge = merge
        self.merge_queue = merge_queue
        self.admission_mode: AdmissionMode = "inline"
        self.diagnoser = Diagnoser(stages)

    def select_daemon_admission(self) -> None:
        if not isinstance(self.merge_queue, _ReviewedMergeQueue):
            raise ValueError("daemon admission requires the composed merge queue")
        self.admission_mode = "daemon"

    async def run(self, ticket: Ticket, *, run_seq: int) -> Delivery:
        delivery = await self.stages.run(ticket, run_seq=run_seq)
        if delivery.outcome not in SETTLED:
            return delivery
        if self.admission_mode == "daemon":
            assert isinstance(self.merge_queue, _ReviewedMergeQueue)
            admission = await self.merge.admit_daemon(
                ticket, delivery, run_seq=run_seq, queue=self.merge_queue)
        else:
            admission = await self.merge.admit(ticket, delivery, run_seq=run_seq)
        return replace(delivery, outcome=admission.outcome, findings=admission.findings,
                       stage="merge", reason=None)

    async def diagnose(self, ticket: Ticket, delivery: Delivery, *,
                       run_seq: int) -> DiagnosisRecord:
        return await self.diagnoser.diagnose(ticket, delivery, run_seq=run_seq)


def compose_pipeline(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,
                     clock: Clock, process: ProcessExec, fs: Filesystem, git: Git,
                     control_inbox: ControlInbox, admission_hold: AdmissionHold) -> Pipeline:
    """The production composition: the stages over the routed provider, the
    admission over the same journal, git, and redactor."""
    repo = Path(repo)
    stages = compose(repo=repo, config=config, env=env, journal=journal, clock=clock,
                     process=process, fs=fs, git=git)
    redact = Redactor.from_config(config, env)
    merge = Merge(repo=repo, config=config, git=git, process=process, fs=fs,
                  effects=Effects(journal), journal=journal,
                  log=EngineLog(repo / config.state_dir, clock=clock, redact=redact),
                  redact=redact, clock=clock, env=env)
    async def regate(candidate: Candidate):
        state = queue.admission_state[candidate.stem, candidate.run_seq]
        findings = (merge._approval(candidate.stem, state.reviewed_head)
                    if state.reviewed_head is not None else [])
        if findings:
            return findings
        if state.ticket is None:
            path = repo / TICKETS_DIR / candidate.stem / TICKET_FILE
            plan = repo / PLAN_FILE
            state.ticket = lint_ticket(
                path.read_text(), stem=candidate.stem, repo=repo,
                plan=plan.read_text() if plan.is_file() else None,
                resolve_stem=lambda stem: (repo / TICKETS_DIR / stem / TICKET_FILE).is_file())
        head = await git.rev_parse(candidate.worktree, "HEAD")
        state.slip = PackingSlip(
            stem=candidate.stem, branch=candidate.branch, verdict=state.verdict,
            summary=state.summary or state.ticket.goal,
            base=await git.rev_parse(repo, "main"), head=head,
            produced_by_spec_version=MERGE_VERSION, produced_at_sha=head)
        state.invoice = await merge._regate(
            state.ticket, state.slip, candidate.worktree, candidate.run_seq)
        return state.invoice.hard_findings

    async def integration_check(candidate: Candidate):
        state = queue.admission_state[candidate.stem, candidate.run_seq]
        verification = Verification(git, repo, process, state.ticket, merge._child_env, redact)
        return (await verification.check(state.slip, candidate.worktree)).findings

    async def integrate(candidate: Candidate):
        state = queue.admission_state[candidate.stem, candidate.run_seq]
        findings = (merge._approval(candidate.stem, state.reviewed_head)
                    if state.reviewed_head is not None else [])
        if findings:
            raise ValueError(findings[0].message)
        if state.reviewed_head is not None and state.invoice.changed_files:
            state.commit = (await merge._squash(
                state.ticket, state.invoice, state.reviewed_head, candidate.run_seq))["commit"]

    queue = compose_merge_queue(
        repo=repo, config=config, env=env, journal=journal, process=process, fs=fs, git=git,
        control_inbox=control_inbox, admission_hold=admission_hold,
        regate=regate, integration_check=integration_check, integrate=integrate)
    return Pipeline(stages, merge, queue)


@dataclass
class _AdmissionState:
    reviewed_head: str | None
    ticket: Ticket | None = None
    slip: PackingSlip | None = None
    invoice: Invoice | None = None
    commit: str | None = None
    verdict: str = "implemented"
    summary: str = ""


class _ReviewedMergeQueue(MergeQueue):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.admission_state: dict[tuple[str, int], _AdmissionState] = {}

    async def admit(self, candidate: Candidate):
        key = candidate.stem, candidate.run_seq
        try:
            # Capture before waiting: only this admission moves its worktree.
            self.admission_state[key] = _AdmissionState(
                await self._git.rev_parse(candidate.worktree, "HEAD"))
            return await super().admit(candidate)
        finally:
            self.admission_state.pop(key, None)

    async def admit_delivery(self, candidate: Candidate, *, ticket: Ticket,
                             delivery: Delivery, reviewed_head: str | None):
        key = candidate.stem, candidate.run_seq
        assert delivery.slip is not None
        state = _AdmissionState(
            reviewed_head=reviewed_head, ticket=ticket, verdict=delivery.slip.verdict,
            summary=delivery.slip.summary)
        self.admission_state[key] = state
        try:
            result = await super().admit(candidate)
            soft = list(state.invoice.soft_findings) if state.invoice is not None else []
            return result, state.commit, soft
        finally:
            self.admission_state.pop(key, None)


def compose_merge_queue(*, repo: Path, config: Config, env: Mapping[str, str], journal: Journal,
                        process: ProcessExec, fs: Filesystem, git: Git,
                        control_inbox: ControlInbox, admission_hold: AdmissionHold,
                        regate, integration_check, integrate):
    """Build admission over the lock holder's shared control state."""
    if admission_hold.inbox is not control_inbox:
        raise ValueError("admission hold must use the shared control inbox")
    return _ReviewedMergeQueue(
        repo=repo, config=config, git=git, process=process, fs=fs, journal=journal,
        env=child_env(env, {p.auth for p in config.providers if p.auth}),
        regate=regate, integration_check=integration_check, integrate=integrate,
        admission_hold=admission_hold,
        timeout=config.drain.max_ticket_minutes * 60)
