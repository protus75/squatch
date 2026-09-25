"""Closed, deterministic report schema for the Phase 2 shakeout battery."""

import json
from typing import Literal

from pydantic import Field, model_validator

from squatch.artifacts import ClosedModel

REPORT_NAME = "shakeout-report.json"


class Entry(ClosedModel):
    member: str = Field(pattern=r"^[^.]+\.[^.]+$")
    group: str = Field(min_length=1)
    fault: str = Field(min_length=1)
    observable: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    observed: str = Field(min_length=1)
    detail: str = Field(min_length=1)
    producing_run: str = Field(pattern=r"^[^/]+/\d+$")
    auditor: Literal["green", "red"]
    green: bool

    @model_validator(mode="after")
    def _green_is_derived(self):
        expected = self.observed == self.expected and self.auditor == "green"
        if self.green != expected:
            raise ValueError("green must be true exactly when observed equals expected "
                             "and auditor is green")
        if self.member.split(".", 1)[0] != self.group:
            raise ValueError("member must start with the entry's group stem")
        return self


class ShakeoutReport(ClosedModel):
    schema_version: Literal[1]
    produced_at_sha: str = Field(min_length=1)
    groups: tuple[str, ...]
    entries: tuple[Entry, ...]

    @model_validator(mode="after")
    def _registry_is_consistent(self):
        if len(self.groups) != len(set(self.groups)):
            raise ValueError("groups must not contain duplicates")
        members = [entry.member for entry in self.entries]
        if len(members) != len(set(members)):
            raise ValueError("entries must not contain duplicate members")
        unknown = [entry.member for entry in self.entries if entry.group not in self.groups]
        if unknown:
            raise ValueError(f"entries name groups absent from groups: {unknown}")
        positions = {group: index for index, group in enumerate(self.groups)}
        if [positions[entry.group] for entry in self.entries] != sorted(
                positions[entry.group] for entry in self.entries):
            raise ValueError("entries must follow the declared group order")
        return self


def dumps(report: ShakeoutReport) -> str:
    """The byte-stable representation used by custody and the double gate."""
    return json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"


def dumps_entries(entries: tuple[Entry, ...] | list[Entry]) -> str:
    """Canonical entry-list bytes for the cumulative report's double gate."""
    return json.dumps([entry.model_dump(mode="json") for entry in entries],
                      sort_keys=True, indent=2) + "\n"
