"""The deterministic, journal-derived capability ladder."""

from collections.abc import Iterable
from dataclasses import dataclass

from squatch.journal import Event
from squatch.llm import EFFORTS, TIERS
from squatch.providers import Registry
from squatch.tickets import Ticket

IDENTICAL_TERMINALS = 3

_SCALE = ("low", "medium", "high", "max")


@dataclass(frozen=True)
class Rung:
    tier: str
    effort: str

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"unknown tier {self.tier!r}")
        if self.effort not in EFFORTS:
            raise ValueError(f"unknown effort {self.effort!r}")

    def body(self) -> dict[str, str]:
        return {"tier": self.tier, "effort": self.effort}


def next_rung(registry: Registry, current: Rung) -> Rung | None:
    """Walk model-first, skipping tier names that resolve to the same model."""
    resolved = registry.resolve(current.tier, "implement")
    identity = (resolved.provider.name, resolved.model)
    for tier in _SCALE[_SCALE.index(current.tier) + 1:]:
        candidate = registry.resolve(tier, "implement")
        if (candidate.provider.name, candidate.model) != identity:
            return Rung(tier, current.effort)
    effort_index = _SCALE.index(current.effort)
    if effort_index == len(_SCALE) - 1:
        return None
    return Rung(current.tier, _SCALE[effort_index + 1])


def _after_keep(events: Iterable[Event], stem: str) -> tuple[Event, ...]:
    kept: list[Event] = []
    for event in events:
        if event.ticket != stem:
            continue
        if (event.type == "signal" and event.body.get("kind") == "confirm"
                and event.body.get("actor") == "operator"):
            kept = []
        else:
            kept.append(event)
    return tuple(kept)


def rungs(events: Iterable[Event], stem: str) -> Rung | None:
    latest = None
    for event in _after_keep(events, stem):
        if event.type != "cap_consumed" or event.body.get("cap") != "retry":
            continue
        body = event.body.get("rung")
        if isinstance(body, dict):
            latest = Rung(tier=body.get("tier"), effort=body.get("effort"))
    return latest


def pending_rung(events: Iterable[Event], stem: str) -> Rung | None:
    """The latest ladder route awaiting its retry draw, unless an operator kept it."""
    terminal = next((event for event in reversed(_after_keep(events, stem))
                     if event.type == "state_transition"
                     and event.body.get("to") not in {"running", "merged"}), None)
    if terminal is None or terminal.body.get("routed") != "ladder":
        return None
    body = terminal.body.get("rung")
    if not isinstance(body, dict):
        return None
    return Rung(tier=body.get("tier"), effort=body.get("effort"))


def effective(ticket: Ticket, rung: Rung | None) -> tuple[str, str]:
    if rung is None:
        return ticket.agent_tier, ticket.agent_effort
    return rung.tier, rung.effort


def _terminals(events: Iterable[Event], stem: str) -> list[Event]:
    source: list[Event] = []
    for event in _after_keep(events, stem):
        if ((event.type == "state_transition" and event.body.get("routed") == "ladder")
                or (event.type == "cap_consumed" and event.body.get("cap") == "retry"
                    and isinstance(event.body.get("rung"), dict))):
            source = []
            continue
        source.append(event)
    return [event for event in source
            if event.ticket == stem and event.type == "state_transition"
            and event.body.get("to") not in {"running", "merged"}]


def identical(events: Iterable[Event], stem: str) -> bool:
    terminals = _terminals(events, stem)[-IDENTICAL_TERMINALS:]
    if len(terminals) != IDENTICAL_TERMINALS:
        return False
    keys = [(event.body.get("to"), event.body.get("reason")) for event in terminals]
    return keys[0][1] is not None and all(key == keys[0] for key in keys[1:])


def finding_codes(delivery) -> tuple[str, ...]:
    return tuple(sorted({finding.code for finding in delivery.findings}))


def same_wall(events: Iterable[Event], stem: str, delivery) -> bool:
    events = tuple(events)
    terminal_indexes = [index for index, event in enumerate(events)
                        if event.ticket == stem and event.type == "state_transition"
                        and event.body.get("to") not in {"running", "merged"}]
    if not terminal_indexes or delivery.outcome != "gate_failed":
        return False
    prior_index = terminal_indexes[-1]
    prior = events[prior_index]
    if prior.body.get("to") != "gate_failed":
        return False
    retry = any(event.ticket == stem and event.type == "cap_consumed"
                and event.body.get("cap") == "retry"
                for event in events[prior_index + 1:])
    prior_codes = tuple(prior.body.get("finding_codes", ()))
    return retry and bool(prior_codes) and prior_codes == finding_codes(delivery)


def oscillating(events: Iterable[Event], stem: str) -> bool:
    terminals = _terminals(events, stem)[-3:]
    if len(terminals) != 3:
        return False
    codes = [tuple(event.body.get("finding_codes", ())) for event in terminals]
    return bool(codes[0]) and codes[0] == codes[2] and codes[0] != codes[1]
