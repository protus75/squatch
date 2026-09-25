"""The Phase 1 CLI verbs: status, new, run <stem> (SQUATCH_PLAN.md sections 13,
18; section 19, Phase 1).

Every test drives the module entry against a temp checkout -- a real git
repo with a config, a plan, and the state dir under it -- through the real
process seam, because the verbs' claims are about git state, the lockfile,
and the journal. The stage seam behind `run` is a scripted fake: dispatch
REACHING it with the locked, validated stem is the tested behavior.
"""

import os
import subprocess
import sys
import textwrap
import tomllib
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pytest

from squatch.__main__ import main
from squatch.artifacts import Cost
from squatch.diagnose import DiagnosisRecord
from squatch.journal import read_events
from squatch.lockfile import LockHeld, Lockfile
from squatch.runner import EXIT_OK, EXIT_REFUSED, EXIT_TICKET
from squatch.stages import Delivery
from squatch.tickets import PLAN_FILE, TEMPLATE, lint_ticket

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
STATE = Path(".squatch/state")

CONFIG = textwrap.dedent(f"""\
    schema_version: 1
    state_dir: {STATE}
    providers: []
    routing: []
    """)

PLAN = textwrap.dedent("""\
    # plan

    ## 13. Ticket contract

    Contract prose.
    """)

GOOD = textwrap.dedent("""\
    ---
    priority: P1
    kind: feature
    ---
    ## Depends on
    - {depends}

    ## Context
    - squatch/existing.py

    ## Goal
    The widget parser lands.

    ## Why
    The next ticket consumes it.

    ## Scope in
    The parser module.

    ## Scope out
    The renderer.

    ## Scope fence
    - squatch/widget.py

    ## Acceptance criteria
    - `uv run pytest tests/test_widget.py` exits 0.

    ## Verification
    ```
    uv run pytest tests/test_widget.py
    ```

    ## Definition of rejected
    Stop if the parser needs a new dependency.

    ## Time budget
    - expected: 20m
    - stuck: 40m
    """)


def clock():
    return T0


def git_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
        "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test",
    }


@pytest.fixture
def checkout(tmp_path):
    """A committed host checkout: config, plan, one Context file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.yaml").write_text(CONFIG)
    (repo / PLAN_FILE).write_text(PLAN)
    (repo / "squatch").mkdir()
    (repo / "squatch" / "existing.py").write_text("")
    env = git_env(tmp_path)
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "add", "--", "config.yaml", PLAN_FILE,
                    "squatch/existing.py"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], env=env, check=True)
    return repo


def author(repo: Path, stem: str, text: str = GOOD, *, depends: str = "none") -> Path:
    path = repo / "tickets" / stem / "ticket.md"
    path.parent.mkdir(parents=True)
    path.write_text(text.format(depends=depends))
    return path


class FakePipeline:
    """The scripted stand-in for prompts 6-7's stages + merge: records what
    reached the seam and proves the lock was held at that moment."""

    def __init__(self, *outcomes: str, state_dir: Path | None = None):
        self._outcomes = list(outcomes)
        self._state_dir = state_dir
        self.calls: list[tuple[str, int]] = []
        self.lock_held_at_dispatch: list[bool] = []

    async def run(self, ticket, *, run_seq):
        self.calls.append((ticket.stem, run_seq))
        if self._state_dir is not None:
            probe = Lockfile(self._state_dir, instance_id="probe", clock=clock)
            try:
                probe.acquire()
            except LockHeld:
                self.lock_held_at_dispatch.append(True)
            else:
                probe.release()
                self.lock_held_at_dispatch.append(False)
        outcome = self._outcomes.pop(0)
        return Delivery(outcome, [], None, None, None, Path("/squatch-no-workspace"),
                        "HEAD", "implement", outcome if outcome != "ok" else None,
                        Cost(tokens=0, seconds=0.0, attempts=0))

    async def diagnose(self, ticket, delivery, *, run_seq):
        detail = f"workspace missing: {delivery.worktree}"
        return DiagnosisRecord(run_seq=run_seq, outcome=delivery.outcome, call="synthetic",
                               verdict="abandon-human", lessons=(detail,), reason=detail,
                               detail=None)


def cli(checkout: Path, *argv: str, pipeline=None) -> tuple[int, str]:
    out = StringIO()
    # The seam is a factory over the lock-held journal; a scripted fake ignores it.
    rc = main(list(argv), cwd=checkout, env=git_env(checkout.parent), out=out,
              pipeline=None if pipeline is None else (lambda journal: pipeline))
    return rc, out.getvalue()


def transitions(checkout: Path, stem: str) -> list[dict]:
    return [e.body for e in read_events(checkout / STATE)
            if e.type == "state_transition" and e.ticket == stem]


def porcelain(checkout: Path) -> list[str]:
    proc = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain"],
                          env=git_env(checkout.parent), capture_output=True, text=True, check=True)
    return proc.stdout.splitlines()


# --- module entry ------------------------------------------------------------------

def test_python_m_squatch_is_the_entry_and_help_exits_0(checkout):
    proc = subprocess.run([sys.executable, "-m", "squatch", "--help"], cwd=checkout,
                          capture_output=True, text=True)
    assert proc.returncode == 0
    assert "status" in proc.stdout and "new" in proc.stdout and "run" in proc.stdout


def test_python_m_squatch_status_runs_in_a_foreign_checkout(checkout):
    proc = subprocess.run([sys.executable, "-m", "squatch", "status"], cwd=checkout,
                          capture_output=True, text=True, env=git_env(checkout.parent))
    assert proc.returncode == 0, proc.stderr
    assert "spend:" in proc.stdout


def test_no_verb_is_a_usage_refusal(checkout):
    proc = subprocess.run([sys.executable, "-m", "squatch"], cwd=checkout,
                          capture_output=True, text=True)
    assert proc.returncode == EXIT_REFUSED


def test_project_stays_virtual_no_console_script():
    pyproject = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
    assert "scripts" not in pyproject["project"]
    assert "gui-scripts" not in pyproject["project"]


def test_missing_config_is_a_named_refusal_not_a_traceback(checkout):
    (checkout / "config.yaml").unlink()
    rc, out = cli(checkout, "status")
    assert rc == EXIT_REFUSED
    assert out.startswith("refused: config:") and "paved road:" in out


def test_config_flag_relocates_the_config_file(checkout, tmp_path):
    (checkout / "config.yaml").rename(tmp_path / "elsewhere.yaml")
    rc, out = cli(checkout, "--config", str(tmp_path / "elsewhere.yaml"), "status")
    assert rc == EXIT_OK


# --- new -----------------------------------------------------------------------------

def test_new_authors_a_lint_clean_template_and_reports_it(checkout):
    rc, out = cli(checkout, "new", "my-ticket")
    assert rc == EXIT_OK
    path = checkout / "tickets" / "my-ticket" / "ticket.md"
    assert path.read_text() == TEMPLATE
    assert "authored tickets/my-ticket/ticket.md" in out and "lint: clean" in out
    lint_ticket(path.read_text(), stem="my-ticket", repo=checkout, plan=PLAN,
                resolve_stem=lambda s: False)


def test_new_never_commits_and_never_touches_the_state_dir(checkout):
    cli(checkout, "new", "my-ticket")
    assert not (checkout / STATE).exists()
    assert porcelain(checkout) == ["?? tickets/"]


def test_new_refuses_an_existing_stem_without_overwriting(checkout):
    author(checkout, "my-ticket")
    before = (checkout / "tickets" / "my-ticket" / "ticket.md").read_text()
    rc, out = cli(checkout, "new", "my-ticket")
    assert rc == EXIT_REFUSED and "already exists" in out
    assert (checkout / "tickets" / "my-ticket" / "ticket.md").read_text() == before


@pytest.mark.parametrize("stem", ["Bad_Stem", "decisions", "retro", "x"])
def test_new_refuses_a_stem_outside_the_grammar(checkout, stem):
    rc, out = cli(checkout, "new", stem)
    assert rc == EXIT_REFUSED and "not a valid ticket stem" in out
    assert not (checkout / "tickets").exists()


# --- status --------------------------------------------------------------------------

def test_status_on_a_fresh_checkout_is_empty_and_read_only(checkout):
    rc, out = cli(checkout, "status")
    assert rc == EXIT_OK
    assert out.startswith("unparsed tickets (failed intake lint) (0)")
    assert "spend: $0.0000 over 0 metered calls" in out
    assert not (checkout / STATE).exists(), "a projection never creates state"


def test_status_names_unparsed_and_pending_tickets_before_intake(checkout):
    author(checkout, "good-one")
    author(checkout, "bad-one", GOOD.replace("kind: feature\n", ""))
    rc, out = cli(checkout, "status")
    assert rc == EXIT_OK
    head = out.split("\n", 2)
    assert head[0] == "unparsed tickets (failed intake lint) (1)"
    assert head[1].startswith("  bad-one: frontmatter key 'kind' is missing --")
    assert "pending intake (1)\n  good-one\n" in out


def test_status_projects_in_flight_ready_blocked_stopped_and_merged(checkout):
    author(checkout, "base")
    author(checkout, "dependent", depends="base")
    fake = FakePipeline("gate_failed")
    assert cli(checkout, "run", "base", pipeline=fake)[0] == EXIT_TICKET
    rc, out = cli(checkout, "status")
    assert rc == EXIT_OK
    assert "ready (1)\n  base\n" in out
    assert "blocked (1)\n  dependent: waiting on base\n" in out
    assert "stopped (1)\n  base: gate_failed\n" in out
    assert "intake (2)\n  base: human, confirmed," in out

    # The settle record is the `to: merged` transition; nothing else moves a
    # stem to merged, and a settled dependency unblocks its dependent.
    from squatch.journal import Journal
    with Journal(checkout / STATE, clock=clock) as journal:
        journal.append("state_transition", {"to": "running", "run_seq": 1}, ticket="base")
        journal.append("state_transition", {"to": "merged", "run_seq": 1}, ticket="base")
        journal.append("state_transition", {"to": "running", "run_seq": 0}, ticket="dependent")
        journal.append("effect_completion", {"result": {}, "cost": {"usd": 0.25}},
                       ticket="dependent", key="llm/dependent/0/implement/1/1")
    rc, out = cli(checkout, "status")
    assert "merged (1)\n  base\n" in out
    assert "in flight (1)\n  dependent (run 0)\n" in out
    assert "blocked (0)" in out and "ready (0)" in out
    assert "spend: $0.2500 over 1 metered calls" in out


# --- run -----------------------------------------------------------------------------

def test_run_is_refused_when_the_lockfile_is_already_held(checkout):
    author(checkout, "base")
    fake = FakePipeline("ok")
    holder = Lockfile(checkout / STATE, instance_id="other-daemon", clock=clock)
    holder.acquire()
    try:
        rc, out = cli(checkout, "run", "base", pipeline=fake)
    finally:
        holder.release()
    assert rc == EXIT_REFUSED
    assert out.startswith("refused: ") and "other-daemon" in out and "paved road:" in out
    assert fake.calls == [], "nothing dispatches without the lock"
    assert list(read_events(checkout / STATE)) == [], "nothing journals without the lock"
    assert "?? tickets/" in porcelain(checkout), "intake commits are lock-fenced too"


def test_run_dispatches_the_locked_validated_stem_to_the_stage_seam(checkout):
    author(checkout, "base")
    fake = FakePipeline("ok", state_dir=checkout / STATE)
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("base", 0)]
    assert fake.lock_held_at_dispatch == [True]
    # Validated = intake committed it through the ticket-plane lane first.
    assert not any(line.endswith("tickets/") for line in porcelain(checkout))
    assert "intake: committed base (human, confirmed)" in out
    assert transitions(checkout, "base") == [{"to": "running", "run_seq": 0}]
    assert "settled: base run 0 ended ok" in out
    # The lock is released on the way out.
    Lockfile(checkout / STATE, instance_id="after", clock=clock).acquire()


def test_run_non_ok_terminal_journals_it_exits_1_and_the_next_run_takes_a_fresh_seq(checkout):
    author(checkout, "base")
    fake = FakePipeline("gate_failed", "ok")
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_TICKET
    assert "stopped: base run 0 ended gate_failed" in out
    assert (checkout / "tickets" / "base" / "ticket.md").is_file()
    transition = transitions(checkout, "base")
    assert transition[0] == {"to": "running", "run_seq": 0}
    assert {k: transition[1][k] for k in ("to", "run_seq", "harvest")} == {
        "to": "gate_failed", "run_seq": 0, "harvest": None}
    assert transition[1]["diagnosis"]["call"] == "synthetic"
    rc, _ = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK
    assert fake.calls == [("base", 0), ("base", 1)]


def test_run_refuses_an_unknown_stem_naming_new(checkout):
    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "ghost", pipeline=fake)
    assert rc == EXIT_REFUSED
    assert "no ticket at tickets/ghost/ticket.md" in out and "squatch new ghost" in out
    assert fake.calls == []


def test_run_refuses_a_stem_intake_refused_with_its_findings(checkout):
    author(checkout, "bad-one", GOOD.replace("kind: feature\n", ""))
    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "bad-one", pipeline=fake)
    assert rc == EXIT_REFUSED
    assert "intake: refused bad-one" in out
    assert "refused: bad-one was refused at intake: frontmatter key 'kind' is missing" in out
    assert fake.calls == [] and transitions(checkout, "bad-one") == []


def test_run_refuses_a_stem_with_unmerged_depends(checkout):
    author(checkout, "base")
    author(checkout, "dependent", depends="base")
    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "dependent", pipeline=fake)
    assert rc == EXIT_REFUSED
    assert "dependent depends on unmerged base" in out
    assert fake.calls == []


def test_run_refuses_a_merged_stem(checkout):
    author(checkout, "base")
    fake = FakePipeline("ok")
    assert cli(checkout, "run", "base", pipeline=fake)[0] == EXIT_OK
    from squatch.journal import Journal
    with Journal(checkout / STATE, clock=clock) as journal:
        journal.append("state_transition", {"to": "merged", "run_seq": 0}, ticket="base")
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_REFUSED and "base is already merged" in out
    assert fake.calls == [("base", 0)]


def test_run_refuses_a_seam_result_outside_the_outcome_vocabulary(checkout):
    author(checkout, "base")
    rc, out = cli(checkout, "run", "base", pipeline=FakePipeline("shrug"))
    assert rc == EXIT_REFUSED and "not an Outcome" in out


def test_production_run_dispatches_through_the_real_pipeline(checkout):
    """No scripted stand-in: `run` composes the stages + merge admission over
    the lock-held journal. This checkout routes no provider, so Implement's
    call is an infra_error -- a ticket outcome (exit 1), never a refusal."""
    author(checkout, "base")
    rc, out = cli(checkout, "run", "base")
    assert rc == EXIT_TICKET, out
    assert "stopped: base run 0 ended infra_error" in out
    assert [t["to"] for t in transitions(checkout, "base")] == ["running", "infra_error"]
