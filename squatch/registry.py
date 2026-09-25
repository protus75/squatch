"""The ticket-plane decision registry (SQUATCH_PLAN.md section 12)."""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from squatch.git import Git
from squatch.seams import Filesystem
from squatch.tickets import STEM, TICKETS_DIR

DECISIONS_DIR = f"{TICKETS_DIR}/decisions"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    kind: Literal["decision", "tombstone"]
    link: str = Field(min_length=1)
    reopen_after_days: int = Field(ge=1)
    message: str = Field(pattern=r"^box-\d{6}-[0-9a-f]{8}$")
    body: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _valid_id(cls, value: str) -> str:
        if not STEM.match(value):
            raise ValueError("id must match the ticket stem grammar")
        return value

    @field_validator("link")
    @classmethod
    def _valid_link(cls, value: str) -> str:
        if not (STEM.match(value) or re.fullmatch(r"box-\d{6}-[0-9a-f]{8}", value)):
            raise ValueError("link must be a ticket stem, record id, or box id")
        return value


def _path(repo: Path, id: str) -> Path:
    return Path(repo) / DECISIONS_DIR / f"{id}.md"


def _render(record: Record) -> bytes:
    meta = record.model_dump(exclude={"body"})
    frontmatter = yaml.safe_dump(meta, sort_keys=False).rstrip()
    return f"---\n{frontmatter}\n---\n{record.body.rstrip()}\n".encode()


def write(repo: Path, record: Record, *, fs: Filesystem) -> Path:
    path = _path(repo, record.id)
    fs.write(path, _render(record))
    return path


def load(repo: Path) -> list[Record]:
    root = Path(repo) / DECISIONS_DIR
    if not root.is_dir():
        return []
    records: list[Record] = []
    for path in sorted(root.glob("*.md")):
        try:
            lines = path.read_text().splitlines()
            if not lines or lines[0] != "---":
                raise ValueError("missing opening frontmatter fence")
            close = lines.index("---", 1)
            meta = yaml.safe_load("\n".join(lines[1:close]))
            if not isinstance(meta, dict):
                raise ValueError("frontmatter is not a mapping")
            if "body" in meta:
                raise ValueError("unknown frontmatter key 'body'")
            records.append(Record.model_validate({**meta, "body": "\n".join(lines[close + 1:])}))
        except (OSError, ValueError, yaml.YAMLError, ValidationError) as e:
            raise ValueError(f"{path}: invalid decision record: {e}") from e
    return records


async def commit(repo: Path, record: Record, *, git: Git) -> str:
    rel = f"{DECISIONS_DIR}/{record.id}.md"
    if not _path(repo, record.id).is_file():
        raise FileNotFoundError(f"write {rel} before committing it")
    await git.add(repo, [rel])
    return await git.commit(repo, f"squatch(decisions): {record.id}", [rel])
