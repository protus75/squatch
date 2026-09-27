"""Dormant, journal-backed flake quarantine boundary."""

from collections.abc import Iterable

from squatch.box import Box
from squatch.journal import Event, Journal, JournalCorruption


def fold_quarantine(events: Iterable[Event]) -> dict[str, str]:
    """Project flake detections into the report-keyed quarantine ledger."""
    quarantine: dict[str, str] = {}
    for event in events:
        if event.type != "signal" or event.body.get("kind") != "flake_detected":
            continue
        try:
            test_id = event.body["test_id"]
            signature = event.body["signature"]
            box_id = event.body["box_id"]
            if (set(event.body) != {"kind", "test_id", "signature", "box_id"}
                    or not all(isinstance(value, str) and value
                               for value in (test_id, signature, box_id))
                    or event.key != f"flake/{box_id}"):
                raise ValueError("flake detection does not have its durable identity")
            previous = quarantine.get(box_id)
            if previous is not None and previous != test_id:
                raise ValueError("flake report is assigned to different tests")
            quarantine[box_id] = test_id
        except (KeyError, ValueError) as error:
            raise JournalCorruption(f"invalid flake detection {event.key!r}: {error}") from error
    return quarantine


class Flake:
    """Record one already-observed flaky rerun in the durable ledger."""

    def __init__(self, *, journal: Journal, box: Box) -> None:
        self._journal = journal
        self._box = box

    def detect(self, *, test_id: str, signature: str, box_id: str) -> bool:
        """Append the report identity once and return whether it was newly recorded."""
        if not all(isinstance(value, str) and value for value in (test_id, signature, box_id)):
            raise ValueError("flake detection needs nonempty test, signature, and box identities")
        report = self._box.get(box_id)
        if report.signature != signature:
            raise ValueError("flake signature does not match its Suggestion Box report")
        quarantine = fold_quarantine(self._journal.read())
        previous = quarantine.get(box_id)
        if previous is not None:
            if previous != test_id:
                raise ValueError("flake report is already assigned to a different test")
            return False
        self._journal.append("signal", {
            "kind": "flake_detected", "test_id": test_id,
            "signature": signature, "box_id": box_id,
        }, key=f"flake/{box_id}")
        return True

    def quarantine(self) -> dict[str, str]:
        """Read the current test quarantine projection from the journal."""
        return fold_quarantine(self._journal.read())
