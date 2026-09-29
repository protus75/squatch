"""Pure surface-scorecard projection for completed retrospective windows."""

from collections import defaultdict
from typing import TYPE_CHECKING

from squatch.artifacts import ClosedModel

if TYPE_CHECKING:
    from squatch.retro import RetroWindow


class SurfaceScorecardRow(ClosedModel):
    surface: str
    evaluated_tickets: int
    catches: int
    escapes: int
    bypass_count: int
    catch_rate: float
    escape_rate: float
    prune_candidate: bool


class Scorecard(ClosedModel):
    boundary: str
    merged_ticket_count: int
    spend_usd: float
    tokens: int
    signal_counts: dict[str, int]
    gate_failure_count: int
    surfaces: tuple[SurfaceScorecardRow, ...]


def project_scorecard(window: "RetroWindow") -> Scorecard:
    """Fold a completed retro window without touching any external seam."""
    observations: dict[str, list[tuple[str, str, str, bool]]] = defaultdict(list)
    for observation in window.check_observations:
        observations[observation[1]].append(observation)

    escapes: dict[str, int] = defaultdict(int)
    seen_escapes: set[tuple[str, str, str]] = set()
    for signature, ticket in window.escape_attributions:
        for observed_ticket, surface, verdict, bypassed in window.check_observations:
            if observed_ticket != ticket or verdict != "pass" or bypassed:
                continue
            identity = (signature, ticket, surface)
            if identity not in seen_escapes:
                seen_escapes.add(identity)
                escapes[surface] += 1

    rows = []
    for surface in sorted(observations):
        values = observations[surface]
        catches = sum(verdict == "fail" and not bypassed
                      for _ticket, _code, verdict, bypassed in values)
        evaluated_tickets = len({ticket for ticket, _code, _verdict, _bypassed in values})
        escaped = escapes[surface]
        rows.append(SurfaceScorecardRow(
            surface=surface,
            evaluated_tickets=evaluated_tickets,
            catches=catches,
            escapes=escaped,
            bypass_count=sum(bypassed for _ticket, _code, _verdict, bypassed in values),
            catch_rate=catches / len(values) if values else 0,
            escape_rate=escaped / len(values) if values else 0,
            prune_candidate=evaluated_tickets >= 25 and catches == 0 and escaped == 0,
        ))
    return Scorecard(
        boundary=window.boundary,
        merged_ticket_count=len(window.merged_tickets),
        spend_usd=window.spend_usd,
        tokens=window.tokens,
        signal_counts=window.signal_counts.copy(),
        gate_failure_count=len(window.gate_failures),
        surfaces=tuple(rows),
    )


def render_report(scorecard: Scorecard) -> str:
    """Render the scorecard's surface rows in their already-sorted order."""
    lines = [
        "## Surface scorecard", "",
        "| Surface | Evaluated tickets | Catches | Escapes | Bypasses | Catch rate | "
        "Escape rate | Prune candidate |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in scorecard.surfaces:
        lines.append(
            f"| `{row.surface}` | {row.evaluated_tickets} | {row.catches} | "
            f"{row.escapes} | {row.bypass_count} | {row.catch_rate:.6f} | "
            f"{row.escape_rate:.6f} | {'yes' if row.prune_candidate else 'no'} |")
    if not scorecard.surfaces:
        lines.append("| none | 0 | 0 | 0 | 0 | 0.000000 | 0.000000 | no |")
    return "\n".join(lines) + "\n"
