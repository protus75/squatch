"""`squatch status`: a read-only projection over the journal (SQUATCH_PLAN.md D3,
section 13 touchpoint 5).

Never authoritative and never a writer: it folds the journal's events into
the per-stem picture (intake, in flight, ready, blocked, stopped, merged,
spend) and lists the working-tree tickets that have not passed intake --
the unparsed ones as the named top-of-output category. A stem's run state is
its LATEST `state_transition`; `merged` is the settle record every dependency
read keys on. The ticket files on disk contribute only `depends` edges and
the pending set; nothing here writes them, the journal, or the lock.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from squatch.artifacts import TERMINAL_RUN_STATES
from squatch.box import Box, Message
from squatch.journal import Event
from squatch.reject import Arrival, awaiting
from squatch.scorecard import Scorecard, render_report
from squatch.seams import LocalFilesystem
from squatch.tickets import (INTAKE_SIGNAL, PLAN_FILE, RESERVED_STEMS, TICKET_FILE, TICKETS_DIR,
                             TicketLintError, depends_of, lint_ticket)


@dataclass(frozen=True)
class Unparsed:
    stem: str
    message: str
    paved_road: str


@dataclass(frozen=True)
class Intaken:
    stem: str
    source: str
    state: str
    commit: str


@dataclass(frozen=True)
class Status:
    unparsed: tuple[Unparsed, ...] = ()
    pending: tuple[str, ...] = ()            # lint-clean, awaiting the next intake
    in_flight: tuple[tuple[str, int], ...] = ()   # (stem, run_seq)
    ready: tuple[str, ...] = ()
    blocked: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (stem, unmerged depends)
    stopped: tuple[tuple[str, str], ...] = ()      # (stem, terminal state)
    merged: tuple[str, ...] = ()
    intake: tuple[Intaken, ...] = ()
    spend_usd: float = 0.0
    calls: int = 0
    box: tuple[Message, ...] = ()
    reject_queue: tuple[tuple[str, Arrival], ...] = ()
    box_activity: tuple[tuple[str, int], ...] = ()
    tombstone_digest: tuple[tuple[str, str, int, bool], ...] = ()
    scorecard: Scorecard | None = None


def project(events: Iterable[Event], *, repo: Path, state_dir: Path,
            scorecard: Scorecard | None = None) -> Status:
    events = tuple(events)
    rejects = awaiting(events)
    repo = Path(repo)
    intake: dict[str, Intaken] = {}
    latest: dict[str, dict] = {}   # stem -> latest state_transition body
    latest_terminal: dict[str, dict] = {}
    spend = 0.0
    calls = 0
    for e in events:
        if e.type == "signal" and e.body.get("kind") == INTAKE_SIGNAL and e.ticket:
            intake[e.ticket] = Intaken(e.ticket, e.body["source"], e.body["state"],
                                       e.body["commit"])
        elif e.type == "state_transition" and e.ticket:
            latest[e.ticket] = e.body
            if e.body.get("to") in TERMINAL_RUN_STATES:
                latest_terminal[e.ticket] = e.body
        elif e.type == "effect_completion" and "cost" in e.body:
            cost = e.body["cost"]
            usd = cost.get("usd") if isinstance(cost, dict) else None
            if isinstance(usd, (int, float)) and not isinstance(usd, bool):
                spend += usd
                calls += 1

    merged = {stem for stem, record in latest_terminal.items() if record.get("to") == "merged"}

    on_disk = _stems(repo)
    plan = repo / PLAN_FILE
    plan_text = plan.read_text() if plan.is_file() else None
    unparsed: list[Unparsed] = []
    pending: list[str] = []
    for stem in on_disk:
        if stem in intake:
            continue
        try:
            lint_ticket(_path(repo, stem).read_text(), stem=stem, repo=repo, plan=plan_text,
                        resolve_stem=lambda s: _path(repo, s).is_file())
        except TicketLintError as e:
            f = e.findings[0]
            unparsed.append(Unparsed(stem, f.message, f.paved_road))
        else:
            pending.append(stem)

    in_flight, ready, blocked, stopped = [], [], [], []
    for stem, rec in sorted(intake.items()):
        if stem in rejects:
            continue
        last = latest.get(stem)
        if last is not None and last.get("to") == "running":
            in_flight.append((stem, last.get("run_seq", 0)))
            continue
        if stem in merged:
            continue
        if last is not None and last.get("to") in TERMINAL_RUN_STATES:
            stopped.append((stem, last["to"]))
        if rec.state != "confirmed":
            continue
        path = _path(repo, stem)
        depends = depends_of(path.read_text()) if path.is_file() else ()
        unmerged = tuple(d for d in depends if d not in merged)
        if unmerged:
            blocked.append((stem, unmerged))
        elif last is None or last.get("to") in TERMINAL_RUN_STATES:
            ready.append(stem)

    box = Box(state_dir, fs=LocalFilesystem(),
              clock=lambda: (_ for _ in ()).throw(AssertionError("status never writes")))
    messages = tuple(box.messages())
    box_messages = tuple(message for message in messages if message.status == "pending")
    activity = tuple((status, sum(message.status == status for message in messages))
                     for status in sorted({message.status for message in messages}))
    tombstones = tuple(sorted(
        (message.id, message.signature, message.reports, message.reopened_from_tombstone)
        for message in messages if message.status == "tombstoned"))
    return Status(
        unparsed=tuple(unparsed), pending=tuple(pending), in_flight=tuple(in_flight),
        ready=tuple(ready), blocked=tuple(blocked), stopped=tuple(stopped),
        merged=tuple(sorted(merged)), intake=tuple(intake[s] for s in sorted(intake)),
        spend_usd=spend, calls=calls, box=box_messages,
        reject_queue=tuple(sorted(rejects.items())), box_activity=activity,
        tombstone_digest=tombstones, scorecard=scorecard)


def render(status: Status) -> str:
    lines: list[str] = []

    def section(title: str, rows: Iterable[str]) -> None:
        rows = list(rows)
        lines.append(f"{title} ({len(rows)})")
        lines.extend(f"  {r}" for r in rows or ["(none)"])

    section("unparsed tickets (failed intake lint)",
            (f"{u.stem}: {u.message} -- {u.paved_road}" for u in status.unparsed))
    section("pending intake", status.pending)
    section("in flight", (f"{s} (run {n})" for s, n in status.in_flight))
    section("ready", status.ready)
    section("blocked", (f"{s}: waiting on {', '.join(d)}" for s, d in status.blocked))
    section("reject queue", (
        f"{s}: {a.reason}; arrived {a.ts}; `squatch confirm {s}` to keep or "
        f"`squatch reject {s}` to kill" for s, a in status.reject_queue))
    section("stopped", (f"{s}: {t}" for s, t in status.stopped))
    section("merged", status.merged)
    section("intake", (f"{i.stem}: {i.source}, {i.state}, {i.commit[:12]}" for i in status.intake))
    section("box", (f"{m.id}: {m.message_class}: {m.summary[:80]}" for m in status.box))
    section("box activity", (f"{state}: {count}" for state, count in status.box_activity))
    section("tombstone digest", (f"{box_id}: {signature}, reports {reports}, reopened {reopened}"
                                 for box_id, signature, reports, reopened
                                 in status.tombstone_digest))
    lines.append(f"spend: ${status.spend_usd:.4f} over {status.calls} metered calls")
    if status.scorecard is not None:
        lines.extend(("", render_report(status.scorecard).rstrip("\n")))
    return "\n".join(lines) + "\n"


def _stems(repo: Path) -> list[str]:
    root = repo / TICKETS_DIR
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir()
                  if (d / TICKET_FILE).is_file() and d.name not in RESERVED_STEMS)


def _path(repo: Path, stem: str) -> Path:
    return repo / TICKETS_DIR / stem / TICKET_FILE
