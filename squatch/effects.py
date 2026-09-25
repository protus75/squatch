"""Once-per-key effect execution over the journal (SQUATCH_PLAN.md sections 2, 6).

`Effects.run` is the primitive every external action crosses: it journals
`effect_intent` (fsync'd before the action runs), runs the action once,
journals `effect_completion` carrying the result, and answers any later call
on the same key with the recorded result instead of re-executing. Once-ness
is keyed on COMPLETION: the set of completed keys is read straight from the
journal at construction (D3, no index) and grown as effects complete. A key
with an intent but no completion re-executes -- reaping that window is
reconcile-on-entry's job (section 11), not this primitive's.

The `@effect(key=...)` decorator is deferred to its first call site.
"""

from collections.abc import Awaitable, Callable

from squatch.journal import Journal


class Effects:
    def __init__(self, journal: Journal):
        self._journal = journal
        self._completed: dict[str, object] = {}
        for event in journal.read():
            if event.type == "effect_completion":
                # First completion wins: a key completes once; anything later
                # under the same key is inert history.
                self._completed.setdefault(event.key, event.body["result"])

    async def run(self, action: Callable[[], Awaitable[object]], *, key: str,
                  ticket: str | None) -> object:
        """Run `action` once per `key`; the result must be JSON data, since the
        completion record IS the value every replay returns."""
        if not isinstance(key, str) or not key:
            raise ValueError("effect key must be a non-empty string")
        if key in self._completed:
            return self._completed[key]
        self._journal.append("effect_intent", {}, ticket=ticket, key=key)
        result = await action()
        self._journal.append("effect_completion", {"result": result},
                             ticket=ticket, key=key)
        self._completed[key] = result
        return result
