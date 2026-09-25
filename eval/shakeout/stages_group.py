"""Shakeout members for the production Implement, Check, and Review stages."""

import asyncio
import json
import sys
import textwrap
from pathlib import Path

from eval.shakeout.bench import Bench
from eval.shakeout.registry import Member
from squatch.llm import FakeLLM, Hang
from squatch.stages import Invoice, RUN_RECORD_SECTIONS, load_review

GROUP = "shakeout-stages"
_DIAGNOSIS = json.dumps({
    "verdict": "retry", "lessons": ["clear the planted fault"],
    "reason": "shakeout fault observed",
})


def _answer(verdict: str, summary: str = "shakeout response") -> str:
    return json.dumps({"verdict": verdict, "summary": summary})


def _review(verdict: str, message: str = "stage shakeout review finding") -> str:
    findings = [] if verdict == "approve" else [{
        "code": "correctness_review", "path": None, "line": None,
        "message": message, "paved_road": "clear the planted review finding",
    }]
    return json.dumps({"verdict": verdict, "summary": f"reviewed: {verdict}",
                       "findings": findings})


def _record(outcome: str = "ok", *, dead_ends: str = "") -> str:
    bodies = {"Outcome": outcome, "Dead ends": dead_ends,
              "Resolved engine/model": "fake/fake-1",
              "Predicted vs actual": "1m / under 1m"}
    return "".join(f"## {name}\n{bodies.get(name, '')}\n" for name in RUN_RECORD_SECTIONS)


def _ticket(stem: str, *, verification: str | None = None, stuck: int = 2,
            fence: str | None = None) -> str:
    verification = verification or (
        f'{sys.executable} -c "import pathlib,sys;'
        f"sys.exit(not pathlib.Path('feature/{stem}.txt').is_file())\"")
    fence = fence or f"feature/{stem}.txt"
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
        Exercise the stage-layer {stem} observable.

        ## Why
        The shakeout must record the production stage result.

        ## Scope in
        One fixture file.

        ## Scope out
        Engine code.

        ## Scope fence
        - {fence}

        ## Acceptance criteria
        - The planted stage fault determines whether `{fence}` satisfies the ticket.

        ## Verification
        ```
        {verification}
        ```

        ## Definition of rejected
        Stop if the fixture cannot plant the stage fault.

        ## Time budget
        - expected: 1m
        - stuck: {stuck}m
        """)


class _ActingFake(FakeLLM):
    def __init__(self, *script, actions=(), provider="fake", model="fake-1"):
        super().__init__(*script, provider=provider, model=model)
        self.actions = list(actions)

    async def call(self, request):
        action = self.actions.pop(0) if self.actions else None
        if action is not None:
            await action(request)
        return await super().call(request)


def _write(git, *, files: tuple[tuple[str, str], ...] = (), record: str | None = None,
           commit: bool = False):
    async def action(request):
        assert request.worktree is not None
        for rel, content in files:
            path = request.worktree / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        if record is not None:
            path = request.worktree / "tickets" / request.ticket / "run.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(record)
        if commit:
            paths = [rel for rel, _ in files]
            await git.add(request.worktree, paths)
            await git.commit(request.worktree, "plant stage fault", paths)
    return action


def _install(bench: Bench, stem: str, fake: FakeLLM, *, ticket: str | None = None) -> None:
    bench.write_ticket(stem, ticket or _ticket(stem))
    bench.fake = fake


def _invoice(bench: Bench, stem: str) -> Invoice:
    return Invoice.model_validate_json(bench.artifact(stem, "checks.json"))


def _check(bench: Bench, stem: str, code: str):
    return next(entry for entry in _invoice(bench, stem).checks if entry.code == code)


def _run_scope_escape(bench: Bench) -> str:
    stem = "scope-escape"
    fake = _ActingFake(
        _answer("implemented"), _DIAGNOSIS,
        actions=(_write(bench.git, files=((f"feature/{stem}.txt", "green\n"),
                              ("escaped.txt", "outside\n")),
                       record=_record(), commit=True), None))
    _install(bench, stem, fake)
    bench.run(stem)
    check = _check(bench, stem, "scope_fence")
    if (bench.terminal(stem, 0) == "gate_failed" and check.verdict == "fail"
            and [finding.code for finding in check.findings] == ["scope_fence"]):
        return "gate_failed:scope_fence"
    return f"terminal={bench.terminal(stem, 0)};check={check.verdict}"


def _run_premise_false(bench: Bench) -> str:
    stem = "premise-false"
    fake = _ActingFake(
        _answer("premise_failed", "fixture premise is false"),
        actions=(_write(bench.git, record=_record("premise_failed")),))
    _install(bench, stem, fake)
    bench.run(stem)
    return bench.terminal(stem, 0) or "missing"


def _run_branch_only_red(bench: Bench) -> str:
    stem = "branch-only-red"
    command = (f'{sys.executable} -c "import pathlib,sys;'
               f"sys.exit(3 if pathlib.Path('feature/{stem}.txt').exists() else 0)\"")
    fake = _ActingFake(
        _answer("implemented"), _DIAGNOSIS,
        actions=(_write(bench.git, files=((f"feature/{stem}.txt", "red\n"),),
                       record=_record(), commit=True), None))
    _install(bench, stem, fake, ticket=_ticket(stem, verification=command))
    bench.run(stem)
    check = _check(bench, stem, "verification")
    if (bench.terminal(stem, 0) == "gate_failed" and check.verdict == "fail"
            and len(check.commands) == 1 and check.commands[0].attribution == "branch"):
        return "gate_failed:verification:branch"
    return f"terminal={bench.terminal(stem, 0)};check={check.verdict}"


def _run_base_red_excused(bench: Bench) -> str:
    stem = "base-red-excused"
    command = f'{sys.executable} -c "raise SystemExit(3)"'
    fake = _ActingFake(
        _answer("implemented"), _review("approve"),
        actions=(_write(bench.git, files=((f"feature/{stem}.txt", "green\n"),),
                       record=_record(), commit=True), None))
    _install(bench, stem, fake, ticket=_ticket(stem, verification=command))
    bench.run(stem)
    check = _check(bench, stem, "verification")
    commands = check.commands
    caps = [event for event in bench.events()
            if event.type == "cap_consumed" and event.ticket == stem]
    if (check.verdict == "pass" and len(commands) == 1
            and commands[0].attribution == "base" and commands[0].filed and not caps
            and any(request.surface == "review" for request in fake.requests)):
        return "check_passed:attribution_base"
    return f"terminal={bench.terminal(stem, 0)};check={check.verdict};caps={len(caps)}"


def _run_empty_diff(bench: Bench) -> str:
    stem = "empty-diff"
    command = f'{sys.executable} -c "raise SystemExit(0)"'
    fake = _ActingFake(
        _answer("implemented"), _DIAGNOSIS,
        actions=(_write(bench.git, record=_record()), None))
    _install(bench, stem, fake, ticket=_ticket(stem, verification=command))
    bench.run(stem)
    check = _check(bench, stem, "verification")
    if (bench.terminal(stem, 0) == "gate_failed" and check.verdict == "fail"
            and any("no committed diff" in finding.message for finding in check.findings)):
        return "gate_failed:verification:empty_diff"
    return f"terminal={bench.terminal(stem, 0)};check={check.verdict}"


def _run_review_reject(bench: Bench) -> str:
    stem = "review-reject"
    fake = _ActingFake(
        _answer("implemented"), _review("snag"), _DIAGNOSIS,
        actions=(_write(bench.git, files=((f"feature/{stem}.txt", "green\n"),),
                       record=_record(), commit=True), None, None))
    _install(bench, stem, fake)
    bench.run(stem)
    meta = load_review(bench.artifact(stem, "review.md").decode())
    if bench.terminal(stem, 0) == "gate_failed" and meta.get("verdict") == "snag":
        return "gate_failed:review_snag"
    return f"terminal={bench.terminal(stem, 0)};verdict={meta.get('verdict')}"


def _run_reject_reentry(bench: Bench) -> str:
    stem = "reject-reentry"
    marker = "criteria-position-review-marker"
    fake = _ActingFake(
        _answer("implemented"), _review("snag", marker), _DIAGNOSIS,
        _answer("premise_failed", "second prompt captured"),
        actions=(_write(bench.git, files=((f"feature/{stem}.txt", "green\n"),),
                       record=_record(), commit=True), None, None,
                 _write(bench.git, record=_record("premise_failed"))))
    _install(bench, stem, fake)
    bench.run(stem)
    bench.run(stem)
    prompt = next(request.rendered for request in fake.requests
                  if request.surface == "implement" and marker in request.rendered)
    prior = prompt.index('<<<squatch:data name="prior_attempts"')
    context = prompt.index('<<<squatch:data name="context"')
    if prompt.count(marker) == 1 and prior < prompt.index(marker) < context:
        return "reentry:criteria_position"
    return f"marker_count={prompt.count(marker)}"


def _run_timeout_dead_ends(bench: Bench) -> str:
    stem = "timeout-dead-ends"
    marker = "dead-end-marker-from-attempt-zero"
    config = bench.repo / "config.yaml"
    config.write_text(config.read_text() + "caps: {infra: 1}\n")
    bench.commit(("config.yaml",), "bound timeout shakeout infra cap")
    fake = _ActingFake(
        Hang(), _answer("premise_failed", "second prompt captured"),
        actions=(_write(bench.git, record=_record(dead_ends=marker)),
                 _write(bench.git, record=_record("premise_failed"))))
    timed = Bench(bench.repo, fake=fake, clock=bench.clock, env=bench.env)
    _install(timed, stem, fake, ticket=_ticket(stem, stuck=0))
    timed.run(stem)
    first = timed.terminal(stem, 0)
    timed.run(stem)
    prompt = next(request.rendered for request in fake.requests
                  if request.surface == "implement" and marker in request.rendered)
    attempt = timed.repo / "tickets" / stem / "attempts" / "0" / "run.md"
    prior = prompt.index('<<<squatch:data name="prior_attempts"')
    context = prompt.index('<<<squatch:data name="context"')
    bench._remember_last_run(stem)
    if (first == "timeout" and attempt.is_file() and prompt.count(marker) == 1
            and prior < prompt.index(marker) < context):
        return "timeout:dead_ends_rendered"
    return f"first={first};attempt={attempt.is_file()};marker={prompt.count(marker)}"


def _run_secret_not_persisted(bench: Bench) -> str:
    stem = "secret-not-persisted"
    name, secret = "SHAKEOUT_PROVIDER_KEY", "shakeout-planted-secret-value"
    config = bench.repo / "config.yaml"
    config.write_text(config.read_text().replace(
        "kind: cli\n", f"kind: cli\n    auth: {name}\n", 1))
    bench.commit(("config.yaml",), "declare shakeout provider auth")
    env = {**bench.env, name: secret}
    fake = _ActingFake(
        _answer("implemented", secret), _review("approve"),
        actions=(_write(bench.git, files=((f"feature/{stem}.txt", "green\n"),),
                       record=_record(dead_ends=secret), commit=True), None))
    secured = Bench(bench.repo, fake=fake, clock=bench.clock, env=env)
    secured.write_ticket(stem, _ticket(stem))
    secured.run(stem)
    bench._remember_last_run(stem)
    prefix = f"tickets/{stem}/"
    committed_paths = [path for path in asyncio.run(secured.git.ls_files(secured.repo))
                       if path.startswith(prefix)]
    committed_leaks = [path for path in committed_paths
                       if secret.encode() in (secured.repo / path).read_bytes()]
    journal = "\n".join(json.dumps(event.body, sort_keys=True) for event in secured.events())
    run = secured.artifact(stem, "run.md").decode()
    if (committed_paths and not committed_leaks and secret not in journal
            and f"[REDACTED:{name}]" in run):
        return "secret:redacted_everywhere"
    return (f"committed={bool(committed_leaks)};journal={secret in journal};"
            f"token={f'[REDACTED:{name}]' in run}")


MEMBERS = (
    Member("scope_escape", "the fake implementer commits a file outside the scope fence",
           "the Check terminal and checks.json carry scope_fence",
           "gate_failed:scope_fence", "tickets/<stem>/checks.json", _run_scope_escape),
    Member("premise_false", "the fake implementer answers premise_failed",
           "the terminal transition is premise_failed", "premise_failed",
           "tickets/<stem>/run.md", _run_premise_false),
    Member("branch_only_red", "verification is green at base and red on the branch",
           "checks.json attributes the verification failure to branch",
           "gate_failed:verification:branch", "tickets/<stem>/checks.json",
           _run_branch_only_red),
    Member("base_red_excused", "verification is red at base and on the branch",
           "Check passes with base attribution, a filed box id, and no cap draw",
           "check_passed:attribution_base", "the filed box message", _run_base_red_excused),
    Member("empty_diff", "the fake implementer commits no diff but answers implemented",
           "verification rejects the empty committed diff",
           "gate_failed:verification:empty_diff", "tickets/<stem>/checks.json",
           _run_empty_diff),
    Member("review_reject", "Review returns a snag finding",
           "the terminal is gate_failed and review.md is pinned snag",
           "gate_failed:review_snag", "tickets/<stem>/review.md", _run_review_reject),
    Member("reject_reentry_criteria_position", "a snagged stem is run a second time",
           "the prior review finding occurs once between ticket and context blocks",
           "reentry:criteria_position", "<state_dir>/spools/<stem>/1/",
           _run_reject_reentry),
    Member("timeout_dead_ends", "attempt zero hangs after writing a marked run record",
           "attempt one times out and attempt two renders its harvested dead ends",
           "timeout:dead_ends_rendered", "tickets/<stem>/attempts/0/run.md",
           _run_timeout_dead_ends),
    Member("secret_not_persisted", "provider auth is echoed in run.md and model output",
           "ticket-plane and journal bytes omit the value while run.md carries its token",
           "secret:redacted_everywhere", "tickets/<stem>/run.md",
           _run_secret_not_persisted),
)
