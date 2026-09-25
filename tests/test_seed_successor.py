"""Production-composed proof that a seeder feeds the current drain."""

import json
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone

from eval.shakeout.bench import Bench
from squatch.llm import FakeLLM
from squatch.seeds import SEED_LIFT_SIGNAL, blob_sha


class Clock:
    def __init__(self):
        self.now = datetime(2026, 9, 25, tzinfo=timezone.utc)

    def __call__(self):
        self.now += timedelta(microseconds=1)
        return self.now


class ActingFake(FakeLLM):
    """Run each scripted Implement action in its granted worktree."""

    def __init__(self, *script, actions=()):
        super().__init__(*script)
        self.actions = list(actions)
        self.seeder_branch_diff: list[str] | None = None
        self.seeder_worktree = None

    async def call(self, request):
        if request.ticket == "seeder" and request.worktree is not None:
            self.seeder_worktree = request.worktree
        if request.surface == "review" and request.ticket == "seeder":
            self.seeder_branch_diff = subprocess.run(
                ["git", "-C", str(self.seeder_worktree), "diff", "--name-only", "main...seeder"],
                check=True, capture_output=True, text=True).stdout.splitlines()
        action = self.actions.pop(0) if self.actions else None
        if action is not None:
            action(request)
        return await super().call(request)


def ticket(stem: str, *, depends: str = "none", source: str | None = None) -> str:
    frontmatter = "" if source is None else f"state: confirmed\n        source: {source}\n        "
    return textwrap.dedent(f"""\
        ---
        {frontmatter}priority: P1
        kind: feature
        ---
        ## Depends on
        - {depends}

        ## Context
        - fixture/context.txt

        ## Plan contract
        - section 20

        ## Goal
        Land the {stem} fixture.

        ## Why
        The drain proof needs a mergeable fixture change.

        ## Scope in
        The {stem} fixture file.

        ## Scope out
        Engine code and other fixture files.

        ## Scope fence
        - fixture/{stem}.txt

        ## Acceptance criteria
        - `fixture/{stem}.txt` exists after merge.

        ## Verification
        ```
        {sys.executable} -c "import pathlib,sys;sys.exit(not pathlib.Path('fixture/{stem}.txt').is_file())"
        ```

        ## Definition of rejected
        Stop if the fixture cannot be written.

        ## Time budget
        - expected: 1m
        - stuck: 2m
        """)


def run_record() -> str:
    return """\
## Outcome
ok
## Surprises / judgment calls
## Dead ends
## Second problems filed
## Resolved engine/model
fake/fake-1
## Predicted vs actual
1m / under 1m
"""


def implement(request) -> None:
    stem = request.ticket
    worktree = request.worktree
    fixture = worktree / "fixture" / f"{stem}.txt"
    fixture.write_text("green\n")
    record = worktree / "tickets" / stem / "run.md"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text(run_record())
    if stem == "seeder":
        successor = worktree / "tickets" / "successor" / "ticket.md"
        successor.parent.mkdir(parents=True, exist_ok=True)
        successor.write_text(ticket("successor", depends="seeder", source="seed"))
    subprocess.run(["git", "-C", str(worktree), "add", "--", str(fixture)], check=True)
    subprocess.run(["git", "-C", str(worktree), "commit", "-q", "-m", "fixture"], check=True)


def response(verdict: str) -> str:
    return json.dumps({"verdict": verdict, "summary": f"reviewed: {verdict}",
                       "findings": []})


def git(repo, env, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], env=env, check=True,
                          capture_output=True, text=True).stdout


def test_a_merged_seeder_lifts_and_dispatches_its_successor_in_one_drain(tmp_path):
    successor_text = ticket("successor", depends="seeder", source="seed")
    fake = ActingFake(
        json.dumps({"verdict": "implemented", "summary": "seeded"}),
        response("approve"), response("approve"),
        json.dumps({"verdict": "implemented", "summary": "implemented"}),
        response("approve"),
        actions=(implement, None, None, implement, None))
    bench = Bench.make(tmp_path / "bench", fake=fake, clock=Clock())
    plan = bench.repo / "SQUATCH_PLAN.md"
    plan.write_text("## 20. Fixture seeding\n\nThe fixture may seed its successor.\n")
    seeder = bench.write_ticket("seeder", ticket("seeder", source="seed"))
    bench.commit((plan, seeder), "plant confirmed seeder")

    assert bench.drain() == 0, bench.lines

    events = bench.events()
    successor_bytes = (bench.repo / "tickets" / "successor" / "ticket.md").read_bytes()
    assert successor_bytes == successor_text.encode()
    assert bench.terminal("seeder", 0) == "merged"
    assert bench.terminal("successor", 0) == "merged"
    assert [event.body["to"] for event in events if event.type == "state_transition"
            and event.ticket == "successor"] == ["running", "merged"]

    checks = json.loads(bench.artifact("seeder", "checks.json"))
    [requisition] = [entry for entry in checks["checks"]
                     if entry["code"] == "requisition_review"]
    assert requisition["verdict"] == "pass"
    assert requisition["path"] == "tickets/successor/ticket.md"
    assert requisition["sha"] == blob_sha(successor_text)

    intake_index, intake = next(
        (index, event) for index, event in enumerate(events)
        if event.type == "signal" and event.ticket == "successor"
        and event.body.get("kind") == "ticket_intake")
    lift_index, lift = next(
        (index, event) for index, event in enumerate(events)
        if event.type == "signal" and event.ticket == "seeder"
        and event.body.get("kind") == SEED_LIFT_SIGNAL)
    successor_running = next(
        index for index, event in enumerate(events)
        if event.type == "state_transition" and event.ticket == "successor"
        and event.body["to"] == "running")
    assert {key: intake.body[key] for key in (
        "kind", "source", "state", "commit", "path", "seeder")} == {
        "kind": "ticket_intake", "source": "seed", "state": "confirmed",
        "commit": intake.body["commit"], "path": "tickets/successor/ticket.md",
        "seeder": "seeder"}
    assert lift.body["seeds"] == {"successor": blob_sha(successor_text)}
    assert intake_index < lift_index < successor_running

    ticket_commit = intake.body["commit"]
    assert git(bench.repo, bench.env, "show", f"{ticket_commit}:tickets/successor/ticket.md") \
        == successor_text
    assert git(bench.repo, bench.env, "diff-tree", "--no-commit-id", "--name-only", "-r",
               ticket_commit).splitlines() == ["tickets/successor/ticket.md"]
    assert git(bench.repo, bench.env, "merge-base", "--is-ancestor", ticket_commit, "main") == ""
    assert git(bench.repo, bench.env, "rev-list", "--ancestry-path",
               f"{ticket_commit}..main").splitlines()
    assert fake.seeder_branch_diff == ["fixture/seeder.txt"]
