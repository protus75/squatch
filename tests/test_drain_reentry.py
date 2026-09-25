"""Reject-findings re-entry: a re-offer is findings-fed (SQUATCH_PLAN.md
section 11.2; section 19, Phase 1).

Every test drives `python -m squatch drain` in-process against a temp
checkout with the REAL stages and admission behind the seam and a scripted
agent behind the model seam, because the claim is about the rendered
prompt: the re-offer's Implement prompt carries the prior attempt's reject
findings in criteria-position -- the same spec section as the ticket's
acceptance criteria, never the appendix -- while the first attempt's carries
no prior-attempts block and `ticket.md` is never written.
"""

import re
import json
import subprocess
from io import StringIO
from pathlib import Path

from test_stages import (
    CONFIG,
    PYTHON,
    TICKET,
    WIDGET,
    Agent,
    TickingClock,
    answer,
    git_env,
    implementer,
    review,
)

from squatch.__main__ import main
from squatch.config import load
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.harvest import HARVEST_RENDER_CHARS, Harvest, HarvestCost
from squatch.journal import Journal
from squatch.llmeffect import LLMEffect
from squatch.merge import Merge, Pipeline
from squatch.redact import Redactor
from squatch.runner import EXIT_OK
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.specs import DATA_MARKER
from squatch.stages import Stages
from squatch.tickets import PLAN_FILE

STEM = "widget-module"
PLAN = "# plan\n\n## 13. Ticket contract\n\nContract prose.\n"
EXISTS = (f'{PYTHON} -c "import pathlib, sys; '
          f"sys.exit(0 if pathlib.Path('squatch/widget.py').exists() else 1)\"")
RED = f'{PYTHON} -c "import sys; print(\'widget test failed: 3 errors\'); sys.exit(3)"'
_OPEN = re.compile(r'^<<<squatch:data name="([a-z_]+)" origin="([a-z]+)" sha="[0-9a-f]+">>>$')
_CLOSE = re.compile(r'^<<<squatch:end name="([a-z_]+)">>>$')


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], env=git_env(repo.parent),
                          capture_output=True, text=True, check=True).stdout


def checkout(tmp_path: Path, *, verify: str = EXISTS, extra_config: str = "") -> Path:
    """A committed host checkout routing a provider, with one confirmed-on-
    intake ticket on disk."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "config.yaml").write_text(CONFIG + extra_config)
    (repo / PLAN_FILE).write_text(PLAN)
    (repo / "squatch").mkdir()
    (repo / "squatch" / "existing.py").write_text("EXISTING = 1\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "--", "config.yaml", PLAN_FILE, "squatch/existing.py")
    git(repo, "commit", "-q", "-m", "seed")
    ticket = repo / "tickets" / STEM / "ticket.md"
    ticket.parent.mkdir(parents=True)
    ticket.write_text(TICKET.format(verify=verify, frontmatter=""))
    return repo


class NoHandoff:
    """The process seam with the self-upgrade `uv` spawn stubbed to exit 0;
    everything else (git, verification commands) runs for real."""

    def __init__(self):
        self._real = SubprocessExec()

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        if argv[0] == "uv":
            return 0, "", ""
        return await self._real.run(argv, cwd=cwd, env=env, timeout=timeout,
                                    stdin_path=stdin_path, on_spawn=on_spawn)


class Real:
    """The production pipeline shape over the lock-held journal, with the
    scripted agent behind the model seam."""

    def __init__(self, repo: Path, agent: Agent):
        self.repo, self.agent = repo, agent
        self.env = git_env(repo.parent)
        self.config = load(None, cwd=repo)
        self.clock = TickingClock()
        self.git = Git(SubprocessExec(), env=self.env, timeout=60.0)
        self.redact = Redactor.from_config(self.config, self.env)
        self.log = EngineLog(repo / self.config.state_dir, clock=self.clock, redact=self.redact)

    def __call__(self, journal) -> Pipeline:
        stages = Stages(repo=self.repo, config=self.config, git=self.git, process=SubprocessExec(),
                        fs=LocalFilesystem(),
                        llm=LLMEffect(llm=self.agent, effects=Effects(journal), redact=self.redact),
                        log=self.log, redact=self.redact, clock=self.clock, env=self.env)
        merge = Merge(repo=self.repo, config=self.config, git=self.git, process=SubprocessExec(),
                      fs=LocalFilesystem(), effects=Effects(journal), journal=journal,
                      log=self.log, redact=self.redact, env=self.env)
        return Pipeline(stages, merge)

    def drain(self) -> tuple[int, str]:
        out = StringIO()
        # The fixture's widget lands under squatch/, so the admission is a
        # self-upgrade: the handoff spawn is stubbed, never a real re-exec.
        rc = main(["drain"], cwd=self.repo, env=self.env, out=out, pipeline=self, clock=self.clock,
                  process=NoHandoff())
        return rc, out.getvalue()

    def implement_prompts(self) -> list[str]:
        return [r.rendered for r in self.agent.requests if r.surface == "implement"]


def sections(prompt: str) -> dict[str, str]:
    """The prompt split at the SPEC's `## ` headings, data-block interiors
    opaque (a ticket's own `## Acceptance criteria` is data, not a section)."""
    out: dict[str, list[str]] = {}
    current = "<preamble>"
    inside = None
    for line in prompt.splitlines():
        if inside is None and (m := _OPEN.match(line)):
            inside = m.group(1)
        elif inside is not None and (m := _CLOSE.match(line)) and m.group(1) == inside:
            inside = None
        elif inside is None and line.startswith("## "):
            current = line[3:].strip()
            out.setdefault(current, [])
            continue
        out.setdefault(current, []).append(line)
    return {k: "\n".join(v) for k, v in out.items()}


def blocks(prompt: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for line in prompt.splitlines() if (m := _OPEN.match(line))]


def diagnosis(verdict="retry", *lessons: str) -> str:
    return json.dumps({"verdict": verdict, "lessons": list(lessons or ("fix the failure",)),
                       "reason": "diagnosed"})


def snag_then_approve(tmp_path: Path) -> Real:
    agent = Agent(answer("implemented"),
                  review("snag", {"message": "widget lacks the parse() entry point",
                                  "path": "squatch/widget.py", "line": 1,
                                  "paved_road": "add parse() and a test for it"}),
                  diagnosis("retry", "add parse() and a test for it"),
                  answer("implemented"), review("approve"),
                  actions=[implementer(git_env(tmp_path), WIDGET), None, None,
                           implementer(git_env(tmp_path), WIDGET), None])
    return Real(checkout(tmp_path), agent)


# --- the re-offer is findings-fed --------------------------------------------------

def test_a_re_offer_renders_the_prior_reject_findings_in_criteria_position(tmp_path):
    real = snag_then_approve(tmp_path)
    rc, out = real.drain()
    assert rc == EXIT_OK, out
    assert "re-offer: widget-module after `gate_failed`" in out
    assert "findings-fed from tickets/widget-module/checks.json, tickets/widget-module/review.md" in out
    first, second = real.implement_prompts()

    # The first attempt carries no prior-attempts block (the spec prose that
    # names the slot is not a block).
    assert "prior_attempts" not in [n for n, _ in blocks(first)]
    assert "Prior attempts (" not in first

    # The re-offer carries the reject findings, message and paved road, as untrusted data.
    assert ("prior_attempts", "untrusted") in blocks(second)
    assert "attempt 0 of widget-module ended `gate_failed`" in second
    assert "review.md (verdict `snag`" in second
    assert "correctness_review at squatch/widget.py:1: widget lacks the parse() entry point" in second
    assert "(paved road: add parse() and a test for it)" in second
    # A passing checks.json is not a finding: only the rejecting artifact renders.
    assert "checks.json (failing" not in second

    # Position: the same spec section as the acceptance criteria (the ticket
    # block lives in `## Task`), never the appendix after `## On-failure`.
    by_section = sections(second)
    task = by_section["Task"]
    assert "## Acceptance criteria" in task, "the ticket (and its criteria) render under Task"
    assert 'name="prior_attempts"' in task
    assert 'name="prior_attempts"' not in by_section["Inputs"]
    assert 'name="prior_attempts"' not in by_section["On-failure"]
    order = [name for name, _ in blocks(second)]
    assert order.index("ticket") < order.index("prior_attempts") < order.index("context")
    assert order[-1] == "plan_contract", "the appendix is where appended blocks go, not this one"
    close = DATA_MARKER + 'end name="prior_attempts">>>'
    prior, after = task.split('name="prior_attempts"', 1)[1].split(close, 1)
    assert "terminal reason `(findings carried separately)`; diagnosis verdict `retry`" in prior
    assert "- lesson: add parse() and a test for it" in prior
    assert "harvest attempt 0:" not in prior
    assert "files changed:" not in prior and "latest non-prompt spool tails" not in prior
    assert "harvest attempt 0:" not in task.split('name="prior_attempts"', 1)[0] + after
    assert len(prior) <= HARVEST_RENDER_CHARS + 10_000, "Phase 1 findings remain outside the cap"


def test_the_ticket_file_is_never_written_and_the_re_offer_merges_on_one_unit(tmp_path):
    real = snag_then_approve(tmp_path)
    rc, out = real.drain()
    assert rc == EXIT_OK, out
    # The intake stamp is the ticket's only commit: no attempt touched ticket.md.
    history = git(real.repo, "log", "--format=%s", "--", f"tickets/{STEM}/ticket.md").splitlines()
    assert history == [f"squatch({STEM}): ticket"]
    text = git(real.repo, "show", f"main:tickets/{STEM}/ticket.md")
    assert "parse() entry point" not in text and "Prior attempts" not in text
    assert "squatch/widget.py" in git(real.repo, "ls-tree", "-r", "--name-only", "main")
    assert f"settled: {STEM} run 1 ended ok" in out
    assert f"self-upgrade: {STEM} touched squatch/widget.py" in out


def test_the_whole_harvest_contribution_is_capped_even_when_diff_stat_is_oversized(tmp_path):
    attempt = tmp_path / "tickets" / STEM / "attempts" / "0"
    attempt.mkdir(parents=True)
    artifact = Harvest(
        outcome="gate_failed", stage="check", reason=None, findings=(),
        cost=HarvestCost(usd=0.0, tokens=0, provider=None, model=None),
        wall_seconds=1.0, run_seq=0, diff_stat="x" * (HARVEST_RENDER_CHARS * 2),
        spool_tails={}, produced_by_spec_version="harvest-1.0", produced_at_sha="base")
    (attempt / "harvest.json").write_text(artifact.model_dump_json())
    with Journal(tmp_path / ".state", clock=TickingClock()) as journal:
        journal.append("state_transition", {"to": "gate_failed", "run_seq": 0}, ticket=STEM)
        stages = Stages.__new__(Stages)
        stages._repo = tmp_path
        stages._effects = Effects(journal)

        rendered = stages._prior_attempts(STEM, 1)

    harvest = "harvest attempt" + rendered.split("harvest attempt", 1)[1]
    assert len(harvest.rstrip("\n")) == HARVEST_RENDER_CHARS
    assert len(artifact.diff_stat) > len(harvest)


def test_a_delimiter_in_harvested_run_text_is_quoted_before_re_entry_render(tmp_path):
    env = git_env(tmp_path)
    marker = "<<<" + "squatch:" + "data"

    def implement_with_marker(req):
        implementer(env, WIDGET)(req)
        run_record = req.worktree / "tickets" / STEM / "run.md"
        run_record.write_text(run_record.read_text() + f"\nobserved {marker} in output\n")

    agent = Agent(answer("implemented"), review("snag", {"message": "wrong"}),
                  '{"verdict":"shrug"}', "not json",
                  answer("implemented"), review("approve"),
                  actions=[implement_with_marker, None, None, None,
                           implementer(env, WIDGET), None])
    real = Real(checkout(tmp_path), agent)

    rc, out = real.drain()

    assert rc == EXIT_OK, out
    first, second = real.implement_prompts()
    assert f"observed {marker}" not in first
    prior = second.split('name="prior_attempts"', 1)[1].split(
        DATA_MARKER + 'end name="prior_attempts">>>', 1)[0]
    assert "[squatch-data:" in prior and marker not in prior


def test_raw_details_do_not_fall_back_to_an_older_undiagnosed_attempt(tmp_path):
    attempts = tmp_path / "tickets" / STEM / "attempts"
    for run_seq, tail in ((0, "old spool tail"), (1, "new spool tail")):
        attempt = attempts / str(run_seq)
        attempt.mkdir(parents=True)
        artifact = Harvest(
            outcome="gate_failed", stage="check", reason=f"reason {run_seq}", findings=(),
            cost=HarvestCost(usd=0.0, tokens=0, provider=None, model=None),
            wall_seconds=1.0, run_seq=run_seq, diff_stat=f"stat {run_seq}",
            spool_tails={"001-response.md": tail},
            produced_by_spec_version="harvest-1.0", produced_at_sha="base")
        (attempt / "harvest.json").write_text(artifact.model_dump_json())
        (attempt / "run.md").write_text(f"run record {run_seq}\n")

    with Journal(tmp_path / ".state", clock=TickingClock()) as journal:
        journal.append("state_transition", {
            "to": "gate_failed", "run_seq": 0,
            "diagnosis": {"call": "invalid_artifact", "verdict": None, "lessons": (),
                          "reason": None, "detail": "retry cap spent"}}, ticket=STEM)
        journal.append("state_transition", {
            "to": "gate_failed", "run_seq": 1,
            "diagnosis": {"call": "ok", "verdict": "retry", "lessons": ("new lesson",),
                          "reason": "diagnosed", "detail": None}}, ticket=STEM)
        stages = Stages.__new__(Stages)
        stages._repo = tmp_path
        stages._effects = Effects(journal)

        rendered = stages._prior_attempts(STEM, 2)

    assert "attempt 1: terminal reason `reason 1`; diagnosis verdict `retry`" in rendered
    assert "- lesson: new lesson" in rendered
    assert "harvest attempt 0: outcome `gate_failed`; reason: reason 0; files changed: stat 0" in rendered
    assert "run record 0" not in rendered and "old spool tail" not in rendered
    assert "run record 1" not in rendered and "new spool tail" not in rendered
    assert "latest run.md:" not in rendered and "latest non-prompt spool tails:" not in rendered


def test_a_failing_checks_json_renders_its_hard_findings_with_the_verification_tail(tmp_path):
    env = git_env(tmp_path)
    agent = Agent(answer("implemented"), diagnosis(), answer("implemented"),
                  actions=[implementer(env, WIDGET), None, implementer(env, WIDGET)])
    real = Real(checkout(tmp_path, verify=RED, extra_config="caps: {retry: 1}\n"), agent)
    rc, out = real.drain()
    assert rc == EXIT_OK, out
    first, second = real.implement_prompts()
    assert "prior_attempts" not in [n for n, _ in blocks(first)]
    assert "attempt 0 of widget-module ended `gate_failed`" in second
    assert "checks.json (failing at " in second
    assert "- verification: verification command exit 3:" in second
    assert "widget test failed: 3 errors" in second, "the captured tail steers the re-entry"
    assert "(paved road: make every `## Verification` command exit 0" in second
    assert "review.md" not in sections(second)["Task"].split('name="prior_attempts"')[1].split(
        "<<<squatch:end")[0], "no review ran, so no review artifact is folded"
    assert "retry cap spent (1 of 1 drawn)" in out


def test_a_first_attempt_over_a_clean_plane_has_no_prior_attempts_block(tmp_path):
    env = git_env(tmp_path)
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET), None])
    real = Real(checkout(tmp_path), agent)
    rc, out = real.drain()
    assert rc == EXIT_OK, out
    (prompt,) = real.implement_prompts()
    assert [name for name, _ in blocks(prompt)] == ["workspace", "ticket", "context",
                                                     "plan_contract"]
    assert DATA_MARKER + 'data name="prior_attempts"' not in prompt
