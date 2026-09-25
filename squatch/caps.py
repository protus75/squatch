"""Failure-spine cap vocabulary, journal writer, and lineage fold."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from squatch.config import Config
from squatch.git import Git
from squatch.journal import Event, Journal
from squatch.tickets import TICKET_FILE, TICKETS_DIR

DIAGNOSIS_CAP = "diagnosis"
RETRY_CAP = "retry"
PREMISE_BOUNCE_CAP = "premise_bounce"
INFRA_CAP = "infra"
QUARANTINE_CAP = "quarantine"
POISON_CAP = "poison"

CAP_NAMES = frozenset({
    DIAGNOSIS_CAP,
    RETRY_CAP,
    PREMISE_BOUNCE_CAP,
    INFRA_CAP,
    QUARANTINE_CAP,
    POISON_CAP,
})
SPINE_CAPS = (RETRY_CAP, DIAGNOSIS_CAP, PREMISE_BOUNCE_CAP, INFRA_CAP)


@dataclass(frozen=True)
class CapFold:
    """Per-lineage counts for every named cap."""

    counts: Mapping[str, Mapping[str, int]]

    def drawn(self, stem: str, cap: str) -> int:
        return self.counts.get(stem, {}).get(cap, 0)


def fold(events: Iterable[Event]) -> CapFold:
    counts: dict[str, dict[str, int]] = {}
    for event in events:
        if (event.type == "signal" and event.ticket is not None
                and event.body.get("kind") == "confirm"
                and event.body.get("actor") == "operator"):
            counts[event.ticket] = {}
            continue
        if (event.type != "cap_consumed" or event.ticket is None
                or (cap := event.body.get("cap")) not in CAP_NAMES):
            continue
        by_cap = counts.setdefault(event.ticket, {})
        by_cap[cap] = by_cap.get(cap, 0) + 1
    return CapFold(counts)


def remaining(config: Config, events: Iterable[Event] | CapFold, stem: str, cap: str) -> int:
    if cap not in CAP_NAMES:
        raise ValueError(f"unknown cap {cap!r}")
    facts = events if isinstance(events, CapFold) else fold(events)
    return getattr(config.caps, cap) - facts.drawn(stem, cap)


def spent(config: Config, events: Iterable[Event] | CapFold, stem: str) -> str | None:
    facts = events if isinstance(events, CapFold) else fold(events)
    for cap in SPINE_CAPS:
        budget = getattr(config.caps, cap)
        drawn = facts.drawn(stem, cap)
        if drawn >= budget:
            return f"{cap} cap spent ({drawn} of {budget} drawn)"
    return None


async def consume(journal: Journal, *, repo: Path, git: Git, stem: str, cap: str,
                  run_seq: int, rung: Mapping[str, str] | None = None) -> None:
    """Journal one cap draw against the stem's committed ticket blob."""
    if cap not in CAP_NAMES:
        raise ValueError(f"unknown cap {cap!r}")
    sha = await git.rev_parse(repo, f"HEAD:{TICKETS_DIR}/{stem}/{TICKET_FILE}")
    body = {"cap": cap, "ticket_sha": sha, "run_seq": run_seq}
    if rung is not None:
        body["rung"] = dict(rung)
    journal.append("cap_consumed", body, ticket=stem)
