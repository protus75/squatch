"""Shakeout member for an expired agent-CLI login."""

import json
import textwrap

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.effects import Effects
from squatch.harvest import Harvest
from squatch.llm import FakeLLM
from squatch.llmeffect import LLMEffect
from squatch.providers import ADAPTERS, CliClient, Registry
from squatch.redact import Redactor

GROUP = "shakeout-providers"


def _diagnosis() -> str:
    return json.dumps({"verdict": "abandon-human", "lessons": ["re-authenticate the CLI"],
                       "reason": "the planted agent login expired"})


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
        Exercise the provider authentication-expiry path for {stem}.

        ## Why
        An expired agent login requires an operator action, not a model retry.

        ## Scope in
        One provider call that fails before writing the fixture.

        ## Scope out
        Engine code.

        ## Scope fence
        - feature/{stem}.txt

        ## Acceptance criteria
        - The expired CLI login terminals as a classified infrastructure failure before `python -c raise SystemExit(0)` is evaluated.

        ## Verification
        ```
        python -c "raise SystemExit(0)"
        ```

        ## Definition of rejected
        Stop if the fake process seam cannot return the CLI signature and exit code.

        ## Time budget
        - expected: 1m
        - stuck: 2m
        """)


class _ExpiredCodex:
    def __init__(self):
        self.calls = 0

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        self.calls += 1
        return 1, "", ADAPTERS["codex"].auth_failure_signature


def _run_auth_expiry_classified(bench: Bench) -> str:
    stem = "auth-expiry-classified"
    process = _ExpiredCodex()
    bench.write_ticket(stem, _ticket(stem))
    bench.configure(fake=FakeLLM(_diagnosis()))

    production_factory = bench.runner._pipeline

    def auth_expired_factory(journal):
        pipeline = production_factory(journal)
        redact = Redactor.from_config(bench.config, bench.env)
        client = CliClient(
            Registry(bench.config), process=process, fs=bench.fs, env=bench.env,
            redact=redact, state_dir=bench.state_dir, cwd=bench.repo)
        effect = LLMEffect(llm=client, effects=Effects(journal), redact=redact,
                           clock=bench.clock)
        pipeline.stages._llm = effect
        pipeline.stages._driver._llm = effect
        return pipeline

    bench.runner._pipeline = auth_expired_factory
    try:
        bench.run(stem)
    finally:
        bench.runner._pipeline = production_factory

    harvest = Harvest.model_validate_json(
        bench.artifact(stem, "attempts/0/harvest.json"))
    findings = harvest.findings
    terminal = next((event for event in reversed(bench.events())
                     if event.type == "state_transition" and event.ticket == stem
                     and event.body.get("to") == "infra_error"), None)
    infra = [event for event in bench.events()
             if event.type == "cap_consumed" and event.ticket == stem
             and event.body.get("cap") == "infra"]
    road = ADAPTERS["codex"].auth_paved_road
    if (process.calls == 1 and terminal is not None
            and terminal.body.get("reason") == "auth_error"
            and len(infra) == 1 and len(findings) == 1
            and findings[0].code == "auth_error"
            and findings[0].paved_road == road):
        return "infra_error:auth_error"
    return (f"calls={process.calls};terminal="
            f"{terminal.body.get('reason') if terminal else None};infra={len(infra)};"
            f"findings={[(finding.code, finding.paved_road) for finding in findings]}")


MEMBERS = (
    Member(
        "auth_expiry_classified",
        "the implement CLI writes its authentication-failure signature and exits non-zero",
        ("infra_error has stable reason auth_error, one infra cap draw, and harvest.json "
         "carries the auth_error finding with the codex login road"),
        "infra_error:auth_error",
        "tickets/<stem>/attempts/<n>/harvest.json",
        _run_auth_expiry_classified,
    ),
)
