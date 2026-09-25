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


def project(events: Iterable[Event], *, repo: Path, state_dir: Path) -> Status:
    events = tuple(events)
    rejects = awaiting(events)
    repo = Path(repo)
    intake: dict[str, Intaken] = {}
    latest: dict[str, dict] = {}   # stem -> latest state_transition body
    merged: set[str] = set()
    spend = 0.0
    calls = 0
    for e in events:
        if e.type == "signal" and e.body.get("kind") == INTAKE_SIGNAL and e.ticket:
            intake[e.ticket] = Intaken(e.ticket, e.body["source"], e.body["state"],
                                       e.body["commit"])
        elif e.type == "state_transition" and e.ticket:
            latest[e.ticket] = e.body
            if e.body.get("to") == "merged":
                merged.add(e.ticket)
        elif e.type == "effect_completion" and "cost" in e.body:
            usd = e.body["cost"].get("usd")
            if usd is not None:
                spend += usd
                calls += 1

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
        if stem in merged:
            continue
        if stem in rejects:
            continue
        last = latest.get(stem)
        if last is not None and last.get("to") == "running":
            in_flight.append((stem, last.get("run_seq", 0)))
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
    box_messages = tuple(box.pending())
    return Status(
        unparsed=tuple(unparsed), pending=tuple(pending), in_flight=tuple(in_flight),
        ready=tuple(ready), blocked=tuple(blocked), stopped=tuple(stopped),
        merged=tuple(sorted(merged)), intake=tuple(intake[s] for s in sorted(intake)),
        spend_usd=spend, calls=calls, box=box_messages,
        reject_queue=tuple(sorted(rejects.items())))


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
    lines.append(f"spend: ${status.spend_usd:.4f} over {status.calls} metered calls")
    return "\n".join(lines) + "\n"


def _stems(repo: Path) -> list[str]:
    root = repo / TICKETS_DIR
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir()
                  if (d / TICKET_FILE).is_file() and d.name not in RESERVED_STEMS)


def _path(repo: Path, stem: str) -> Path:
    return repo / TICKETS_DIR / stem / TICKET_FILE
