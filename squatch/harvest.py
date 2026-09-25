"""Fail-closed custody of the allowlisted material from a dying worktree."""

from collections.abc import Mapping
from pathlib import Path

from pydantic import Field

from squatch.artifacts import Artifact, ClosedModel, Cost, Finding
from squatch.box import Box, enqueue_second_problems
from squatch.git import Git
from squatch.redact import Redactor
from squatch.specs import DATA_MARKER
from squatch.tickets import TICKETS_DIR

TAIL_CHARS = 8_000
HARVEST_RENDER_CHARS = 24_000
HARVEST_FILE = "harvest.json"
RUN_RECORD = "run.md"


class HarvestCost(ClosedModel):
    usd: float
    tokens: int
    provider: str | None
    model: str | None


class Harvest(Artifact):
    outcome: str
    stage: str
    reason: str | None
    findings: tuple[Finding, ...]
    cost: HarvestCost
    wall_seconds: float = Field(ge=0)
    run_seq: int = Field(ge=0)
    diff_stat: str
    spool_tails: dict[str, str]
    filed: tuple[str, ...] = ()


def _without_diff_blocks(text: str) -> str:
    """Elide Review's untrusted diff payload before a prompt enters custody."""
    opened = f'{DATA_MARKER}data name="diff" '
    closed = f'{DATA_MARKER}end name="diff">>>'
    kept: list[str] = []
    diff: list[str] | None = None
    for line in text.splitlines(keepends=True):
        if diff is None:
            if line.startswith(opened):
                diff = []
                kept.append(line)
            else:
                kept.append(line)
        elif line.rstrip("\r\n") == closed:
            kept.append(f"(diff elided: {sum(map(len, diff))} chars)\n")
            kept.append(line)
            diff = None
        else:
            diff.append(line)
    if diff is not None:
        kept.append(f"(unterminated diff elided: {sum(map(len, diff))} chars)\n")
    return "".join(kept)


async def extract(*, repo: Path, state_dir: Path, git: Git, stem: str, run_seq: int,
                  worktree: Path, base: str, outcome: str, stage: str, reason: str | None,
                  findings: list[Finding], cost: Cost, wall_seconds: float,
                  box: Box | None = None, redact: Redactor | None = None) -> Mapping[str, bytes]:
    """Return the complete closed file set for one attempt; never copy diff content."""
    spool = state_dir / "spools" / stem / str(run_seq)
    tails: dict[str, str] = {}
    if spool.is_dir():
        for path in sorted(spool.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"attempt spool contains symlink {path.name!r}")
            if path.is_file():
                name = path.relative_to(spool).as_posix()
                safe = _without_diff_blocks(path.read_text(errors="replace"))
                tails[name] = safe[-TAIL_CHARS:]
    run_record = worktree / TICKETS_DIR / stem / RUN_RECORD
    if run_record.is_symlink():
        raise ValueError("run record is a symlink")
    filed: tuple[str, ...] = ()
    if box is not None and run_record.is_file():
        text = run_record.read_text()
        filed = tuple(enqueue_second_problems(
            box, redact(text) if redact is not None else text,
            stem=stem, stage=stage, outcome=outcome, run_seq=run_seq))
    artifact = Harvest(
        outcome=outcome, stage=stage, reason=reason, findings=tuple(findings),
        cost=HarvestCost(usd=cost.usd, tokens=cost.tokens, provider=cost.provider,
                         model=cost.model),
        wall_seconds=wall_seconds, run_seq=run_seq,
        diff_stat=await git.diff_stat(worktree, base), spool_tails=tails, filed=filed,
        produced_by_spec_version="harvest-1.0", produced_at_sha=base)
    prefix = f"attempts/{run_seq}"
    files: dict[str, bytes] = {
        f"{prefix}/{HARVEST_FILE}": artifact.model_dump_json(indent=2).encode()}
    if run_record.is_file():
        files[f"{prefix}/{RUN_RECORD}"] = run_record.read_bytes()
    return files
