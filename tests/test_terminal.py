"""Non-ok terminal handling (SQUATCH_PLAN.md section 11; section 18's exit-code
contract; section 19, Phase 1).

A non-ok terminal -- a spent cap or any non-ok terminal state -- journals its
state transition and exits 1, leaving the ticket and the branch in place and
naming where its detail lives (the engine log, before harvest exists). An
engine-plane refusal exits 2 and journals no terminal. A FAULT escaping the
stage seam is a named stop, never a traceback: exit 2, the traceback in the
engine log, and the interrupted run left `running` with no terminal for
reconcile-on-entry to reap. No retry, diagnosis, or harvest here: those are
the Phase 2 spine.

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
from squatch.artifacts import TERMINAL_RUN_STATES
from squatch.config import load
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
from squatch.stages import Stages

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

    def __init__(self, repo: Path, env: dict, llm=None, *, pipeline=None):
        self.repo, self.env = repo, env
        self.config = load(None, cwd=repo)
        self.state = repo / self.config.state_dir
        self.clock = TickingClock()
        self.git = Git(SubprocessExec(), env=env, timeout=60.0)
        self.redact = Redactor.from_config(self.config, env)
        self.log = EngineLog(self.state, clock=self.clock, redact=self.redact)
        self.lines: list[str] = []
        self._llm, self._pipeline = llm, pipeline

    def _factory(self, journal):
        if self._pipeline is not None:
            return self._pipeline
        stages = Stages(repo=self.repo, config=self.config, git=self.git, process=SubprocessExec(),
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


def set_config(repo: Path, env: dict, text: str) -> None:
    (repo / "config.yaml").write_text(text)
    git(repo, env, "add", "--", "config.yaml")
    git(repo, env, "commit", "-q", "-m", "config")


# --- a non-ok terminal: journaled, exit 1, ticket and branch in place -----------------


def rejected_at_review(env):
    return Agent(answer("implemented"), review("snag", {"message": "wrong"}),
                 actions=[implementer(env, WIDGET)])


def red_verification(env):
    return Agent(answer("implemented"), actions=[implementer(env, WIDGET)])


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
    assert d.transitions() == [{"to": "running", "run_seq": 0}, {"to": terminal, "run_seq": 0}]
    # The ticket: as intake committed it (stamped `source`/`state`), untouched since.
    committed = d.committed_ticket()
    assert (repo / "tickets" / STEM / "ticket.md").read_text() == committed
    assert body(committed) == body(ticket(verify=verify))
    # The branch and its worktree: left in place, the work still on them.
    assert d.branch_exists() and d.worktree().is_dir()
    assert ("squatch/widget.py" in d.branch_diff_names()) is on_branch
    assert "squatch/widget.py" not in d.main_files(), "nothing non-ok reaches main"
    # The stop names the outcome and where its detail lives (Phase 1: the engine log).
    stopped = [line for line in d.lines if line.startswith("stopped:")]
    assert stopped == [f"stopped: {STEM} run 0 ended {terminal}; ticket and branch left in "
                       f"place; detail: {d.log.path}"]
    assert d.log.path.is_file()
    assert d.lock_is_free()


async def test_a_spent_in_stage_retry_cap_is_a_named_non_ok_terminal_never_a_loop(repo, env):
    """The driver's re-prompt allowance is `caps.retry` (section 11.1): when
    it is spent the stage terminals with the cap NAMED, the runner journals
    that terminal and exits 1 -- no further call, no retry, no diagnosis."""
    set_config(repo, env, CONFIG + "caps: {retry: 1}\n")
    author(repo, ticket())
    agent = Agent("not json", "still not json", actions=[implementer(env, WIDGET), None])
    d = Drive(repo, env, agent)

    rc = await d.run()

    assert rc == EXIT_TICKET
    assert d.transitions() == [{"to": "running", "run_seq": 0},
                               {"to": "invalid_artifact", "run_seq": 0}]
    assert len(agent.requests) == 2, "the cap bounds the calls: one allowance, then terminal"
    terminal = [e for e in d.log_events() if e["event"] == "terminal"][-1]
    assert terminal["outcome"] == "invalid_artifact"
    assert terminal["reason"] == "retry cap spent" and terminal["cap"] == "retry"
    assert d.branch_exists() and d.worktree().is_dir()


async def test_a_non_ok_stem_stays_eligible_and_re_enters_on_a_fresh_run_sequence(repo, env):
    """Left in place is not parked forever: the next `run` takes the next
    run sequence and fresh keys (section 6), tearing the old branch down."""
    author(repo, ticket())
    d = Drive(repo, env, Agent(answer("implemented"), review("snag", {"message": "wrong"}),
                               answer("implemented"), review("approve"),
                               actions=[implementer(env, WIDGET), None,
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
    d = Drive(repo, env, Agent(answer("implemented"), actions=[implementer(env, WIDGET)]))

    rc = await d.run()

    assert rc == EXIT_TICKET
    assert [t["to"] for t in d.transitions()] == ["running", "gate_failed"]
    check = [e for e in d.log_events() if e["event"] == "check"][-1]
    assert check["passed"] is False
    assert any(NO_SUCH_BINARY in f["message"] and f["code"] == "verification"
               for f in check["findings"])
    assert d.branch_exists() and d.worktree().is_dir()


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
    rc = main(["run", STEM], cwd=repo, env=env, out=out, pipeline=Raising(RuntimeError("boom")))
    assert rc == EXIT_REFUSED
    assert f"\nrefused: {STEM} run 0 faulted: RuntimeError: boom\n" in out.getvalue()
    assert "paved road:" in out.getvalue() and "Traceback" not in out.getvalue()
