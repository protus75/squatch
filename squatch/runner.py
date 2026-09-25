"""The `run <stem>` scaffold: intake, single-writer lock, dispatch (SQUATCH_PLAN.md
sections 9, 11, 18; section 19, Phase 1).

One process holds the single-writer lock for the whole verb: take the lock,
open the journal, reconcile on entry (reap any orphaned in-flight run an
interrupted predecessor left, section 11.2), intake pending hand-authored
tickets through the ticket-plane lane, validate the named stem against the committed ticket plane
and its eligibility (`confirmed`, every `depends` merged, not merged), journal
the run's `running` transition, and hand the stem to the stage-dispatch seam.
The stages and the merge admission live BEHIND that seam (`Pipeline`, built
over the lock-held journal by the factory the caller supplies); this module
owns the run's terminal `state_transition` write for every non-ok outcome
(the section 9 ownership law) and the section 18 exit-code contract: 0 = the
ticket settled, 1 = a non-ok ticket terminal (ticket and branch left in
place; the engine log is where its detail lives in Phase 1), 2 = an
engine-plane refusal (lock, config, journal, eligibility, and any FAULT
escaping the stage seam -- named and stopped, never a traceback; the run it
interrupted stays `running` with no terminal until reconcile-on-entry reaps
it, section 11.2).
"""

import traceback
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Protocol

from squatch.artifacts import OUTCOMES, Finding
from squatch.config import Config
from squatch.effects import run_sequence
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Event, Journal, JournalCorruption
from squatch.lockfile import LockHeld, Lockfile
from squatch.reconcile import reconcile
from squatch.seams import Clock, ExecutableNotFound, Filesystem
from squatch.tickets import (PLAN_FILE, TICKET_FILE, TICKETS_DIR, Intake, IntakeResult, Ticket,
                             TicketLintError, lint_ticket)

EXIT_OK = 0
EXIT_TICKET = 1
EXIT_REFUSED = 2

SETTLED = frozenset({"ok", "already_satisfied"})

Report = Callable[[str], None]


class Refusal(Exception):
    """An engine-plane refusal (exit 2). Never a traceback: a message plus the
    paved road that releases it."""

    def __init__(self, message: str, paved_road: str):
        self.message = message
        self.paved_road = paved_road
        super().__init__(f"{message} -- {paved_road}")


class Pipeline(Protocol):
    """The stage-dispatch seam: Implement -> Check -> Review -> Merge for one
    validated, lock-held stem. Returns the run's `Outcome`; on `ok` /
    `already_satisfied` the admission behind the seam has journaled the
    `to: merged` transition, and every other value is the non-ok terminal
    the runner journals."""

    async def run(self, ticket: Ticket, *, run_seq: int) -> str: ...


# The journal is opened under the lock, so the pipeline over it is built there.
PipelineFactory = Callable[[Journal], Pipeline]


def merged_stems(events: Iterable[Event]) -> frozenset[str]:
    return frozenset(e.ticket for e in events
                     if e.type == "state_transition" and e.body.get("to") == "merged"
                     and e.ticket is not None)


class Runner:
    def __init__(self, *, repo: Path, config: Config, git: Git, fs: Filesystem, clock: Clock,
                 instance_id: str, pipeline: PipelineFactory, log: EngineLog, report: Report):
        self._repo = Path(repo)
        self._config = config
        self._git = git
        self._fs = fs
        self._clock = clock
        self._instance_id = instance_id
        self._pipeline = pipeline
        self._log = log
        self._report = report

    @property
    def state_dir(self) -> Path:
        return self._repo / self._config.state_dir

    async def run(self, stem: str) -> int:
        lock = Lockfile(self.state_dir, instance_id=self._instance_id, clock=self._clock)
        try:
            lock.acquire()
        except LockHeld as e:
            raise Refusal(str(e), "wait for the holding process to exit; the kernel frees the "
                          "lock when it dies, so no stale lock needs reclaiming") from None
        try:
            try:
                journal = Journal(self.state_dir, clock=self._clock)
            except JournalCorruption as e:
                raise Refusal(f"journal corruption: {e}",
                              "a corrupt record is never skipped; inspect the named segment "
                              "line and repair it from the engine log before re-running") from None
            with journal:
                return await self._locked(stem, journal)
        finally:
            lock.release()

    async def _locked(self, stem: str, journal: Journal) -> int:
        await reconcile(repo=self._repo, config=self._config, git=self._git, journal=journal,
                        log=self._log, report=self._report)
        intake = Intake(repo=self._repo, git=self._git, journal=journal, fs=self._fs)
        result = await intake.run()
        self._report_intake(result)
        ticket = self._validated(stem, result)
        self._eligible(ticket, journal)
        run_seq = run_sequence(journal, stem)
        journal.append("state_transition", {"to": "running", "run_seq": run_seq}, ticket=stem)
        try:
            outcome = await self._pipeline(journal).run(ticket, run_seq=run_seq)
            if outcome not in OUTCOMES:
                raise TypeError(f"the stage seam returned {outcome!r}, not an Outcome "
                                f"(one of {sorted(OUTCOMES)})")
        except Refusal:
            raise
        except Exception as e:
            raise self._fault(stem, run_seq, e) from None
        if outcome in SETTLED:
            self._report(f"settled: {stem} run {run_seq} ended {outcome}")
            return EXIT_OK
        journal.append("state_transition", {"to": outcome, "run_seq": run_seq}, ticket=stem)
        self._report(f"stopped: {stem} run {run_seq} ended {outcome}; ticket and branch left "
                     f"in place; detail: {self._log.path}")
        return EXIT_TICKET

    def _fault(self, stem: str, run_seq: int, e: Exception) -> Refusal:
        """A fault outside the stage vocabulary: the traceback goes to the
        engine log, the operator gets a named stop. No terminal is written --
        the orphaned `running` is reconcile's to reap as `abandoned`."""
        self._log.event("fault", ticket=stem, run_seq=run_seq, error=type(e).__name__,
                        message=str(e), traceback="".join(traceback.format_exception(e)))
        orphan = (f"run {run_seq} of {stem} is left `running` with no terminal for the next "
                  f"entry to reconcile (section 11.2); fix the cause, then `squatch run {stem}`")
        if isinstance(e, ExecutableNotFound):
            return Refusal(f"{stem} run {run_seq}: `{e}` is not on PATH",
                           f"install it, or fix the provider `cli` entry that names it; {orphan}")
        return Refusal(f"{stem} run {run_seq} faulted: {type(e).__name__}: {e}",
                       f"traceback at {self._log.path}; {orphan}")

    def _report_intake(self, result: IntakeResult) -> None:
        for c in result.committed:
            self._report(f"intake: committed {c.stem} ({c.source}, {c.state}) at {c.sha[:12]}")
        for r in result.refused:
            self._report(f"intake: refused {r.stem}")
            for f in r.findings:
                self._report(f"  {f.message} -- {f.paved_road}")

    def _path(self, stem: str) -> Path:
        return self._repo / TICKETS_DIR / stem / TICKET_FILE

    def _validated(self, stem: str, intake: IntakeResult) -> Ticket:
        """The stem as the committed ticket plane holds it, re-linted."""
        refused = next((r for r in intake.refused if r.stem == stem), None)
        if refused is not None:
            raise Refusal(f"{stem} was refused at intake: " + _first(refused.findings),
                          "fix the named findings in tickets/%s/%s and re-run" % (stem, TICKET_FILE))
        path = self._path(stem)
        if not path.is_file():
            raise Refusal(f"no ticket at {TICKETS_DIR}/{stem}/{TICKET_FILE}",
                          f"author it with `squatch new {stem}` (or hand-author the file), then re-run")
        plan = self._repo / PLAN_FILE
        try:
            return lint_ticket(path.read_text(), stem=stem, repo=self._repo,
                               plan=plan.read_text() if plan.is_file() else None,
                               resolve_stem=lambda s: self._path(s).is_file())
        except TicketLintError as e:
            raise Refusal(f"{stem} no longer lints: " + _first(e.findings),
                          "the committed ticket drifted from the grammar (a Context file removed, "
                          "a dependency dir gone); edit ticket.md and re-run") from None

    def _eligible(self, ticket: Ticket, journal: Journal) -> None:
        if ticket.state != "confirmed":
            raise Refusal(f"{ticket.stem} is `state: {ticket.state}`, not `confirmed`",
                          "intake commits hand-authored tickets `confirmed`; set state: confirmed "
                          "in ticket.md and re-run")
        merged = merged_stems(journal.read())
        if ticket.stem in merged:
            raise Refusal(f"{ticket.stem} is already merged",
                          "a merged stem never re-runs; author a new ticket for further work")
        unmerged = [d for d in ticket.depends if d not in merged]
        if unmerged:
            raise Refusal(f"{ticket.stem} depends on unmerged {', '.join(unmerged)}",
                          "run the dependencies first (`squatch run <stem>` each), or `drain`")


def _first(findings: Iterable[Finding]) -> str:
    f = next(iter(findings))
    return f"{f.message} -- {f.paved_road}"
