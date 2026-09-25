"""Shakeout members for the committed ticket plane."""

import json
import sys
import textwrap

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.llm import FakeLLM

GROUP = "shakeout-tickets"


def _ticket(stem: str, *, priority: str = "P1", verification: bool = True) -> str:
    text = textwrap.dedent(f"""\
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
        Exercise {stem} on the committed ticket plane.

        ## Why
        The drain must distinguish valid work from invalid committed input.

        ## Scope in
        The existing fixture context.

        ## Scope out
        Engine code and configuration.

        ## Scope fence
        - fixture/context.txt

        ## Acceptance criteria
        - `fixture/context.txt` remains present.

        ## Verification
        ```
        {sys.executable} -c "import pathlib,sys;sys.exit(not pathlib.Path('fixture/context.txt').is_file())"
        ```

        ## Definition of rejected
        Stop if the fixture checkout cannot represent the ticket.

        ## Time budget
        - expected: 1m
        - stuck: 2m
        """)
    if verification:
        return text
    verification_block = text[text.index("## Verification\n"):text.index(
        "## Definition of rejected\n")]
    return text.replace(verification_block, "")


def _run_bad_schema(bench: Bench) -> str:
    bad = bench.write_ticket("bad-schema", _ticket(
        "bad-schema", priority="P9", verification=False))
    green = bench.write_ticket("green", _ticket("green"))
    record = bench.repo / "tickets" / "green" / "run.md"
    record.write_text("""\
## Outcome
already_satisfied
## Surprises / judgment calls
## Dead ends
## Second problems filed
## Resolved engine/model
fake/fake-1
## Predicted vs actual
1m / under 1m
""")
    bench.commit((bad, green, record), "plant bad-schema ticket beside green control")
    bench.fake = FakeLLM(json.dumps({
        "verdict": "already_satisfied", "summary": "fixture context already exists"}))

    rc = bench.drain()
    bad_transitions = [event for event in bench.events()
                       if event.type == "state_transition" and event.ticket == "bad-schema"]
    held = next((line for line in bench.lines if line.startswith("held: bad-schema ")), "")
    if (rc == 0 and not bad_transitions and bench.terminal("green", 0) == "merged"
            and "priority 'P9'" in held and "closed vocabulary" in held):
        return "held:no_running_transition"
    return (f"rc={rc};bad_transitions={len(bad_transitions)};"
            f"green={bench.terminal('green', 0)};held={held or 'missing'}")


MEMBERS = (
    Member(
        name="bad_schema",
        fault=("a committed tickets/bad-schema/ticket.md has priority P9 and no "
               "Verification section"),
        observable=("drain exits at quiescence with no bad-schema state_transition while "
                    "the green control reaches merged"),
        expected="held:no_running_transition",
        detail="the drain's held: report line and the ticket_schema findings",
        run=_run_bad_schema,
    ),
)
