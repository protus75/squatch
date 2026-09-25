"""Shakeout members for the bounded LLM-stage driver."""

import asyncio
import json
import sys
import textwrap
from datetime import timedelta

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.config import Caps
from squatch.llm import FakeLLM, Hang
from squatch.llmeffect import llm_key
from squatch.stages import RUN_RECORD_SECTIONS

GROUP = "shakeout-driver"


def _answer(verdict: str) -> str:
    return json.dumps({"verdict": verdict, "summary": "driver shakeout response"})


def _review(verdict: str) -> str:
    return json.dumps({"verdict": verdict, "summary": "driver shakeout review",
                       "findings": []})


def _diagnosis() -> str:
    return json.dumps({"verdict": "retry", "lessons": ["clear the planted fault"],
                       "reason": "driver shakeout fault observed"})


def _record(outcome: str = "ok") -> str:
    bodies = {"Outcome": outcome, "Resolved engine/model": "fake/fake-1",
              "Predicted vs actual": "1m / under 1m"}
    return "".join(f"## {name}\n{bodies.get(name, '')}\n" for name in RUN_RECORD_SECTIONS)


def _ticket(stem: str, *, priority: str = "P1", stuck: int = 2) -> str:
    command = (f'{sys.executable} -c "import pathlib,sys;'
               f"sys.exit(not pathlib.Path('feature/{stem}.txt').is_file())\"")
    return textwrap.dedent(f"""\
        ---
        state: confirmed
        source: human
        priority: {priority}
        kind: chore
        ---
        ## Depends on
        - none

        ## Context
        - fixture/context.txt

        ## Goal
        Exercise the driver-layer {stem} observable.

        ## Why
        The shakeout must distinguish a bounded stage failure from a green run.

        ## Scope in
        One fixture file.

        ## Scope out
        Engine code.

        ## Scope fence
        - feature/{stem}.txt

        ## Acceptance criteria
        - `feature/{stem}.txt` exists unless the planted driver fault terminals the run.

        ## Verification
        ```
        {command}
        ```

        ## Definition of rejected
        Stop if the fixture cannot plant the driver fault.

        ## Time budget
        - expected: 1m
        - stuck: {stuck}m
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


def _write(git, *, file: str | None = None, record: str | None = None):
    async def action(request):
        assert request.worktree is not None
        paths = []
        if file is not None:
            path = request.worktree / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("green\n")
            paths.append(file)
        if record is not None:
            path = request.worktree / "tickets" / request.ticket / "run.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(record)
        if paths:
            await git.add(request.worktree, paths)
            await git.commit(request.worktree, "plant driver shakeout", paths)
    return action


def _run_schema_invalid_exhausts_reprompt(bench: Bench) -> str:
    stem = "schema-invalid-exhausts-reprompt"
    invalid = _review("outside-the-review-vocabulary")
    fake = _ActingFake(
        _answer("implemented"), *([invalid] * (Caps().retry + 1)), _diagnosis(),
        actions=(_write(bench.git, file=f"feature/{stem}.txt", record=_record()),))
    bench.write_ticket(stem, _ticket(stem))
    bench.configure(fake=fake)

    bench.run(stem)

    completions = [event.key for event in bench.events()
                   if event.type == "effect_completion" and event.key
                   and f"/{stem}/0/review/" in event.key]
    expected = [llm_key(stem, 0, "review", 0, call_seq)
                for call_seq in range(1, Caps().retry + 2)]
    harvest = f"tickets/{stem}/attempts/0/harvest.json"
    tracked = asyncio.run(bench.git.ls_files(bench.repo))
    if (completions == expected and bench.terminal(stem, 0) == "invalid_artifact"
            and harvest in tracked):
        return "invalid_artifact:reprompt_exhausted"
    return (f"calls={len(completions)};terminal={bench.terminal(stem, 0)};"
            f"harvest={harvest in tracked}")


def _run_stuck_budget_killed(bench: Bench) -> str:
    stuck, green = "stuck-budget-killed", "stuck-budget-green"
    expired = False

    async def expire(seconds: float) -> None:
        nonlocal expired
        if not expired:
            expired = True
            bench.clock.now += timedelta(seconds=seconds)
            await asyncio.sleep(0)
            return
        await asyncio.sleep(seconds)

    fake = _ActingFake(
        Hang(resist=True), _diagnosis(), _answer("implemented"), _review("approve"),
        _answer("premise_failed"),
        actions=(_write(bench.git, record=_record("premise_failed")),
                 None, _write(bench.git, file=f"feature/{green}.txt", record=_record()),
                 None, _write(bench.git, record=_record("premise_failed"))))
    bench.write_ticket(stuck, _ticket(stuck, priority="P0", stuck=1))
    bench.write_ticket(green, _ticket(green, priority="P1"))
    bench.configure(fake=fake, sleep=expire)

    bench.drain()

    harvest = f"tickets/{stuck}/attempts/0/harvest.json"
    tracked = asyncio.run(bench.git.ls_files(bench.repo))
    if (fake.aborted == 1 and bench.terminal(stuck, 0) == "timeout"
            and harvest in tracked and bench.terminal(green, 0) == "merged"):
        return "timeout:killed_harvested_drain_continued"
    return (f"aborted={fake.aborted};timeout={bench.terminal(stuck, 0)};"
            f"harvest={harvest in tracked};green={bench.terminal(green, 0)}")


MEMBERS = (
    Member("schema_invalid_exhausts_reprompt",
           "review answers with a verdict outside its schema on every driver call",
           "retry plus one consecutive review effect completions precede invalid_artifact",
           "invalid_artifact:reprompt_exhausted",
           "tickets/<stem>/attempts/<n>/harvest.json",
           _run_schema_invalid_exhausts_reprompt),
    Member("stuck_budget_killed",
           "a cancellation-resistant stage crosses its clock-derived one-minute budget",
           "the fake is aborted, timeout is harvested, and the same drain merges the next ticket",
           "timeout:killed_harvested_drain_continued",
           "tickets/<stem>/attempts/<n>/harvest.json",
           _run_stuck_budget_killed),
)
