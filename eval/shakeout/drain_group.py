"""Shakeout members for drain re-offers and premise parks."""

import asyncio
import json
import sys
import textwrap

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.journal import Journal
from squatch.llm import FakeLLM
from squatch.stages import RUN_RECORD_SECTIONS
from squatch.tickets import Intake

GROUP = "shakeout-drain"


def _answer(verdict: str) -> str:
    return json.dumps({"verdict": verdict, "summary": "drain shakeout response"})


def _review() -> str:
    return json.dumps({"verdict": "approve", "summary": "drain shakeout approved",
                       "findings": []})


def _diagnosis() -> str:
    return json.dumps({"verdict": "retry", "lessons": ["clear the planted red file"],
                       "reason": "the first verification run was planted red"})


def _record(outcome: str = "ok") -> str:
    bodies = {"Outcome": outcome, "Resolved engine/model": "fake/fake-1",
              "Predicted vs actual": "1m / under 1m"}
    return "".join(f"## {name}\n{bodies.get(name, '')}\n" for name in RUN_RECORD_SECTIONS)


def _ticket(stem: str) -> str:
    command = (f'{sys.executable} -c "import pathlib,sys;'
               f"p=pathlib.Path('feature/{stem}.txt');"
               "sys.exit(p.is_file() and p.read_text() == 'red\\n')\"")
    return textwrap.dedent(f"""\
        ---
        state: confirmed
        source: human
        priority: P1
        kind: chore
        ---
        ## Depends on
        - none

        ## Context
        - fixture/context.txt

        ## Goal
        Exercise the drain scheduling observable for {stem}.

        ## Why
        The shakeout must distinguish a parked run from eligible work.

        ## Scope in
        One fixture file.

        ## Scope out
        Engine code.

        ## Scope fence
        - feature/{stem}.txt

        ## Acceptance criteria
        - `feature/{stem}.txt` contains the green fixture after the drain releases the stem.

        ## Verification
        ```
        {command}
        ```

        ## Definition of rejected
        Stop if the fixture cannot plant or release the parked stem.

        ## Time budget
        - expected: 1m
        - stuck: 2m
        """)


class _ActingFake(FakeLLM):
    def __init__(self, *script, actions=()):
        super().__init__(*script)
        self.actions = list(actions)

    async def call(self, request):
        action = self.actions.pop(0) if self.actions else None
        if action is not None:
            await action(request)
        return await super().call(request)


def _write(git, content: str | None, *, outcome: str = "ok"):
    async def action(request):
        record = request.worktree / "tickets" / request.ticket / "run.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(_record(outcome))
        if content is None:
            return
        rel = f"feature/{request.ticket}.txt"
        path = request.worktree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        await git.add(request.worktree, (rel,))
        await git.commit(request.worktree, "plant drain shakeout", (rel,))
    return action


def _running(bench: Bench, stem: str) -> list[int]:
    return [event.body["run_seq"] for event in bench.events()
            if event.type == "state_transition" and event.ticket == stem
            and event.body.get("to") == "running"]


def _run_red_then_green_one_invocation(bench: Bench) -> str:
    stem = "red-then-green-one-invocation"
    fake = _ActingFake(
        _answer("implemented"), _diagnosis(), _answer("implemented"), _review(),
        actions=(_write(bench.git, "red\n"), None,
                 _write(bench.git, "green\n"), None))
    bench.write_ticket(stem, _ticket(stem))
    bench.configure(fake=fake)

    rc = bench.drain()

    events = [event for event in bench.events() if event.ticket == stem]
    terminals = [(event.body.get("to"), event.body.get("run_seq")) for event in events
                 if event.type == "state_transition" and event.body.get("to") != "running"]
    retries = [event for event in events if event.type == "cap_consumed"
               and event.body.get("cap") == "retry"]
    if (rc == 0 and terminals == [("gate_failed", 0), ("merged", 1)]
            and len(retries) == 1 and retries[0].body.get("run_seq") == 1):
        return "merged:one_invocation_one_retry"
    return f"rc={rc};terminals={terminals};retry={len(retries)}"


def _commit_ticket_edit(bench: Bench, stem: str) -> None:
    path = bench.repo / "tickets" / stem / "ticket.md"
    path.write_text(path.read_text().replace(
        "The shakeout must distinguish a parked run from eligible work.",
        "The edited ticket now distinguishes a parked run from eligible work."))

    async def commit() -> None:
        with Journal(bench.state_dir, clock=bench.clock) as journal:
            intake = Intake(repo=bench.repo, git=bench.git, journal=journal, fs=bench.fs)
            await intake.commit(stem)

    asyncio.run(commit())


def _run_premise_park_released_by_edit(bench: Bench) -> str:
    stem = "premise-park-released-by-edit"
    fake = _ActingFake(
        _answer("premise_failed"),
        actions=(_write(bench.git, None, outcome="premise_failed"),))
    bench.write_ticket(stem, _ticket(stem))
    bench.configure(fake=fake)

    first = bench.drain()
    before = _running(bench, stem)
    line_start = len(bench.lines)
    second = bench.drain()
    after_second = _running(bench, stem)
    parked = [line for line in bench.lines[line_start:] if line.startswith(f"parked: {stem}")]

    _commit_ticket_edit(bench, stem)
    released = _ActingFake(
        _answer("implemented"), _review(),
        actions=(_write(bench.git, "green\n"), None))
    bench.configure(fake=released)
    third = bench.drain()
    after_third = _running(bench, stem)

    road = (len(parked) == 1 and f"edit tickets/{stem}/ticket.md" in parked[0]
            and "SQUATCH_PLAN.md" not in parked[0])
    if (first == second == third == 0 and before == after_second == [0]
            and after_third == [0, 1] and road):
        return "premise_failed:skipped_until_edit"
    return (f"rc={first},{second},{third};running={before},{after_second},{after_third};"
            f"road={road}")


MEMBERS = (
    Member(
        "red_then_green_one_invocation",
        "the fake implementer writes a verification-red file on run 0 and green on run 1",
        ("one drain journals gate_failed for run 0, exactly one retry draw, and merged "
         "for run 1"),
        "merged:one_invocation_one_retry",
        "tickets/<stem>/attempts/0/harvest.json",
        _run_red_then_green_one_invocation,
    ),
    Member(
        "premise_park_released_by_edit",
        "the fake implementer answers premise_failed on run 0",
        ("a second drain adds no running transition and reports the source-keyed road; "
         "a committed ticket.md edit releases run 1 on the third drain"),
        "premise_failed:skipped_until_edit",
        "tickets/<stem>/run.md",
        _run_premise_park_released_by_edit,
    ),
)
