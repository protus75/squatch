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

At quiescence -- nothing eligible -- each parked stem whose `retry` cap still
holds budget is RE-OFFERED in the same order, one unit drawn per re-offer as
a `cap_consumed` event naming the cap and the ticket's blob sha; remaining
budget is the journal fold over retry-NAMED draws (a lifetime lineage budget,
never a counter). Eligible work always runs ahead of re-offers, and every
merge re-evaluates quiescence, so an unblocked dependent runs in the same
invocation. Two config ceilings bound an unattended drain (section 15): a
ticket whose stuck budget exceeds `drain.max_ticket_minutes` is held at
dispatch with a paved road and never runs; once `drain.max_runtime_hours`
has elapsed no NEW ticket is admitted -- the in-flight one reaches its stage
terminal, the trip is journaled as the armed timer firing, and the stop
names the continuing `squatch drain`. Exit codes (section 18): 0 =
quiescence (parked reds included), 1 = the ceiling halt, 2 = a refusal.

A re-offer is findings-fed by construction: the stage layer's Implement
render folds the parked stem's durable `review.md`/`checks.json` findings
into criteria-position (section 11.2, `squatch.stages`), so this module
draws the unit and dispatches through the same path as `run <stem>`. One
seam is left for the deliverable that follows: the self-upgrade trigger
after a merge, a no-op here.
"""

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from squatch.artifacts import OUTCOMES
from squatch.config import Config
from squatch.effects import run_sequence
from squatch.git import Git
from squatch.journal import Event, Journal
from squatch.runner import EXIT_OK, EXIT_TICKET, Refusal, Report, Runner, Session
from squatch.seams import Clock
from squatch.tickets import (INTAKE_SIGNAL, PLAN_FILE, RESERVED_STEMS, TICKET_FILE, TICKETS_DIR,
                             Ticket, TicketLintError, cycle_through, lint_ticket, on_disk_stems,
                             pending_stems)

RETRY_CAP = "retry"
NON_OK = OUTCOMES - {"ok"}
CEILING_TIMER = "drain_max_runtime"
CONTINUE = "`squatch drain`"

# Prompt 13's seam: called after every settled admission with the admitted
# stem and the invocation's parked set.
Upgrade = Callable[[str, Sequence[str]], Awaitable[None]]


async def no_upgrade(stem: str, parked: Sequence[str]) -> None:
    return None


@dataclass(frozen=True)
class Fold:
    """The journal facts the sort and the caps read, folded once per scan."""

    merged: frozenset[str]
    latest: Mapping[str, str]        # stem -> its latest run state
    first_intake: Mapping[str, str]  # stem -> ts of its first intake signal
    retry_drawn: Mapping[str, int]   # stem -> retry-named cap_consumed count


def fold(events: Iterable[Event]) -> Fold:
    latest: dict[str, str] = {}
    first: dict[str, str] = {}
    drawn: dict[str, int] = {}
    merged: set[str] = set()
    for e in events:
        if e.ticket is None:
            continue
        if e.type == "state_transition":
            latest[e.ticket] = e.body["to"]
            if e.body["to"] == "merged":
                merged.add(e.ticket)
        elif e.type == "signal" and e.body.get("kind") == INTAKE_SIGNAL:
            first.setdefault(e.ticket, e.ts)
        elif e.type == "cap_consumed" and e.body.get("cap") == RETRY_CAP:
            drawn[e.ticket] = drawn.get(e.ticket, 0) + 1
    return Fold(frozenset(merged), latest, first, drawn)


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


class Drain:
    def __init__(self, *, runner: Runner, repo: Path, config: Config, git: Git, clock: Clock,
                 report: Report, upgrade: Upgrade = no_upgrade):
        self._runner = runner
        self._repo = Path(repo)
        self._config = config
        self._git = git
        self._clock = clock
        self._report = report
        self._upgrade = upgrade

    async def run(self) -> int:
        async with self._runner.session() as session:
            return await self._drain(session)

    async def _drain(self, session: Session) -> int:
        journal = session.journal
        started = self._clock()
        ceiling = timedelta(hours=self._config.drain.max_runtime_hours)
        journal.append("timer_armed", {"kind": CEILING_TIMER,
                                       "deadline": (started + ceiling).isoformat()})
        merged_now: list[str] = []
        while True:
            facts = fold(journal.read())
            plane = await self._scan(facts)
            self._refuse_cycles(plane)
            queue = self._eligible(plane, facts)
            offer = None if queue else self._reoffer(plane, facts)
            ticket = queue[0] if queue else offer
            if ticket is None:
                return self._quiescent(plane, facts, merged_now)
            if self._clock() - started >= ceiling:
                journal.append("timer_fired", {"kind": CEILING_TIMER, "next": ticket.stem})
                return self._halted(plane, facts, merged_now, ticket)
            if offer is not None:
                await self._draw_retry(journal, ticket)
            run = await self._runner.dispatch(ticket, journal)
            if run.settled:
                merged_now.append(ticket.stem)
                await self._upgrade(ticket.stem, self._parked(plane, fold(journal.read())))

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
                 if facts.latest.get(t.stem) in (None, "abandoned")
                 and all(d in facts.merged for d in t.depends)]
        return sorted(ready, key=sort_key(facts))

    def _parked(self, plane: Plane, facts: Fold) -> list[str]:
        return sorted(s for s in plane.tickets if facts.latest.get(s) in NON_OK)

    def _reoffer(self, plane: Plane, facts: Fold) -> Ticket | None:
        offers = [plane.tickets[s] for s in self._parked(plane, facts)
                  if self.retry_budget(facts, s) > 0
                  and all(d in facts.merged for d in plane.tickets[s].depends)]
        offers.sort(key=sort_key(facts))
        return offers[0] if offers else None

    def retry_budget(self, facts: Fold, stem: str) -> int:
        return self._config.caps.retry - facts.retry_drawn.get(stem, 0)

    async def _draw_retry(self, journal: Journal, ticket: Ticket) -> None:
        stem = ticket.stem
        sha = await self._git.rev_parse(self._repo, f"HEAD:{TICKETS_DIR}/{stem}/{TICKET_FILE}")
        facts = fold(journal.read())
        run_seq = run_sequence(journal, stem)
        journal.append("cap_consumed", {"cap": RETRY_CAP, "ticket_sha": sha, "run_seq": run_seq},
                       ticket=stem)
        fed = ", ".join(str(p.relative_to(self._repo)) for p in self._artifacts(stem))
        self._report(f"re-offer: {stem} after `{facts.latest[stem]}`; retry unit "
                     f"{facts.retry_drawn.get(stem, 0) + 1} of {self._config.caps.retry} drawn"
                     + (f"; findings-fed from {fed}" if fed else ""))

    # --- the stop ------------------------------------------------------------------

    def _quiescent(self, plane: Plane, facts: Fold, merged_now: list[str]) -> int:
        self._report(f"quiescence: nothing eligible, unparked, re-offerable, or newly authored; "
                     f"{len(merged_now)} merged this drain"
                     + (f" ({', '.join(merged_now)})" if merged_now else ""))
        self._tail(plane, facts)
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
        cap = self._config.caps.retry
        for stem in self._parked(plane, facts):
            left = self.retry_budget(facts, stem)
            where = ", ".join(str(p.relative_to(self._repo)) for p in self._artifacts(stem))
            detail = f"findings: {where}; log: {self._runner.log_path}" if where else (
                f"findings: {self._runner.log_path}")
            if left > 0:
                road = f"{left} retry unit(s) left; {CONTINUE} re-offers it findings-fed"
            else:
                road = (f"retry cap spent ({cap} of {cap} drawn); {CONTINUE} never re-dispatches "
                        f"it -- fix the cause it names; the re-arm is the operator's Reject-queue "
                        f"keep (section 13 touchpoint 3)")
            self._report(f"parked: {stem} ended `{facts.latest[stem]}`; {detail}; {road}")
        for h in plane.held.values():
            self._report(f"held: {h.stem} {h.reason} -- {h.paved_road}")
        for stem, t in sorted(plane.tickets.items()):
            unmerged = [d for d in t.depends if d not in facts.merged]
            if unmerged and facts.latest.get(stem) not in NON_OK:
                self._report(f"blocked: {stem} waiting on {', '.join(unmerged)}")
        for stem in plane.pending:
            self._report(f"pending intake: {stem} (uncommitted; the next {CONTINUE} intakes it)")

    def _artifacts(self, stem: str) -> list[Path]:
        root = self._repo / TICKETS_DIR / stem
        return [p for p in (root / "checks.json", root / "review.md") if p.is_file()]

    def _path(self, stem: str) -> Path:
        return self._repo / TICKETS_DIR / stem / TICKET_FILE

    def _exists(self, stem: str) -> bool:
        return self._path(stem).is_file()

