"""Write the bounded daemon-soak report to an Implement worktree outbox."""

import json
from pathlib import Path

from squatch.artifacts import DAEMON_SOAK_REPORT, DaemonSoakReport
from squatch.seams import Filesystem

REPORT_NAME = DAEMON_SOAK_REPORT


def dumps(report: DaemonSoakReport) -> str:
    """Return the byte-stable representation used by ordinary-lane custody."""
    return json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"


def write_report(*, workspace: Path, stem: str, report: DaemonSoakReport,
                 fs: Filesystem) -> Path:
    """Leave a validated report for the stage-terminal ordinary lane to lift."""
    if not stem or Path(stem).name != stem:
        raise ValueError("stem must be one non-empty path component")
    # Validate a copy at the write boundary so subclasses or unvalidated input
    # cannot bypass the same closed contract the ordinary lane applies.
    data = dumps(DaemonSoakReport.model_validate(report.model_dump(mode="json"))).encode()
    destination = Path(workspace) / "tickets" / stem / REPORT_NAME
    fs.write(destination, data)
    return destination
