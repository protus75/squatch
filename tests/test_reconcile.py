"""reconcile.py: reconcile-on-entry, the reap of orphaned in-flight runs
(SQUATCH_PLAN.md section 11.2; section 18; section 19, Phase 1).

Every test drives `run` against a temp checkout -- a real git repo with a
worktree an interrupted predecessor left behind -- because the claims are
about the journal, the worktree registry, and what reaches dispatch. The
orphan is planted through the Journal seam (an appended `running` with no
terminal) and a real `git worktree add`, exactly the state a scaffold
killed mid-run leaves.
"""

import subprocess
from pathlib import Path

from test_cli import (
    STATE,
    FakePipeline,
    author,
    checkout,  # noqa: F401 -- fixture
    cli,
    clock,
    git_env,
    transitions,
)

from squatch.config import load
from squatch.effects import Effects
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.lockfile import Lockfile
from squatch.reconcile import Orphan, orphans
from squatch.runner import EXIT_OK, EXIT_REFUSED, EXIT_TICKET
from squatch.stages import Stages


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], env=git_env(repo.parent),
                          capture_output=True, text=True, check=True)
    return proc.stdout


def worktree_of(repo: Path, stem: str) -> Path:
    return repo / load(None, cwd=repo).worktree_root / stem


def registered_worktrees(repo: Path) -> list[str]:
    return [line.removeprefix("worktree ")
            for line in git(repo, "worktree", "list", "--porcelain").splitlines()
            if line.startswith("worktree ")]


def recovery_alerts(repo: Path, stem: str):
    return [event for event in read_events(repo / STATE)
            if event.type == "signal" and event.body.get("kind") == "recovery_alert"
            and event.ticket == stem]


def plant_orphan(repo: Path, stem: str, run_seq: int = 0, *, worktree: bool = True) -> Path:
    """What a predecessor killed between `running` and its terminal leaves."""
    with Journal(repo / STATE, clock=clock) as journal:
        journal.append("state_transition", {"to": "running", "run_seq": run_seq}, ticket=stem)
        journal.append("effect_intent", {}, ticket=stem, key=f"worktree/{stem}/{run_seq}")
        journal.append("effect_completion", {
            "result": {"path": str(worktree_of(repo, stem)), "branch": stem,
                       "base": git(repo, "rev-parse", "main").strip()}},
            ticket=stem, key=f"worktree/{stem}/{run_seq}")
    path = worktree_of(repo, stem)
    if worktree:
        git(repo, "worktree", "add", "-q", "-b", stem, str(path), "main")
        (path / "debris.txt").write_text("uncommitted work the dead run left\n")
        run = path / "tickets" / stem / "run.md"
        run.parent.mkdir(parents=True)
        run.write_text("orphan run record\n")
    return path


# --- the fold ------------------------------------------------------------------------

def test_orphans_is_a_running_with_no_terminal_or_an_intent_with_no_completion(checkout):
    with Journal(checkout / STATE, clock=clock) as j:
        # settled: running -> terminal, every intent completed
        j.append("state_transition", {"to": "running", "run_seq": 0}, ticket="done")
        j.append("effect_intent", {}, ticket="done", key="worktree/done/0")
        j.append("effect_completion", {"result": None}, ticket="done", key="worktree/done/0")
        j.append("state_transition", {"to": "merged", "run_seq": 0}, ticket="done")
        # orphaned by its transition: the second run of a stem is still open
        j.append("state_transition", {"to": "running", "run_seq": 0}, ticket="twice")
        j.append("state_transition", {"to": "gate_failed", "run_seq": 0}, ticket="twice")
        j.append("state_transition", {"to": "running", "run_seq": 1}, ticket="twice")
        j.append("effect_intent", {}, ticket="twice", key="llm/twice/1/implement")
        # orphaned by an intent alone, after its last terminal
        j.append("state_transition", {"to": "running", "run_seq": 0}, ticket="intent")
        j.append("state_transition", {"to": "timeout", "run_seq": 0}, ticket="intent")
        j.append("effect_intent", {}, ticket="intent", key="worktree/intent/1")
        # an intent left open BEFORE a terminal is inert history, never an orphan
        j.append("effect_intent", {}, ticket="stale", key="llm/stale/0/review")
        j.append("state_transition", {"to": "running", "run_seq": 0}, ticket="stale")
        j.append("state_transition", {"to": "infra_error", "run_seq": 0}, ticket="stale")
    assert orphans(read_events(checkout / STATE)) == [
        Orphan("intent", 1, ("worktree/intent/1",)),
        Orphan("twice", 1, ("llm/twice/1/implement",)),
    ]


def test_orphans_of_an_empty_journal_is_empty(checkout):
    assert orphans(read_events(checkout / STATE)) == []


# --- reconcile on entry --------------------------------------------------------------

def test_an_orphaned_running_is_reaped_abandoned_and_its_worktree_removed_on_the_next_run(
        checkout, monkeypatch):
    author(checkout, "base")
    path = plant_orphan(checkout, "base")
    assert path.is_dir() and str(path) in registered_worktrees(checkout)

    removal_events = []
    worktree_remove = Git.worktree_remove

    async def observed_remove(self, repo, removed):
        assert removed == path and path.is_dir()
        removal_events.extend(read_events(checkout / STATE))
        await worktree_remove(self, repo, removed)

    monkeypatch.setattr(Git, "worktree_remove", observed_remove)

    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK, out
    # The terminal is journaled through the seam, before the wipe, and frees
    # the stem: the re-run takes the next sequence and is real work.
    assert transitions(checkout, "base") == [{"to": "running", "run_seq": 0},
                                             {"to": "abandoned", "run_seq": 0,
                                              "harvest": "tickets/base/attempts/0"},
                                             {"to": "running", "run_seq": 1}]
    alert = recovery_alerts(checkout, "base")
    assert [(event.ticket, event.body) for event in alert] == [("base", {
        "kind": "recovery_alert",
        "run_seq": 0,
        "disposition": "alert",
        "outcome": "abandoned",
        "reason": "orphan reaped during entry reconciliation",
    })]
    terminal_index = next(i for i, event in enumerate(removal_events)
                          if event.type == "state_transition"
                          and event.body.get("to") == "abandoned")
    alert_index = next(i for i, event in enumerate(removal_events)
                       if event.type == "signal"
                       and event.body.get("kind") == "recovery_alert")
    assert alert_index == terminal_index + 1
    assert fake.calls == [("base", 1)]
    assert not path.exists()
    assert registered_worktrees(checkout) == [str(checkout)], "removed AND pruned"
    assert "reconciled: base run 0" in out and "abandoned" in out
    # Only the worktree is reaped: the branch stays for the next run's
    # teardown-and-create (and, from Phase 2, the harvest) -- never rm -rf.
    assert git(checkout, "branch", "--list", "base").strip() == "base"
    assert (checkout / "tickets" / "base" / "attempts" / "0" / "run.md").read_text() == (
        "orphan run record\n")

    with Journal(checkout / STATE, clock=clock) as journal:
        probe = Stages.__new__(Stages)
        probe._repo = checkout
        probe._effects = Effects(journal)
        prior = probe._prior_attempts("base", 1)
    assert prior is not None
    assert "attempt 0 of base ended `abandoned`" in prior
    assert "harvest attempt 0: outcome `abandoned`" in prior
    assert "orphan run record" in prior


def test_reconcile_reaps_every_orphan_not_just_the_stem_being_run(checkout):
    author(checkout, "base")
    author(checkout, "other")
    other = plant_orphan(checkout, "other", run_seq=2)
    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK, out
    assert transitions(checkout, "other") == [{"to": "running", "run_seq": 2},
                                              {"to": "abandoned", "run_seq": 2,
                                               "harvest": "tickets/other/attempts/2"}]
    assert [(event.ticket, event.body["run_seq"]) for event in
            recovery_alerts(checkout, "other")] == [("other", 2)]
    assert transitions(checkout, "base") == [{"to": "running", "run_seq": 0}]
    assert not other.exists()
    assert fake.calls == [("base", 0)]
    # The reaped stem reads as stopped, never in flight, and stays eligible.
    _, status = cli(checkout, "status")
    assert "other: abandoned" in status and "other, run" not in status


def test_an_orphan_with_no_worktree_is_reaped_and_the_registry_pruned(checkout, monkeypatch):
    author(checkout, "base")
    path = plant_orphan(checkout, "base")
    # A worktree removed out from under git leaves a dangling registry entry.
    subprocess.run(["rm", "-rf", str(path)], check=True)
    assert str(path) in registered_worktrees(checkout)

    prune_snapshots = []
    worktree_prune = Git.worktree_prune

    async def observed_prune(self, repo):
        assert not path.exists()
        prune_snapshots.append(list(read_events(checkout / STATE)))
        await worktree_prune(self, repo)

    monkeypatch.setattr(Git, "worktree_prune", observed_prune)
    rc, out = cli(checkout, "run", "base", pipeline=FakePipeline("gate_failed"))
    assert rc == EXIT_TICKET, out
    assert transitions(checkout, "base")[1] == {"to": "abandoned", "run_seq": 0,
                                                "harvest": None}
    assert [(event.ticket, event.body) for event in recovery_alerts(checkout, "base")] == [
        ("base", {
            "kind": "recovery_alert",
            "run_seq": 0,
            "disposition": "alert",
            "outcome": "abandoned",
            "reason": "orphan reaped during entry reconciliation",
        })]
    assert [(event.type, event.body.get("to") or event.body.get("kind"))
            for event in prune_snapshots[0][-2:]] == [
                ("state_transition", "abandoned"),
                ("signal", "recovery_alert"),
            ]
    assert registered_worktrees(checkout) == [str(checkout)]

    rc, out = cli(checkout, "run", "base", pipeline=FakePipeline("gate_failed"))
    assert rc == EXIT_TICKET, out
    assert "reconciled" not in out
    assert [transition for transition in transitions(checkout, "base")
            if transition["to"] == "abandoned"] == [
                {"to": "abandoned", "run_seq": 0, "harvest": None}]
    assert len(recovery_alerts(checkout, "base")) == 1


def test_a_clean_journal_is_a_no_op(checkout):
    author(checkout, "base")
    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK, out
    assert "reconciled" not in out
    assert transitions(checkout, "base") == [{"to": "running", "run_seq": 0}]
    assert [e.type for e in read_events(checkout / STATE) if e.ticket == "base"] == [
        "signal", "state_transition"]


def test_a_settled_run_is_never_reaped(checkout):
    author(checkout, "base")
    fake = FakePipeline("gate_failed", "ok")
    cli(checkout, "run", "base", pipeline=fake)
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK, out
    assert "reconciled" not in out
    assert [t["to"] for t in transitions(checkout, "base")] == ["running", "gate_failed", "running"]


def test_reconcile_runs_only_under_the_writer_lock(checkout):
    author(checkout, "base")
    path = plant_orphan(checkout, "base")
    holder = Lockfile(checkout / STATE, instance_id="other-daemon", clock=clock)
    holder.acquire()
    try:
        rc, _ = cli(checkout, "run", "base", pipeline=FakePipeline("ok"))
    finally:
        holder.release()
    assert rc == EXIT_REFUSED
    assert [t["to"] for t in transitions(checkout, "base")] == ["running"]
    assert path.is_dir(), "a run under another writer's lock is not provably dead"


def test_a_faulted_run_is_reaped_by_the_next_entry(checkout):
    """The end-to-end shape: a fault escaping the stage seam leaves `running`
    with no terminal (runner), and the next entry reaps it."""
    author(checkout, "base")

    class Faulting(FakePipeline):
        async def run(self, ticket, *, run_seq):
            git(checkout, "worktree", "add", "-q", "-b", ticket.stem,
                str(worktree_of(checkout, ticket.stem)), "main")
            raise RuntimeError("the worker died")

    rc, out = cli(checkout, "run", "base", pipeline=Faulting())
    assert rc == EXIT_REFUSED and "faulted" in out
    fake = FakePipeline("ok")
    rc, out = cli(checkout, "run", "base", pipeline=fake)
    assert rc == EXIT_OK, out
    assert [t["to"] for t in transitions(checkout, "base")] == ["running", "abandoned", "running"]
    assert fake.calls == [("base", 1)]
    assert not worktree_of(checkout, "base").exists()
