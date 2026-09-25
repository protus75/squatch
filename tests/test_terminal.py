"""Non-ok terminal handling (SQUATCH_PLAN.md section 11; section 18's exit-code
contract; section 19, Phase 2).

A non-ok terminal -- a spent cap or any non-ok terminal state -- harvests its
allowlisted detail, journals its state transition, wipes the worktree, and
exits 1 with the branch in place and the attempt directory named. An
engine-plane refusal exits 2 and journals no terminal. A FAULT escaping the
stage seam is a named stop, never a traceback: exit 2, the traceback in the
engine log, and the interrupted run left `running` with no terminal for
reconcile-on-entry to reap. No diagnosis or cross-attempt retry is here.

Every test drives the real `Runner` -- intake, lock, dispatch -- over the
real stages + admission with the scripted agent behind the model seam,
against a temp checkout; the process-level tests run `python -m squatch`.
"""

import json
import subprocess
import sys
import textwrap
from io import StringIO
from pathlib import Path

import pytest
from test_stages import (
    CONFIG,
    EXISTS,
    PLAN,
    PYTHON,
    STEM,
    TICKET,
    WIDGET,
    Agent,
    TickingClock,
    answer,
    env,  # noqa: F401 -- fixture
    git,
    implementer,
    repo,  # noqa: F401 -- fixture
    review,
)

from squatch.__main__ import main
from squatch.artifacts import TERMINAL_RUN_STATES, Cost
from squatch.config import load
from squatch.diagnose import DIAG_DIFF_CHARS, DiagnosisRecord
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import read_events
from squatch.llmeffect import LLMEffect
from squatch.lockfile import Lockfile
from squatch.merge import Merge, Pipeline
from squatch.redact import Redactor
from squatch.runner import EXIT_OK, EXIT_REFUSED, EXIT_TICKET, Refusal, Runner
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.specs import DATA_MARKER
from squatch.stages import Delivery, Stages

RED = f'{PYTHON} -c "import sys; sys.exit(3)"'
NO_SUCH_BINARY = "squatch-no-such-binary-7f3a"
# The CLI checkout routes no provider: Implement's call is an infra_error.
UNROUTED = textwrap.dedent("""\
    schema_version: 1
    state_dir: .squatch/state
    providers: []
    routing: []
    """)


class Drive:
    """`run <stem>` in-process: the real Runner over the real stages and
    admission, built over the lock-held journal the runner opens."""

    def __init__(self, repo: Path, env: dict, llm=None, *, pipeline=None,
                 stages_type=Stages):
        self.repo, self.env = repo, env
        self.config = load(None, cwd=repo)
        self.state = repo / self.config.state_dir
        self.clock = TickingClock()
        self.git = Git(SubprocessExec(), env=env, timeout=60.0)
        self.redact = Redactor.from_config(self.config, env)
        self.log = EngineLog(self.state, clock=self.clock, redact=self.redact)
        self.lines: list[str] = []
        self._llm, self._pipeline, self._stages_type = llm, pipeline, stages_type

    def _factory(self, journal):
        if self._pipeline is not None:
            return self._pipeline
        stages = self._stages_type(
            repo=self.repo, config=self.config, git=self.git, process=SubprocessExec(),
            fs=LocalFilesystem(),
            llm=LLMEffect(llm=self._llm, effects=Effects(journal), redact=self.redact),
            log=self.log, redact=self.redact, clock=self.clock, env=self.env)
        merge = Merge(repo=self.repo, config=self.config, git=self.git, process=SubprocessExec(),
                      fs=LocalFilesystem(), effects=Effects(journal), journal=journal,
                      log=self.log, redact=self.redact, env=self.env)
        return Pipeline(stages, merge)

    async def run(self, stem: str = STEM) -> int:
        runner = Runner(repo=self.repo, config=self.config, git=self.git, fs=LocalFilesystem(),
                        clock=self.clock, instance_id="test", pipeline=self._factory,
                        log=self.log, report=self.lines.append)
        return await runner.run(stem)

    def transitions(self, stem: str = STEM) -> list[dict]:
        return [e.body for e in read_events(self.state)
                if e.type == "state_transition" and e.ticket == stem]

    def events(self, stem: str = STEM):
        return [e for e in read_events(self.state) if e.ticket == stem]

    def log_events(self) -> list[dict]:
        return [json.loads(line) for line in self.log.path.read_text().splitlines()]

    def branch_exists(self, stem: str = STEM) -> bool:
        return subprocess.run(["git", "-C", str(self.repo), "rev-parse", "--verify",
                               f"refs/heads/{stem}"], env=self.env, capture_output=True
                              ).returncode == 0

    def worktree(self, stem: str = STEM) -> Path:
        return self.repo / self.config.worktree_root / stem

    def branch_diff_names(self, stem: str = STEM) -> list[str]:
        return git(self.repo, self.env, "diff", "--name-only", f"main...{stem}").splitlines()

    def main_files(self) -> list[str]:
        return git(self.repo, self.env, "ls-tree", "-r", "--name-only", "main").splitlines()

    def committed_ticket(self, stem: str = STEM) -> str:
        return git(self.repo, self.env, "show", f"main:tickets/{stem}/ticket.md")

    def lock_is_free(self) -> bool:
        probe = Lockfile(self.state, instance_id="probe", clock=self.clock)
        try:
            probe.acquire()
        except Exception:
            return False
        probe.release()
        return True


def author(repo: Path, text: str, stem: str = STEM) -> Path:
    path = repo / "tickets" / stem / "ticket.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


def ticket(**fmt) -> str:
    fmt.setdefault("verify", EXISTS)
    fmt.setdefault("frontmatter", "")
    return TICKET.format(**fmt)


def body(text: str) -> str:
    """The ticket below its frontmatter (intake stamps the frontmatter)."""
    return text.split("---\n", 2)[2]


def diagnosis(verdict="retry", *lessons: str) -> str:
    return json.dumps({"verdict": verdict, "lessons": list(lessons or ("fix the failure",)),
                       "reason": "diagnosed"})


def set_config(repo: Path, env: dict, text: str) -> None:
    (repo / "config.yaml").write_text(text)
    git(repo, env, "add", "--", "config.yaml")
    git(repo, env, "commit", "-q", "-m", "config")


# --- a non-ok terminal: journaled, exit 1, ticket and branch in place -----------------


def rejected_at_review(env):
    return Agent(answer("implemented"), review("snag", {"message": "wrong"}), diagnosis(),
                 actions=[implementer(env, WIDGET), None, None])


def red_verification(env):
    return Agent(answer("implemented"), diagnosis(), actions=[implementer(env, WIDGET), None])


def premise_failed(env):
    return Agent(answer("premise_failed", "the ticket contradicts the plan"))


@pytest.mark.parametrize("agent, verify, terminal, on_branch", [
    (rejected_at_review, EXISTS, "gate_failed", True),
    (red_verification, RED, "gate_failed", True),
    (premise_failed, EXISTS, "premise_failed", False),
], ids=["review-reject", "red-verification", "premise-failed"])
async def test_a_non_ok_terminal_journals_it_exits_1_and_leaves_ticket_and_branch_in_place(
        repo, env, agent, verify, terminal, on_branch):
    author(repo, ticket(verify=verify))
    d = Drive(repo, env, agent(env))

    rc = await d.run()

    assert rc == EXIT_TICKET
    assert terminal in TERMINAL_RUN_STATES
    transitions_ = d.transitions()
    assert transitions_[0] == {"to": "running", "run_seq": 0}
    assert {k: transitions_[1][k] for k in ("to", "run_seq", "harvest")} == {
        "to": terminal, "run_seq": 0, "harvest": f"tickets/{STEM}/attempts/0"}
    assert transitions_[1]["diagnosis"]["call"] == (
        "skipped" if terminal == "premise_failed" else "ok")
    committed = d.committed_ticket()
    events = d.events()
    lift_index, lift = next(
        (index, event) for index, event in enumerate(events)
        if event.type == "effect_completion"
        and event.key == f"lift/{STEM}/0/harvest"
        and event.body["result"]["commit"] is not None)
    terminal_index = next(
        index for index, event in enumerate(events)
        if event.type == "state_transition" and event.body.get("to") == terminal)
    assert lift_index < terminal_index, "harvest custody reaches main before the terminal"
    diagnosis_draws = [
        (index, event) for index, event in enumerate(events)
        if event.type == "cap_consumed" and event.body["cap"] == "diagnosis"]
    diagnose_effects = [
        event for event in events if event.key and "/diagnose/" in event.key]
    diagnosis_lift = next(
        index for index, event in enumerate(events)
        if event.type == "effect_completion"
        and event.key == f"lift/{STEM}/0/diagnosis")
    record = json.loads((repo / "tickets" / STEM / "diagnosis.json").read_text())
    assert record == transitions_[1]["diagnosis"]
    if terminal == "premise_failed":
        assert diagnosis_draws == [] and diagnose_effects == []
        assert diagnosis_lift < terminal_index
    else:
        assert len(diagnosis_draws) == 1
        diagnosis_draw, draw = diagnosis_draws[0]
        blob = git(repo, env, "rev-parse", f"HEAD:tickets/{STEM}/ticket.md").strip()
        assert draw.body == {"cap": "diagnosis", "ticket_sha": blob, "run_seq": 0}
        diagnosis_intent = next(
            index for index, event in enumerate(events)
            if event.type == "effect_intent"
            and event.key == f"llm/{STEM}/0/diagnose/0/1")
        diagnosis_completion = next(
            index for index, event in enumerate(events)
            if event.type == "effect_completion"
            and event.key == f"llm/{STEM}/0/diagnose/0/1")
        assert (lift_index < diagnosis_draw < diagnosis_intent < diagnosis_completion
                < diagnosis_lift < terminal_index)
        diagnose_request = next(r for r in d._llm.requests if r.surface == "diagnose")
        assert 'name="ticket" origin="host"' in diagnose_request.rendered
        assert 'name="harvest" origin="untrusted"' in diagnose_request.rendered
        assert committed in diagnose_request.rendered
        harvest = (repo / "tickets" / STEM / "attempts" / "0" / "harvest.json").read_text()
        assert harvest.replace(DATA_MARKER, "[squatch-data:") in diagnose_request.rendered
    git(repo, env, "merge-base", "--is-ancestor", lift.body["result"]["commit"], "main")
    # The ticket: as intake committed it (stamped `source`/`state`), untouched since.
    assert (repo / "tickets" / STEM / "ticket.md").read_text() == committed
    assert body(committed) == body(ticket(verify=verify))
    # The branch survives for re-entry; the dying worktree is wiped after harvest.
    assert d.branch_exists() and not d.worktree().exists()
    assert ("squatch/widget.py" in d.branch_diff_names()) is on_branch
    assert "squatch/widget.py" not in d.main_files(), "nothing non-ok reaches main"
    # The stop names the outcome and where its detail lives (Phase 1: the engine log).
    stopped = [line for line in d.lines if line.startswith("stopped:")]
    assert stopped == [f"stopped: {STEM} run 0 ended {terminal}; branch left in place; "
                       f"detail: tickets/{STEM}/attempts/0/"]
    assert d.log.path.is_file()
    assert d.lock_is_free()


async def test_a_spent_in_stage_retry_cap_is_a_named_non_ok_terminal_never_a_loop(repo, env):
    """The driver's re-prompt allowance is `caps.retry` (section 11.1): when
    it is spent the stage terminals with the cap NAMED, the runner journals
    that terminal and exits 1 -- no further call, no retry, no diagnosis."""
    set_config(repo, env, CONFIG + "caps: {retry: 1}\n")
    author(repo, ticket())
    agent = Agent("not json", "still not json", diagnosis(),
                  actions=[implementer(env, WIDGET), None, None])
    d = Drive(repo, env, agent)

    rc = await d.run()

    assert rc == EXIT_TICKET
    assert [t["to"] for t in d.transitions()] == ["running", "invalid_artifact"]
    assert d.transitions()[-1]["harvest"] == f"tickets/{STEM}/attempts/0"
    assert d.transitions()[-1]["diagnosis"]["call"] == "ok"
    assert len(agent.requests) == 3, "two implement calls plus the one diagnosis call"
    terminal = [e for e in d.log_events()
                if e["event"] == "terminal" and e["surface"] == "implement"][-1]
    assert terminal["outcome"] == "invalid_artifact"
    assert terminal["reason"] == "retry cap spent" and terminal["cap"] == "retry"
    assert d.branch_exists() and not d.worktree().exists()


@pytest.mark.parametrize("outcome", ["infra_error", "timeout"])
async def test_an_infra_terminal_draws_before_its_state_transition(repo, env, outcome):
    author(repo, ticket())
    d = Drive(repo, env, pipeline=RaisingOutcome(outcome))

    assert await d.run() == EXIT_TICKET

    events = d.events()
    draw = next(e for e in events if e.type == "cap_consumed" and e.body["cap"] == "infra")
    blob = git(repo, env, "rev-parse", f"HEAD:tickets/{STEM}/ticket.md").strip()
    assert draw.body == {"cap": "infra", "ticket_sha": blob, "run_seq": 0}
    assert {k: events[-1].body[k] for k in ("to", "run_seq", "harvest")} == {
        "to": outcome, "run_seq": 0, "harvest": None}
    assert events[-1].body["diagnosis"]["call"] == "synthetic"
    assert events.index(draw) < len(events) - 1


async def test_a_live_workspace_infra_terminal_draws_infra_then_diagnosis(repo, env):
    author(repo, ticket())
    agent = Agent(RuntimeError("provider down"), diagnosis())
    d = Drive(repo, env, agent)

    assert await d.run() == EXIT_TICKET

    events = d.events()
    infra = next(i for i, e in enumerate(events)
                 if e.type == "cap_consumed" and e.body["cap"] == "infra")
    diagnosis_draw = next(i for i, e in enumerate(events)
                          if e.type == "cap_consumed" and e.body["cap"] == "diagnosis")
    terminal = next(i for i, e in enumerate(events)
                    if e.type == "state_transition" and e.body.get("to") == "infra_error")
    assert infra < diagnosis_draw < terminal


async def test_a_spent_infra_cap_skips_diagnosis_after_the_infra_draw(repo, env):
    set_config(repo, env, CONFIG + "caps: {infra: 1}\n")
    author(repo, ticket())
    agent = Agent(RuntimeError("provider down"))
    d = Drive(repo, env, agent)

    assert await d.run() == EXIT_TICKET

    caps = [e.body["cap"] for e in d.events() if e.type == "cap_consumed"]
    assert caps == ["infra"]
    assert not any(e.key and "/diagnose/" in e.key for e in d.events())
    record = d.transitions()[-1]["diagnosis"]
    assert record["call"] == "skipped"
    assert record["detail"] == "infra cap spent (1 of 1 drawn)"
    assert len(agent.requests) == 1


async def test_an_invalid_diagnosis_reprompts_once_and_fails_closed(repo, env):
    author(repo, ticket(verify=RED))
    agent = Agent(answer("implemented"), '{"verdict":"shrug"}', "not json",
                  actions=[implementer(env, WIDGET), None, None])
    d = Drive(repo, env, agent)

    assert await d.run() == EXIT_TICKET

    diagnosis_keys = [e.key for e in d.events()
                      if e.type == "effect_intent" and e.key and "/diagnose/" in e.key]
    assert diagnosis_keys == [f"llm/{STEM}/0/diagnose/0/1",
                              f"llm/{STEM}/0/diagnose/0/2"]
    assert [e.body["cap"] for e in d.events() if e.type == "cap_consumed"].count(
        "diagnosis") == 1
    record = d.transitions()[-1]["diagnosis"]
    assert record["call"] == "invalid_artifact" and record["verdict"] is None


async def test_a_non_infra_terminal_draws_no_infra_cap(repo, env):
    author(repo, ticket())
    d = Drive(repo, env, pipeline=RaisingOutcome("gate_failed"))

    assert await d.run() == EXIT_TICKET
    assert [e for e in d.events() if e.type == "cap_consumed"] == []


async def test_setup_death_skips_harvest_and_journals_null(repo, env):
    author(repo, ticket())
    d = Drive(repo, env, Agent(), stages_type=MissingWorkspaceStages)

    assert await d.run() == EXIT_TICKET

    terminal = d.transitions()[-1]
    assert {k: terminal[k] for k in ("to", "run_seq", "harvest")} == {
        "to": "gate_failed", "run_seq": 0, "harvest": None}
    assert terminal["diagnosis"]["call"] == "synthetic"
    assert terminal["diagnosis"]["verdict"] == "abandon-human"
    events = d.events()
    assert not any(e.type == "cap_consumed" and e.body.get("cap") == "diagnosis"
                   for e in events)
    assert not any(e.key and "/diagnose/" in e.key for e in events)
    assert json.loads((repo / "tickets" / STEM / "diagnosis.json").read_text()) == \
        terminal["diagnosis"]
    assert not (repo / "tickets" / STEM / "attempts").exists()


async def test_diagnosis_cuts_an_oversized_committed_diff_at_the_exact_bound(repo, env):
    author(repo, ticket(verify=RED))
    large_widget = ("squatch/widget.py", "WIDGET = '" + "x" * (DIAG_DIFF_CHARS + 2_000) + "'\n")
    agent = Agent(answer("implemented"), diagnosis(),
                  actions=[implementer(env, large_widget), None])
    d = Drive(repo, env, agent)

    assert await d.run() == EXIT_TICKET

    uncut = git(repo, env, "diff", f"main...{STEM}")
    assert len(uncut) > DIAG_DIFF_CHARS
    request = next(r for r in agent.requests if r.surface == "diagnose").rendered
    opened = next(line for line in request.splitlines()
                  if line.startswith(DATA_MARKER + 'data name="diff" '))
    diff = request.split(opened + "\n", 1)[1].split(
        "\n" + DATA_MARKER + 'end name="diff">>>', 1)[0]
    assert len(diff) <= DIAG_DIFF_CHARS


async def test_harvest_failure_is_soft_and_the_worktree_is_still_wiped(
        repo, env, monkeypatch):
    import squatch.runner as runner_module

    async def broken(**kwargs):
        raise RuntimeError("custody unavailable")

    monkeypatch.setattr(runner_module, "extract", broken)
    author(repo, ticket(verify=RED))
    d = Drive(repo, env, Agent(answer("implemented"), diagnosis(),
                               actions=[implementer(env, WIDGET), None]))

    assert await d.run() == EXIT_TICKET

    terminal = d.transitions()[-1]
    assert terminal["harvest"] is None
    assert terminal["harvest_error"] == "RuntimeError: custody unavailable"
    assert not d.worktree().exists() and d.branch_exists()


async def test_second_problem_enqueue_failure_is_a_soft_harvest_error(repo, env, monkeypatch):
    from squatch.box import Box

    def broken(self, **kwargs):
        raise RuntimeError("box unavailable")

    monkeypatch.setattr(Box, "enqueue", broken)
    record = "".join(
        f"## {name}\n{'ok' if name == 'Outcome' else '- adjacent bug' if name == 'Second problems filed' else ''}\n"
        for name in ("Outcome", "Surprises / judgment calls", "Dead ends",
                     "Second problems filed", "Resolved engine/model", "Predicted vs actual"))
    author(repo, ticket(verify=RED))
    d = Drive(repo, env, Agent(answer("implemented"), diagnosis(),
                               actions=[implementer(env, WIDGET, record=record), None]))

    assert await d.run() == EXIT_TICKET
    terminal = d.transitions()[-1]
    assert terminal["harvest"] is None
    assert terminal["harvest_error"] == "RuntimeError: box unavailable"
    assert not d.worktree().exists()


async def test_a_non_ok_stem_stays_eligible_and_re_enters_on_a_fresh_run_sequence(repo, env):
    """Left in place is not parked forever: the next `run` takes the next
    run sequence and fresh keys (section 6), tearing the old branch down."""
    author(repo, ticket())
    d = Drive(repo, env, Agent(answer("implemented"), review("snag", {"message": "wrong"}),
                               diagnosis(), answer("implemented"), review("approve"),
                               actions=[implementer(env, WIDGET), None, None,
                                        implementer(env, WIDGET), None]))
    assert await d.run() == EXIT_TICKET
    assert await d.run() == EXIT_OK
    assert [t["to"] for t in d.transitions()] == ["running", "gate_failed", "running", "merged"]
    assert [t["run_seq"] for t in d.transitions()] == [0, 0, 1, 1]
    assert "squatch/widget.py" in d.main_files()


# --- an engine-plane refusal: exit 2, no terminal ------------------------------------


async def test_a_refusal_before_dispatch_journals_no_transition(repo, env):
    d = Drive(repo, env, Agent())
    with pytest.raises(Refusal) as info:
        await d.run("ghost")
    assert "no ticket at tickets/ghost/ticket.md" in info.value.message
    assert d.transitions("ghost") == [] and d.lock_is_free()


class Raising:
    def __init__(self, exc: Exception):
        self.exc = exc

    async def run(self, ticket, *, run_seq):
        raise self.exc

    async def diagnose(self, ticket, delivery, *, run_seq):
        raise AssertionError("a faulted run is never diagnosed")


class RaisingOutcome:
    def __init__(self, outcome: str):
        self.outcome = outcome

    async def run(self, ticket, *, run_seq):
        return Delivery(self.outcome, [], None, None, None, Path("/squatch-no-workspace"),
                        "HEAD", "implement", self.outcome,
                        Cost(tokens=0, seconds=0.0, attempts=0))

    async def diagnose(self, ticket, delivery, *, run_seq):
        detail = f"workspace missing: {delivery.worktree}"
        return DiagnosisRecord(run_seq=run_seq, outcome=delivery.outcome, call="synthetic",
                               verdict="abandon-human", lessons=(detail,), reason=detail,
                               detail=None)


class MissingWorkspaceStages(Stages):
    async def run(self, ticket, *, run_seq):
        return Delivery("gate_failed", [], None, None, None, Path("/squatch-no-workspace"),
                        "HEAD", "implement", "gate_failed",
                        Cost(tokens=0, seconds=0.0, attempts=0))


async def test_a_fault_escaping_the_stage_seam_is_a_named_refusal_with_the_orphan_named(repo, env):
    author(repo, ticket())
    d = Drive(repo, env, pipeline=Raising(RuntimeError("boom")))

    with pytest.raises(Refusal) as info:
        await d.run()

    assert info.value.message == f"{STEM} run 0 faulted: RuntimeError: boom"
    assert str(d.log.path) in info.value.paved_road
    assert "left `running` with no terminal" in info.value.paved_road
    assert f"`squatch run {STEM}`" in info.value.paved_road
    # No terminal is invented for a fault: the orphan is reconcile's to reap.
    assert d.transitions() == [{"to": "running", "run_seq": 0}]
    fault = [e for e in d.log_events() if e["event"] == "fault"]
    assert len(fault) == 1 and fault[0]["error"] == "RuntimeError"
    assert "Traceback" in fault[0]["traceback"] and "boom" in fault[0]["traceback"]
    assert d.lock_is_free()


async def test_a_verification_command_naming_a_missing_binary_is_a_gate_failed_terminal(repo, env):
    """A HOST check that crashes fails closed as a hard finding (section 7),
    so the ticket's own command naming a missing binary is a ticket outcome
    -- exit 1, the finding naming the binary -- never an engine fault."""
    author(repo, ticket(verify=f"{NO_SUCH_BINARY} --check"))
    d = Drive(repo, env, Agent(answer("implemented"), diagnosis(),
                               actions=[implementer(env, WIDGET), None]))

    rc = await d.run()

    assert rc == EXIT_TICKET
    assert [t["to"] for t in d.transitions()] == ["running", "gate_failed"]
    check = [e for e in d.log_events() if e["event"] == "check"][-1]
    assert check["passed"] is False
    assert any(NO_SUCH_BINARY in f["message"] and f["code"] == "verification"
               for f in check["findings"])
    assert d.branch_exists() and not d.worktree().exists()


async def test_a_missing_provider_binary_is_a_setup_refusal_not_an_infra_terminal(repo, env):
    """Section 11.1: an unresolvable binary at the ENGINE'S own seam is the
    config/setup refusal -- a provider `cli` binary that never resolved is
    not a call that RAN, so it draws no infra terminal."""
    from squatch.seams import ExecutableNotFound

    class Missing(Agent):
        async def call(self, req):
            raise ExecutableNotFound("claude")

    author(repo, ticket())
    d = Drive(repo, env, Missing())
    with pytest.raises(Refusal) as info:
        await d.run()
    assert info.value.message == f"{STEM} run 0: `claude` is not on PATH"
    assert "provider `cli` entry" in info.value.paved_road
    assert d.transitions() == [{"to": "running", "run_seq": 0}]


# --- the process: `python -m squatch run` exits 1 / 2, never a traceback ------------


def cli(repo: Path, env: dict, *argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "squatch", *argv], cwd=repo, env=env,
                          capture_output=True, text=True)


def test_the_process_exits_1_on_a_non_ok_terminal_and_2_on_a_refusal(repo, env):
    assert (EXIT_OK, EXIT_TICKET, EXIT_REFUSED) == (0, 1, 2)
    set_config(repo, env, UNROUTED)
    author(repo, ticket())

    proc = cli(repo, env, "run", STEM)
    assert proc.returncode == EXIT_TICKET, proc.stdout + proc.stderr
    assert f"stopped: {STEM} run 0 ended infra_error" in proc.stdout
    assert "Traceback" not in proc.stderr
    events = [e for e in read_events(repo / ".squatch/state")
              if e.type == "state_transition" and e.ticket == STEM]
    assert [e.body["to"] for e in events] == ["running", "infra_error"]
    assert body((repo / "tickets" / STEM / "ticket.md").read_text()) == body(ticket())

    proc = cli(repo, env, "run", "ghost")
    assert proc.returncode == EXIT_REFUSED
    assert proc.stdout.startswith("refused: ") and "Traceback" not in proc.stderr


def test_the_process_reports_a_fault_as_a_refusal_not_a_traceback(repo, env):
    author(repo, ticket())
    out = StringIO()
    rc = main(["run", STEM], cwd=repo, env=env, out=out,
              pipeline=lambda journal: Raising(RuntimeError("boom")))
    assert rc == EXIT_REFUSED
    assert f"\nrefused: {STEM} run 0 faulted: RuntimeError: boom\n" in out.getvalue()
    assert "paved road:" in out.getvalue() and "Traceback" not in out.getvalue()
