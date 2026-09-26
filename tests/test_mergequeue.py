"""Direct proofs for the dormant serial merge-admission construction."""

import asyncio
import inspect
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

import squatch.git as git_module
import squatch.mergequeue as mergequeue_module
from squatch.config import parse
from squatch.git import Git, GitError, RebaseConflict
from squatch.journal import Journal
from squatch.merge import Merge, Pipeline, compose_merge_queue, compose_pipeline
from squatch.mergequeue import (
    CONFLICT_FACTS_SIGNAL,
    REBASE_FAILURE_ROAD,
    Candidate,
    CandidateRebaseFinding,
    CandidateTreeHashFinding,
    MergeQueue,
    UnresolvedConflictHandoff,
)
from squatch.seams import LocalFilesystem, SubprocessExec


def config(*strategies):
    return parse({
        "schema_version": 1,
        "state_dir": ".state",
        "providers": [],
        "routing": [],
        "merge": {"strategies": list(strategies)},
    }, source="test")


def git_env(tmp_path: Path) -> dict[str, str]:
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
        "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test",
    }


async def fixture_repo(tmp_path: Path, *, path: str = "shared.txt"):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = git_env(tmp_path)
    git = Git(SubprocessExec(), env=env, timeout=60.0)
    await git.init(repo)
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text("start\n")
    await git.add(repo, [path])
    await git.commit(repo, "base")
    return repo, env, git


async def divergent_candidate(tmp_path: Path, *, stem: str = "candidate",
                              path: str = "shared.txt"):
    repo, env, git = await fixture_repo(tmp_path, path=path)
    worktree = tmp_path / stem
    await git.worktree_add(repo, worktree, stem, "main")
    (worktree / path).write_text("start\nbranch\n")
    await git.add(worktree, [path])
    branch_head = await git.commit(worktree, f"{stem} change")
    (repo / path).write_text("start\nmain\n")
    await git.add(repo, [path])
    await git.commit(repo, "main change")
    return repo, worktree, env, git, branch_head


def queue(repo, env, git, journal, cfg, *, regate, integration, integrate):
    return MergeQueue(
        repo=repo, config=cfg, git=git, process=SubprocessExec(),
        fs=LocalFilesystem(), journal=journal, env=env,
        regate=regate, integration_check=integration, integrate=integrate)


async def green(_candidate):
    return ()


async def test_post_rebase_regate_and_integration_check_precede_tree_assert_and_integration(
        tmp_path):
    repo, env, git = await fixture_repo(tmp_path, path="base.txt")
    worktree = tmp_path / "candidate"
    await git.worktree_add(repo, worktree, "candidate", "main")
    (worktree / "feature.txt").write_text("branch\n")
    await git.add(worktree, ["feature.txt"])
    branch_head = await git.commit(worktree, "candidate change")
    (repo / "base.txt").write_text("start\nmain\n")
    await git.add(repo, ["base.txt"])
    await git.commit(repo, "main change")
    order = []

    async def regate(candidate):
        order.append("post-rebase-regate")
        assert (candidate.worktree / "feature.txt").read_text() == "branch\n"
        assert (candidate.worktree / "base.txt").read_text() == "start\nmain\n"
        assert await git.rev_parse(candidate.worktree, "HEAD") != branch_head
        return ()

    async def integration(candidate):
        order.append("integration-check")
        assert (candidate.worktree / "feature.txt").read_text() == "branch\n"
        return ()

    async def integrate(candidate):
        order.append("integrate")
        await git.merge_squash(repo, candidate.branch)
        await git.commit(repo, "integrated", ["feature.txt"])

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, config(), regate=regate,
                  integration=integration, integrate=integrate)
        result = await q.admit(Candidate(
            stem="candidate", branch="candidate", worktree=worktree, run_seq=7))

    assert result.outcome == "integrated"
    assert order == ["post-rebase-regate", "integration-check", "integrate"]
    assert result.checked_tree == await git.rev_parse(repo, "main^{tree}")


async def test_concurrent_admissions_share_one_non_preemptive_serial_slot(tmp_path):
    repo, env, git = await fixture_repo(tmp_path, path="base.txt")
    candidates = []
    for stem in ("first", "second"):
        worktree = tmp_path / stem
        await git.worktree_add(repo, worktree, stem, "main")
        (worktree / f"{stem}.txt").write_text(f"{stem}\n")
        await git.add(worktree, [f"{stem}.txt"])
        await git.commit(worktree, stem)
        candidates.append(Candidate(
            stem=stem, branch=stem, worktree=worktree, run_seq=1))

    first_started = asyncio.Event()
    release_first = asyncio.Event()
    calls = []
    active = maximum_active = 0

    async def regate(candidate):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        calls.append(candidate.stem)
        if candidate.stem == "first":
            first_started.set()
            await release_first.wait()
        active -= 1
        return ()

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, config(), regate=regate,
                  integration=green, integrate=lambda candidate: _nothing())
        first = asyncio.create_task(q.admit(candidates[0]))
        await first_started.wait()
        second = asyncio.create_task(q.admit(candidates[1]))
        await asyncio.sleep(0)
        assert calls == ["first"]
        release_first.set()
        results = await asyncio.gather(first, second)

    assert [result.outcome for result in results] == ["integrated", "integrated"]
    assert calls == ["first", "second"] and maximum_active == 1


@pytest.mark.parametrize("path, prefix", [
    ("shared.txt", "shared.txt"),
    ("generated/x.lock", "generated"),
    ("generated/x.lock", "generated/"),
])
async def test_fixture_conflict_uses_union_rung_and_journals_conflict_facts(
        tmp_path, path, prefix):
    repo, worktree, env, git, _ = await divergent_candidate(tmp_path, path=path)
    cfg = config({"paths": [prefix], "strategy": "union"})

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, cfg, regate=green,
                  integration=green, integrate=lambda candidate: _nothing())
        result = await q.admit(Candidate(
            stem="candidate", branch="candidate", worktree=worktree, run_seq=2))
        events = tuple(journal.read())

    assert result.outcome == "integrated"
    assert (worktree / path).read_text() == "start\nmain\nbranch\n"
    assert result.conflict_facts.model_dump() == {
        "stem": "candidate", "paths": (path,), "rung": "mechanical",
        "strategy_hits": ({"path": path, "strategy": "union"},),
        "integration_red_paths": (),
    }
    [event] = [event for event in events
               if event.type == "signal" and event.body.get("kind") == CONFLICT_FACTS_SIGNAL]
    assert event.ticket == "candidate" and event.body["rung"] == "mechanical"


@pytest.mark.parametrize("prefix", ["*.lock", "generated/?.lock", "generated/[x].lock",
                                         "generate"])
async def test_strategy_declarations_are_literal_prefixes(tmp_path, prefix):
    repo, worktree, env, git, branch_head = await divergent_candidate(
        tmp_path, path="generated/x.lock")
    cfg = config({"paths": [prefix], "strategy": "union"})
    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, cfg, regate=green,
                  integration=green, integrate=lambda candidate: _nothing())
        result = await q.admit(Candidate(
            stem="candidate", branch="candidate", worktree=worktree, run_seq=2))
        handoff = await q.next_rework()

    assert result.outcome == "rework" and handoff is result.rework
    assert result.conflict_facts.paths == ("generated/x.lock",)
    assert result.conflict_facts.strategy_hits == ()
    assert await git.rev_parse(worktree, "HEAD") == branch_head
    assert await git.status(worktree) == []


async def _nothing():
    return None


async def test_unresolved_conflict_aborts_before_typed_rework_handoff_is_consumable(tmp_path):
    repo, worktree, env, git, branch_head = await divergent_candidate(tmp_path)
    aborted = False
    rebase_abort = git.rebase_abort

    async def track_abort(cwd):
        nonlocal aborted
        await rebase_abort(cwd)
        aborted = True

    git.rebase_abort = track_abort

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, config(), regate=green,
                  integration=green, integrate=lambda candidate: _nothing())
        put = q._rework.put_nowait

        def publish(handoff):
            assert aborted and not q._slot.locked()
            put(handoff)

        q._rework.put_nowait = publish

        async def consume_in_rework() -> UnresolvedConflictHandoff:
            handoff = await q.next_rework()
            assert isinstance(handoff, UnresolvedConflictHandoff)
            assert not q._slot.locked()
            return handoff

        consumer = asyncio.create_task(consume_in_rework())
        result = await q.admit(Candidate(
            stem="candidate", branch="candidate", worktree=worktree, run_seq=3))
        handoff = await consumer

    assert result.outcome == "rework"
    assert handoff is result.rework and isinstance(handoff, UnresolvedConflictHandoff)
    assert handoff.approval_invalidated is True
    assert handoff.facts.rung == "rework" and handoff.facts.paths == ("shared.txt",)
    assert await git.rev_parse(worktree, "HEAD") == branch_head
    assert await git.status(worktree) == []
    state_paths = [(await git._run(worktree, "rev-parse", "--git-path", name)).strip()
        for name in ("rebase-merge", "rebase-apply")]
    assert not any(Path(path).exists() for path in state_paths)


@pytest.mark.parametrize("continue_failure", [False, True])
async def test_failed_abort_is_one_typed_refusal_with_facts_and_no_rework(
        tmp_path, continue_failure):
    repo, worktree, env, git, _ = await divergent_candidate(tmp_path)
    clean = tmp_path / "clean"
    await git.worktree_add(repo, clean, "clean", "main")
    main_before = await git.rev_parse(repo, "main")
    aborts = []

    async def fail_abort(cwd):
        aborts.append(cwd)
        raise GitError(["git", "rebase", "--abort"], 1, "", "abort failed")

    git.rebase_abort = fail_abort
    cfg = config()
    if continue_failure:
        cfg = config({"paths": ["shared.txt"], "strategy": "union"})

        async def fail_continue(cwd):
            # The resolver staged all conflicts before continue failed.
            assert await git.conflicted_paths(cwd) == []
            raise GitError(["git", "rebase", "--continue"], 1, "", "continue failed")

        git.rebase_continue = fail_continue
    integrated = []

    async def integrate(candidate):
        integrated.append(candidate.stem)

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, cfg, regate=green,
                  integration=green, integrate=integrate)
        refused = await q.admit(Candidate(
            stem="candidate", branch="candidate", worktree=worktree, run_seq=8))
        assert not q._slot.locked() and q._rework.empty()
        accepted = await q.admit(Candidate(
            stem="clean", branch="clean", worktree=clean, run_seq=8))
        events = tuple(journal.read())

    assert aborts == [worktree]
    assert refused.outcome == "gate_failed" and refused.rework is None
    [finding] = refused.findings
    assert isinstance(finding, CandidateRebaseFinding)
    assert "abort failed" in finding.message and finding.paved_road
    assert refused.conflict_facts.paths == ("shared.txt",)
    assert len(refused.conflict_facts.strategy_hits) == int(continue_failure)
    [event] = [event for event in events if event.ticket == "candidate"]
    assert event.body["kind"] == CONFLICT_FACTS_SIGNAL
    assert event.body["paths"] == ["shared.txt"]
    assert accepted.outcome == "integrated" and integrated == ["clean"]
    assert await git.rev_parse(repo, "main") == main_before
    assert not hasattr(q, "pause") and not hasattr(q, "hold")


async def test_tree_mismatch_refuses_only_candidate_leaves_main_and_releases_slot(tmp_path):
    repo, env, git = await fixture_repo(tmp_path, path="base.txt")
    first = tmp_path / "first"
    second = tmp_path / "second"
    await git.worktree_add(repo, first, "first", "main")
    (first / "first.txt").write_text("first\n")
    await git.add(first, ["first.txt"])
    await git.commit(first, "first")
    await git.worktree_add(repo, second, "second", "main")
    (second / "second.txt").write_text("second\n")
    await git.add(second, ["second.txt"])
    await git.commit(second, "second")
    main_before = await git.rev_parse(repo, "main^{tree}")
    integrated = []

    async def integration(candidate):
        if candidate.stem == "first":
            (candidate.worktree / "late.txt").write_text("changed after check began\n")
            await git.add(candidate.worktree, ["late.txt"])
            await git.commit(candidate.worktree, "late mutation")
        return ()

    async def integrate(candidate):
        integrated.append(candidate.stem)

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, config(), regate=green,
                  integration=integration, integrate=integrate)
        refused = await q.admit(Candidate(
            stem="first", branch="first", worktree=first, run_seq=1))
        accepted = await q.admit(Candidate(
            stem="second", branch="second", worktree=second, run_seq=1))

    assert refused.outcome == "gate_failed"
    [finding] = refused.findings
    assert isinstance(finding, CandidateTreeHashFinding)
    assert finding.code == "candidate_tree_hash" and finding.paved_road
    assert await git.rev_parse(repo, "main^{tree}") == main_before
    assert accepted.outcome == "integrated" and integrated == ["second"]
    assert not hasattr(q, "pause") and not hasattr(q, "hold")


async def test_pre_start_rebase_failure_is_typed_and_releases_slot(tmp_path):
    repo, env, git = await fixture_repo(tmp_path, path="base.txt")
    dirty = tmp_path / "dirty"
    clean = tmp_path / "clean"
    await git.worktree_add(repo, dirty, "dirty", "main")
    await git.worktree_add(repo, clean, "clean", "main")
    (dirty / "base.txt").write_text("uncommitted\n")
    aborts = []
    rebase_abort = git.rebase_abort

    async def track_abort(cwd):
        aborts.append(cwd)
        await rebase_abort(cwd)

    git.rebase_abort = track_abort
    integrated = []

    async def integrate(candidate):
        integrated.append(candidate.stem)

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, config(), regate=green,
                  integration=green, integrate=integrate)
        refused = await q.admit(Candidate(
            stem="dirty", branch="dirty", worktree=dirty, run_seq=1))
        accepted = await q.admit(Candidate(
            stem="clean", branch="clean", worktree=clean, run_seq=1))
        events = tuple(journal.read())

    assert refused.outcome == "gate_failed"
    [finding] = refused.findings
    assert isinstance(finding, CandidateRebaseFinding)
    assert finding.code == "candidate_rebase" and finding.paved_road
    assert refused.conflict_facts.paths == () and aborts == [dirty]
    assert accepted.outcome == "integrated" and integrated == ["clean"]
    assert any(event.ticket == "dirty" and event.body.get("rung") == "none"
               for event in events)


async def test_rebase_failure_after_start_aborts_and_restores_branch_head(tmp_path):
    repo, env, git = await fixture_repo(tmp_path, path="base.txt")
    blocked = tmp_path / "blocked"
    await git.worktree_add(repo, blocked, "blocked", "main")
    (blocked / "collision.txt").write_text("committed then removed\n")
    await git.add(blocked, ["collision.txt"])
    await git.commit(blocked, "add collision")
    (blocked / "collision.txt").unlink()
    await git.add(blocked, ["collision.txt"])
    branch_head = await git.commit(blocked, "remove collision")
    (blocked / "collision.txt").write_text("untracked obstruction\n")
    aborts_with_rebase_state = []
    rebase_abort = git.rebase_abort

    async def track_abort(cwd):
        state_paths = [(await git._run(cwd, "rev-parse", "--git-path", name)).strip()
            for name in ("rebase-merge", "rebase-apply")]
        aborts_with_rebase_state.append(any(Path(path).exists() for path in state_paths))
        await rebase_abort(cwd)

    git.rebase_abort = track_abort

    (repo / "base.txt").write_text("start\nmain\n")
    await git.add(repo, ["base.txt"])
    await git.commit(repo, "move main")
    clean = tmp_path / "clean"
    await git.worktree_add(repo, clean, "clean", "main")
    integrated = []

    async def integrate(candidate):
        integrated.append(candidate.stem)

    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, config(), regate=green,
                  integration=green, integrate=integrate)
        refused = await q.admit(Candidate(
            stem="blocked", branch="blocked", worktree=blocked, run_seq=1))
        accepted = await q.admit(Candidate(
            stem="clean", branch="clean", worktree=clean, run_seq=1))

    assert refused.outcome == "gate_failed"
    [finding] = refused.findings
    assert isinstance(finding, CandidateRebaseFinding)
    assert finding.paved_road == REBASE_FAILURE_ROAD
    assert await git.rev_parse(blocked, "HEAD") == branch_head
    assert aborts_with_rebase_state == [True]
    state_paths = [(await git._run(blocked, "rev-parse", "--git-path", name)).strip()
        for name in ("rebase-merge", "rebase-apply")]
    assert not any(Path(path).exists() for path in state_paths)
    assert accepted.outcome == "integrated" and integrated == ["clean"]


@pytest.mark.parametrize("fail_at", [2, 3])
@pytest.mark.parametrize("git_failure", [False, True])
async def test_conflict_inspection_exception_aborts_before_returning(
        tmp_path, fail_at, git_failure):
    repo, worktree, env, git, branch_head = await divergent_candidate(tmp_path)
    conflicted_paths = git.conflicted_paths
    calls = 0

    async def fail_in_resolution_loop(cwd):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            if git_failure:
                raise GitError(["git", "diff"], 1, "", "conflict inspection failed")
            raise RuntimeError("conflict inspection failed")
        return await conflicted_paths(cwd)

    async def fail_continue(cwd):
        raise GitError(["git", "rebase", "--continue"], 1, "", "continue failed")

    git.conflicted_paths = fail_in_resolution_loop
    git.rebase_continue = fail_continue
    cfg = config({"paths": ["shared.txt"], "strategy": "union"})
    with Journal(repo / ".state", clock=lambda: datetime.now(timezone.utc)) as journal:
        q = queue(repo, env, git, journal, cfg, regate=green,
                  integration=green, integrate=lambda candidate: _nothing())
        candidate = Candidate(
            stem="candidate", branch="candidate", worktree=worktree, run_seq=4)
        if git_failure:
            result = await q.admit(candidate)
            assert result.outcome == "gate_failed"
            assert isinstance(result.findings[0], CandidateRebaseFinding)
        else:
            with pytest.raises(RuntimeError, match="conflict inspection failed"):
                await q.admit(candidate)
        assert not q._slot.locked() and q._rework.empty()

    assert await git.rev_parse(worktree, "HEAD") == branch_head
    assert await git.status(worktree) == []
    state_paths = [(await git._run(worktree, "rev-parse", "--git-path", name)).strip()
        for name in ("rebase-merge", "rebase-apply")]
    assert not any(Path(path).exists() for path in state_paths)


class FakeProcess:
    def __init__(self, results=()):
        self.results = list(results)
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None):
        self.calls.append(list(argv))
        return self.results.pop(0) if self.results else (0, "", "")


async def test_git_conflict_seams_are_only_additions_and_old_rebase_still_aborts():
    process = FakeProcess([
        (1, "", "CONFLICT"),
        (0, "a.py\nb.py\n", ""),
        (0, "a.py\nb.py\n", ""),
        (0, "", ""),
        (1, "", "CONFLICT"),
        (0, "", ""),
    ])
    git = Git(process, env={}, timeout=1)
    with pytest.raises(RebaseConflict):
        await git.rebase_stop_at_conflict(Path("/work"), "main")
    assert await git.conflicted_paths(Path("/work")) == ["a.py", "b.py"]
    await git.rebase_continue(Path("/work"))
    with pytest.raises(RebaseConflict):
        await git.rebase(Path("/work"), "main")
    assert process.calls == [
        ["git", "-C", "/work", "rebase", "main"],
        ["git", "-C", "/work", "diff", "--name-only", "--diff-filter=U"],
        ["git", "-C", "/work", "diff", "--name-only", "--diff-filter=U"],
        ["git", "-C", "/work", "-c", "core.editor=true", "rebase", "--continue"],
        ["git", "-C", "/work", "rebase", "main"],
        ["git", "-C", "/work", "rebase", "--abort"],
    ]
    public = {name for name, member in inspect.getmembers(Git, inspect.iscoroutinefunction)
              if not name.startswith("_")}
    assert public - {
        "init", "status", "rev_parse", "git_common_dir", "diff_names", "diff",
        "untracked_names", "ls_files", "diff_stat", "add", "commit", "branch",
        "branch_delete", "worktree_add", "worktree_add_detached", "worktree_remove",
        "worktree_prune", "rebase", "rebase_abort", "restore", "merge_squash", "describe",
    } == {"rebase_stop_at_conflict", "conflicted_paths", "rebase_continue"}


async def test_stop_at_conflict_preserves_non_conflict_git_error():
    process = FakeProcess([(1, "", "dirty worktree"), (0, "", ""),
                           (1, "", "no rebase in progress")])
    git = Git(process, env={}, timeout=1)

    with pytest.raises(GitError) as caught:
        await git.rebase_stop_at_conflict(Path("/work"), "main")

    assert type(caught.value) is GitError
    assert process.calls == [
        ["git", "-C", "/work", "rebase", "main"],
        ["git", "-C", "/work", "diff", "--name-only", "--diff-filter=U"],
        ["git", "-C", "/work", "rebase", "--abort"],
    ]


def test_additive_composition_hook_does_not_change_phase1_composition(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    cfg = config()
    env = git_env(tmp_path)
    process = SubprocessExec()
    git = Git(process, env=env, timeout=60)
    with Journal(repo / cfg.state_dir, clock=lambda: datetime.now(timezone.utc)) as journal:
        pipeline = compose_pipeline(
            repo=repo, config=cfg, env=env, journal=journal,
            clock=lambda: datetime.now(timezone.utc), process=process,
            fs=LocalFilesystem(), git=git)
        dormant = compose_merge_queue(
            repo=repo, config=cfg, env=env, journal=journal, process=process,
            fs=LocalFilesystem(), git=git, regate=green,
            integration_check=green, integrate=lambda candidate: _nothing())
    assert isinstance(pipeline, Pipeline) and isinstance(pipeline.merge, Merge)
    assert isinstance(dormant, MergeQueue)
    assert not hasattr(pipeline, "merge_queue")


def test_mergequeue_has_no_scheduler_or_watcher_dependency():
    source = Path(mergequeue_module.__file__).read_text()
    assert "squatch.scheduler" not in source and "squatch.watcher" not in source
    assert inspect.getsource(git_module.Git.rebase).count("rebase_abort") == 1
