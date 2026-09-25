"""Engine log: the diagnostic sink that is not the journal (SQUATCH_PLAN.md section 6).

One line-oriented JSON log at `<state_dir>/engine.log`, size-rotated at the
engine constants below, never authoritative: no gate or dispatch decision
reads it. Every line passes the redaction seam before it is written.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from squatch.journal import render_ts
from squatch.redact import Redactor
from squatch.seams import Clock

# Engine constants, not config: 16 MiB x 4 files.
MAX_BYTES = 16 * 2**20
KEEP = 4
NAME = "engine.log"


class EngineLog:
    def __init__(self, state_dir: Path, *, clock: Clock, redact: Redactor):
        self._clock = clock
        self._redact = redact
        self.path = Path(state_dir) / NAME
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, name: str, **fields) -> None:
        record = {"ts": render_ts(self._clock()), "event": name, **fields}
        # Scrub BEFORE encoding: json.dumps rewrites quotes, backslashes and
        # non-ASCII, so a secret carrying any of them would no longer match
        # as a literal substring of the encoded line.
        line = (json.dumps(_scrub(record, self._redact)) + "\n").encode()
        # Rotate whole lines only: a line is never split across files.
        if self.path.exists() and self.path.stat().st_size + len(line) > MAX_BYTES:
            self._rotate()
        with self.path.open("ab") as fh:
            fh.write(line)

    def _rotate(self) -> None:
        for n in range(KEEP - 1, 0, -1):
            src = self.path if n == 1 else self.path.with_name(f"{NAME}.{n - 1}")
            if src.exists():
                os.replace(src, self.path.with_name(f"{NAME}.{n}"))


def _scrub(value, redact: Redactor):
    """Redact every string in a record, keys and values, nested; non-JSON
    leaves are stringified first (what `json.dumps(default=str)` did)."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, Mapping):
        return {(redact(k) if isinstance(k, str) else k): _scrub(v, redact)
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_scrub(v, redact) for v in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(str(value))
