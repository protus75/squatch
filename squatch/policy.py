"""Starting-state policy for machine-authored box tickets (plan section 12)."""

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from squatch.config import Config, ConfigError
from squatch.journal import Event
from squatch.llm import TIERS
from squatch.providers import PLACEHOLDER, Registry, RoutingError
from squatch.specs import load_spec


def _major(path: Path) -> int | None:
    return int(load_spec(path).version.split(".")[0]) if path.is_file() else None


def _identity(config: Config, tiers: Iterable[str]) -> tuple[dict, dict]:
    registry = Registry(config)
    tiers = tuple(tiers)
    if not tiers or any(tier not in TIERS for tier in tiers):
        raise ValueError("baseline tiers must be a non-empty subset of the tier vocabulary")
    identity = {
        surface: {
            tier: {"provider": resolved.provider.name, "model": resolved.model}
            for tier in tiers
            for resolved in (registry.resolve(tier, surface),)
            if PLACEHOLDER not in (resolved.provider.auth, resolved.model)
        }
        for surface in ("review", "author")
    }
    if any(len(rows) != len(tiers) for rows in identity.values()):
        raise ValueError("baseline identity contains an unresolved placeholder")
    specs = Path(__file__).resolve().parent.parent / "specs"
    majors = {surface: _major(specs / f"{surface}.md")
              for surface in ("review", "author")}
    return identity, majors


def go_binds(config: Config, events: Iterable[Event]) -> bool:
    """Whether the newest baseline is GO for the currently routed identity."""
    baseline = next((event for event in reversed(tuple(events))
                     if event.type == "signal"
                     and event.body.get("kind") == "review_baseline"), None)
    if baseline is None or baseline.body.get("verdict") != "GO":
        return False
    try:
        identity, majors = _identity(config, baseline.body.get("tiers", ()))
    except (ConfigError, RoutingError, TypeError, ValueError):
        return False
    return (baseline.body.get("identity") == identity
            and baseline.body.get("spec_major") == majors)


def _row(config: Config, message_class: str, bug_origin: str | None,
         has_repro: bool) -> str:
    if message_class == "bug_report":
        if bug_origin == "self_diagnosed":
            return config.box_policy.bug_report_self_diagnosed
        if bug_origin == "player":
            return (config.box_policy.bug_report_player_repro if has_repro
                    else config.box_policy.bug_report_player_no_repro)
        raise ValueError("bug_report bug_origin must be 'self_diagnosed' or 'player'")
    rows = {
        "failure_report": config.box_policy.failure_report,
        "retro_finding": config.box_policy.retro_finding,
        "override_report": config.box_policy.override_report,
        "suggestion": config.box_policy.suggestion,
    }
    try:
        return rows[message_class]
    except KeyError:
        raise ValueError(f"unknown message class {message_class!r}") from None


def _under(path: str, prefix: str) -> bool:
    child = PurePosixPath(path)
    parent = PurePosixPath(prefix)
    return child == parent or parent in child.parents


def starting_state(config: Config, *, message_class: str, bug_origin: str | None = None,
                   has_repro: bool = False, fence: Iterable[str] = (), reopened: bool = False,
                   bypass: bool = False, go_binds: bool) -> str:
    """Apply the configured row and the fail-closed authority overrides."""
    configured = _row(config, message_class, bug_origin, has_repro)
    inventory = config.engine_plane_safety_inventory
    if (configured != "confirmed" or not go_binds or reopened or bypass or not inventory
            or any(_under(path, prefix) for path in fence for prefix in inventory)):
        return "draft"
    return "confirmed"
