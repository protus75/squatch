"""Authored seed discovery and batch validation (SQUATCH_PLAN.md section 19)."""

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from squatch.artifacts import Finding
from squatch.config import Config
from squatch.git import Git
from squatch.journal import Event
from squatch.tickets import (TICKET_FILE, TICKETS_DIR, TicketLintError, cycle_through,
                             depends_of, lint_ticket, on_disk_stems, parse_frontmatter)

SEED_LIFT_SIGNAL = "seed_lift"
CODE = "requisition_review"
SPLIT_ROAD = "split the batch using the plan's `-continue` shape"
REVIEWED_BYTES_ROAD = ("re-run the stem: authored seed bytes changed after "
                       "requisition_review")


@dataclass(frozen=True)
class Seed:
    stem: str
    text: str
    sha: str

    @property
    def path(self) -> str:
        return f"{TICKETS_DIR}/{self.stem}/{TICKET_FILE}"


def blob_sha(text: str) -> str:
    data = text.encode()
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


async def authored_seeds(worktree: Path, stem: str, git: Git) -> tuple[Seed, ...]:
    """Foreign ticket files held by the worktree filesystem but not its HEAD."""
    worktree = Path(worktree)
    dirty = [entry.path.split(" -> ")[-1] for entry in await git.status(worktree)]
    seeds = []
    for candidate in on_disk_stems(worktree):
        if candidate == stem:
            continue
        rel = f"{TICKETS_DIR}/{candidate}/{TICKET_FILE}"
        if not any(rel == path or (path.endswith("/") and rel.startswith(path))
                   for path in dirty):
            continue
        text = (worktree / rel).read_text()
        seeds.append(Seed(candidate, text, blob_sha(text)))
    return tuple(seeds)


async def reviewed_seeds(worktree: Path, stem: str, git: Git,
                         reviewed: dict[str, str]) -> tuple[tuple[Seed, ...], list[Finding]]:
    """Bind the dirty worktree batch to the shas returned by the Check effect."""
    current = await authored_seeds(worktree, stem, git)
    by_stem = {seed.stem: seed for seed in current}
    findings = []
    for candidate in sorted(set(reviewed) | set(by_stem)):
        path = f"{TICKETS_DIR}/{candidate}/{TICKET_FILE}"
        expected = reviewed.get(candidate)
        actual = by_stem.get(candidate)
        if expected is None:
            message = f"{path} was not in the reviewed seed batch"
        elif actual is None:
            message = f"reviewed seed {path} is no longer authored in the worktree"
        elif actual.sha != expected:
            message = (f"reviewed seed {path} changed from blob {expected} "
                       f"to {actual.sha}")
        else:
            continue
        findings.append(_finding(message, REVIEWED_BYTES_ROAD, path=path))
    return tuple(by_stem[name] for name in sorted(by_stem) if name in reviewed), findings


def validate_batch(seeds: tuple[Seed, ...], *, repo: Path, plan: str | None,
                   config: Config, events: Iterable[Event], seeder: str) -> list[Finding]:
    """Fail-closed mechanical validation before any seed spends a review call."""
    repo = Path(repo)
    findings: list[Finding] = []
    if len(seeds) > config.seeding.max_seeds_per_admission:
        findings.append(_finding(
            f"seed batch has {len(seeds)} entries, over seeding.max_seeds_per_admission "
            f"{config.seeding.max_seeds_per_admission}", SPLIT_ROAD))

    batch = {seed.stem: seed for seed in seeds}
    plane = set(on_disk_stems(repo))
    resolve = lambda candidate: candidate in plane or candidate in batch
    prior = _prior_lifted(events, seeder)
    graph: dict[str, tuple[str, ...]] = {}

    for seed in seeds:
        try:
            meta, _ = parse_frontmatter(seed.text)
        except ValueError:
            meta = {}
        if meta.get("source") != "seed" or meta.get("state") != "confirmed":
            findings.append(_finding(
                "seed frontmatter must carry `source: seed` and `state: confirmed`",
                "author the seed as confirmed machine work before re-running",
                path=seed.path))
        try:
            lint_ticket(seed.text, stem=seed.stem, repo=repo, plan=plan,
                        resolve_stem=resolve)
        except TicketLintError as error:
            findings.extend(_finding(
                issue.message, issue.paved_road, path=seed.path, line=issue.line)
                for issue in error.findings)
        graph[seed.stem] = depends_of(seed.text)
        if seed.stem in plane and seed.stem not in prior:
            findings.append(_finding(
                f"seed stem {seed.stem!r} already exists on main",
                "choose a new stem; only this seeder's own prior seed_lift may be re-offered",
                path=seed.path))

    for existing in plane - batch.keys():
        path = repo / TICKETS_DIR / existing / TICKET_FILE
        graph[existing] = depends_of(path.read_text())
    for seed in seeds:
        if cycle := cycle_through(seed.stem, graph):
            findings.append(_finding(
                f"dependency cycle: {' -> '.join(cycle)}",
                "break the cycle so `Depends on` stays acyclic across the ticket plane",
                path=seed.path))
    return findings


def _prior_lifted(events: Iterable[Event], seeder: str) -> set[str]:
    events = tuple(events)
    lifted: set[str] = set()
    for event in events:
        if (event.type == "signal" and event.ticket == seeder
                and event.body.get("kind") == SEED_LIFT_SIGNAL
                and event.body.get("seeder") == seeder
                and isinstance(event.body.get("seeds"), dict)):
            lifted.update(event.body["seeds"])
    # An interrupted lift can have committed one or more seeds after its
    # intent but before its batch signal/completion. Those intake signals are
    # still this seeder's output, so replay must not misclassify them as
    # foreign collisions. A replay can open another intent without emitting
    # another intake for an already-matching seed, so partials accumulate
    # across open attempts and clear only when one completes.
    prefix = f"lift/{seeder}/"
    active = False
    partial: set[str] = set()
    for event in events:
        if (event.type == "effect_intent" and event.ticket == seeder
                and event.key and event.key.startswith(prefix)
                and event.key.endswith("/seeds")):
            active = True
        elif (active and event.type == "signal"
              and event.body.get("kind") == "ticket_intake"
              and event.body.get("source") == "seed"
              and event.body.get("seeder") == seeder and event.ticket):
            partial.add(event.ticket)
        elif (active and event.type == "effect_completion" and event.ticket == seeder
              and event.key and event.key.startswith(prefix)
              and event.key.endswith("/seeds")):
            active = False
            partial = set()
    if active:
        lifted.update(partial)
    return lifted


def _finding(message: str, paved_road: str, *, path: str | None = None,
             line: int | None = None) -> Finding:
    return Finding(code=CODE, path=path, line=line, message=message,
                   paved_road=paved_road)
