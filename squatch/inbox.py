"""Bounded version-1 host report intake into durable Suggestion Box custody.

Captured-stream writer: Inbox redacts host report text before Box storage.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squatch.box import Box
from squatch.redact import Redactor
from squatch.seams import Filesystem


REPLAY_LIMIT = 1024 * 1024
LOG_EXCERPT_LIMIT = 64 * 1024
METADATA_LIMIT = 6 * LOG_EXCERPT_LIMIT + 16 * 1024


class ReportError(ValueError):
    """A host report is not safe to admit into durable custody."""


class Report(BaseModel):
    """The complete closed envelope, validated before replay bytes are touched."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    origin: Literal["self_diagnosed", "player"]
    summary: str = Field(min_length=1)
    signature: str = Field(min_length=1)
    app_commit: str = Field(min_length=1)
    app_version: str = Field(min_length=1)
    implicated_paths: tuple[str, ...] = Field(min_length=1, max_length=32)
    replay_file: str = Field(min_length=1)
    replay_bytes: int = Field(gt=0, le=REPLAY_LIMIT)
    log_excerpt: str
    log_excerpt_bytes: int = Field(ge=0, le=LOG_EXCERPT_LIMIT)

    @field_validator("implicated_paths")
    @classmethod
    def _relative_paths(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        for value in paths:
            path = PurePosixPath(value)
            if not value or path.is_absolute() or ".." in path.parts:
                raise ValueError("implicated_paths must be non-empty relative paths")
        return paths

    @field_validator("replay_file")
    @classmethod
    def _relative_replay(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("replay_file must be relative to the report inbox")
        return value

    @model_validator(mode="after")
    def _excerpt_size(self):
        if len(self.log_excerpt.encode()) != self.log_excerpt_bytes:
            raise ValueError("log_excerpt_bytes does not match the UTF-8 excerpt")
        return self


@dataclass(frozen=True)
class IngestedReport:
    filed: int
    duplicates: int
    rejected: int


class Inbox:
    """Consume explicit report files, isolating invalid arrivals from later work."""

    def __init__(self, path: Path, *, box: Box, fs: Filesystem, redact: Redactor):
        self.path = Path(path)
        self._box = box
        self._fs = fs
        self._redact = redact

    def consume(self) -> IngestedReport:
        filed = duplicates = rejected = 0
        for report_path in self._fs.list(self.path, "*.report.json"):
            try:
                duplicate = self._consume_one(report_path)
            except ReportError:
                self._fs.replace(report_path, report_path.with_suffix(".rejected"))
                rejected += 1
            else:
                self._fs.replace(report_path, report_path.with_suffix(".filed"))
                if duplicate:
                    duplicates += 1
                else:
                    filed += 1
        return IngestedReport(filed, duplicates, rejected)

    def _consume_one(self, report_path: Path) -> bool:
        report, receipt = self._metadata(report_path)
        replay_file = report.replay_file
        # Validate raw byte counts first; replacement tokens can expand the excerpt.
        excerpt = self._redact(report.log_excerpt).encode()[:LOG_EXCERPT_LIMIT].decode(
            errors="ignore")
        report = report.model_copy(update={
            "summary": self._redact(report.summary),
            "signature": self._redact(report.signature),
            "app_commit": self._redact(report.app_commit),
            "app_version": self._redact(report.app_version),
            "implicated_paths": tuple(self._redact(path) for path in report.implicated_paths),
            "replay_file": self._redact(report.replay_file),
            "log_excerpt": excerpt, "log_excerpt_bytes": len(excerpt.encode()),
        })
        origin = f"report-inbox/{report.signature}"
        if existing := self._box.by_origin(origin):
            self._box.record_rereport(existing.id, incoming_id=receipt)
            return True
        try:
            replay_path = (report_path.parent / replay_file).resolve()
            inbox_root = report_path.parent.resolve()
        except (OSError, ValueError) as error:
            raise ReportError(f"{report_path}: replay path is invalid: {error}") from error
        if inbox_root not in replay_path.parents:
            raise ReportError(f"{report_path}: replay_file escapes the report directory")
        try:
            actual_size = replay_path.stat().st_size
        except OSError as error:
            raise ReportError(f"{report_path}: replay file is unreadable: {error}") from error
        if actual_size > REPLAY_LIMIT:
            raise ReportError(f"{report_path}: replay file exceeds {REPLAY_LIMIT} bytes")
        if actual_size != report.replay_bytes:
            raise ReportError(f"{report_path}: replay_bytes does not match the replay file")
        try:
            replay = self._fs.read(replay_path)
        except OSError as error:
            raise ReportError(f"{report_path}: replay file is unreadable: {error}") from error
        if len(replay) != actual_size:
            raise ReportError(f"{report_path}: replay file changed while reading")
        # Custody hashes the original bytes; reject secrets instead of rewriting them.
        replay_text = replay.decode(errors="surrogateescape")
        if self._redact(replay_text) != replay_text:
            raise ReportError(f"{report_path}: replay contains a configured secret; "
                              "remove it and submit a new report")
        evidence = self._box.store_evidence(
            report_signature=report.signature, app_commit=report.app_commit,
            app_version=report.app_version, implicated_paths=report.implicated_paths,
            replay=replay, log_excerpt=report.log_excerpt)
        result = self._box.enqueue(
            message_class="bug_report", summary=report.summary,
            detail=_detail(report, evidence.replay_path), origin=origin,
            bug_origin=report.origin, has_repro=True, evidence=evidence,
            incoming_id=receipt)
        return result.duplicate

    def _metadata(self, path: Path) -> tuple[Report, str]:
        try:
            if path.stat().st_size > METADATA_LIMIT:
                raise ReportError(f"{path}: report metadata exceeds {METADATA_LIMIT} bytes")
            raw = self._fs.read(path)
            report = Report.model_validate(json.loads(raw))
            # Distinct filenames are distinct arrivals even with identical bytes;
            # the same file retried after a failed rename keeps its receipt.
            receipt = hashlib.sha256(path.name.encode() + b"\0" + raw).hexdigest()
            return report, f"report-inbox/{receipt}"
        except ReportError:
            raise
        except Exception as error:
            raise ReportError(f"{path}: invalid version-1 report metadata: {error}") from error


def _detail(report: Report, replay_path: str) -> str:
    return (f"report signature: {report.signature}\napp commit: {report.app_commit}\n"
            f"app version: {report.app_version}\nimplicated paths: "
            f"{', '.join(report.implicated_paths)}\nreplay custody: {replay_path}\n"
            f"log excerpt:\n{report.log_excerpt}")
