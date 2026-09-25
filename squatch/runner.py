"""The scaffold verbs' shared spine: the lock-held session and one stem's
dispatch (SQUATCH_PLAN.md sections 9, 11, 18; section 19, Phase 2).

One process holds the single-writer lock for the whole verb. `Runner.session`
takes the lock, opens the journal, reconciles on entry (reaping any orphaned
in-flight run an interrupted predecessor left, section 11.2), and intakes
pending hand-authored tickets through the ticket-plane lane. `Runner.dispatch`
drives ONE validated stem: it journals the run's `running` transition, hands
the stem to the stage-dispatch seam, and owns the non-ok terminal handler:
harvest, cap draw where applicable, terminal `state_transition`, then worktree
wipe (the section 9 ownership law). `run <stem>` composes the two around one
named stem; `drain`
(`squatch.drain`) composes them around the eligibility sort it owns.

The stages and the merge admission live BEHIND the seam (`Pipeline`, built
over the lock-held journal by the factory the caller supplies). The section
18 exit-code contract: 0 = settled, 1 = a non-ok ticket terminal (ticket and
branch left in place; the attempt directory holds its harvested detail),
2 = an engine-plane refusal (lock, config, journal, eligibility, and any
FAULT escaping the stage seam -- named and stopped, never a traceback; the
run it interrupted stays `running` with no terminal until reconcile-on-entry
reaps it, section 11.2).
"""

import traceback
from collections.abc import AsyncIterator, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from squatch.artifacts import OUTCOMES, Finding
from squatch.box import Box
from squatch.caps import INFRA_CAP, PREMISE_BOUNCE_CAP, consume
from squatch.config import Config
from squatch.diagnose import DIAGNOSIS_FILE, DiagnosisRecord
from squatch.effects import Effects, run_sequence
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.harvest import extract
from squatch.journal import Event, Journal, JournalCorruption
from squatch.ladder import Rung, effective, finding_codes, rungs
from squatch.lockfile import LockHeld, Lockfile
from squatch.reconcile import reconcile
from squatch.reject import ARRIVAL, route
from squatch.seams import Clock, ExecutableNotFound, Filesystem
from squatch.stages import Delivery, lift_ticket_files
from squatch.tickets import (PLAN_FILE, TICKET_FILE, TICKETS_DIR, Intake, IntakeResult, Ticket,
                             TicketLintError, depends_of, lint_ticket, on_disk_stems,
                             parse_frontmatter, stamp)

EXIT_OK = 0
EXIT_TICKET = 1
EXIT_REFUSED = 2

SETTLED = frozenset({"ok", "already_satisfied"})
VERDICT_SIGNALS = frozenset({"confirm", "reject"})
ACTORS = frozenset({"operator", "machine"})

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

    async def run(self, ticket: Ticket, *, run_seq: int) -> Delivery: ...

    async def diagnose(self, ticket: Ticket, delivery: Delivery, *,
                       run_seq: int) -> DiagnosisRecord: ...


# The journal is opened under the lock, so the pipeline over it is built there.
PipelineFactory = Callable[[Journal], Pipeline]


def merged_stems(events: Iterable[Event]) -> frozenset[str]:
    return frozenset(e.ticket for e in events
                     if e.type == "state_transition" and e.body.get("to") == "merged"
                     and e.ticket is not None)


@dataclass(frozen=True)
class Session:
    """What a verb holds once it is the writer: the open journal and the
    intake result of its entry."""

    journal: Journal
    intake: IntakeResult


@dataclass(frozen=True)
class Dispatched:
    run_seq: int
    outcome: str

    @property
    def settled(self) -> bool:
        return self.outcome in SETTLED


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

    @property
    def log_path(self) -> Path:
        return self._log.path

    @asynccontextmanager
    async def session(self) -> AsyncIterator[Session]:
        """Lock -> journal -> reconcile -> intake; the lock is held until exit."""
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
                await reconcile(repo=self._repo, config=self._config, git=self._git,
                                journal=journal, log=self._log, report=self._report)
                intake = Intake(repo=self._repo, git=self._git, journal=journal, fs=self._fs)
                result = await intake.run()
                self._report_intake(result)
                yield Session(journal, result)
        finally:
            lock.release()

    async def run(self, stem: str) -> int:
        async with self.session() as session:
            ticket = self.validated(stem, session.intake)
            self._eligible(ticket, session.journal)
            run = await self.dispatch(ticket, session.journal)
            return EXIT_OK if run.settled else EXIT_TICKET

    async def confirm(self, stem: str) -> int:
        async with self.session() as session:
            events = tuple(session.journal.read())
            self._identity(stem, events)
            self._verdictable(stem, events)
            sha = await self._ticket_sha(stem)
            path = self._path(stem)
            if path.is_file():
                meta, _ = parse_frontmatter(path.read_text())
                if meta.get("state") == "draft":
                    source = meta.get("source")
                    intake = Intake(repo=self._repo, git=self._git, journal=session.journal,
                                    fs=self._fs)
                    await intake.commit(stem, source=source, state="confirmed")
                    sha = await self._ticket_sha(stem)
                    self._verdict(session.journal, stem, "confirm", sha, events,
                                  "draft confirmed")
                    self._report(f"confirmed: {stem} moved from draft to confirmed")
                    return EXIT_OK
                if (meta.get("state") == "confirmed"
                        and not any(e.type == "state_transition" for e in events
                                    if e.ticket == stem)):
                    raise Refusal(f"{stem} is confirmed and has never run",
                                  "nothing is parked or awaiting a verdict to confirm")
            previous = next((e for e in reversed(events)
                             if e.ticket == stem and e.type == "signal"
                             and e.body.get("kind") == "confirm"
                             and e.body.get("actor") == "operator"), None)
            if previous is not None and previous.body.get("ticket_sha") == sha:
                raise Refusal(f"{stem} was already confirmed at this ticket revision",
                              "edit the ticket (or fix the plan and regenerate it) before "
                              "re-enqueueing")
            self._verdict(session.journal, stem, "confirm", sha, events, "operator keep")
            self._report(f"confirmed: {stem} re-enqueued")
            return EXIT_OK

    async def reject(self, stem: str) -> int:
        async with self.session() as session:
            events = tuple(session.journal.read())
            self._identity(stem, events)
            self._verdictable(stem, events)
            sha = await self._ticket_sha(stem)
            run_seq = self._latest_run_seq(stem, events)
            stamped: str | None = None
            source: str | None = None
            path = self._path(stem)
            if path.is_file():
                text = path.read_text()
                try:
                    stamped = stamp(text, state="rejected")
                except ValueError:
                    # An unstampable ticket is a journal-only kill, like a
                    # dirless identity.  Decide that before the terminal writes.
                    pass
                else:
                    try:
                        meta, _ = parse_frontmatter(text)
                        source = meta.get("source")
                    except ValueError:
                        pass
            self._verdict(session.journal, stem, "reject", sha, events, "operator kill")
            session.journal.append("state_transition", {"to": "rejected", "run_seq": run_seq},
                                   ticket=stem)
            if stamped is not None:
                intake = Intake(repo=self._repo, git=self._git, journal=session.journal,
                                fs=self._fs)
                await intake.commit_lane(stem, stamped, source=source, state="rejected")
            dead = await self._dead_dependents(stem, session.journal, events)
            self._report(f"rejected: {stem}; {dead} dependent(s) reported")
            return EXIT_OK

    def _identity(self, stem: str, events: tuple[Event, ...]) -> None:
        if not any(e.ticket == stem for e in events):
            raise Refusal(f"{stem} has no journal identity; intake or author it first",
                          f"run or drain {stem} through intake before applying a verdict")

    def _verdictable(self, stem: str, events: tuple[Event, ...]) -> None:
        if stem in merged_stems(events):
            raise Refusal(f"{stem} is already merged",
                          "a merged stem has no Reject-queue verdict to resolve")
        latest = next((e.body.get("to") for e in reversed(events)
                       if e.ticket == stem and e.type == "state_transition"), None)
        if latest == "rejected":
            raise Refusal(f"{stem} is already rejected",
                          "a rejected stem is terminal; author a successor for further work")

    async def _ticket_sha(self, stem: str) -> str | None:
        if not self._path(stem).is_file():
            return None
        return await self._git.rev_parse(self._repo, f"HEAD:{TICKETS_DIR}/{stem}/{TICKET_FILE}")

    def _latest_run_seq(self, stem: str, events: tuple[Event, ...]) -> int | None:
        seq = None
        for event in events:
            if event.ticket == stem and isinstance(event.body.get("run_seq"), int):
                seq = event.body["run_seq"]
        return seq

    def _verdict(self, journal: Journal, stem: str, kind: str, ticket_sha: str | None,
                 events: tuple[Event, ...], reason: str, *, actor: str = "operator") -> None:
        if kind not in VERDICT_SIGNALS:
            raise ValueError(f"unknown verdict signal {kind!r}")
        if actor not in ACTORS:
            raise ValueError(f"unknown verdict actor {actor!r}")
        journal.append("signal", {"kind": kind, "actor": actor,
                                  "ticket_sha": ticket_sha,
                                  "run_seq": self._latest_run_seq(stem, events),
                                  "reason": reason}, ticket=stem)

    async def signal_verdict(self, journal: Journal, stem: str, kind: str, *, actor: str,
                             reason: str) -> None:
        """The shared verdict-signal writer used by operator verbs and drain auto-keep."""
        events = tuple(journal.read())
        self._verdict(journal, stem, kind, await self._ticket_sha(stem), events, reason,
                      actor=actor)

    async def _dead_dependents(self, dead: str, journal: Journal,
                               events: tuple[Event, ...]) -> int:
        merged = merged_stems(events)
        box = Box(self.state_dir, fs=self._fs, clock=self._clock)
        count = 0
        for dependent in on_disk_stems(self._repo):
            if dependent == dead or dependent in merged:
                continue
            path = self._path(dependent)
            try:
                await self._git.rev_parse(
                    self._repo, f"HEAD:{TICKETS_DIR}/{dependent}/{TICKET_FILE}")
            except GitError:
                continue
            if dead not in depends_of(path.read_text()):
                continue
            journal.append("signal", {"kind": "dead_dependency", "dead": dead,
                                      "dependent": dependent}, ticket=dependent)
            road = (f"{dependent} depends on rejected {dead}; re-wire, re-scope, or "
                    f"`squatch reject {dependent}`")
            box.enqueue(message_class="failure_report",
                        summary=f"{dependent} is blocked by rejected {dead}", detail=road,
                        origin=dead)
            count += 1
        return count

    async def dispatch(self, ticket: Ticket, journal: Journal) -> Dispatched:
        """One run of a validated, eligible stem under the held lock: the
        `running` transition, the stage seam, and the non-ok terminal write."""
        stem = ticket.stem
        tier, effort = effective(ticket, rungs(journal.read(), stem))
        ticket = replace(ticket, agent_tier=tier, agent_effort=effort)
        run_seq = run_sequence(journal, stem)
        journal.append("state_transition", {"to": "running", "run_seq": run_seq}, ticket=stem)
        started = self._clock()
        try:
            pipeline = self._pipeline(journal)
            delivery = await pipeline.run(ticket, run_seq=run_seq)
            if not isinstance(delivery, Delivery):
                raise TypeError(f"the stage seam returned {delivery!r}, not a Delivery")
            outcome = delivery.outcome
            if outcome not in OUTCOMES:
                raise TypeError(f"the stage seam returned {outcome!r}, not an Outcome "
                                f"(one of {sorted(OUTCOMES)})")
        except Refusal:
            raise
        except Exception as e:
            raise self._fault(stem, run_seq, e) from None
        if outcome in SETTLED:
            self._report(f"settled: {stem} run {run_seq} ended {outcome}")
            return Dispatched(run_seq, outcome)
        attempt = f"{TICKETS_DIR}/{stem}/attempts/{run_seq}"
        harvested: str | None = None
        harvest_error: str | None = None
        if delivery.worktree.is_dir():
            try:
                files = await extract(
                    repo=self._repo, state_dir=self.state_dir, git=self._git, stem=stem,
                    run_seq=run_seq, worktree=delivery.worktree, base=delivery.base,
                    outcome=outcome, stage=delivery.stage, reason=delivery.reason,
                    findings=delivery.findings, cost=delivery.cost,
                    wall_seconds=max(0.0, (self._clock() - started).total_seconds()),
                    box=Box(self.state_dir, fs=self._fs, clock=self._clock),
                    redact=self._log._redact)
                await lift_ticket_files(
                    repo=self._repo, git=self._git, fs=self._fs, effects=Effects(journal),
                    redact=self._log._redact, stem=stem, run_seq=run_seq, kind="harvest",
                    files=files)
                harvested = attempt
            except Exception as e:
                harvest_error = f"{type(e).__name__}: {e}"
                self._log.event("harvest_error", ticket=stem, run_seq=run_seq,
                                error=type(e).__name__, message=str(e),
                                traceback="".join(traceback.format_exception(e)))
        if outcome in {"infra_error", "timeout"}:
            await consume(journal, repo=self._repo, git=self._git, stem=stem, cap=INFRA_CAP,
                          run_seq=run_seq)
        elif outcome == "premise_failed":
            await consume(journal, repo=self._repo, git=self._git, stem=stem,
                          cap=PREMISE_BOUNCE_CAP, run_seq=run_seq)
        try:
            diagnosis = await pipeline.diagnose(ticket, delivery, run_seq=run_seq)
            await lift_ticket_files(
                repo=self._repo, git=self._git, fs=self._fs, effects=Effects(journal),
                redact=self._log._redact, stem=stem, run_seq=run_seq, kind="diagnosis",
                files={DIAGNOSIS_FILE: diagnosis.model_dump_json(indent=2).encode()})
        except Refusal:
            raise
        except Exception as e:
            raise self._fault(stem, run_seq, e) from None
        codes = finding_codes(delivery)
        reason = ",".join(codes) if codes else outcome
        body = {"to": outcome, "run_seq": run_seq, "harvest": harvested,
                "reason": reason, "finding_codes": list(codes),
                "diagnosis": diagnosis.model_dump(mode="json")}
        if harvest_error is not None:
            body["harvest_error"] = harvest_error
        routing = route(self._config, journal.read(), stem, outcome, diagnosis,
                        current=Rung(tier, effort), delivery=delivery)
        if routing.routed is not None:
            body["routed"] = routing.routed
        if routing.routed == "reject_queue":
            body["reject_reason"] = routing.reason
        if routing.rung is not None:
            body["rung"] = routing.rung.body()
        journal.append("state_transition", body, ticket=stem)
        if routing.routed == "reject_queue":
            journal.append("signal", {"kind": "escalation", "escalation": ARRIVAL,
                                      "reason": routing.reason, "run_seq": run_seq},
                           ticket=stem)
        if delivery.worktree.exists():
            await self._git.worktree_remove(self._repo, delivery.worktree)
        else:
            await self._git.worktree_prune(self._repo)
        suffix = (f"; reject queue: `squatch confirm {stem}` to keep or "
                  f"`squatch reject {stem}` to kill"
                  if routing.routed == "reject_queue" else "")
        self._report(f"stopped: {stem} run {run_seq} ended {outcome}; branch left in place; "
                     f"detail: {attempt}/{suffix}")
        return Dispatched(run_seq, outcome)

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

    def validated(self, stem: str, intake: IntakeResult) -> Ticket:
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
