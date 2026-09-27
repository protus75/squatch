"""Dormant, journal-backed flake quarantine boundary."""

from collections.abc import Iterable
from dataclasses import dataclass

from squatch.box import Box
from squatch.journal import Event, Journal, JournalCorruption


@dataclass(frozen=True)
class FlakeRerun:
    """One caller-observed rerun tied to the test and fix that caused it."""

    test_id: str
    fix_stem: str
    green: bool


def fold_quarantine(events: Iterable[Event]) -> dict[str, str]:
    """Project flake detections into the report-keyed quarantine ledger."""
    quarantine: dict[str, tuple[str, str]] = {}
    for event in events:
        if event.type != "signal":
            continue
        kind = event.body.get("kind")
        if kind == "flake_detected":
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
                if previous is not None and previous[0] != test_id:
                    raise ValueError("flake report is assigned to different tests")
                quarantine[box_id] = (test_id, signature)
            except (KeyError, ValueError) as error:
                raise JournalCorruption(
                    f"invalid flake detection {event.key!r}: {error}") from error
        elif kind == "flake_released":
            try:
                test_id = event.body["test_id"]
                signature = event.body["signature"]
                box_id = event.body["box_id"]
                fix_stem = event.body["fix_stem"]
                if (set(event.body) != {"kind", "test_id", "signature", "box_id", "fix_stem"}
                        or not all(isinstance(value, str) and value
                                   for value in (test_id, signature, box_id, fix_stem))
                        or event.key != f"flake-release/{box_id}/{fix_stem}"):
                    raise ValueError("flake release does not have its durable identity")
                if quarantine.get(box_id) != (test_id, signature):
                    raise ValueError("flake release does not match a quarantined test")
                del quarantine[box_id]
            except (KeyError, ValueError) as error:
                raise JournalCorruption(
                    f"invalid flake release {event.key!r}: {error}") from error
    return {box_id: test_id for box_id, (test_id, _) in quarantine.items()}


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

    def release(self, *, box_id: str, rerun: FlakeRerun) -> bool:
        """Release one quarantined test after its authored fix reruns green."""
        if (not isinstance(box_id, str) or not box_id
                or not isinstance(rerun, FlakeRerun)
                or not all(isinstance(value, str) and value
                           for value in (rerun.test_id, rerun.fix_stem))
                or type(rerun.green) is not bool):
            raise ValueError("flake release needs report and typed rerun identities")
        events = tuple(self._journal.read())
        release_key = f"flake-release/{box_id}/{rerun.fix_stem}"
        if any(event.type == "signal" and event.key == release_key for event in events):
            return False
        quarantine = fold_quarantine(events)
        if quarantine.get(box_id) != rerun.test_id or not rerun.green:
            return False
        report = self._box.get(box_id)
        if (report.status != "authored" or report.resolution is None
                or report.resolution.link != rerun.fix_stem):
            return False
        if not any(event.type == "state_transition" and event.ticket == rerun.fix_stem
                   and event.body.get("to") == "merged"
                   and set(event.body) == {"to", "run_seq", "commit", "reviewed_sha"}
                   for event in events):
            return False
        self._journal.append("signal", {
            "kind": "flake_released", "test_id": rerun.test_id,
            "signature": report.signature, "box_id": box_id, "fix_stem": rerun.fix_stem,
        }, key=release_key)
        return True
