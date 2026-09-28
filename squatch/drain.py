"""The `drain` verb: run the ready queue to quiescence (SQUATCH_PLAN.md sections
9, 11, 18; section 19, Phase 1).

One process holds the single-writer lock for the whole verb (the runner's
session: lock, journal, reconcile-on-entry, intake). This module owns the
ELIGIBILITY SORT (the section 9 ownership law): eligible = a committed
`confirmed` ticket on the plane, every `depends` merged, its latest run state
none or `abandoned`; sorted by (priority, age, stem) where age is the stem's
first intake signal in the journal -- a stem with no signal sorts after every
stem with one, never a synthetic now. Dispatch is one at a time through the
same path as `run <stem>`; a non-ok terminal PARKS the stem (journal-derived:
its latest state is a non-ok Outcome) and the drain continues. The committed
tickets dir is re-scanned before every dispatch, so a stem a running ticket
committed through the ticket-plane lane is eligible in the same invocation.

At quiescence -- nothing eligible -- each parked stem whose spine caps still
hold budget is RE-OFFERED in the same order, one retry unit drawn per re-offer
as a `cap_consumed` event naming the cap and the ticket's blob sha; remaining
budgets are the journal fold over each cap's named draws (lifetime lineage
budgets, never counters). Eligible work always runs ahead of re-offers, and
every merge re-evaluates quiescence, so an unblocked dependent runs in the
same invocation. Two config ceilings bound an unattended drain (section 15): a
ticket whose stuck budget exceeds `drain.max_ticket_minutes` is held at
dispatch with a paved road and never runs; once `drain.max_runtime_hours`
has elapsed no NEW ticket is admitted -- the in-flight one reaches its stage
terminal, the trip is journaled as the armed timer firing, and the stop
names the continuing `squatch drain`. Exit codes (section 18): 0 =
quiescence (parked reds included), 1 = the ceiling halt, 2 = a refusal.

A re-offer is findings-fed by construction: the stage layer's Implement
render folds the parked stem's durable `review.md`/`checks.json` findings
into criteria-position (section 11.2, `squatch.stages`), so this module
draws the unit and dispatches through the same path as `run <stem>`.

Two parks are not re-offers. A `premise_failed` terminal answered the ticket
AS WRITTEN, so re-asking it unchanged replays a judgment (section 2): the
stem stays parked, draws nothing, and is never re-offered until a later
ticket-plane `ticket.md` commit lands -- journal-derived as an intake signal
after the terminal -- at which point it is eligible work again. Its paved
road is `source`-keyed (section 13): a seed's false premise is a plan
defect fixed in the plan first, a human or box stem's is a direct edit.

A SELF-UPGRADE is the other. An admission whose squash touches `squatch/**`
or `specs/**` means the running process is stale against the checkout it
drains, so before the next dispatch the drain re-execs itself through the
process-exec seam as `uv run python -m squatch drain` -- one form,
dependency changes included (uv's sync is a no-op when nothing changed; D1's
one runtime `uv` exception) -- carrying this invocation's parked set as
repeated `--parked <stem>` flags. The HANDOFF order is fixed: journal the
handoff, close the journal, release the lock (both are the session's exit),
spawn with `timeout=None` and inherited stdio, await, exit with the child's
code -- nothing else after the spawn, so the child is the only writer. The
child unions the carried set into its own parked set: it runs UPGRADED code
whose fold may read the record differently, and the parent's verdicts hold.
"""

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from squatch.artifacts import OUTCOMES
from squatch.caps import (PREMISE_BOUNCE_CAP, CapFold, RETRY_CAP, consume,
                          fold as fold_caps, remaining, spent)
from squatch.config import Config
from squatch.daemon import ConsumerCallback, DispatchPause, DrainControl
from squatch.effects import run_sequence
from squatch.git import Git
from squatch.journal import Event, Journal
from squatch.ladder import pending_rung
from squatch.runner import EXIT_OK, EXIT_TICKET, Refusal, Report, Runner, Session
from squatch.reject import ARRIVAL, Arrival, awaiting
from squatch.seams import Clock, ExecutableNotFound, ProcessExec
from squatch.tickets import (INTAKE_SIGNAL, PLAN_FILE, RESERVED_STEMS, TICKET_FILE, TICKETS_DIR,
                             Ticket, TicketLintError, cycle_through, lint_ticket, on_disk_stems,
                             pending_stems)

NON_OK = OUTCOMES - {"ok"}
PREMISE = "premise_failed"
CEILING_TIMER = "drain_max_runtime"
CONTINUE = "`squatch drain`"
HANDOFF_SIGNAL = "drain_handoff"
UPGRADE_PREFIXES = ("squatch/", "specs/")
UV_FORM = ("uv", "run", "python", "-m", "squatch")
ControlFactory = Callable[[Journal], tuple[DispatchPause, ConsumerCallback]]
RetroHook = Callable[[str | None, bool], Awaitable[bool]]
RetroFactory = Callable[[Session], RetroHook | None]


def _is_phase_exit(stem: str) -> bool:
    prefix, separator, suffix = stem.partition("-")
    return (separator == "-" and prefix.startswith("phase")
            and prefix[5:].isdigit() and suffix == "exit")


@dataclass(frozen=True)
class Fold:
    """The journal facts the sort and the caps read, folded once per scan."""

    merged: frozenset[str]
    latest: Mapping[str, str]        # stem -> its latest run state
    first_intake: Mapping[str, str]  # stem -> ts of its first intake signal
    cap_drawn: CapFold               # stem -> named cap_consumed counts
    commits: Mapping[str, str | None]  # stem -> the squash commit its merge put on main
    edited: frozenset[str]           # stems with an intake signal after their latest transition
    terminals: Mapping[str, Mapping]  # stem -> latest terminal body
    confirmed: frozenset[str]        # operator confirm after the latest transition
    rejects: Mapping[str, Arrival]    # unresolved Reject-queue arrivals


def fold(events: Iterable[Event]) -> Fold:
    events = tuple(events)
    latest: dict[str, str] = {}
    first: dict[str, str] = {}
    commits: dict[str, str | None] = {}
    merged: set[str] = set()
    edited: set[str] = set()
    terminals: dict[str, Mapping] = {}
    confirmed: set[str] = set()
    for e in events:
        if e.ticket is None:
            continue
        if e.type == "state_transition":
            latest[e.ticket] = e.body["to"]
            edited.discard(e.ticket)
            confirmed.discard(e.ticket)
            if e.body["to"] != "running":
                terminals[e.ticket] = e.body
            if e.body["to"] == "merged":
                merged.add(e.ticket)
                commits[e.ticket] = e.body.get("commit")
        elif e.type == "signal" and e.body.get("kind") == INTAKE_SIGNAL:
            first.setdefault(e.ticket, e.ts)
            edited.add(e.ticket)
        elif (e.type == "signal" and e.body.get("kind") == "confirm"
              and e.body.get("actor") == "operator"):
            confirmed.add(e.ticket)
    return Fold(frozenset(merged), latest, first, fold_caps(events), commits,
                frozenset(edited), terminals, frozenset(confirmed), awaiting(events))


def sort_key(fold: Fold) -> Callable[[Ticket], tuple]:
    def key(t: Ticket) -> tuple:
        ts = fold.first_intake.get(t.stem)
        return (t.priority, ts is None, ts or "", t.stem)
    return key


@dataclass(frozen=True)
class Held:
    """A stem the drain will not dispatch this invocation, with its road."""

    stem: str
    reason: str
    paved_road: str


@dataclass(frozen=True)
class Plane:
    """The committed ticket plane as one scan saw it."""

    tickets: dict[str, Ticket]   # committed, lint-clean, not merged, not rejected
    held: dict[str, Held]
    pending: tuple[str, ...]     # on disk, not yet intaken


@dataclass(frozen=True)
class Handoff:
    """The self-upgrade re-exec the session's exit hands to the spawn."""

    argv: tuple[str, ...]


class Drain:
    def __init__(self, *, runner: Runner, repo: Path, config: Config, git: Git, clock: Clock,
                 process: ProcessExec, env: Mapping[str, str], report: Report,
                 config_path: Path | None = None, carried: Sequence[str] = (),
                 pause: DispatchPause | None = None,
                 wait_for_control: ConsumerCallback | None = None,
                 control_factory: ControlFactory | None = None,
                 reconcile_notifications: Callable[[Journal], Awaitable[None]] | None = None,
                 retro_factory: RetroFactory | None = None):
        if control_factory is not None and (pause is not None or wait_for_control is not None):
            raise ValueError("control_factory replaces pause and wait_for_control")
        if pause is not None and wait_for_control is None:
            raise ValueError("pause requires wait_for_control")
        self._pause = pause
        self._wait_for_control = wait_for_control
        self._control_factory = control_factory
        self._reconcile_notifications = reconcile_notifications
        self._retro_factory = retro_factory
        self._runner = runner
        self._repo = Path(repo)
        self._config = config
        self._git = git
        self._clock = clock
        self._process = process
        self._env = env
        self._report = report
        self._config_path = config_path
        self._carried = frozenset(carried)

    async def run(self) -> int:
        async with self._runner.session() as session:
            result = await self._drain(session)
        # Past the session: the journal is closed and the lock released, so
        # the child spawned here is the only writer (section 18).
        if isinstance(result, Handoff):
            return await self._exec(result)
        return result

    async def _drain(self, session: Session) -> int | Handoff:
        journal = session.journal
        if self._reconcile_notifications is not None:
            await self._reconcile_notifications(journal)
        if self._control_factory is not None and self._pause is None:
            self._pause, self._wait_for_control = self._control_factory(journal)
        retro = self._retro_factory(session) if self._retro_factory is not None else None
        started = self._clock()
        ceiling = timedelta(hours=self._config.drain.max_runtime_hours)
        journal.append("timer_armed", {"kind": CEILING_TIMER,
                                       "deadline": (started + ceiling).isoformat()})
        merged_now: list[str] = []
        while True:
            if retro is not None:
                await retro(None, False)
            facts = fold(journal.read())
            plane = await self._scan(facts)
            plane = self._provider_holds(plane, journal)
            self._refuse_cycles(plane)
            if await self._resolve_rejects(journal, plane, facts):
                continue
            queue = self._eligible(plane, facts)
            offers = () if queue else self._reoffers(plane, facts)
            candidates = queue if queue else offers
            ticket = self._select_offer(candidates)
            offer = ticket if offers else None
            if ticket is None:
                if retro is not None:
                    await retro("quiescence", True)
                return self._quiescent(plane, facts, merged_now)
            if not await self._wait_for_offer(started + ceiling, ticket.stem):
                journal.append("timer_fired", {"kind": CEILING_TIMER, "next": ticket.stem})
                return self._halted(plane, facts, merged_now, ticket)
            if self._stopping:
                return self._killed()
            if self._runner.provider_hold(ticket, journal) is not None:
                continue
            if offer is not None:
                await self._draw_retry(journal, ticket)
                if not await self._wait_for_offer(started + ceiling, ticket.stem):
                    journal.append("timer_fired", {"kind": CEILING_TIMER, "next": ticket.stem})
                    return self._halted(plane, facts, merged_now, ticket)
                if self._stopping:
                    return self._killed()
            if retro is not None and _is_phase_exit(ticket.stem):
                await retro("phase-exit", True)
            try:
                if isinstance(self._pause, DrainControl):
                    assert self._wait_for_control is not None
                    run = await self._pause.run_dispatch(
                        self._runner.dispatch(ticket, journal), self._wait_for_control)
                else:
                    run = await self._runner.dispatch(ticket, journal)
            finally:
                if self._reconcile_notifications is not None:
                    await self._reconcile_notifications(journal)
            if run is None:
                return self._killed()
            if run.settled:
                merged_now.append(ticket.stem)
                facts = fold(journal.read())
                touched = await self._upgrading(facts.commits.get(ticket.stem))
                if touched:
                    return self._handoff(journal, ticket.stem, facts, plane, touched)

    async def _wait_for_offer(self, deadline: datetime, stem: str) -> bool:
        while self._clock() < deadline:
            allowed = self._pause is None or await self._pause.allow_offer(stem)
            if self._stopping:
                return True
            if allowed:
                # Control consumption or a wait may cross the admission ceiling.
                return self._clock() < deadline
            assert self._wait_for_control is not None
            await self._wait_for_control()
        return self._stopping

    @property
    def _stopping(self) -> bool:
        return isinstance(self._pause, DrainControl) and self._pause.stopping

    # --- the scan ----------------------------------------------------------------

    async def _scan(self, facts: Fold) -> Plane:
        pending = tuple(await pending_stems(self._repo, self._git))
        tickets: dict[str, Ticket] = {}
        held: dict[str, Held] = {}
        plan = self._repo / PLAN_FILE
        plan_text = plan.read_text() if plan.is_file() else None
        limit = self._config.drain.max_ticket_minutes
        for stem in on_disk_stems(self._repo):
            if (stem in RESERVED_STEMS or stem in pending or stem in facts.merged
                    or facts.latest.get(stem) == "rejected"):
                continue
            try:
                ticket = lint_ticket(self._path(stem).read_text(), stem=stem, repo=self._repo,
                                     plan=plan_text, resolve_stem=self._exists)
            except TicketLintError as e:
                f = e.findings[0]
                held[stem] = Held(stem, f"no longer lints: {f.message}",
                                  f"{f.paved_road}; edit tickets/{stem}/{TICKET_FILE}")
                continue
            if ticket.state != "confirmed":
                continue
            if ticket.stuck_minutes > limit:
                held[stem] = Held(stem, f"`## Time budget` stuck {ticket.stuck_minutes}m exceeds "
                                        f"drain.max_ticket_minutes {limit:g}",
                                  f"lower the stuck budget in tickets/{stem}/{TICKET_FILE} "
                                  f"to {limit:g}m or under")
                continue
            tickets[stem] = ticket
        return Plane(tickets, held, pending)

    def _provider_holds(self, plane: Plane, journal: Journal) -> Plane:
        tickets, held = {}, dict(plane.held)
        for stem, ticket in plane.tickets.items():
            reason = self._runner.provider_hold(ticket, journal)
            if reason is None:
                tickets[stem] = ticket
            else:
                held[stem] = Held(stem, "provider cooldown", reason)
        return Plane(tickets, held, plane.pending)

    def _refuse_cycles(self, plane: Plane) -> None:
        graph = {s: t.depends for s, t in plane.tickets.items()}
        for stem in sorted(graph):
            cycle = cycle_through(stem, graph)
            if cycle:
                raise Refusal(f"dependency cycle on the committed ticket plane: "
                              f"{' -> '.join(cycle)}",
                              "break the cycle in one of the named tickets' `## Depends on` "
                              "and re-run")

    def _eligible(self, plane: Plane, facts: Fold) -> list[Ticket]:
        ready = [t for t in plane.tickets.values()
                 if (facts.latest.get(t.stem) in (None, "abandoned")
                     or self._released(facts, t.stem))
                 and t.stem not in facts.rejects
                 and all(d in facts.merged for d in t.depends)]
        return sorted(ready, key=sort_key(facts))

    def _released(self, facts: Fold, stem: str) -> bool:
        """A premise park whose ticket-plane `ticket.md` commit has changed."""
        if stem in facts.confirmed or facts.terminals.get(stem, {}).get("provider_cooldown"):
            return True
        return (facts.latest.get(stem) == PREMISE and stem in facts.edited
                and remaining(self._config, facts.cap_drawn, stem, PREMISE_BOUNCE_CAP) > 0)

    def _parked(self, plane: Plane, facts: Fold) -> list[str]:
        parked = {s for s in plane.tickets
                  if facts.latest.get(s) in NON_OK and not self._released(facts, s)}
        return sorted(parked | (self._carried & plane.tickets.keys()))

    def _reoffers(self, plane: Plane, facts: Fold) -> list[Ticket]:
        offers = [plane.tickets[s] for s in self._parked(plane, facts)
                  if s not in facts.rejects
                  if facts.latest.get(s) != PREMISE
                  and spent(self._config, facts.cap_drawn, s) is None
                  and all(d in facts.merged for d in plane.tickets[s].depends)]
        offers.sort(key=sort_key(facts))
        return offers

    def _select_offer(self, offers: Sequence[Ticket]) -> Ticket | None:
        if not offers:
            return None
        if self._pause is None:
            return offers[0]
        return next((ticket for ticket in offers
                     if not self._pause.holds_offer(ticket.stem)), offers[0])

    async def _resolve_rejects(self, journal: Journal, plane: Plane, facts: Fold) -> bool:
        """Materialize legacy spent arrivals or auto-keep one funded arrival."""
        for stem in self._parked(plane, facts):
            reason = spent(self._config, facts.cap_drawn, stem)
            if stem in facts.rejects:
                if reason is None:
                    await self._runner.signal_verdict(
                        journal, stem, "confirm", actor="machine",
                        reason="auto-keep: retry budget remains")
                    return True
                continue
            if reason is not None:
                journal.append(
                    "signal", {"kind": "escalation", "escalation": ARRIVAL,
                               "reason": reason,
                               "run_seq": facts.terminals.get(stem, {}).get("run_seq")},
                    ticket=stem)
                return True
        return False

    def retry_budget(self, facts: Fold, stem: str) -> int:
        return remaining(self._config, facts.cap_drawn, stem, RETRY_CAP)

    async def _draw_retry(self, journal: Journal, ticket: Ticket) -> None:
        stem = ticket.stem
        events = tuple(journal.read())
        facts = fold(events)
        run_seq = run_sequence(journal, stem)
        pending = pending_rung(events, stem)
        rung = pending.body() if pending is not None else None
        await consume(journal, repo=self._repo, git=self._git, stem=stem, cap=RETRY_CAP,
                      run_seq=run_seq, rung=rung)
        fed = ", ".join(str(p.relative_to(self._repo)) for p in self._artifacts(stem))
        diagnosis = facts.terminals.get(stem, {}).get("diagnosis")
        diagnosed = ""
        if isinstance(diagnosis, dict):
            verdict = diagnosis.get("verdict")
            lessons = diagnosis.get("lessons", ())
            diagnosed = (f"; diagnosis {verdict or diagnosis.get('call')}"
                         + "".join(f"; lesson: {lesson}" for lesson in lessons))
        self._report(f"re-offer: {stem} after `{facts.latest[stem]}`; retry unit "
                     f"{facts.cap_drawn.drawn(stem, RETRY_CAP) + 1} of "
                     f"{self._config.caps.retry} drawn"
                     + (f"; rung {rung['tier']}/{rung['effort']}" if rung else "")
                     + diagnosed + (f"; findings-fed from {fed}" if fed else ""))

    # --- the self-upgrade handoff ----------------------------------------------------

    async def _upgrading(self, commit: str | None) -> list[str]:
        """The engine-plane paths the admitted squash touched; empty for a
        host-only diff or an `already_satisfied` settle (nothing integrated)."""
        if commit is None:
            return []
        names = await self._git.diff_names(self._repo, f"{commit}^", commit)
        return [p for p in names if p.startswith(UPGRADE_PREFIXES)]

    def _handoff(self, journal: Journal, stem: str, facts: Fold, plane: Plane,
                 touched: list[str]) -> Handoff:
        parked = self._parked(plane, facts)
        argv = [*UV_FORM]
        if self._config_path is not None:
            argv += ["--config", str(self._config_path)]
        argv.append("drain")
        for s in parked:
            argv += ["--parked", s]
        journal.append("signal", {"kind": HANDOFF_SIGNAL, "admitted": stem,
                                  "commit": facts.commits[stem], "touched": touched,
                                  "parked": parked, "argv": argv})
        self._report(f"self-upgrade: {stem} touched {', '.join(touched)}; handing off to "
                     f"`{' '.join(argv)}` (this process releases the lock, then awaits it)")
        return Handoff(tuple(argv))

    async def _exec(self, handoff: Handoff) -> int:
        try:
            rc, _, _ = await self._process.run(handoff.argv, cwd=self._repo, env=self._env,
                                               timeout=None)
        except ExecutableNotFound:
            raise Refusal("`uv` is not on PATH, so the self-upgrade handoff cannot re-exec",
                          f"install uv (D1's one runtime exception), then run "
                          f"`{' '.join(handoff.argv)}` -- the lock is free and the child "
                          f"reconciles on entry") from None
        return rc

    # --- the stop ------------------------------------------------------------------

    def _quiescent(self, plane: Plane, facts: Fold, merged_now: list[str]) -> int:
        self._report(f"quiescence: nothing eligible, unparked, re-offerable, or newly authored; "
                     f"{len(merged_now)} merged this drain"
                     + (f" ({', '.join(merged_now)})" if merged_now else ""))
        self._tail(plane, facts)
        return EXIT_OK

    def _killed(self) -> int:
        self._report("stopped: kill accepted; run is restart-reconcilable")
        return EXIT_OK

    def _halted(self, plane: Plane, facts: Fold, merged_now: list[str], next_: Ticket) -> int:
        self._report(f"halted: drain.max_runtime_hours "
                     f"{self._config.drain.max_runtime_hours:g} elapsed; {next_.stem} was next "
                     f"and was not admitted (not quiescence); {len(merged_now)} merged this drain"
                     + (f" ({', '.join(merged_now)})" if merged_now else ""))
        self._tail(plane, facts)
        self._report(f"continue: {CONTINUE} (reconciles on entry and resumes)")
        return EXIT_TICKET

    def _tail(self, plane: Plane, facts: Fold) -> None:
        for stem, arrival in sorted(facts.rejects.items()):
            if stem not in plane.tickets:
                continue
            self._report(
                f"reject queue: {stem}: {arrival.reason}; "
                f"`squatch confirm {stem}` to keep (re-arms spent caps) or "
                f"`squatch reject {stem}` to kill")
        for stem in self._parked(plane, facts):
            if stem in facts.rejects:
                continue
            ended = facts.latest.get(stem)
            where = ", ".join(str(p.relative_to(self._repo)) for p in self._artifacts(stem))
            detail = f"findings: {where}; log: {self._runner.log_path}" if where else (
                f"findings: {self._runner.log_path}")
            if ended == PREMISE:
                drawn = facts.cap_drawn.drawn(stem, PREMISE_BOUNCE_CAP)
                budget = self._config.caps.premise_bounce
                if remaining(self._config, facts.cap_drawn, stem, PREMISE_BOUNCE_CAP) <= 0:
                    reason = f"premise_bounce cap spent ({drawn} of {budget} drawn)"
                    road = (f"{reason}; edit the ticket as required, then "
                            f"`squatch confirm {stem}` to re-arm and re-enqueue it")
                else:
                    road = self._premise_road(plane.tickets[stem])
            elif (reason := spent(self._config, facts.cap_drawn, stem)) is not None:
                road = (f"{reason}; {CONTINUE} never re-dispatches it -- fix the cause it names; "
                        f"the re-arm is `squatch confirm {stem}` after the fix")
            else:
                left = self.retry_budget(facts, stem)
                road = f"{left} retry unit(s) left; {CONTINUE} re-offers it findings-fed"
            self._report(f"parked: {stem} ended `{ended}`; {detail}; {road}")
        for h in plane.held.values():
            self._report(f"held: {h.stem} {h.reason} -- {h.paved_road}")
        for stem, t in sorted(plane.tickets.items()):
            unmerged = [d for d in t.depends if d not in facts.merged]
            if unmerged and facts.latest.get(stem) not in NON_OK:
                dead = [d for d in unmerged if facts.latest.get(d) == "rejected"]
                suffix = f" (dead: {', '.join(dead)})" if dead else ""
                self._report(f"blocked: {stem} waiting on {', '.join(unmerged)}{suffix}")
        for stem in plane.pending:
            self._report(f"pending intake: {stem} (uncommitted; the next {CONTINUE} intakes it)")

    def _premise_road(self, ticket: Ticket) -> str:
        """Source-keyed (sections 13, 18): the one release is a changed
        ticket-plane `ticket.md` commit; only where the fix originates differs."""
        path = f"tickets/{ticket.stem}/{TICKET_FILE}"
        if ticket.source == "seed":
            fix = (f"a seed renders the plan, so fix the false assumption in {PLAN_FILE} first, "
                   f"then regenerate {path} in place from it")
        else:
            fix = f"edit {path} to answer the verdict"
        return (f"the verdict answered the ticket as written, so {CONTINUE} never re-offers it "
                f"unchanged; {fix}; the next {CONTINUE} intakes the edit and runs it again")

    def _artifacts(self, stem: str) -> list[Path]:
        root = self._repo / TICKETS_DIR / stem
        return [p for p in (root / "checks.json", root / "review.md") if p.is_file()]

    def _path(self, stem: str) -> Path:
        return self._repo / TICKETS_DIR / stem / TICKET_FILE

    def _exists(self, stem: str) -> bool:
        return self._path(stem).is_file()
