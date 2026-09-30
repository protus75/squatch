"""stages.py: the Implement, Check, and Review stages and their transitions
(SQUATCH_PLAN.md sections 4, 5, 7, 9, 10; section 19, Phase 1).

Every test drives `Stages.run` against a real temp checkout through the real
process seam -- the claims are about a worktree, a branch, ticket-plane
commits on main, and the journal -- with the scripted fake standing in for
the model: an `Agent` acts in the granted worktree (writes, commits) before
each scripted reply, exactly as an agent CLI would. Review wires the
committed `specs/review.md`; Implement renders `specs/implement.md`.
"""

import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from squatch import specs as specs_module
from squatch import stages as stages_module
from squatch.artifacts import REVIEW_BASELINE_REPORT, Finding, ReviewBaselineReport
from squatch.box import Box
from squatch.config import load
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.harvest import HARVEST_FILE, Harvest, HarvestCost
from squatch.journal import Journal
from squatch.llm import FakeLLM
from squatch.llmeffect import LLMEffect
from squatch.redact import Redactor
from squatch.providers import ProviderRuntime, Registry
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.shakeout import REPORT_NAME, ShakeoutReport
from squatch.specs import RenderRefused, load_spec
from squatch.stages import (
    CHECK_CODES,
    RUN_RECORD_SECTIONS,
    SPECS_DIR,
    ApprovedInvoice,
    Invoice,
    PackingSlip,
    RMA,
    SnagList,
    Stages,
    Verification,
    build_invoice,
    compose,
    load_review,
)
from squatch.tickets import PLAN_FILE, Intake, Ticket, lint_ticket
from squatch.timers import Timers

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)
STATE = Path(".squatch/state")
STEM = "widget-module"
KEY_NAME = "FAKE_PROVIDER_KEY"
PYTHON = sys.executable

CONFIG = textwrap.dedent(f"""\
    schema_version: 1
    state_dir: {STATE}
    providers:
      - name: claude
        kind: cli
        auth: {KEY_NAME}
        models_by_tier: {{low: a, medium: b, high: c, max: d}}
        limits: {{concurrency: 1}}
    routing:
      - {{tier: medium, surface: implement, candidates: [{{provider: claude}}]}}
      - {{tier: medium, surface: review, candidates: [{{provider: claude}}]}}
    """)

PLAN = textwrap.dedent("""\
    # plan

    ## 13. Ticket contract

    Contract prose.
    """)

EXISTS = (f'{PYTHON} -c "import pathlib, sys; '
          f"sys.exit(0 if pathlib.Path('squatch/widget.py').exists() else 1)\"")

TICKET = textwrap.dedent("""\
    ---
    priority: P1
    kind: feature
    {frontmatter}
    ---
    ## Depends on
    - none

    ## Context
    - squatch/existing.py

    ## Plan contract
    - section 13

    ## Goal
    The widget module lands.

    ## Why
    The next ticket consumes it.

    ## Scope in
    The widget module.

    ## Scope out
    The renderer.

    ## Scope fence
    - squatch/widget.py

    ## Acceptance criteria
    - `squatch/widget.py` exists after merge.

    ## Verification
    ```
    {verify}
    ```

    ## Definition of rejected
    Stop if the widget needs a new dependency.

    ## Time budget
    - expected: 20m
    - stuck: 40m
    """)


class TickingClock:
    def __init__(self, start=T0):
        self.now = start

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


def git_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
        "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test",
    }


def git(repo: Path, env: dict, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], env=env, capture_output=True,
                          text=True, check=True)
    return proc.stdout


def run_record(outcome: str = "ok") -> str:
    return "".join(f"## {name}\n{outcome if name == 'Outcome' else ''}\n"
                   for name in RUN_RECORD_SECTIONS)


def answer(verdict: str, summary: str = "done") -> str:
    return json.dumps({"verdict": verdict, "summary": summary})


def review(verdict: str, *findings: dict) -> str:
    return json.dumps({"verdict": verdict, "summary": f"reviewed: {verdict}",
                       "findings": [{"code": "correctness_review", "path": None, "line": None,
                                     "paved_road": "fix it", **f} for f in findings]})


class Agent(FakeLLM):
    """The scripted implementer: an action runs against the granted worktree
    before each scripted reply, like an agent CLI mutating its tree."""

    def __init__(self, *script, actions=()):
        super().__init__(*script)
        self.actions = list(actions)

    async def call(self, req):
        if self.actions:
            action = self.actions.pop(0)
            if action is not None:
                action(req)
        return await super().call(req)


@pytest.fixture
def env(tmp_path):
    return git_env(tmp_path)


@pytest.fixture
def repo(tmp_path, env):
    """A committed host checkout: config, plan, one Context file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.yaml").write_text(CONFIG)
    (repo / PLAN_FILE).write_text(PLAN)
    (repo / "squatch").mkdir()
    (repo / "squatch" / "existing.py").write_text("EXISTING = 1\n")
    git(repo, env, "init", "-q", "-b", "main")
    git(repo, env, "add", "--", "config.yaml", PLAN_FILE, "squatch/existing.py")
    git(repo, env, "commit", "-q", "-m", "seed")
    return repo


class Harness:
    def __init__(self, repo: Path, env: dict, llm: FakeLLM):
        self.repo = repo
        self.env = env
        self.llm = llm
        self.config = load(None, cwd=repo)
        self.state = repo / self.config.state_dir
        self.clock = TickingClock()
        self.git = Git(SubprocessExec(), env=env, timeout=60.0)
        self.journal = Journal(self.state, clock=self.clock)
        redact = Redactor.from_config(self.config, env)
        self.stages = Stages(
            repo=repo, config=self.config, git=self.git, process=SubprocessExec(),
            fs=LocalFilesystem(),
            llm=LLMEffect(llm=llm, effects=Effects(self.journal), redact=redact),
            log=EngineLog(self.state, clock=self.clock, redact=redact), redact=redact,
            clock=self.clock, env=env)

    async def intake(self, text: str):
        path = self.repo / "tickets" / STEM / "ticket.md"
        if not path.exists():  # a committed ticket is the plane's; never re-authored here
            path.parent.mkdir(parents=True)
            path.write_text(text)
        result = await Intake(repo=self.repo, git=self.git, journal=self.journal,
                              fs=LocalFilesystem()).run()
        assert result.refused == (), result.refused
        return lint_ticket(path.read_text(), stem=STEM, repo=self.repo, plan=PLAN,
                           resolve_stem=lambda s: False)

    async def run(self, text: str = None, *, run_seq: int = 0, **fmt):
        fmt.setdefault("verify", EXISTS)
        fmt.setdefault("frontmatter", "")
        ticket = await self.intake(text if text is not None else TICKET.format(**fmt))
        return await self.stages.run(ticket, run_seq=run_seq)

    def worktree(self) -> Path:
        return self.repo / self.config.worktree_root / STEM

    def subjects(self) -> list[str]:
        return git(self.repo, self.env, "log", "--format=%s", "main").splitlines()

    def main_files(self) -> list[str]:
        return git(self.repo, self.env, "ls-tree", "-r", "--name-only", "main").splitlines()

    def branch_diff_names(self) -> list[str]:
        return git(self.repo, self.env, "diff", "--name-only", f"main...{STEM}").splitlines()

    def completions(self) -> list[str]:
        return [e.key for e in self.journal.read() if e.type == "effect_completion"]

    def prompts(self) -> list[str]:
        return [r.rendered for r in self.llm.requests]


def commit(env: dict):
    """An action: commit every change in the worktree (explicit paths)."""
    def act(req):
        wt = req.worktree
        names = git(wt, env, "status", "--porcelain").splitlines()
        paths = [line[3:] for line in names if not line[3:].startswith("tickets/")]
        git(wt, env, "add", "--", *paths)
        git(wt, env, "commit", "-q", "-m", "implement")
    return act


def writes(*files: tuple[str, str], record: str | None = run_record()):
    """An action: write files (and the run record) into the worktree."""
    def act(req):
        wt = req.worktree
        for rel, content in files:
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        if record is not None:
            out = wt / "tickets" / STEM / "run.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(record)
    return act


def implementer(env: dict, *files: tuple[str, str], record=run_record()):
    both = (writes(*files, record=record), commit(env))

    def act(req):
        for a in both:
            a(req)
    return act


WIDGET = ("squatch/widget.py", "WIDGET = 1\n")
OUTPUT = (f"tickets/{STEM}/evidence/{REPORT_NAME}", ShakeoutReport(
    schema_version=1, produced_at_sha="fixture", groups=(), entries=()).model_dump_json())
GREEN = f'{PYTHON} -c "pass"'


@pytest.mark.parametrize("tracked", [False, True])
async def test_empty_code_delivery_requires_a_report_produced_in_this_run(repo, env, tracked):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                actions=[writes(OUTPUT)]))
    await h.intake(TICKET.format(verify=GREEN, frontmatter=""))
    if tracked:
        path = repo / OUTPUT[0]
        path.parent.mkdir(parents=True)
        path.write_text(OUTPUT[1].replace("fixture", "earlier"))
        await h.git.add(repo, [OUTPUT[0]])
        await h.git.commit(repo, "earlier report", [OUTPUT[0]])
    d = await h.run(verify=GREEN)
    assert d.outcome == "ok", d.findings
    assert d.invoice.changed_files == () and h.branch_diff_names() == []
    assert (repo / OUTPUT[0]).read_text() == OUTPUT[1]
    assert len(h.llm.requests) == 2
    checked = next(e.body["result"] for e in h.journal.read()
                   if e.key == f"check/{STEM}/0" and e.type == "effect_completion")
    assert checked["output_paths"] == [OUTPUT[0]]
    replay = await h.stages.run(await h.intake(TICKET.format(verify=GREEN, frontmatter="")),
                                run_seq=0)
    assert replay.outcome == "ok" and len(h.llm.requests) == 2


async def test_unchanged_report_from_an_earlier_run_does_not_admit_a_noop(repo, env):
    h = Harness(repo, env, Agent(answer("implemented")))
    await h.intake(TICKET.format(verify=GREEN, frontmatter=""))
    path = repo / OUTPUT[0]
    path.parent.mkdir(parents=True)
    path.write_text(OUTPUT[1])
    record = f"tickets/{STEM}/run.md"
    (repo / record).write_text(run_record())
    await h.git.add(repo, [OUTPUT[0], record])
    await h.git.commit(repo, "earlier report", [OUTPUT[0], record])

    d = await h.run(verify=GREEN)

    lift = next(e.body["result"] for e in h.journal.read()
                if e.key == f"lift/{STEM}/0/run-record" and e.type == "effect_completion")
    assert OUTPUT[0] in lift["paths"]
    assert lift["commit"] is None
    assert d.outcome == "gate_failed"
    assert any("no committed diff" in f.message for f in d.findings)


@pytest.mark.parametrize("evidence", ["missing", "intent", "signal", "stale", "foreign",
                                     "foreign-path", "run-record", "unknown"])
async def test_empty_diff_requires_a_matching_completed_registered_lift(
        repo, env, monkeypatch, evidence):
    h = Harness(repo, env, Agent(answer("implemented"), actions=[writes(OUTPUT)]))
    original = h.stages._lift

    async def lift(stem, run_seq, kind, **kwargs):
        if kind != "run-record":
            return await original(stem, run_seq, kind, **kwargs)
        key = f"lift/{stem}/{run_seq}/run-record"
        paths = [OUTPUT[0]]
        if evidence == "missing":
            return {}
        if evidence == "intent":
            h.journal.append("effect_intent", {}, ticket=stem, key=key)
            return {}
        if evidence == "signal":
            h.journal.append("signal", {"kind": "output_lift", "paths": paths,
                                        "run_seq": run_seq}, ticket=stem)
            return {}
        if evidence == "stale":
            key = f"lift/{stem}/{run_seq + 1}/run-record"
        if evidence == "foreign":
            stem = "other"
        if evidence == "foreign-path":
            paths = [OUTPUT[0].replace(STEM, "other")]
        if evidence == "run-record":
            paths = [f"tickets/{stem}/run.md", f"tickets/{stem}/checks.json"]
        if evidence == "unknown":
            paths = [f"tickets/{stem}/unknown.json"]
        h.journal.append("effect_completion", {"result": {"paths": paths, "commit": None}},
                         ticket=stem, key=key)
        return {}

    monkeypatch.setattr(h.stages, "_lift", lift)
    d = await h.run(verify=GREEN)
    assert d.outcome == "gate_failed"
    assert any("no committed diff" in f.message for f in d.findings)
    assert len(h.llm.requests) == 1


@pytest.mark.parametrize("extra", ["code", "foreign-outbox", "rename", "ordinary", "unknown"])
async def test_output_admission_preserves_empty_diff_and_dirty_code_refusals(repo, env, extra):
    def act(req):
        writes(*(() if extra in ("ordinary", "unknown") else (OUTPUT,)))(req)
        if extra == "code":
            writes(WIDGET)(req)
        elif extra == "foreign-outbox":
            writes(("tickets/other/note.txt", "foreign"))(req)
        elif extra == "rename":
            source = req.worktree / "squatch/existing.py"
            destination = f"tickets/{STEM}/existing.py"
            source.rename(req.worktree / destination)
            git(req.worktree, env, "add", "--", "squatch/existing.py", destination)
            assert " -> " in git(req.worktree, env, "status", "--porcelain")
        elif extra == "unknown":
            writes((f"tickets/{STEM}/unknown.json", "{}"))(req)

    h = Harness(repo, env, Agent(answer("implemented"), actions=[act]))
    d = await h.run(verify=GREEN)
    assert d.outcome == "gate_failed"
    assert any("no committed diff" in f.message for f in d.findings)


@pytest.mark.parametrize("invalid", [False, True])
async def test_output_admission_keeps_schema_validation_and_verification(repo, env, invalid):
    h = Harness(repo, env, Agent(answer("implemented"),
                                actions=[writes((OUTPUT[0], "{}") if invalid else OUTPUT)]))
    d = await h.run(verify=f'{PYTHON} -c "exit(7)"')
    if invalid:
        assert d.outcome == "invalid_artifact"
        assert OUTPUT[0] not in h.main_files()
    else:
        assert d.outcome == "gate_failed"
        assert any("exit 7" in f.message for f in d.findings)


# --- the happy path: Implement -> Check -> Review, full artifacts + provenance -----


async def test_delivers_ok_with_every_artifact_lifted_committed_and_stamped(repo, env):
    agent = Agent(answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    base = git(repo, env, "rev-parse", "main").strip()

    d = await h.run()

    assert d.outcome == "ok" and d.findings == []
    head = git(repo, env, "rev-parse", STEM).strip()
    # The packing slip: the branch plus the run record, stamped at the branch head.
    assert isinstance(d.slip, PackingSlip)
    assert (d.slip.stem, d.slip.verdict, d.slip.branch) == (STEM, "implemented", STEM)
    assert d.slip.head == head and d.slip.head != d.slip.base
    assert d.slip.produced_at_sha == head and d.slip.produced_by_spec_version == "1.1"
    assert d.slip.base == git(repo, env, "rev-parse", "main~3").strip()
    assert d.slip.base != base, "the ticket-plane intake commit moved main before the branch"
    # The invoice: every Check gate passed, persisted as checks.json on main.
    assert isinstance(d.invoice, Invoice) and d.invoice.passed
    assert tuple(c.code for c in d.invoice.checks) == CHECK_CODES
    assert all(c.verdict == "pass" and not c.bypassed for c in d.invoice.checks)
    assert d.invoice.changed_files == ("squatch/widget.py",)
    assert d.invoice.produced_at_sha == head
    on_disk = Invoice.model_validate_json((repo / "tickets" / STEM / "checks.json").read_text())
    assert on_disk == d.invoice
    # The review: the approve branch of emits_by_verdict, pinned to the reviewed SHA.
    assert isinstance(d.review, ApprovedInvoice)
    assert (d.review.reviewed_sha, d.review.produced_at_sha) == (head, head)
    assert (d.review.provider, d.review.model) == ("fake", "fake-1")
    assert d.review.produced_by_spec_version == "1.0"
    review_md = load_review((repo / "tickets" / STEM / "review.md").read_text())
    assert review_md["verdict"] == "approve" and review_md["reviewed_sha"] == head
    # The run record was lifted from the worktree outbox into the canonical dir.
    assert (repo / "tickets" / STEM / "run.md").read_text() == run_record()
    # One ticket-plane commit per stage terminal, in order, no code on main.
    assert h.subjects() == [f"squatch({STEM}): review", f"squatch({STEM}): checks",
                            f"squatch({STEM}): run-record", f"squatch({STEM}): ticket", "seed"]
    assert "squatch/widget.py" not in h.main_files()
    # The branch carries code only; the outbox never rides it.
    assert h.branch_diff_names() == ["squatch/widget.py"]
    assert d.worktree == h.worktree() and d.worktree.is_dir()


async def test_outbox_lift_carries_nested_evidence_and_never_ticket_md(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(
        env, WIDGET, (f"tickets/{STEM}/evidence/trace.txt", "trace\n"))])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "ok"
    assert (repo / "tickets" / STEM / "evidence" / "trace.txt").read_text() == "trace\n"
    lifted = git(repo, env, "show", "--format=", "--name-only", f"main~2").splitlines()
    assert lifted == [f"tickets/{STEM}/evidence/trace.txt", f"tickets/{STEM}/run.md"]
    assert git(repo, env, "status", "--porcelain", "--", "tickets/") == ""
    assert h.branch_diff_names() == ["squatch/widget.py"]


async def test_every_external_action_is_a_run_scoped_effect(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    await h.run()
    assert h.completions() == [
        f"worktree/{STEM}/0",
        f"llm/{STEM}/0/implement/0/1",
        f"lift/{STEM}/0/run-record",
        f"check/{STEM}/0",
        f"lift/{STEM}/0/checks",
        f"llm/{STEM}/0/review/0/1",
        f"lift/{STEM}/0/review",
    ]
    lifts = [e for e in h.journal.read() if e.type == "effect_completion"
             and e.key.startswith("lift/")]
    for e in lifts:
        assert e.ticket == STEM and e.body["result"]["commit"]
    assert lifts[0].body["result"]["paths"] == [f"tickets/{STEM}/run.md"]


async def test_implement_writes_the_worktree_and_review_reads_a_separate_session(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    await h.run(frontmatter="agent_tier: high\nagent_effort: low")
    implement, rev = agent.requests
    assert implement.surface == "implement" and implement.worktree == h.worktree()
    assert rev.surface == "review" and rev.worktree is None
    # Every surface invoked FOR a ticket resolves at the ticket's capability.
    assert (implement.tier, implement.effort) == ("high", "low")
    assert (rev.tier, rev.effort) == ("high", "low")
    assert implement.ticket == rev.ticket == STEM


async def test_implement_prompt_renders_the_spec_over_ticket_context_and_plan(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    await h.run()
    prompt = h.prompts()[0]
    assert prompt.startswith("squatch prompt: surface=implement spec_version=1.1\n")
    assert '<<<squatch:data name="workspace" origin="engine"' in prompt
    assert f"run record: tickets/{STEM}/run.md" in prompt
    assert '<<<squatch:data name="ticket" origin="host"' in prompt
    assert "The widget module lands." in prompt
    assert '<<<squatch:data name="context" origin="host"' in prompt
    assert "squatch/existing.py" in prompt and "EXISTING = 1" in prompt
    assert '<<<squatch:data name="plan_contract" origin="engine"' in prompt
    assert "Contract prose." in prompt


async def test_review_wires_the_committed_review_spec_unchanged(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    await h.run()
    spec = load_spec(SPECS_DIR / "review.md")
    # The baselined identity is the spec's MAJOR version; a rewrite here
    # would silently drift the recorded baseline.
    assert spec.version.split(".")[0] == "1"
    assert spec.slots == ("ticket", "diff", "check_report")
    prompt = h.prompts()[1]
    assert prompt.startswith(f"squatch prompt: surface=review spec_version={spec.version}\n")
    assert '<<<squatch:data name="ticket" origin="host"' in prompt
    assert '<<<squatch:data name="diff" origin="untrusted"' in prompt
    assert "+WIDGET = 1" in prompt
    assert '<<<squatch:data name="check_report" origin="engine"' in prompt
    assert '"code": "verification"' in prompt
    assert "Contract prose." not in prompt, "review renders exactly the spec's three slots"


# --- Check: the four mechanical gates, fail-closed ---------------------------------


async def test_out_of_fence_edit_fails_the_scope_fence_gate(repo, env):
    agent = Agent(answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET, ("squatch/other.py", "x = 1\n"))])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "scope_fence"]
    assert f.path == "squatch/other.py" and f.paved_road
    assert d.invoice is not None and not d.invoice.passed
    assert d.review is None and len(agent.requests) == 1, "a red Check never reaches Review"
    # The failing invoice is durable: the re-entry's senior source.
    assert (repo / "tickets" / STEM / "checks.json").is_file()
    assert h.subjects()[0] == f"squatch({STEM}): checks"
    # Ticket and branch stay in place for the operator.
    assert h.worktree().is_dir() and git(repo, env, "rev-parse", "--verify", STEM)


async def test_ticket_md_is_never_the_agents_to_edit(repo, env):
    def edit_ticket(req):
        path = req.worktree / "tickets" / STEM / "ticket.md"
        path.write_text(path.read_text() + "\n")
    agent = Agent(answer("implemented"),
                  actions=[lambda req: (writes(WIDGET)(req), edit_ticket(req),
                                        git(req.worktree, env, "add", "-A"),
                                        git(req.worktree, env, "commit", "-q", "-m", "x"))])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "gate_failed"
    assert [f.path for f in d.findings if f.code == "scope_fence"] == [f"tickets/{STEM}/ticket.md"]


async def test_red_verification_fails_the_check(repo, env):
    agent = Agent(answer("implemented"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    verify = (f'{PYTHON} -c "import pathlib, sys; '
              f'sys.exit(3 if pathlib.Path(\'squatch/widget.py\').exists() else 0)"')
    d = await h.run(verify=verify)
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "verification"]
    assert "exit 3" in f.message and "sys.exit(3 if" in f.message
    check = next(c for c in d.invoice.checks if c.code == "verification")
    [command] = check.commands
    assert command.attribution == "branch" and command.filed is None
    assert not list((repo / h.config.worktree_root).glob(f"{STEM}-base-*"))
    assert f"{STEM}-base-" not in git(repo, env, "worktree", "list")


async def test_an_uncommitted_edit_is_an_empty_diff_and_fails_verification(repo, env):
    agent = Agent(answer("implemented"), actions=[writes(WIDGET)])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "verification"]
    assert "no committed diff" in f.message and "commit" in f.paved_road
    assert h.branch_diff_names() == []


async def test_verification_runs_in_the_worktree_without_any_provider_key(repo, env):
    verify = (f'{PYTHON} -c "import os, sys; '
              f"sys.exit(1 if '{KEY_NAME}' in os.environ or 'HOME' not in os.environ else 0)\"")
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, {**env, KEY_NAME: "sk-secret"}, agent)
    d = await h.run(verify=verify)
    assert d.outcome == "ok", d.findings


SECRET = "sk-super-secret-value"
TOKEN = f"[REDACTED:{KEY_NAME}]"


async def test_red_verification_output_is_redacted_in_findings_checks_json_and_journal(repo, env):
    """The config-to-writer path end to end (section 6): a red command that
    echoes a host file holding the configured value persists only the token."""
    verify = (f'{PYTHON} -c "import pathlib, sys; '
              f"p=pathlib.Path('.env'); sys.stderr.write(p.read_text() if p.exists() else ''); "
              f"sys.exit(1 if p.exists() else 0)\"")
    agent = Agent(answer("implemented"),
                  actions=[implementer(env, WIDGET, (".env", f"{KEY_NAME}={SECRET}\n"))])
    h = Harness(repo, {**env, KEY_NAME: SECRET}, agent)
    d = await h.run(verify=verify)
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "verification"]
    assert TOKEN in f.message and SECRET not in f.message
    checks = (repo / "tickets" / STEM / "checks.json").read_text()
    assert TOKEN in checks and SECRET not in checks
    assert f"tickets/{STEM}/checks.json" in h.main_files()
    assert SECRET not in git(repo, env, "show", f"main:tickets/{STEM}/checks.json")
    [completion] = [e for e in h.journal.read()
                    if e.type == "effect_completion" and e.key == f"check/{STEM}/0"]
    body = json.dumps(completion.body)
    assert TOKEN in body and SECRET not in body


class AttributionGit:
    def __init__(self, *, names=("squatch/widget.py",), refuse=False,
                 refusal_stderr="refused"):
        self.names = list(names)
        self.refuse = refuse
        self.refusal_stderr = refusal_stderr
        self.added: list[Path] = []
        self.removed: list[Path] = []

    async def diff_names(self, repo, base, branch):
        return self.names

    async def worktree_add_detached(self, repo, path, commit):
        if self.refuse:
            argv = ["git", "worktree", "add", "--detach", str(path), commit]
            raise GitError(argv, 128, "", self.refusal_stderr)
        self.added.append(path)

    async def worktree_remove(self, repo, path):
        self.removed.append(path)


class AttributionProcess:
    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None):
        self.calls.append((list(argv), cwd, env, timeout))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def attribution_ticket(stem: str, command_count: int = 1) -> Ticket:
    return Ticket(
        stem=stem, state="confirmed", source="seed", priority="P1", kind="feature",
        agent_tier="medium", agent_effort="medium", gate_bypass=(), depends=(), context=(),
        plan_sections=(), goal="attribute", scope_fence=("squatch/widget.py",),
        verification=tuple((PYTHON, "-c", f"raise SystemExit({index + 1})")
                           for index in range(command_count)), regression=None,
        expected_minutes=1, stuck_minutes=2, exit_read_window=())


def attribution_slip(stem: str) -> PackingSlip:
    return PackingSlip(
        stem=stem, verdict="implemented", summary="done", branch=stem, base="base-sha",
        head="head-sha", produced_by_spec_version="1.1", produced_at_sha="head-sha")


async def attributed_check(tmp_path, clock, stem, git_, process, box, *, command_count=1,
                           redactor=None):
    verification = Verification(
        git_, tmp_path, process, attribution_ticket(stem, command_count), {},
        redactor or Redactor({}), box=box,
        base_worktree=tmp_path / "worktrees" / f"{stem}-base-0", run_seq=0)
    slip = attribution_slip(stem)
    from squatch.gates import run_gates
    run = await run_gates((verification,), slip, tmp_path / "branch")
    invoice = build_invoice(run, slip, git_.names, bypassed=set(), version="test",
                            verification=verification)
    return invoice.checks[0]


async def test_base_red_is_excused_and_box_dedup_preserves_each_stems_origin(tmp_path):
    clock = TickingClock()
    box = Box(tmp_path / "state", fs=LocalFilesystem(), clock=clock)
    first_git = AttributionGit()
    first = await attributed_check(
        tmp_path, clock, "first-stem", first_git,
        AttributionProcess((1, "", "branch red"), (1, "", "base red 123")), box)
    [first_command] = first.commands
    assert first.verdict == "pass" and first_command.attribution == "base"
    assert first_command.filed
    assert first_git.added == first_git.removed

    repeat_git = AttributionGit()
    repeat = await attributed_check(
        tmp_path, clock, "first-stem", repeat_git,
        AttributionProcess((1, "", "branch red"), (1, "", "base red 456")), box)
    [repeat_command] = repeat.commands
    assert repeat.verdict == "pass" and repeat_command.filed == first_command.filed
    [message] = box.pending()
    assert (message.message_class, message.origin, message.outcome, message.reports) == (
        "failure_report", "first-stem", "base_red", 2)
    assert repeat_git.added == repeat_git.removed

    second_git = AttributionGit()
    second = await attributed_check(
        tmp_path, clock, "second-stem", second_git,
        AttributionProcess((1, "", "branch red"), (1, "", "base red 789")), box)
    [second_command] = second.commands
    assert second.verdict == "pass" and second_command.filed != first_command.filed
    assert [(m.origin, m.reports) for m in box.pending()] == [
        ("first-stem", 2), ("second-stem", 1)]
    assert second_git.added == second_git.removed


async def test_branch_red_and_green_commands_record_attribution_and_cleanup(tmp_path):
    box = Box(tmp_path / "state", fs=LocalFilesystem(), clock=TickingClock())
    git_ = AttributionGit()
    red = await attributed_check(
        tmp_path, TickingClock(), "branch-red", git_,
        AttributionProcess((1, "", "branch red"), (0, "", "")), box)
    [red_command] = red.commands
    assert red.verdict == "fail" and red_command.attribution == "branch"
    assert red_command.filed is None
    assert git_.added == git_.removed

    green_git = AttributionGit()
    green = await attributed_check(
        tmp_path, TickingClock(), "branch-green", green_git,
        AttributionProcess((0, "", "")), box)
    [green_command] = green.commands
    assert green.verdict == "pass" and green_command.attribution is None
    assert green_command.filed is None
    assert green_git.added == green_git.removed == []


async def test_mixed_commands_keep_per_command_attribution_and_filed_ids(tmp_path):
    box = Box(tmp_path / "state", fs=LocalFilesystem(), clock=TickingClock())
    git_ = AttributionGit()
    check = await attributed_check(
        tmp_path, TickingClock(), "mixed", git_,
        AttributionProcess(
            (1, "", "branch one"), (1, "", "base one"),
            (1, "", "branch two"), (1, "", "base two"),
            (1, "", "branch regression"), (0, "", ""),
            (0, "", "")),
        box, command_count=4)

    assert check.verdict == "fail"
    assert [command.attribution for command in check.commands] == [
        "base", "base", "branch", None]
    filed = [command.filed for command in check.commands]
    assert filed[0] and filed[1] and filed[0] != filed[1]
    assert filed[2:] == [None, None]
    assert [message.id for message in box.pending()] == filed[:2]
    assert git_.added == git_.removed


async def test_base_worktree_refusal_fails_closed_and_empty_diff_never_creates_one(tmp_path):
    box = Box(tmp_path / "state", fs=LocalFilesystem(), clock=TickingClock())
    refused_git = AttributionGit(refuse=True, refusal_stderr=f"refused {SECRET}")
    refused = await attributed_check(
        tmp_path, TickingClock(), "refused", refused_git,
        AttributionProcess((1, "", "branch red")), box,
        redactor=Redactor({KEY_NAME: SECRET}))
    [refused_command] = refused.commands
    assert refused.verdict == "fail" and refused_command.attribution == "branch"
    assert "base attribution failed" in refused.findings[0].message
    assert TOKEN in refused.findings[0].message and SECRET not in refused.findings[0].message

    empty_git = AttributionGit(names=())
    empty = await attributed_check(
        tmp_path, TickingClock(), "empty", empty_git,
        AttributionProcess((1, "", "branch red")), box)
    [empty_command] = empty.commands
    assert empty.verdict == "fail" and empty_command.attribution is None
    assert "no committed diff" in empty.findings[0].message
    assert empty_git.added == empty_git.removed == []


async def test_a_raised_base_run_fails_closed_and_still_removes_the_worktree(tmp_path):
    box = Box(tmp_path / "state", fs=LocalFilesystem(), clock=TickingClock())
    git_ = AttributionGit()
    check = await attributed_check(
        tmp_path, TickingClock(), "base-raises", git_,
        AttributionProcess((1, "", "branch red"), RuntimeError("base runner broke")), box)

    [command] = check.commands
    assert check.verdict == "fail" and command.attribution == "branch"
    assert command.filed is None
    assert "base attribution failed: RuntimeError: base runner broke" in check.findings[0].message
    assert git_.added == git_.removed


async def test_lifted_run_record_is_redacted_on_main(repo, env):
    record = run_record().replace("## Dead ends\n", f"## Dead ends\nenv: {KEY_NAME}={SECRET}\n")
    agent = Agent(answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET, record=record)])
    h = Harness(repo, {**env, KEY_NAME: SECRET}, agent)
    d = await h.run()
    assert d.outcome == "ok", d.findings
    on_main = git(repo, env, "show", f"main:tickets/{STEM}/run.md")
    assert TOKEN in on_main and SECRET not in on_main
    assert SECRET not in (repo / "tickets" / STEM / "run.md").read_text()
    assert SECRET not in "\n".join(json.dumps(event.body) for event in h.journal.read())


async def test_missing_or_malformed_run_record_fails_the_run_record_gate(repo, env):
    agent = Agent(answer("implemented"), actions=[implementer(env, WIDGET, record=None)])
    d = await Harness(repo, env, agent).run()
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "run_record"]
    assert "run.md" in f.message and "## Outcome" in f.paved_road

    bad = run_record().replace("## Dead ends\n", "")
    agent = Agent(answer("implemented"), actions=[implementer(env, WIDGET, record=bad)])
    d = await Harness(repo, env, agent).run(run_seq=1)
    [f] = [f for f in d.findings if f.code == "run_record"]
    assert "Dead ends" in f.message

    agent = Agent(answer("implemented"), actions=[implementer(env, WIDGET, record=run_record("done"))])
    d = await Harness(repo, env, agent).run(run_seq=2)
    [f] = [f for f in d.findings if f.code == "run_record"]
    assert "done" in f.message and "Outcome" in f.message


async def test_diff_budget_caps_the_reviewable_diff(repo, env, monkeypatch):
    monkeypatch.setattr(stages_module, "DIFF_BUDGET_LINES", 3)
    big = ("squatch/widget.py", "".join(f"L{n} = {n}\n" for n in range(10)))
    agent = Agent(answer("implemented"), actions=[implementer(env, big)])
    d = await Harness(repo, env, agent).run()
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "diff_budget"]
    assert "10 inserted lines" in f.message and "split the ticket" in f.paved_road


async def test_gate_bypass_downgrades_the_named_gate_to_soft(repo, env):
    agent = Agent(answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET, ("squatch/other.py", "x = 1\n"))])
    h = Harness(repo, env, agent)
    d = await h.run(frontmatter="gate_bypass: [{code: scope_fence, reason: generated sibling}]")
    assert d.outcome == "ok"
    fence = next(c for c in d.invoice.checks if c.code == "scope_fence")
    assert fence.verdict == "fail" and fence.bypassed and fence.severity == "soft"
    assert d.invoice.passed and d.review is not None
    assert [f.code for f in d.findings] == ["scope_fence"], "soft findings are returned, never hidden"


# --- the first-class short-circuits -------------------------------------------------


async def test_render_implement_is_the_production_first_render_and_uses_chosen_effort(
        repo, env, monkeypatch):
    agent = Agent(answer("premise_failed", "render captured"))
    h = Harness(repo, env, agent)
    ticket = await h.intake(TICKET.format(
        verify=EXISTS, frontmatter="agent_effort: max"))
    expected = h.stages.render_implement(ticket, effort="max")
    size = len(expected)
    monkeypatch.setattr(
        specs_module, "RENDER_BOUND_CHARS",
        {"low": size + 2, "medium": size, "high": size, "max": size - 1})

    await h.stages.run(ticket, run_seq=0)

    assert agent.requests[0].rendered == expected
    assert h.stages.render_implement(ticket, effort="medium") == expected
    with pytest.raises(RenderRefused, match="max"):
        h.stages.render_implement(ticket, effort="max")


async def test_already_satisfied_settles_without_review_when_proven_on_the_base(repo, env):
    (repo / "squatch" / "widget.py").write_text("WIDGET = 0\n")
    git(repo, env, "add", "--", "squatch/widget.py")
    git(repo, env, "commit", "-q", "-m", "already there")
    agent = Agent(answer("already_satisfied"),
                  actions=[writes(record=run_record("already_satisfied"))])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "already_satisfied"
    assert d.slip.verdict == "already_satisfied" and d.slip.head == d.slip.base
    assert d.invoice.passed and d.invoice.changed_files == ()
    assert d.review is None and len(agent.requests) == 1
    assert (repo / "tickets" / STEM / "run.md").read_text() == run_record("already_satisfied")
    assert h.subjects()[:2] == [f"squatch({STEM}): checks", f"squatch({STEM}): run-record"]


async def test_already_satisfied_is_never_taken_on_judgment_alone(repo, env):
    agent = Agent(answer("already_satisfied"),
                  actions=[writes(record=run_record("already_satisfied"))])
    d = await Harness(repo, env, agent).run()
    assert d.outcome == "gate_failed"
    assert any(f.code == "verification" and "exit 1" in f.message for f in d.findings)


async def test_already_satisfied_with_a_committed_diff_is_a_false_claim(repo, env):
    agent = Agent(answer("already_satisfied"),
                  actions=[implementer(env, WIDGET, record=run_record("already_satisfied"))])
    d = await Harness(repo, env, agent).run()
    assert d.outcome == "gate_failed"
    [f] = [f for f in d.findings if f.code == "verification"]
    assert "already_satisfied" in f.message and "squatch/widget.py" in f.message


async def test_premise_failed_from_implement_skips_check_and_review(repo, env):
    agent = Agent(answer("premise_failed", "the fence forbids squatch/renderer.py"),
                  actions=[writes(record=run_record("premise_failed"))])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "premise_failed"
    assert d.slip.verdict == "premise_failed"
    assert [f.message for f in d.findings] == ["the fence forbids squatch/renderer.py"]
    assert d.invoice is None and d.review is None and len(agent.requests) == 1
    assert (repo / "tickets" / STEM / "run.md").is_file()
    assert not (repo / "tickets" / STEM / "checks.json").exists()
    assert h.subjects()[0] == f"squatch({STEM}): run-record"


async def test_an_over_bound_render_is_a_premise_failed_terminal_before_any_call(
        repo, env, monkeypatch):
    monkeypatch.setattr(specs_module, "RENDER_BOUND_CHARS",
                        {k: 100 for k in specs_module.RENDER_BOUND_CHARS})
    agent = Agent(answer("implemented"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "premise_failed" and agent.requests == []
    [f] = d.findings
    assert "over the 100-char bound" in f.message and "split the ticket" in f.paved_road
    assert h.subjects()[0] == f"squatch({STEM}): ticket", "nothing lifted, nothing committed"


# --- Review: one of three artifact types by verdict -------------------------------


async def test_review_snag_is_gate_failed_and_review_md_carries_the_findings(repo, env):
    agent = Agent(answer("implemented"),
                  review("snag", {"path": "squatch/widget.py", "line": 1,
                                  "message": "WIDGET should be 2"}),
                  actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "gate_failed"
    assert isinstance(d.review, SnagList) and d.review.verdict == "snag"
    assert [(f.code, f.path, f.line) for f in d.findings] == [
        ("correctness_review", "squatch/widget.py", 1)]
    text = (repo / "tickets" / STEM / "review.md").read_text()
    assert load_review(text)["verdict"] == "snag"
    assert "WIDGET should be 2" in text and "squatch/widget.py:1" in text
    assert h.subjects()[0] == f"squatch({STEM}): review"


async def test_review_rma_is_premise_failed(repo, env):
    agent = Agent(answer("implemented"),
                  review("rma", {"message": "criteria contradict each other"}),
                  actions=[implementer(env, WIDGET)])
    d = await Harness(repo, env, agent).run()
    assert d.outcome == "premise_failed"
    assert isinstance(d.review, RMA)
    assert [f.message for f in d.findings] == ["criteria contradict each other"]


async def test_review_visibly_quotes_engine_delimiters_without_changing_the_diff(repo, env):
    marker = "<<<" + "squatch:"
    content = f'VALUE = "{marker}data name=not-a-block"\n'
    changed = ("squatch/widget.py", content)
    agent = Agent(answer("implemented"), review("approve"),
                  actions=[implementer(env, changed)])
    h = Harness(repo, env, agent)

    delivery = await h.run()

    assert delivery.outcome == "ok"
    prompt = agent.requests[1].rendered
    assert f'+VALUE = "{marker}' not in prompt
    assert "[squatch-data:data name=not-a-block" in prompt
    assert git(h.worktree(), env, "show", "HEAD:squatch/widget.py") == content


async def test_review_reply_outside_the_verdict_vocabulary_is_reprompted_then_terminal(repo, env):
    agent = Agent(answer("implemented"), review("maybe"), review("approve"),
                  actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "ok"
    assert len(agent.requests) == 3
    assert '<<<squatch:data name="findings"' in h.prompts()[2]
    assert h.completions()[-3:] == [f"llm/{STEM}/0/review/0/1", f"llm/{STEM}/0/review/0/2",
                                    f"lift/{STEM}/0/review"]


async def test_review_call_failure_is_infra_error_with_the_invoice_still_durable(repo, env):
    agent = Agent(answer("implemented"), RuntimeError("provider down"),
                  actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await h.run()
    assert d.outcome == "infra_error"
    assert d.invoice is not None and d.review is None
    assert not (repo / "tickets" / STEM / "review.md").exists()
    assert h.subjects()[0] == f"squatch({STEM}): checks"


# --- re-entry: a fresh run takes a fresh worktree and fresh keys -------------------


async def test_review_finding_reenters_once_between_ticket_and_context_blocks(repo, env):
    marker = "review-finding-in-criteria-position"
    agent = Agent(
        answer("implemented"), review("snag", {"message": marker}),
        answer("premise_failed", "captured re-entry"),
        actions=[implementer(env, WIDGET), None,
                 writes(record=run_record("premise_failed"))])
    h = Harness(repo, env, agent)
    first = await h.run(run_seq=0)
    assert first.outcome == "gate_failed"
    h.journal.append("state_transition", {"to": "gate_failed", "run_seq": 0}, ticket=STEM)

    second = await h.stages.run(
        await h.intake(TICKET.format(verify=EXISTS, frontmatter="")), run_seq=1)

    assert second.outcome == "premise_failed"
    prompt = agent.requests[-1].rendered
    prior = prompt.index('<<<squatch:data name="prior_attempts"')
    context = prompt.index('<<<squatch:data name="context"')
    assert prompt.count(marker) == 1
    assert prior < prompt.index(marker) < context


async def test_harvested_dead_ends_render_in_the_next_attempts_prior_block(repo, env):
    marker = "timed-out-dead-end-marker"
    agent = Agent(answer("premise_failed", "captured prior attempt"),
                  actions=[writes(record=run_record("premise_failed"))])
    h = Harness(repo, env, agent)
    ticket = await h.intake(TICKET.format(verify=EXISTS, frontmatter=""))
    attempt = repo / "tickets" / STEM / "attempts" / "0"
    attempt.mkdir(parents=True)
    (attempt / "run.md").write_text(
        run_record("ok").replace("## Dead ends\n", f"## Dead ends\n{marker}\n"))
    harvest = Harvest(
        outcome="timeout", stage="implement", reason="stuck budget exceeded", findings=(),
        cost=HarvestCost(usd=0, tokens=0, provider=None, model=None), wall_seconds=1,
        run_seq=0, diff_stat="", spool_tails={}, produced_by_spec_version="harvest-1.0",
        produced_at_sha=git(repo, env, "rev-parse", "main").strip())
    (attempt / HARVEST_FILE).write_text(harvest.model_dump_json(indent=2))
    h.journal.append("state_transition", {"to": "timeout", "run_seq": 0}, ticket=STEM)

    delivery = await h.stages.run(ticket, run_seq=1)

    assert delivery.outcome == "premise_failed"
    prompt = agent.requests[0].rendered
    prior = prompt.index('<<<squatch:data name="prior_attempts"')
    context = prompt.index('<<<squatch:data name="context"')
    assert prompt.count(marker) == 1
    assert prior < prompt.index(marker) < context


async def test_a_second_run_takes_a_fresh_worktree_branch_and_keys(repo, env):
    agent = Agent(answer("implemented"),
                  answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET, ("squatch/other.py", "x = 1\n")),
                           implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    first = await h.run(run_seq=0)
    assert first.outcome == "gate_failed"
    stale = h.worktree() / "squatch" / "other.py"
    assert stale.is_file()

    second = await h.stages.run(await h.intake(TICKET.format(verify=EXISTS, frontmatter="")),
                                run_seq=1)

    assert second.outcome == "ok"
    assert not stale.exists(), "teardown-and-create clears the dead run's tree"
    assert h.branch_diff_names() == ["squatch/widget.py"]
    assert f"llm/{STEM}/1/implement/1/1" in h.completions()
    assert (h.state / "spools" / STEM / "0").is_dir() and (h.state / "spools" / STEM / "1").is_dir()
    assert (repo / "tickets" / STEM / "checks.json").is_file()
    assert Invoice.model_validate_json(
        (repo / "tickets" / STEM / "checks.json").read_text()).passed


async def test_a_replayed_run_sequence_re_delivers_without_recalling(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    first = await h.run()
    never = Agent(RuntimeError("must not be called"))
    h2 = Harness(repo, env, never)
    ticket = lint_ticket((repo / "tickets" / STEM / "ticket.md").read_text(), stem=STEM,
                         repo=repo, plan=PLAN, resolve_stem=lambda s: False)
    again = await h2.stages.run(ticket, run_seq=0)
    assert never.requests == []
    assert again.outcome == first.outcome == "ok"
    assert again.review == first.review and again.invoice == first.invoice
    assert len(h2.completions()) == 7, "a replay records nothing new"


# --- the production composition ----------------------------------------------------


def test_compose_builds_the_production_stages_from_config(repo, env):
    config = load(None, cwd=repo)
    clock = TickingClock()
    with Journal(repo / config.state_dir, clock=clock) as journal:
        providers = ProviderRuntime(
            Registry(config), timers=Timers(journal=journal, clock=clock), clock=clock)
        stages = compose(repo=repo, config=config, env=env, journal=journal, clock=clock,
                         process=SubprocessExec(), fs=LocalFilesystem(),
                         git=Git(SubprocessExec(), env=env, timeout=60.0),
                         providers=providers)
    assert isinstance(stages, Stages)
    assert stages.implement_spec.surface == "implement"
    assert stages.review_spec.surface == "review"


def test_the_shipped_specs_lint_and_name_their_gates():
    implement = load_spec(SPECS_DIR / "implement.md")
    assert implement.surface == "implement" and implement.version == "1.1"
    assert implement.slots == ("workspace", "ticket", "prior_attempts", "context")
    assert implement.optional == frozenset({"prior_attempts"})
    assert load_spec(SPECS_DIR / "review.md").surface == "review"


def _baseline_report(*, unknown=False) -> str:
    body = ReviewBaselineReport(
        schema_version=1, produced_at_sha="fixture", planted_defect_count=50, spend_usd=5,
        authored_tickets=("a",), dependency_graph={"a": ()},
        scored_summary={"known_bad": 50, "clean": 0, "caught": 50, "false_approve": 0,
                        "unmatched": 0, "false_snag": 0, "catch_rate": 1,
                        "false_approve_rate": 0, "usd": 5},
        verdict_signal_identity={"tiers": ("medium",), "identity": {
            "review": {"medium": {"provider": "claude", "model": "b"}},
            "author": {"medium": {"provider": "claude", "model": "b"}}},
            "spec_major": {"review": 1, "author": 1}}).model_dump()
    if unknown:
        body["unknown"] = True
    return json.dumps(body)


async def test_ordinary_lift_validates_and_counts_review_baseline_report(repo, env):
    output = (f"tickets/{STEM}/{REVIEW_BASELINE_REPORT}", _baseline_report())
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                actions=[writes(output)]))
    delivery = await h.run(verify=GREEN)
    assert delivery.outcome == "ok", delivery.findings
    assert (repo / output[0]).is_file()
    lifted = stages_module.completed_output_lift(h.journal, STEM, 0, checked=True)
    assert output[0] in lifted


async def test_ordinary_lift_refuses_unknown_review_baseline_report_field(repo, env):
    output = (f"tickets/{STEM}/{REVIEW_BASELINE_REPORT}", _baseline_report(unknown=True))
    h = Harness(repo, env, Agent(answer("implemented"), actions=[writes(output)]))
    delivery = await h.run(verify=GREEN)
    assert delivery.outcome == "invalid_artifact"
    assert any(f.code == "invalid_artifact" and REVIEW_BASELINE_REPORT in f.message
               for f in delivery.findings)
    assert not (repo / output[0]).exists()
