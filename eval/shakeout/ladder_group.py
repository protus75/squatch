"""Shakeout members for identical-terminal ladder routing."""

import json
import sys
import textwrap

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.config import Config
from squatch.llm import FakeLLM
from squatch.stages import RUN_RECORD_SECTIONS

GROUP = "shakeout-ladder"


def _answer() -> str:
    return json.dumps({"verdict": "implemented", "summary": "ladder shakeout response"})


def _review() -> str:
    return json.dumps({"verdict": "approve", "summary": "ladder shakeout approved",
                       "findings": []})


def _diagnosis() -> str:
    return json.dumps({"verdict": "retry", "lessons": ["the planted fault is unchanged"],
                       "reason": "retry the identical verification failure"})


def _record() -> str:
    bodies = {"Outcome": "ok", "Resolved engine/model": "fake/fake-1",
              "Predicted vs actual": "1m / under 1m"}
    return "".join(f"## {name}\n{bodies.get(name, '')}\n" for name in RUN_RECORD_SECTIONS)


def _ticket(stem: str, *, tier: str, effort: str) -> str:
    command = (f'{sys.executable} -c "import pathlib,sys;'
               f"p=pathlib.Path('feature/{stem}.txt');"
               "sys.exit(p.is_file() and p.read_text().startswith('red'))\"")
    return textwrap.dedent(f"""\
        ---
        state: confirmed
        source: human
        priority: P1
        kind: chore
        agent_tier: {tier}
        agent_effort: {effort}
        ---
        ## Depends on
        - none

        ## Context
        - fixture/context.txt

        ## Goal
        Exercise identical-terminal ladder routing for {stem}.

        ## Why
        The third identical failure must bypass another same-rung offer.

        ## Scope in
        One fixture file whose content controls verification.

        ## Scope out
        Engine code.

        ## Scope fence
        - feature/{stem}.txt

        ## Acceptance criteria
        - `feature/{stem}.txt` remains verification-red until the ladder decision is journaled.

        ## Verification
        ```
        {command}
        ```

        ## Definition of rejected
        Stop if the identical terminal cannot be observed.

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


def _write(git, content: str):
    async def action(request):
        record = request.worktree / "tickets" / request.ticket / "run.md"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(_record())
        rel = f"feature/{request.ticket}.txt"
        path = request.worktree / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        await git.add(request.worktree, (rel,))
        await git.commit(request.worktree, "plant ladder shakeout", (rel,))
    return action


def _config(bench: Bench, models: dict[str, str], *, retry: int | None = None) -> Config:
    data = bench.config.model_dump(mode="python")
    data["providers"][0]["models_by_tier"] = models
    if retry is not None:
        data["caps"]["retry"] = retry
    return Config.model_validate(data)


def _run_identical_terminals_climb(bench: Bench) -> str:
    stem = "identical-terminals-climb"
    fake = _ActingFake(
        _answer(), _diagnosis(), _answer(), _diagnosis(), _answer(), _diagnosis(),
        _answer(), _review(),
        actions=(_write(bench.git, "red-0\n"), None,
                 _write(bench.git, "red-1\n"), None,
                 _write(bench.git, "red-2\n"), None,
                 _write(bench.git, "green\n"), None))
    models = {"low": "low", "medium": "medium", "high": "high", "max": "high"}
    bench.write_ticket(stem, _ticket(stem, tier="medium", effort="medium"))
    bench.configure(config=_config(bench, models), fake=fake)

    direct = [bench.run(stem) for _ in range(3)]
    drained = bench.drain()

    events = [event for event in bench.events() if event.ticket == stem]
    terminals = [event for event in events if event.type == "state_transition"
                 and event.body.get("to") == "gate_failed"]
    draws = [event for event in events if event.type == "cap_consumed"
             and event.body.get("cap") == "retry"]
    fourth = next((event for event in events if event.type == "state_transition"
                   and event.body.get("to") == "running"
                   and event.body.get("run_seq") == 3), None)
    climbed = (len(terminals) == 3
               and terminals[-1].body.get("routed") == "ladder"
               and terminals[-1].body.get("rung") == {"tier": "high", "effort": "medium"}
               and len(draws) == 1
               and draws[0].body.get("rung") == {"tier": "high", "effort": "medium"}
               and fourth is not None and events.index(draws[0]) < events.index(fourth))
    if direct == [1, 1, 1] and drained == 0 and climbed:
        return "identical:climbed"
    return (f"rc={direct},{drained};terminals={len(terminals)};"
            f"draws={[draw.body for draw in draws]};climbed={climbed}")


def _run_identical_terminals_reject_when_exhausted(bench: Bench) -> str:
    stem = "identical-terminals-reject-when-exhausted"
    fake = _ActingFake(
        _answer(), _diagnosis(), _answer(), _diagnosis(), _answer(), _diagnosis(),
        actions=(_write(bench.git, "red-0\n"), None,
                 _write(bench.git, "red-1\n"), None,
                 _write(bench.git, "red-2\n"), None))
    models = {tier: "only" for tier in ("low", "medium", "high", "max")}
    bench.write_ticket(stem, _ticket(stem, tier="max", effort="max"))
    bench.configure(config=_config(bench, models), fake=fake)

    direct = [bench.run(stem) for _ in range(3)]
    terminal = next((event for event in reversed(bench.events())
                     if event.type == "state_transition" and event.ticket == stem
                     and event.body.get("to") == "gate_failed"), None)
    line_start = len(bench.lines)
    bench.configure(config=_config(bench, models, retry=0))
    drained = bench.drain()
    queue = [line for line in bench.lines[line_start:]
             if line.startswith(f"reject queue: {stem}:")]
    rejected = (terminal is not None
                and terminal.body.get("run_seq") == 2
                and terminal.body.get("routed") == "reject_queue"
                and "identical terminal reasons" in terminal.body.get("reject_reason", "")
                and "capability ladder exhausted" in terminal.body.get("reject_reason", "")
                and len(queue) == 1 and "capability ladder exhausted" in queue[0])
    if direct == [1, 1, 1] and drained == 0 and rejected:
        return "identical:rejected_exhausted"
    return (f"rc={direct},{drained};terminal={terminal.body if terminal else None};"
            f"queue={queue}")


MEMBERS = (
    Member(
        "identical_terminals_climb",
        "the fake fails the same verification command on three consecutive public runs",
        ("the third gate_failed routes to the ladder and its next retry draw carries a rung "
         "above the authored tier before run 3 dispatches"),
        "identical:climbed",
        "tickets/<stem>/diagnosis.json",
        _run_identical_terminals_climb,
    ),
    Member(
        "identical_terminals_reject_when_exhausted",
        ("the fake repeats one verification failure three times at the top rung of a "
         "single-model fixture"),
        ("the third gate_failed routes to the Reject queue with an exhausted-ladder reason "
         "and drain reports the queued stem"),
        "identical:rejected_exhausted",
        "tickets/<stem>/diagnosis.json",
        _run_identical_terminals_reject_when_exhausted,
    ),
)
