"""Starting-state policy for machine-authored box tickets (plan section 12)."""

from collections.abc import Iterable
from pathlib import PurePosixPath

from squatch.config import Config


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
