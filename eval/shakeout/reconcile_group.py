"""Shakeout member for reconcile-on-entry after an engine fault."""

import json
import textwrap

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.llm import FakeLLM
from squatch.runner import Refusal
from squatch.stages import RUN_RECORD_SECTIONS

GROUP = "shakeout-reconcile"


def _answer(verdict: str) -> str:
    return json.dumps({"verdict": verdict, "summary": "reconcile shakeout response"})


def _diagnosis() -> str:
    return json.dumps({"verdict": "retry", "lessons": ["the predecessor process died"],
                       "reason": "reconcile shakeout fault observed"})


def _record(outcome: str, *, dead_ends: str = "") -> str:
    bodies = {"Outcome": outcome, "Dead ends": dead_ends,
              "Resolved engine/model": "fake/fake-1",
              "Predicted vs actual": "1m / under 1m"}
    return "".join(f"## {name}\n{bodies.get(name, '')}\n" for name in RUN_RECORD_SECTIONS)


def _ticket(stem: str) -> str:
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
        Exercise reconcile-on-entry for {stem}.

        ## Why
        A dead engine must not strand the stem or discard its run record.

        ## Scope in
        One fixture run record.

        ## Scope out
        Engine code.

        ## Scope fence
        - feature/{stem}.txt

        ## Acceptance criteria
        - `python -c raise SystemExit(0)` exits 0 after the reaped run is harvested and the next attempt is findings-fed.

        ## Verification
        ```
        python -c "raise SystemExit(0)"
        ```

        ## Definition of rejected
        Stop if the fixture cannot leave an orphaned worktree.

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
            action(request)
        return await super().call(request)


def _write_record(text: str):
    def action(request):
        path = request.worktree / "tickets" / request.ticket / "run.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return action


class _ProcessDeath(RuntimeError):
    pass


def _run_engine_death_reaped(bench: Bench) -> str:
    stem = "engine-death-reaped"
    marker = "dead-engine-run-record-marker"
    fake = _ActingFake(
        _answer("implemented"), _answer("premise_failed"), _diagnosis(),
        actions=(_write_record(_record("ok", dead_ends=marker)),
                 _write_record(_record("premise_failed")), None))
    bench.write_ticket(stem, _ticket(stem))
    bench.configure(fake=fake)

    production_factory = bench.runner._pipeline

    def faulting_factory(journal):
        pipeline = production_factory(journal)

        async def process_died(*args, **kwargs):
            raise _ProcessDeath("the implementer process died after writing run.md")

        pipeline.stages._lift = process_died
        return pipeline

    bench.runner._pipeline = faulting_factory
    faulted = False
    try:
        bench.run(stem)
    except Refusal as error:
        faulted = "left `running` with no terminal" in error.paved_road
    finally:
        bench.runner._pipeline = production_factory

    before = bench.events()
    no_terminal = bench.terminal(stem, 0) is None
    worktree_present = (bench.repo / bench.config.worktree_root / stem).is_dir()
    bench.run(stem)

    events = bench.events()
    transitions = [event for event in events
                   if event.type == "state_transition" and event.ticket == stem]
    abandoned = next((event for event in transitions
                      if event.body.get("to") == "abandoned"), None)
    rerun = next((event for event in transitions
                  if event.body.get("to") == "running"
                  and event.body.get("run_seq") == 1), None)
    lift = next((event for event in events
                 if event.type == "effect_completion" and event.ticket == stem
                 and event.key == f"lift/{stem}/0/harvest"), None)
    abandoned_index = events.index(abandoned) if abandoned is not None else -1
    lift_index = events.index(lift) if lift is not None else -1
    prompt = bench.state_dir / "spools" / stem / "1" / "001-prompt.md"
    rendered = prompt.read_text() if prompt.is_file() else ""
    harvested = bench.repo / "tickets" / stem / "attempts" / "0" / "harvest.json"
    harvested_record = bench.repo / "tickets" / stem / "attempts" / "0" / "run.md"

    if (faulted and no_terminal and worktree_present and len(before) < len(events)
            and abandoned is not None
            and abandoned.body == {"to": "abandoned", "run_seq": 0,
                                   "harvest": f"tickets/{stem}/attempts/0"}
            and lift_index >= 0 and lift_index < abandoned_index and rerun is not None
            and harvested.is_file() and harvested_record.is_file()
            and marker in rendered
            and "harvest attempt 0: outcome `abandoned`" in rendered):
        return "abandoned:harvested_reentered"
    return (f"faulted={faulted};open={no_terminal};worktree={worktree_present};"
            f"abandoned={abandoned is not None};lift_order={lift_index < abandoned_index};"
            f"rerun={rerun is not None};harvest={harvested.is_file()};"
            f"rendered={marker in rendered}")


MEMBERS = (
    Member(
        "engine_death_reaped",
        "the fake implementer writes run.md and the engine faults before a terminal is written",
        ("the next entry lifts attempts/0 before abandoned, then dispatches run 1 with the "
         "harvested outcome and run record in its Implement prompt"),
        "abandoned:harvested_reentered",
        "tickets/<stem>/attempts/<n>/harvest.json",
        _run_engine_death_reaped,
    ),
)
