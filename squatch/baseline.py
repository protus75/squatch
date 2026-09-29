"""Fail-closed reader for the review baseline binding."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from squatch.config import Config
from squatch.journal import Event
from squatch.llm import TIERS
from squatch.providers import PLACEHOLDER, Registry
from squatch.specs import load_spec


ABSENT = "ABSENT"
NO_GO = "NO_GO"
GO = "GO"
REVOKED = "REVOKED"


@dataclass(frozen=True)
class BaselineResolution:
    state: Literal["ABSENT", "NO_GO", "GO", "REVOKED"]
    binds: bool


def resolve_baseline(config: Config, events: Iterable[Event], *, specs_dir: Path) -> BaselineResolution:
    """Resolve the newest baseline without allowing supervised input to escape."""
    selected = None
    torn = False
    try:
        for event in events:
            if (getattr(event, "type", None) == "signal"
                    and isinstance(getattr(event, "body", None), dict)
                    and event.body.get("kind") == "review_baseline"):
                selected = event.body
    except Exception:
        torn = True
    if selected is None:
        return BaselineResolution(ABSENT, False)
    if selected.get("verdict") != "GO":
        return BaselineResolution(NO_GO, False)
    if torn or not _matches(config, selected, Path(specs_dir)):
        return BaselineResolution(REVOKED, False)
    return BaselineResolution(GO, True)


def _matches(config: Config, body: dict, specs_dir: Path) -> bool:
    try:
        tiers = body["tiers"]
        if not isinstance(tiers, (list, tuple)) or not tiers or any(
                type(tier) is not str or tier not in TIERS for tier in tiers):
            return False
        identity = body["identity"]
        majors = body["spec_major"]
        if not isinstance(identity, dict) or set(identity) != {"review", "author"}:
            return False
        if not isinstance(majors, dict) or set(majors) != {"review", "author"}:
            return False
        if any(type(value) is not int for value in majors.values()):
            return False
        registry = Registry(config)
        expected = {}
        for surface in ("review", "author"):
            rows = identity[surface]
            if not isinstance(rows, dict) or set(rows) != set(tiers):
                return False
            expected[surface] = {}
            for tier in tiers:
                row = rows[tier]
                if not isinstance(row, dict) or set(row) != {"provider", "model"}:
                    return False
                if not all(isinstance(row[name], str) and row[name]
                           for name in ("provider", "model")):
                    return False
                resolved = registry.resolve(tier, surface)
                if PLACEHOLDER in (resolved.provider.auth, resolved.model):
                    return False
                expected[surface][tier] = {
                    "provider": resolved.provider.name, "model": resolved.model}
        expected_majors = {surface: _major(specs_dir / f"{surface}.md")
                           for surface in ("review", "author")}
        return identity == expected and majors == expected_majors
    except Exception:
        return False


def _major(path: Path) -> int:
    version = load_spec(path).version
    major, minor = version.split(".")
    if not major.isdigit() or not minor.isdigit():
        raise ValueError("spec version must be X.Y")
    return int(major)
