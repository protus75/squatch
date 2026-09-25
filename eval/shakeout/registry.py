"""Ordered shakeout group registry; group tickets append to this tuple."""

from collections.abc import Callable
from dataclasses import dataclass
from types import ModuleType

from eval.shakeout.bench import Bench


@dataclass(frozen=True)
class Member:
    name: str
    fault: str
    observable: str
    expected: str
    detail: str
    run: Callable[[Bench], str]


# A member module exports a `MEMBERS` tuple of Member values. Strings are
# import paths in production; accepting a module object keeps fixture groups
# local to their tests without registering them globally.
GROUPS: tuple[tuple[str, str | ModuleType], ...] = (
    ("shakeout-tickets", "eval.shakeout.tickets_group"),
    ("shakeout-stages", "eval.shakeout.stages_group"),
    ("shakeout-driver", "eval.shakeout.driver_group"),
    ("shakeout-reconcile", "eval.shakeout.reconcile_group"),
    ("shakeout-merge", "eval.shakeout.merge_group"),
    ("shakeout-providers", "eval.shakeout.providers_group"),
)
