"""Serial merge admission with a daemon-composed Rework consumer (section 20).

Direct callers hand it the two check tiers and the integration operation; the
queue owns their ordering, conflict resolution, conflict facts, and the
checked-tree invariant.  A composed Rework consumer receives the same typed
post-unwind handoff through ``next_rework``; this module owns neither a second
queue nor a second handoff schema.
"""

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from squatch.artifacts import ClosedModel, Finding
from squatch.config import Config, Strategy
from squatch.control import ControlInbox, ControlRequest
from squatch.git import Git, GitError, RebaseConflict
from squatch.journal import Journal
from squatch.seams import Filesystem, ProcessExec

CONFLICT_FACTS_SIGNAL = "merge_conflict_facts"
TREE_HASH_CODE = "candidate_tree_hash"
TREE_HASH_ROAD = ("re-run the candidate from its reviewed branch head; admission leaves main "
                  "untouched when the checked candidate tree changes")
REBASE_FAILURE_CODE = "candidate_rebase"
REBASE_FAILURE_ROAD = "correct the reported rebase precondition and retry admission"


class Candidate(ClosedModel):
    stem: str
    branch: str
    worktree: Path
    run_seq: int


class ResolutionHit(ClosedModel):
    path: str
    strategy: Literal["regenerate", "union"]


class ConflictFacts(ClosedModel):
    stem: str
    paths: tuple[str, ...] = ()
    rung: Literal["none", "mechanical", "rework"] = "none"
    strategy_hits: tuple[ResolutionHit, ...] = ()
    integration_red_paths: tuple[str, ...] = ()


class UnresolvedConflictHandoff(ClosedModel):
    """Rung 2's input.  Rework imports this record instead of redefining it."""

    kind: Literal["unresolved_conflict"] = "unresolved_conflict"
    stem: str
    branch: str
    run_seq: int
    approval_invalidated: Literal[True] = True
    facts: ConflictFacts


class CandidateTreeHashFinding(Finding):
    code: Literal["candidate_tree_hash"] = TREE_HASH_CODE


class CandidateRebaseFinding(Finding):
    code: Literal["candidate_rebase"] = REBASE_FAILURE_CODE


class Admission(ClosedModel):
    outcome: Literal["integrated", "gate_failed", "rework"]
    findings: tuple[Finding, ...] = ()
    checked_tree: str | None = None
    conflict_facts: ConflictFacts
    rework: UnresolvedConflictHandoff | None = None


Check = Callable[[Candidate], Awaitable[Sequence[Finding]]]
Integrate = Callable[[Candidate], Awaitable[None]]


class AdmissionHold:
    """One session's integration streak and durable, identity-bound hold."""

    def __init__(self, inbox: ControlInbox, journal: Journal):
        self.inbox = inbox
        self._journal = journal
        self._reds: set[str] = set()
        self.hold_id: UUID | None = None
        self._released = asyncio.Event()
        self._released.set()
        for event in journal.read():
            body = event.body
            if (event.type == "signal" and body.get("kind") == "control_hold"
                    and body.get("trigger") in {"integration_red_streak", "tree_hash_mismatch"}
                    and body.get("lifecycle") == str(inbox.lifecycle)):
                hold_id = UUID(body["hold_id"])
                if hold_id in inbox.holds:
                    self.hold_id = hold_id
                    self._released.clear()

    async def wait(self) -> None:
        await self._released.wait()

    def integration_result(self, candidate: Candidate, *, red: bool) -> None:
        if not red:
            self._reds.clear()
            return
        self._reds.add(candidate.stem)
        if len(self._reds) >= 3:
            self.trip(candidate, trigger="integration_red_streak")

    def trip(self, candidate: Candidate, *, trigger: Literal[
            "integration_red_streak", "tree_hash_mismatch"]) -> None:
        if self.hold_id is not None:
            return
        hold_id = uuid4()
        self._journal.append("signal", {
            "kind": "control_hold", "hold_id": str(hold_id), "released": False,
            "lifecycle": str(self.inbox.lifecycle), "trigger": trigger,
            "stems": sorted(self._reds), "run_seq": candidate.run_seq,
        }, ticket=candidate.stem)
        # Identity and trigger commit together before either consumer mutates.
        # Rehydration also recovers a crash immediately after this append.
        self.inbox.rehydrate_holds()
        self.hold_id = hold_id
        self._reds.clear()
        self._released.clear()

    async def apply(self, request: ControlRequest) -> None:
        if (request.action == "release" and request.lifecycle == self.inbox.lifecycle
                and self.hold_id is not None and request.hold_id == self.hold_id):
            self.hold_id = None
            self._reds.clear()
            self._released.set()


class MergeQueue:
    """One non-preemptive admission slot with a post-unwind Rework outbox."""

    def __init__(self, *, repo: Path, config: Config, git: Git, process: ProcessExec,
                 fs: Filesystem, journal: Journal, env: Mapping[str, str],
                 regate: Check, integration_check: Check, integrate: Integrate,
                 timeout: float = 60.0, admission_hold: AdmissionHold | None = None):
        self._repo = Path(repo)
        self._strategies = tuple(config.merge.strategies)
        self._git = git
        self._process = process
        self._fs = fs
        self._journal = journal
        self._env = env
        self._regate = regate
        self._integration_check = integration_check
        self._integrate = integrate
        self._timeout = timeout
        self._slot = asyncio.Lock()
        self._rework: asyncio.Queue[UnresolvedConflictHandoff] = asyncio.Queue()
        self.admission_hold = admission_hold

    async def admit(self, candidate: Candidate) -> Admission:
        """Admit one candidate; concurrent callers wait for the same serial slot."""
        async with self._slot:
            hold = getattr(self, "admission_hold", None)
            if hold is not None:
                await hold.wait()
            admission = await self._admit(candidate)

        # Rung 2 becomes observable only after rebase abort and after the
        # admission slot has unwound.  Rework can therefore never run inline.
        if admission.rework is not None:
            self._rework.put_nowait(admission.rework)
        return admission

    async def next_rework(self) -> UnresolvedConflictHandoff:
        """Consume the next rung-2 record after its admission has unwound."""
        return await self._rework.get()

    async def _admit(self, candidate: Candidate) -> Admission:
        facts, unresolved, rebase_findings = await self._rebase(candidate)
        if rebase_findings:
            self._record(candidate, facts)
            return Admission(outcome="gate_failed", findings=rebase_findings,
                             conflict_facts=facts)
        if unresolved:
            self._record(candidate, facts)
            handoff = UnresolvedConflictHandoff(
                stem=candidate.stem, branch=candidate.branch,
                run_seq=candidate.run_seq, facts=facts)
            return Admission(outcome="rework", conflict_facts=facts, rework=handoff)

        findings = tuple(await self._regate(candidate))
        if findings:
            self._record(candidate, facts)
            return Admission(outcome="gate_failed", findings=findings,
                             conflict_facts=facts)

        # This is the exact tree exercised by the full integration check.
        checked_tree = await self._git.rev_parse(candidate.worktree, "HEAD^{tree}")
        findings = tuple(await self._integration_check(candidate))
        hold = getattr(self, "admission_hold", None)
        if hold is not None:
            hold.integration_result(candidate, red=bool(findings))
        if findings:
            facts = facts.model_copy(update={
                "integration_red_paths": tuple(dict.fromkeys(
                    finding.path for finding in findings if finding.path is not None))})
            self._record(candidate, facts)
            return Admission(outcome="gate_failed", findings=findings,
                             checked_tree=checked_tree, conflict_facts=facts)

        # No bytes may move to main between this assertion and integration.
        current_tree = await self._git.rev_parse(candidate.worktree, "HEAD^{tree}")
        if current_tree != checked_tree:
            if hold is not None:
                hold.trip(candidate, trigger="tree_hash_mismatch")
            finding = CandidateTreeHashFinding(
                message=(f"{candidate.stem}: checked candidate tree {checked_tree} changed to "
                         f"{current_tree} before integration"),
                paved_road=TREE_HASH_ROAD)
            self._record(candidate, facts)
            return Admission(outcome="gate_failed", findings=(finding,),
                             checked_tree=checked_tree, conflict_facts=facts)

        await self._integrate(candidate)
        self._record(candidate, facts)
        return Admission(outcome="integrated", checked_tree=checked_tree,
                         conflict_facts=facts)

    async def _rebase(
            self, candidate: Candidate
    ) -> tuple[ConflictFacts, bool, tuple[Finding, ...]]:
        try:
            await self._git.rebase_stop_at_conflict(candidate.worktree, "main")
        except RebaseConflict:
            pass
        except GitError as error:
            facts = ConflictFacts(stem=candidate.stem)
            finding = CandidateRebaseFinding(
                message=(f"{candidate.stem}: rebase failed before git stopped on a conflict "
                         f"(exit {error.rc})"),
                paved_road=REBASE_FAILURE_ROAD)
            return facts, False, (finding,)
        else:
            return ConflictFacts(stem=candidate.stem), False, ()

        paths: list[str] = []
        hits: list[ResolutionHit] = []
        completed = False
        failure: BaseException | None = None
        try:
            while True:
                conflicted = await self._git.conflicted_paths(candidate.worktree)
                paths.extend(path for path in conflicted if path not in paths)
                resolved = await self._resolve(candidate.worktree, conflicted)
                if resolved is None:
                    break
                hits.extend(resolved)
                try:
                    await self._git.rebase_continue(candidate.worktree)
                except GitError:
                    # A later commit may expose another conflict; inspect it on
                    # the next turn.  A non-conflict failure also fails closed.
                    if await self._git.conflicted_paths(candidate.worktree):
                        continue
                    break
                completed = True
                break
        except BaseException as error:
            failure = error

        facts = ConflictFacts(stem=candidate.stem, paths=tuple(paths),
                              rung="mechanical" if completed else "rework",
                              strategy_hits=tuple(hits))
        if not completed:
            # One unwind owns every refusal and exception. A failed abort
            # cannot emit a Rework handoff for a still-conflicted worktree.
            try:
                await self._git.rebase_abort(candidate.worktree)
            except GitError as error:
                if failure is not None and not isinstance(failure, GitError):
                    raise failure from error
                finding = CandidateRebaseFinding(
                    message=f"{candidate.stem}: rebase abort failed (exit {error.rc})",
                    paved_road="restore the candidate worktree to its branch head, then "
                               "correct the reported rebase precondition and retry admission")
                return facts, False, (finding,)
        if isinstance(failure, GitError):
            finding = CandidateRebaseFinding(
                message=f"{candidate.stem}: conflict resolution failed (exit {failure.rc})",
                paved_road=REBASE_FAILURE_ROAD)
            return facts, False, (finding,)
        if failure is not None:
            raise failure
        return facts, not completed, ()

    async def _resolve(self, worktree: Path,
                       paths: Sequence[str]) -> tuple[ResolutionHit, ...] | None:
        if not paths:
            return None
        selected: list[tuple[str, Strategy]] = []
        for path in paths:
            matches = [strategy for strategy in self._strategies
                       if any(_path_matches(path, declared) for declared in strategy.paths)]
            if len(matches) != 1:
                return None
            selected.append((path, matches[0]))

        regenerate: list[Strategy] = []
        for path, strategy in selected:
            target = worktree / path
            try:
                text = target.read_text()
                resolved = _resolve_markers(text, union=strategy.strategy == "union")
            except (OSError, ValueError, UnicodeError):
                return None
            self._fs.write(target, resolved.encode())
            if strategy.strategy == "regenerate" and strategy not in regenerate:
                regenerate.append(strategy)

        for strategy in regenerate:
            assert strategy.argv is not None
            rc, _, _ = await self._process.run(
                strategy.argv, cwd=worktree, env=self._env, timeout=self._timeout)
            if rc != 0:
                return None
        await self._git.add(worktree, paths)
        return tuple(ResolutionHit(path=path, strategy=strategy.strategy)
                     for path, strategy in selected)

    def _record(self, candidate: Candidate, facts: ConflictFacts) -> None:
        self._journal.append(
            "signal", {"kind": CONFLICT_FACTS_SIGNAL,
                       **facts.model_dump(mode="json", exclude={"stem"})},
            ticket=candidate.stem,
            key=f"{CONFLICT_FACTS_SIGNAL}/{candidate.stem}/{candidate.run_seq}")


def _path_matches(path: str, declared: str) -> bool:
    return path == declared or path.startswith(
        declared if declared.endswith("/") else declared + "/")


def _resolve_markers(text: str, *, union: bool) -> str:
    """Resolve ordinary or diff3 conflict markers, preserving outer context."""
    out: list[str] = []
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        if not lines[i].startswith("<<<<<<< "):
            if lines[i].startswith(("=======", ">>>>>>> ", "||||||| ")):
                raise ValueError("unbalanced conflict marker")
            out.append(lines[i])
            i += 1
            continue
        i += 1
        ours: list[str] = []
        while i < len(lines) and not lines[i].startswith(("||||||| ", "=======")):
            ours.append(lines[i])
            i += 1
        if i < len(lines) and lines[i].startswith("||||||| "):
            i += 1
            while i < len(lines) and not lines[i].startswith("======="):
                i += 1
        if i >= len(lines) or not lines[i].startswith("======="):
            raise ValueError("incomplete conflict marker")
        i += 1
        theirs: list[str] = []
        while i < len(lines) and not lines[i].startswith(">>>>>>> "):
            theirs.append(lines[i])
            i += 1
        if i >= len(lines):
            raise ValueError("incomplete conflict marker")
        out.extend(ours)
        if union:
            out.extend(theirs)
        i += 1
    return "".join(out)
