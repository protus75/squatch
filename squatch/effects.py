"""Once-per-key effect execution over the journal (SQUATCH_PLAN.md sections 2, 6).

`Effects.run` is the primitive every external action crosses: it journals
`effect_intent` (fsync'd before the action runs), runs the action once,
journals `effect_completion` carrying the result (and, for a metered effect,
its cost -- the ledger is the read-time fold over that field), and answers
any later call on the same key with the recorded result instead of
re-executing. Once-ness is keyed on COMPLETION: the set of completed keys is
read straight from the journal at construction (D3, no index) and grown as
effects complete. A key with an intent but no completion re-executes --
reaping that window is reconcile-on-entry's job (section 11), not this
primitive's.

`@effect(key=...)` is the decorator sugar over the primitive; `run_sequence`
is the read-time fold every per-run key carries.
"""

import functools
from collections.abc import Awaitable, Callable

from squatch.artifacts import RUN_STATES, TERMINAL_RUN_STATES
from squatch.journal import Journal

Cost = Callable[[object], dict]


def effect_key(*parts: object) -> str:
    """The pinned key join: components joined with `/`. Keys persist across
    restarts and self-upgrades, so the join is never per-call-site taste."""
    rendered = []
    for part in parts:
        if part is None or "/" in str(part) or str(part) == "":
            raise ValueError(f"effect key component {part!r} is empty or contains '/'")
        rendered.append(str(part))
    return "/".join(rendered)


class Effects:
    def __init__(self, journal: Journal):
        self.journal = journal
        self._completed: dict[str, object] = {}
        for event in journal.read():
            if event.type == "effect_completion":
                # First completion wins: a key completes once; anything later
                # under the same key is inert history.
                self._completed.setdefault(event.key, event.body["result"])

    async def run(self, action: Callable[[], Awaitable[object]], *, key: str,
                  ticket: str | None, cost: Cost | None = None) -> object:
        """Run `action` once per `key`; the result must be JSON data, since the
        completion record IS the value every replay returns. `cost` maps the
        result to the completion's cost field: a replay journals nothing, so
        a metered effect costs exactly once per key."""
        if not isinstance(key, str) or not key:
            raise ValueError("effect key must be a non-empty string")
        if key in self._completed:
            return self._completed[key]
        self.journal.append("effect_intent", {}, ticket=ticket, key=key)
        result = await action()
        body = {"result": result}
        if cost is not None:
            body["cost"] = cost(result)
        self.journal.append("effect_completion", body, ticket=ticket, key=key)
        self._completed[key] = result
        return result


def effect(*, key: str | Callable[..., str], ticket: Callable[..., str | None] | None = None,
           cost: Cost | None = None):
    """Decorate an async method of an object holding `self.effects`. `key`
    (and `ticket`) are callables over the effect's own arguments -- the
    arguments they close over select the key domain (section 6); a bare
    string keys a singleton effect."""
    def decorate(fn):
        @functools.wraps(fn)
        async def wrapper(self, *args, **kwargs):
            k = key if isinstance(key, str) else key(*args, **kwargs)
            t = None if ticket is None else ticket(*args, **kwargs)
            return await self.effects.run(lambda: fn(self, *args, **kwargs),
                                          key=k, ticket=t, cost=cost)
        return wrapper
    return decorate


def latest_terminal(journal: Journal, stem: str) -> str | None:
    """The terminal state the stem's latest run ended in, or None before any
    run has ended: the run-entry fold's second reading (section 11.2), so a
    re-entry renderer knows a prior run ended and how."""
    latest = None
    for event in journal.read():
        if event.type != "state_transition" or event.ticket != stem:
            continue
        to = event.body["to"]
        if to not in RUN_STATES:
            raise ValueError(f"state_transition to {to!r} is not a run state")
        if to in TERMINAL_RUN_STATES:
            latest = to
    return latest


def run_sequence(journal: Journal, stem: str) -> int:
    """The stem's run sequence at entry: the count of its prior terminal
    `state_transition` events (completed terminals and `abandoned` reaps)."""
    count = 0
    for event in journal.read():
        if event.type != "state_transition" or event.ticket != stem:
            continue
        to = event.body["to"]
        if to not in RUN_STATES:
            raise ValueError(f"state_transition to {to!r} is not a run state")
        if to in TERMINAL_RUN_STATES:
            count += 1
    return count
