"""merge.py: the Phase 1 merge admission (SQUATCH_PLAN.md sections 7, 9, 10;
section 19, Phase 1).

Every test drives Implement -> Check -> Review through the stages harness of
`test_stages` (scripted agent, real temp checkout) and then the admission,
because the claims are about main's history, the branch, the worktree, and
the journal.
"""

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from test_stages import (
    EXISTS,
    GREEN,
    OUTPUT,
    PLAN,
    PYTHON,
    STEM,
    TICKET,
    WIDGET,
    Agent,
    Harness,
    TickingClock,
    answer,
    env,  # noqa: F401 -- fixture
    git,
    implementer,
    repo,  # noqa: F401 -- fixture
    review,
    run_record,
    writes,
)

from squatch.config import load
from squatch.control import ControlInbox
from squatch.mergequeue import AdmissionHold
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git, GitError
from squatch.journal import Journal
from squatch.merge import (
    CODE_LANE_ROAD,
    REVIEWED_TRAILER,
    SEED_SAFETY_ROAD,
    TICKET_TRAILER,
    Merge,
    Pipeline,
    compose_pipeline,
)
from squatch.redact import Redactor
from squatch.runner import merged_stems
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.tickets import lint_ticket


def requisition_approve() -> str:
    return json.dumps({"verdict": "approve", "summary": "reviewed: approve",
                       "findings": []})


def seed_ticket() -> str:
    return TICKET.format(
        verify=f'{PYTHON} -c "import sys; sys.exit(0)"',
        frontmatter="source: seed\nstate: confirmed").replace(
            "## Depends on\n- none", f"## Depends on\n- {STEM}")

# Green alone, red together: passes on the branch as delivered, fails once
# main moves `existing.py` under it.
BOTH = (f'{PYTHON} -c "import pathlib, sys; '
        "present=pathlib.Path('squatch/widget.py').exists(); "
        "changed=pathlib.Path('squatch/existing.py').read_text() != 'EXISTING = 1\\n'; "
        "sys.exit(1 if present and changed else 0)\"")
BASE_RED = f'{PYTHON} -c "import sys; sys.exit(3)"'


def merge_of(h: Harness, git: Git | None = None) -> Merge:
    redact = Redactor.from_config(h.config, h.env)
    return Merge(repo=h.repo, config=h.config, git=git or h.git, process=SubprocessExec(),
                 fs=LocalFilesystem(), effects=Effects(h.journal), journal=h.journal,
                 log=EngineLog(h.state, clock=h.clock, redact=redact), redact=redact,
                 clock=h.clock, env=h.env)


def composed_pipeline_of(h: Harness) -> Pipeline:
    inbox = ControlInbox(h.state, journal=h.journal, fs=LocalFilesystem())
    hold = AdmissionHold(inbox, h.journal)
    return compose_pipeline(
        control_inbox=inbox, admission_hold=hold, repo=h.repo, config=h.config,
        env=h.env, journal=h.journal, clock=h.clock, process=SubprocessExec(),
        fs=LocalFilesystem(), git=h.git)


class SettledStages:
    def __init__(self, delivery):
        self.delivery = delivery

    async def run(self, ticket, *, run_seq):
        return self.delivery


def ticket_of(h: Harness):
    return lint_ticket((h.repo / "tickets" / STEM / "ticket.md").read_text(), stem=STEM,
                       repo=h.repo, plan=PLAN, resolve_stem=lambda s: False)


async def deliver(h: Harness, **fmt):
    d = await h.run(**fmt)
    assert d.outcome in ("ok", "already_satisfied"), d.findings
    return d


def trailer(h: Harness, key: str) -> str:
    return git(h.repo, h.env, "log", "-1", f"--format=%(trailers:key={key},valueonly)",
               "main").strip()


def transitions(h: Harness) -> list[dict]:
    return [e.body for e in h.journal.read() if e.type == "state_transition" and e.ticket == STEM]


def branch_exists(h: Harness) -> bool:
    return subprocess.run(["git", "-C", str(h.repo), "rev-parse", "--verify", f"refs/heads/{STEM}"],
                          env=h.env, capture_output=True).returncode == 0


def rebase_state_paths(h: Harness) -> tuple[str, str]:
    return tuple(git(h.worktree(), h.env, "rev-parse", "--git-path", name).strip()
                 for name in ("rebase-merge", "rebase-apply"))


def tree_hash(h: Harness, rev: str) -> str:
    return git(h.repo, h.env, "rev-parse", f"{rev}^{{tree}}").strip()


def commit_on_main(h: Harness, rel: str, content: str, subject: str) -> str:
    (h.repo / rel).write_text(content)
    git(h.repo, h.env, "add", "--", rel)
    git(h.repo, h.env, "commit", "-q", "-m", subject)
    return git(h.repo, h.env, "rev-parse", "main").strip()


class FailingBranchDeleteGit(Git):
    def __init__(self, *, env: dict[str, str], delete_branch: bool):
        super().__init__(SubprocessExec(), env=env, timeout=60.0)
        self.delete_branch = delete_branch
        self.error: GitError | None = None

    async def branch_delete(self, repo, name: str) -> None:
        if self.delete_branch:
            await super().branch_delete(repo, name)
        self.error = GitError(["git", "branch", "-D", name], 1, "", "forced delete failure")
        raise self.error


# --- admission: squash + trailers, both lanes, the journal record ------------------


async def test_a_passing_ticket_squash_merges_onto_main_with_trailers(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(
        env, WIDGET, (f"tickets/{STEM}/evidence/trace.txt", "trace\n"))])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    before = h.subjects()

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "ok" and a.findings == []
    main = git(repo, env, "rev-parse", "main").strip()
    assert a.commit == main and a.reviewed_sha == d.slip.head
    # One squash commit per ticket on top of the ticket-plane lifts: subject
    # from the Goal line, the two identity trailers, the code diff only.
    assert h.subjects() == [f"squatch({STEM}): The widget module lands.", *before]
    assert trailer(h, TICKET_TRAILER) == STEM
    assert trailer(h, REVIEWED_TRAILER) == d.slip.head
    assert git(repo, env, "show", "--format=", "--name-only", "main").split() == ["squatch/widget.py"]
    assert git(repo, env, "show", "main:squatch/widget.py") == "WIDGET = 1\n"
    assert f"tickets/{STEM}/run.md" in h.main_files()
    assert git(repo, env, "status", "--porcelain", "--untracked-files=no") == ""
    # The branch and its worktree are retired; the ticket's frontmatter rests
    # where intake left it (merged is the journal's record, never a restamp).
    assert not branch_exists(h) and not h.worktree().exists()
    assert "state: confirmed" in (repo / "tickets" / STEM / "ticket.md").read_text()
    assert transitions(h) == [{"to": "merged", "run_seq": 0, "commit": main,
                               "reviewed_sha": d.slip.head}]
    assert STEM in merged_stems(h.journal.read())
    assert not any(
        event.key and event.key.startswith("llm/requisition_review/")
        for event in h.journal.read())


async def test_every_admission_step_is_a_run_scoped_effect(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)
    assert h.completions()[-4:] == [f"rebase/{STEM}/0", f"regate/{STEM}/0", f"merge/{STEM}/0",
                                    f"retire/{STEM}/0"]
    done = {e.key: e for e in h.journal.read() if e.type == "effect_completion"}
    assert all(done[k].ticket == STEM for k in h.completions()[-4:])
    assert done[f"merge/{STEM}/0"].body["result"] == {"commit": a.commit}


async def test_already_satisfied_settles_merged_without_a_code_commit(repo, env):
    commit_on_main(Harness(repo, env, Agent()), "squatch/widget.py", "WIDGET = 0\n", "already there")
    agent = Agent(answer("already_satisfied"),
                  actions=[writes(record=run_record("already_satisfied"))])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    before = git(repo, env, "rev-parse", "main").strip()

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "already_satisfied" and a.commit is None and a.reviewed_sha is None
    assert git(repo, env, "rev-parse", "main").strip() == before, "nothing to integrate"
    assert transitions(h) == [{"to": "merged", "run_seq": 0, "commit": None, "reviewed_sha": None}]
    assert not branch_exists(h) and not h.worktree().exists()


@pytest.mark.parametrize("daemon", [False, True])
@pytest.mark.parametrize("tracked", [False, True])
async def test_output_only_admission_replays_check_evidence_and_retires_once(
        repo, env, daemon, tracked):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                actions=[writes(OUTPUT)]))
    await h.intake(TICKET.format(verify=GREEN, frontmatter=""))
    if tracked:
        (repo / OUTPUT[0]).parent.mkdir(parents=True)
        commit_on_main(h, OUTPUT[0], OUTPUT[1].replace("fixture", "earlier"), "earlier report")
    delivery = await deliver(h, verify=GREEN)
    before = git(repo, env, "rev-parse", "main").strip()
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)
    if daemon:
        pipeline.select_daemon_admission()

    result = await pipeline.run(ticket_of(h), run_seq=0)

    assert result.outcome == "ok", result.findings
    assert git(repo, env, "rev-parse", "main").strip() == before
    assert (repo / OUTPUT[0]).read_text() == OUTPUT[1]
    assert transitions(h) == [{"to": "merged", "run_seq": 0, "commit": None,
                               "reviewed_sha": delivery.slip.head}]
    assert h.completions().count(f"retire/{STEM}/0") == 1
    assert f"merge/{STEM}/0" not in h.completions()
    assert not branch_exists(h) and not h.worktree().exists()
    regate = next(e.body["result"] for e in h.journal.read()
                  if e.type == "effect_completion" and e.key == f"regate/{STEM}/0")
    assert regate["changed_files"] == []
    assert all(c["verdict"] == "pass" for c in regate["checks"])
    # Effect replay must neither rerun verification in a retired tree nor retire twice.
    await merge_of(h)._retire(STEM, h.worktree(), 0)
    invoice = await merge_of(h)._regate(ticket_of(h), delivery.slip, h.worktree(), 0)
    assert invoice.passed
    assert h.completions().count(f"retire/{STEM}/0") == 1
    assert len(transitions(h)) == 1


@pytest.mark.parametrize("evidence", ["missing", "stale", "foreign", "run-record", "unknown",
                                     "no-check", "stale-check"])
async def test_merge_regate_requires_current_completed_output_and_check_evidence(
        repo, env, evidence):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                actions=[writes(OUTPUT)]))
    delivery = await deliver(h, verify=GREEN)
    merge = merge_of(h)
    rebased = await merge._rebase(STEM, h.worktree(), 0)
    candidate = delivery.slip.model_copy(update={"base": rebased["base"], "head": rebased["head"]})
    isolated = Journal(h.state / "regate-evidence", clock=h.clock)
    events = [e for e in h.journal.read() if e.type == "effect_completion"
              and e.key in (f"lift/{STEM}/0/run-record", f"check/{STEM}/0")]
    for event in events:
        key, ticket, body = event.key, event.ticket, event.body
        if key.startswith("lift/"):
            if evidence == "missing":
                continue
            if evidence == "stale":
                key = f"lift/{STEM}/1/run-record"
            if evidence == "foreign":
                ticket = "other"
            if evidence in ("run-record", "unknown"):
                name = "run.md" if evidence == "run-record" else "unknown.json"
                body = {"result": {"paths": [f"tickets/{STEM}/{name}"], "commit": None}}
        else:
            if evidence == "no-check":
                continue
            if evidence == "stale-check":
                key = f"check/{STEM}/1"
        isolated.append("effect_completion", body, ticket=ticket, key=key)
    merge._journal = isolated
    merge._effects = Effects(isolated)

    invoice = await merge._regate(ticket_of(h), candidate, h.worktree(), 0)

    assert not invoice.passed
    assert any("no committed diff" in f.message for f in invoice.hard_findings)


@pytest.mark.parametrize("daemon", [False, True])
@pytest.mark.parametrize("rel", ["squatch/widget.py", "tickets/other/note.txt"])
async def test_output_merge_refuses_foreign_edits_before_ticket_plane_cleanup(
        repo, env, daemon, rel):
    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                actions=[writes(OUTPUT)]))
    delivery = await deliver(h, verify=GREEN)
    path = h.worktree() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("uncommitted")
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)
    if daemon:
        pipeline.select_daemon_admission()
    result = await pipeline.run(ticket_of(h), run_seq=0)
    assert result.outcome == "gate_failed"
    assert any("no committed diff" in f.message for f in result.findings)
    assert path.read_text() == "uncommitted"
    assert transitions(h) == [] and branch_exists(h)


@pytest.mark.parametrize("daemon", [False, True])
async def test_committed_registered_output_is_still_refused_by_code_lane(repo, env, daemon):
    def act(req):
        writes(OUTPUT)(req)
        git(req.worktree, env, "add", "--", OUTPUT[0])
        git(req.worktree, env, "commit", "-q", "-m", "committed report", "--", OUTPUT[0])

    h = Harness(repo, env, Agent(answer("implemented"), review("approve"), actions=[act]))
    delivery = await deliver(h, verify=GREEN)
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)
    if daemon:
        pipeline.select_daemon_admission()
    result = await pipeline.run(ticket_of(h), run_seq=0)
    assert result.outcome == "gate_failed"
    assert any(f.path == OUTPUT[0] and f.paved_road == CODE_LANE_ROAD for f in result.findings)
    assert transitions(h) == [] and branch_exists(h)


async def test_retire_tolerates_a_failed_delete_when_the_branch_is_already_gone(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    failing_git = FailingBranchDeleteGit(env=env, delete_branch=True)

    a = await merge_of(h, failing_git).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "ok" and not branch_exists(h)


async def test_retire_re_raises_a_failed_delete_when_the_branch_still_exists(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    failing_git = FailingBranchDeleteGit(env=env, delete_branch=False)

    with pytest.raises(GitError) as raised:
        await merge_of(h, failing_git).admit(ticket_of(h), d, run_seq=0)

    assert raised.value is failing_git.error and branch_exists(h)


async def test_a_re_entry_worktree_with_a_modified_tracked_outbox_still_rebases(repo, env):
    """Run 0 leaves run.md, checks.json and review.md tracked on main; run 1's
    worktree is born from that main and its agent overwrites the tracked
    run.md, which the ticket-plane restore has to clear before the rebase."""
    agent = Agent(answer("implemented"), review("snag", {"message": "WIDGET should be 2"}),
                  answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET), None,
                           implementer(env, ("squatch/widget.py", "WIDGET = 2\n"),
                                       record=run_record().replace("## Dead ends\n",
                                                                   "## Dead ends\nsecond\n"))])
    h = Harness(repo, env, agent)
    first = await h.run(run_seq=0)
    assert first.outcome == "gate_failed"
    second = await h.stages.run(ticket_of(h), run_seq=1)
    assert second.outcome == "ok", second.findings
    assert git(h.worktree(), env, "status", "--porcelain", "--", "tickets/").startswith(" M ")

    a = await merge_of(h).admit(ticket_of(h), second, run_seq=1)

    assert a.outcome == "ok", a.findings
    assert git(repo, env, "show", "main:squatch/widget.py") == "WIDGET = 2\n"
    assert "second" in git(repo, env, "show", f"main:tickets/{STEM}/run.md")



async def test_the_ticket_plane_restore_never_follows_a_symlink_out_of_the_worktree(repo, env):
    """An agent-planted link under tickets/ is removed as the link alone; the
    tree it points at, outside the engine's fence, is left intact."""
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    outside = repo.parent / "outside"
    (outside / "nested").mkdir(parents=True)
    (outside / "top.txt").write_text("top\n")
    (outside / "nested" / "deep.txt").write_text("deep\n")
    link = h.worktree() / "tickets" / STEM / "ext"
    link.symlink_to(outside)
    file_link = h.worktree() / "tickets" / STEM / "ext.txt"
    file_link.symlink_to(outside / "top.txt")

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "ok", a.findings
    assert sorted(p.name for p in outside.rglob("*")) == ["deep.txt", "nested", "top.txt"]
    assert (outside / "top.txt").read_text() == "top\n"
    assert not h.worktree().exists()


async def test_gate_bypass_applies_at_the_merge_re_run(repo, env):
    agent = Agent(answer("implemented"), review("approve"),
                  actions=[implementer(env, WIDGET, ("squatch/other.py", "x = 1\n"))])
    h = Harness(repo, env, agent)
    d = await deliver(h, frontmatter="gate_bypass: [{code: scope_fence, reason: generated sibling}]")
    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)
    assert a.outcome == "ok"
    assert [f.code for f in a.findings] == ["scope_fence"], "soft findings are returned, never hidden"
    assert "squatch/other.py" in h.main_files()


# --- a failing hard gate blocks admission ------------------------------------------


async def test_an_inherited_base_red_is_excused_again_during_regate(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h, verify=BASE_RED)

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "ok" and a.findings == []
    [report] = list((h.state / "box").glob("*.json"))
    message = json.loads(report.read_text())
    assert message["origin"] == STEM and message["outcome"] == "base_red"
    assert message["reports"] == 2, "Check and regate deduplicate through Box.enqueue"


async def test_the_integration_check_runs_against_the_rebased_candidate(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h, verify=BOTH)
    moved = commit_on_main(h, "squatch/existing.py", "EXISTING = 2\n", "main moved")

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "gate_failed"
    [f] = [f for f in a.findings if f.code == "verification"]
    assert "exit 1" in f.message
    # main is untouched; the branch stays in place, rebased onto the moved main.
    assert git(repo, env, "rev-parse", "main").strip() == moved
    assert "squatch/widget.py" not in h.main_files()
    assert branch_exists(h) and h.worktree().is_dir()
    assert git(repo, env, "rev-parse", f"{STEM}~1").strip() == moved
    assert transitions(h) == []


async def test_a_refused_rebase_is_gate_failed_aborted_and_left_re_runnable(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    moved = commit_on_main(h, "squatch/widget.py", "WIDGET = 9\n", "conflicting")
    main_tree = tree_hash(h, "main")

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "gate_failed"
    [f] = a.findings
    assert f.code == "post_rebase_regate" and "re-run" in f.paved_road
    assert git(repo, env, "rev-parse", STEM).strip() == d.slip.head, "aborted to its own head"
    assert git(h.worktree(), env, "rev-parse", "HEAD").strip() == d.slip.head
    assert not any(Path(path).exists() for path in rebase_state_paths(h))
    assert git(repo, env, "rev-parse", "main").strip() == moved
    assert tree_hash(h, "main") == main_tree
    assert transitions(h) == []


async def test_a_branch_carrying_a_ticket_plane_commit_fails_merge_safety(repo, env):
    def commit_everything(req):
        writes(WIDGET)(req)
        git(req.worktree, env, "add", "-A")
        git(req.worktree, env, "commit", "-q", "-m", "code plus outbox")
    agent = Agent(answer("implemented"), review("approve"), actions=[commit_everything])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    assert f"tickets/{STEM}/run.md" in h.branch_diff_names()

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "gate_failed"
    [f] = a.findings
    assert (f.code, f.path, f.paved_road) == ("post_rebase_regate", f"tickets/{STEM}/run.md",
                                              CODE_LANE_ROAD)
    assert "squatch/widget.py" not in h.main_files()
    assert git(repo, env, "rev-parse", STEM).strip() == d.slip.head, "refused before any rebase"


@pytest.mark.parametrize("tamper", [False, True])
@pytest.mark.parametrize("old_report", [False, True])
async def test_seed_merge_safety_matches_approved_lifted_bytes(repo, env, tamper, old_report):
    text = seed_ticket()
    agent = Agent(answer("implemented"), requisition_approve(), review("approve"),
                  actions=[writes(("tickets/next-seed/ticket.md", text),
                                  record=run_record())])
    h = Harness(repo, env, agent)
    if old_report:
        await h.intake(TICKET.format(verify=GREEN, frontmatter=""))
        (repo / OUTPUT[0]).parent.mkdir(parents=True)
        commit_on_main(h, OUTPUT[0], OUTPUT[1], "earlier report")
    d = await deliver(
        h, verify=f'{PYTHON} -c "import sys; sys.exit(0)"')
    if tamper:
        commit_on_main(h, "tickets/next-seed/ticket.md",
                       text.replace("The widget module lands.", "Changed after approval."),
                       "tamper with seed")

    admission = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    if tamper:
        assert admission.outcome == "gate_failed"
        [finding] = admission.findings
        assert finding.code == "requisition_review"
        assert finding.paved_road == SEED_SAFETY_ROAD
        assert finding.path == "tickets/next-seed/ticket.md"
    else:
        assert admission.outcome == "ok" and admission.findings == []


async def test_seed_merge_safety_uses_the_committed_checks_blob(repo, env):
    text = seed_ticket()
    agent = Agent(answer("implemented"), requisition_approve(), review("approve"),
                  actions=[writes(("tickets/next-seed/ticket.md", text),
                                  record=run_record())])
    h = Harness(repo, env, agent)
    delivery = await deliver(h, verify=f'{PYTHON} -c "import sys; sys.exit(0)"')
    checks = repo / "tickets" / STEM / "checks.json"
    checks.write_text("working-tree bytes that are not committed\n")

    admission = await merge_of(h).admit(ticket_of(h), delivery, run_seq=0)

    assert admission.outcome == "ok" and admission.findings == []


async def test_seed_merge_safety_requires_approval_for_the_lifted_sha(repo, env):
    text = seed_ticket()
    agent = Agent(answer("implemented"), requisition_approve(), review("approve"),
                  actions=[writes(("tickets/next-seed/ticket.md", text),
                                  record=run_record())])
    h = Harness(repo, env, agent)
    delivery = await deliver(h, verify=f'{PYTHON} -c "import sys; sys.exit(0)"')
    assert delivery.invoice is not None
    checks = tuple(
        entry.model_copy(update={"sha": "0" * 40})
        if entry.code == "requisition_review" else entry
        for entry in delivery.invoice.checks)
    stale = delivery.invoice.model_copy(update={"checks": checks})
    commit_on_main(h, f"tickets/{STEM}/checks.json",
                   stale.model_dump_json(indent=2), "stale seed approval")

    admission = await merge_of(h).admit(
        ticket_of(h), replace(delivery, invoice=stale), run_seq=0)

    assert admission.outcome == "gate_failed"
    [finding] = admission.findings
    assert finding.code == "requisition_review"
    assert finding.path == "tickets/next-seed/ticket.md"
    assert finding.paved_road == SEED_SAFETY_ROAD


async def test_an_admission_without_a_seed_lift_does_not_read_seed_checks(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    delivery = await deliver(h)
    (repo / "tickets" / STEM / "checks.json").unlink()

    admission = await merge_of(h).admit(ticket_of(h), delivery, run_seq=0)

    assert admission.outcome == "ok" and admission.findings == []


async def test_the_approval_must_pin_the_head_being_admitted(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    (h.worktree() / "squatch" / "widget.py").write_text("WIDGET = 3\n")
    git(h.worktree(), env, "commit", "-q", "-am", "unreviewed")
    moved_head = git(repo, env, "rev-parse", STEM).strip()

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "gate_failed"
    [f] = a.findings
    assert f.code == "correctness_review" and moved_head[:12] in f.message
    assert "squatch/widget.py" not in h.main_files() and transitions(h) == []


async def test_no_review_verdict_on_the_ticket_plane_blocks_admission(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    d = await deliver(h)
    (repo / "tickets" / STEM / "review.md").unlink()

    a = await merge_of(h).admit(ticket_of(h), d, run_seq=0)

    assert a.outcome == "gate_failed"
    [f] = a.findings
    assert f.code == "correctness_review" and "review.md" in f.message
    assert "squatch/widget.py" not in h.main_files()


# --- the pipeline behind the runner's seam -----------------------------------------


async def test_pipeline_runs_the_stages_then_the_admission(repo, env):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    ticket = await h.intake(TICKET.format(verify=EXISTS, frontmatter=""))
    delivery = await Pipeline(h.stages, merge_of(h)).run(ticket, run_seq=0)
    assert delivery.outcome == "ok"
    assert STEM in merged_stems(h.journal.read()) and "squatch/widget.py" in h.main_files()


async def test_composed_pipeline_keeps_bootstrap_admission_inline(repo, env, monkeypatch):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    delivery = await deliver(h)
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)

    async def queue_must_stay_dormant(*args, **kwargs):
        raise AssertionError("bootstrap admission reached the daemon queue")

    monkeypatch.setattr(pipeline.merge_queue, "admit_delivery", queue_must_stay_dormant)
    result = await pipeline.run(ticket_of(h), run_seq=0)

    assert pipeline.admission_mode == "inline" and result.outcome == "ok"
    assert not branch_exists(h) and not h.worktree().exists()


async def test_daemon_pipeline_offers_one_candidate_and_finalizes_once(repo, env, monkeypatch):
    agent = Agent(answer("implemented"), review("approve"), actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    delivery = await deliver(h)
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)
    pipeline.select_daemon_admission()
    offered = []
    original = pipeline.merge_queue.admit_delivery

    async def admit_delivery(candidate, **kwargs):
        offered.append(candidate)
        return await original(candidate, **kwargs)

    monkeypatch.setattr(pipeline.merge_queue, "admit_delivery", admit_delivery)
    result = await pipeline.run(ticket_of(h), run_seq=0)

    assert result.outcome == "ok" and len(offered) == 1
    assert offered[0].stem == STEM and offered[0].worktree == h.worktree()
    main = git(repo, env, "rev-parse", "main").strip()
    assert transitions(h) == [{"to": "merged", "run_seq": 0, "commit": main,
                               "reviewed_sha": delivery.slip.head}]
    assert h.completions().count(f"retire/{STEM}/0") == 1
    assert not branch_exists(h) and not h.worktree().exists()
    merge_events = [json.loads(line) for line in (h.state / "engine.log").read_text().splitlines()
                    if json.loads(line).get("event") == "merge"]
    assert [(event["commit"], event["reviewed_sha"]) for event in merge_events] == [
        (main, delivery.slip.head)]


async def test_daemon_prechecks_code_lane_before_offering(repo, env, monkeypatch):
    def commit_everything(req):
        writes(WIDGET)(req)
        git(req.worktree, env, "add", "-A")
        git(req.worktree, env, "commit", "-q", "-m", "code plus outbox")

    h = Harness(repo, env, Agent(answer("implemented"), review("approve"),
                                 actions=[commit_everything]))
    delivery = await deliver(h)
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)
    pipeline.select_daemon_admission()

    async def queue_must_not_run(*args, **kwargs):
        raise AssertionError("unsafe delivery reached the daemon queue")

    monkeypatch.setattr(pipeline.merge_queue, "admit_delivery", queue_must_not_run)
    result = await pipeline.run(ticket_of(h), run_seq=0)

    assert result.outcome == "gate_failed"
    assert [finding.code for finding in result.findings] == ["post_rebase_regate"]
    assert branch_exists(h) and h.worktree().is_dir() and transitions(h) == []


async def test_daemon_prechecks_seed_safety_before_offering(repo, env, monkeypatch):
    text = seed_ticket()
    agent = Agent(answer("implemented"), requisition_approve(), review("approve"),
                  actions=[writes(("tickets/next-seed/ticket.md", text),
                                  record=run_record())])
    h = Harness(repo, env, agent)
    delivery = await deliver(h, verify=f'{PYTHON} -c "import sys; sys.exit(0)"')
    commit_on_main(h, "tickets/next-seed/ticket.md",
                   text.replace("The widget module lands.", "Changed after approval."),
                   "tamper with seed")
    pipeline = composed_pipeline_of(h)
    pipeline.stages = SettledStages(delivery)
    pipeline.select_daemon_admission()

    async def queue_must_not_run(*args, **kwargs):
        raise AssertionError("stale seed approval reached the daemon queue")

    monkeypatch.setattr(pipeline.merge_queue, "admit_delivery", queue_must_not_run)
    result = await pipeline.run(ticket_of(h), run_seq=0)

    assert result.outcome == "gate_failed"
    assert [finding.code for finding in result.findings] == ["requisition_review"]
    assert branch_exists(h) and h.worktree().is_dir() and transitions(h) == []


async def test_pipeline_skips_the_admission_on_a_non_ok_stage_terminal(repo, env):
    agent = Agent(answer("implemented"), review("snag", {"message": "no"}),
                  actions=[implementer(env, WIDGET)])
    h = Harness(repo, env, agent)
    ticket = await h.intake(TICKET.format(verify=EXISTS, frontmatter=""))
    delivery = await Pipeline(h.stages, merge_of(h)).run(ticket, run_seq=0)
    assert delivery.outcome == "gate_failed"
    assert transitions(h) == [] and "squatch/widget.py" not in h.main_files()
    assert branch_exists(h) and h.worktree().is_dir()


def test_compose_pipeline_builds_the_production_composition_from_config(repo, env):
    config = load(None, cwd=repo)
    clock = TickingClock()
    with Journal(repo / config.state_dir, clock=clock) as journal:
        inbox = ControlInbox(repo / config.state_dir, journal=journal, fs=LocalFilesystem())
        hold = AdmissionHold(inbox, journal)
        pipeline = compose_pipeline(control_inbox=inbox, admission_hold=hold,
                                    repo=repo, config=config, env=env, journal=journal,
                                    clock=clock, process=SubprocessExec(), fs=LocalFilesystem(),
                                    git=Git(SubprocessExec(), env=env, timeout=60.0))
    assert pipeline.merge_queue.admission_hold is hold
    assert hold.inbox is inbox
    assert isinstance(pipeline, Pipeline)
    assert isinstance(pipeline.merge, Merge)
    assert pipeline.stages.review_spec.surface == "review"
