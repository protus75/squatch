"""git.py: every git call is an argv list, dir-pinned, through the process seam
(SQUATCH_PLAN.md section 10, D1).

The fake seam records each spawn so a test can assert the exact argv, cwd, env
and timeout a wrapper hands to the process seam; one test drives the real
`SubprocessExec` against a temp repo to prove the argv shapes are ones git
actually accepts.
"""

import os
from pathlib import Path

import pytest

from squatch import git as gitmod
from squatch.git import Git, GitError, RebaseConflict, StatusEntry
from squatch.seams import SubprocessExec

ENV = {"PATH": "/usr/bin", "HOME": "/nowhere"}


class FakeProcessExec:
    def __init__(self, results=None):
        self.calls = []
        # Queue of (rc, out, err) consumed in call order; default success.
        self.results = list(results or [])

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None):
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": env,
                           "timeout": timeout, "stdin_path": stdin_path})
        if self.results:
            return self.results.pop(0)
        return 0, "", ""


def make(results=None, **kw):
    px = FakeProcessExec(results)
    return px, Git(px, env=ENV, timeout=30.0, **kw)


REPO = Path("/repo")


def argv(px, i=0):
    return px.calls[i]["argv"]


# --- construction and pinning -------------------------------------------------

def test_env_is_required_keyword():
    px = FakeProcessExec()
    with pytest.raises(TypeError):
        Git(px, timeout=30.0)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        Git(px, ENV, 30.0)  # type: ignore[misc]


async def test_every_call_is_dir_pinned_argv_with_declared_env_and_timeout():
    px, git = make()
    await git.status(REPO)
    call = px.calls[0]
    assert call["argv"][:3] == ["git", "-C", "/repo"]
    assert all(isinstance(a, str) for a in call["argv"])
    assert call["cwd"] == REPO
    assert call["env"] == ENV
    assert call["timeout"] == 30.0
    assert call["stdin_path"] is None


async def test_nonzero_rc_raises_git_error_with_argv_and_stderr():
    px, git = make([(128, "", "fatal: not a git repository")])
    with pytest.raises(GitError) as ei:
        await git.rev_parse(REPO, "HEAD")
    err = ei.value
    assert err.rc == 128
    assert err.argv == argv(px)
    assert "not a git repository" in err.stderr
    assert "not a git repository" in str(err)


# --- the Phase-1 op set ---------------------------------------------------------

async def test_init():
    px, git = make()
    await git.init(REPO)
    assert argv(px) == ["git", "-C", "/repo", "init", "-q", "-b", "main"]


async def test_status_porcelain_parses_entries():
    px, git = make([(0, " M a.py\n?? new/\nA  b.txt\n", "")])
    entries = await git.status(REPO)
    assert argv(px) == ["git", "-C", "/repo", "status", "--porcelain"]
    assert entries == [StatusEntry(" M", "a.py"), StatusEntry("??", "new/"),
                       StatusEntry("A ", "b.txt")]


async def test_status_clean_is_empty_list():
    px, git = make([(0, "", "")])
    assert await git.status(REPO) == []


async def test_rev_parse_strips_output():
    px, git = make([(0, "abc123\n", "")])
    assert await git.rev_parse(REPO, "main") == "abc123"
    assert argv(px) == ["git", "-C", "/repo", "rev-parse", "--verify", "main"]


async def test_git_common_dir_strips_output():
    px, git = make([(0, ".git\n", "")])
    assert await git.git_common_dir(REPO) == ".git"
    assert argv(px) == ["git", "-C", "/repo", "rev-parse", "--git-common-dir"]


async def test_diff_names_uses_three_dot_range():
    px, git = make([(0, "a.py\nb/c.py\n", "")])
    names = await git.diff_names(REPO, "main", "stem-1")
    assert argv(px) == ["git", "-C", "/repo", "diff", "--name-only", "main...stem-1"]
    assert names == ["a.py", "b/c.py"]


async def test_diff_returns_patch_text_verbatim():
    patch = "diff --git a/x b/x\n+line\n"
    px, git = make([(0, patch, "")])
    assert await git.diff(REPO, "main", "stem-1") == patch
    assert argv(px) == ["git", "-C", "/repo", "diff", "main...stem-1"]


async def test_diff_stat_includes_worktree_changes_from_base():
    px, git = make([(0, " a.py | 2 +-\n", "")])
    assert await git.diff_stat(REPO, "abc123") == " a.py | 2 +-\n"
    assert argv(px) == ["git", "-C", "/repo", "diff", "--stat", "abc123"]


async def test_diff_stat_appends_untracked_names_without_their_content():
    px, git = make([(0, " a.py | 2 +-\n", ""), (0, "new.py\n", "")])
    assert await git.diff_stat(REPO, "abc123") == " a.py | 2 +-\n new.py | untracked\n"
    assert argv(px, 1) == ["git", "-C", "/repo", "ls-files", "--others",
                           "--exclude-standard"]


async def test_add_is_explicit_paths_after_separator():
    px, git = make()
    await git.add(REPO, ["a.py", Path("tickets/x/run.md")])
    assert argv(px) == ["git", "-C", "/repo", "add", "--", "a.py", "tickets/x/run.md"]


async def test_add_refuses_empty_paths():
    px, git = make()
    with pytest.raises(ValueError):
        await git.add(REPO, [])
    assert px.calls == []


async def test_commit_passes_message_as_single_argv_element_and_returns_sha():
    msg = "squatch(stem): goal\n\nsquatch-ticket: stem\nsquatch-reviewed-sha: abc\n"
    px, git = make([(0, "", ""), (0, "deadbeef\n", "")])
    sha = await git.commit(REPO, msg)
    assert argv(px, 0) == ["git", "-C", "/repo", "commit", "-q", "-m", msg]
    assert argv(px, 1) == ["git", "-C", "/repo", "rev-parse", "--verify", "HEAD"]
    assert sha == "deadbeef"


async def test_commit_with_paths_is_a_pathspec_commit():
    px, git = make([(0, "", ""), (0, "deadbeef\n", "")])
    await git.commit(REPO, "squatch(x): ticket", ["tickets/x/ticket.md"])
    assert argv(px, 0) == ["git", "-C", "/repo", "commit", "-q", "-m", "squatch(x): ticket",
                           "--", "tickets/x/ticket.md"]


async def test_branch_create_and_delete():
    px, git = make()
    await git.branch(REPO, "stem-1", "main")
    await git.branch_delete(REPO, "stem-1")
    assert argv(px, 0) == ["git", "-C", "/repo", "branch", "stem-1", "main"]
    assert argv(px, 1) == ["git", "-C", "/repo", "branch", "-D", "stem-1"]


async def test_worktree_add_creates_branch_at_path():
    px, git = make()
    await git.worktree_add(REPO, Path("/wt/stem-1"), "stem-1", "main")
    assert argv(px) == ["git", "-C", "/repo", "worktree", "add", "-b", "stem-1",
                        "/wt/stem-1", "main"]


async def test_worktree_add_detached_checks_out_named_commit_without_a_branch():
    px, git = make()
    await git.worktree_add_detached(REPO, Path("/wt/base"), "abc123")
    assert argv(px) == ["git", "-C", "/repo", "worktree", "add", "--detach",
                        "/wt/base", "abc123"]


async def test_worktree_remove_is_remove_then_prune_never_rm_rf():
    px, git = make()
    await git.worktree_remove(REPO, Path("/wt/stem-1"))
    assert argv(px, 0) == ["git", "-C", "/repo", "worktree", "remove", "--force",
                           "/wt/stem-1"]
    assert argv(px, 1) == ["git", "-C", "/repo", "worktree", "prune"]
    assert len(px.calls) == 2


async def test_worktree_prune_alone():
    px, git = make()
    await git.worktree_prune(REPO)
    assert argv(px) == ["git", "-C", "/repo", "worktree", "prune"]


async def test_rebase_success():
    px, git = make()
    await git.rebase(Path("/wt/stem-1"), "main")
    assert argv(px) == ["git", "-C", "/wt/stem-1", "rebase", "main"]
    assert len(px.calls) == 1


async def test_rebase_failure_aborts_before_raising():
    px, git = make([(1, "", "CONFLICT (content): Merge conflict in a.py"),
                    (0, "", "")])
    with pytest.raises(RebaseConflict) as ei:
        await git.rebase(Path("/wt/stem-1"), "main")
    assert argv(px, 1) == ["git", "-C", "/wt/stem-1", "rebase", "--abort"]
    assert "CONFLICT" in ei.value.stderr
    assert isinstance(ei.value, GitError)


async def test_rebase_abort_failure_does_not_mask_the_conflict():
    px, git = make([(1, "", "CONFLICT"), (128, "", "fatal: No rebase in progress?")])
    with pytest.raises(RebaseConflict) as ei:
        await git.rebase(Path("/wt/stem-1"), "main")
    assert ei.value.stderr == "CONFLICT"


async def test_rebase_abort():
    px, git = make()
    await git.rebase_abort(Path("/wt/stem-1"))
    assert argv(px) == ["git", "-C", "/wt/stem-1", "rebase", "--abort"]


async def test_restore_from_source_into_index_and_worktree():
    px, git = make()
    await git.restore(Path("/wt/stem-1"), ["tickets"], source="main")
    assert argv(px) == ["git", "-C", "/wt/stem-1", "restore", "--source", "main",
                        "--staged", "--worktree", "--", "tickets"]


async def test_merge_squash():
    px, git = make()
    await git.merge_squash(REPO, "stem-1")
    assert argv(px) == ["git", "-C", "/repo", "merge", "--squash", "stem-1"]


async def test_describe_for_lockfile_identity():
    px, git = make([(0, "v0.1.0-3-gabc123-dirty\n", "")])
    assert await git.describe(REPO) == "v0.1.0-3-gabc123-dirty"
    assert argv(px) == ["git", "-C", "/repo", "describe", "--tags", "--always",
                        "--dirty"]


def test_module_never_imports_shell_machinery():
    # D1: no shell, no string assembly. The module reaches processes only
    # through the seam handed to it.
    src = Path(gitmod.__file__).read_text()
    for banned in ("subprocess", "shell=True", "os.system", "shlex", "rm -rf"):
        assert banned not in src, banned


# --- one real repo through the real seam --------------------------------------

def _git_env(tmp_path: Path) -> dict[str, str]:
    # A hermetic child env: no user config, no hooks from the operator's HOME,
    # committer identity supplied so `commit` needs nothing from the machine.
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
        "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test",
    }


async def test_real_repo_ticket_branch_roundtrip(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(SubprocessExec(), env=_git_env(tmp_path), timeout=60.0)

    await git.init(repo)
    assert Path(await git.git_common_dir(repo)) == Path(".git")
    (repo / "a.txt").write_text("base\n")
    await git.add(repo, ["a.txt"])
    base = await git.commit(repo, "base")
    assert base == await git.rev_parse(repo, "HEAD")
    assert await git.status(repo) == []
    assert await git.rev_parse(repo, "main") == base
    await git.branch(repo, "aux", base)
    assert await git.rev_parse(repo, "aux") == base

    wt = tmp_path / "worktrees" / "stem-1"
    await git.worktree_add(repo, wt, "stem-1", "main")
    assert Path(await git.git_common_dir(wt)).resolve() == (repo / ".git").resolve()
    (wt / "b.txt").write_text("feature\n")
    (wt / "tickets" / "stem-1").mkdir(parents=True)
    (wt / "tickets" / "stem-1" / "run.md").write_text("outbox\n")
    assert await git.status(wt) == [StatusEntry("??", "b.txt"),
                                    StatusEntry("??", "tickets/")]
    await git.add(wt, ["b.txt"])
    await git.commit(wt, "wip")

    # main advances underneath the branch; the branch rebases cleanly.
    (repo / "a.txt").write_text("base2\n")
    await git.add(repo, ["a.txt"])
    await git.commit(repo, "advance")
    await git.rebase(wt, "main")
    assert await git.diff_names(repo, "main", "stem-1") == ["b.txt"]
    assert "+feature" in await git.diff(repo, "main", "stem-1")

    # restore puts a worktree-side change to a tracked path back to main's content
    (wt / "a.txt").write_text("drift\n")
    await git.restore(wt, ["a.txt"], source="main")
    assert (wt / "a.txt").read_text() == "base2\n"

    await git.merge_squash(repo, "stem-1")
    merged = await git.commit(repo, "squatch(stem-1): goal\n\nsquatch-ticket: stem-1\n")
    assert (repo / "b.txt").read_text() == "feature\n"
    assert merged != base

    await git.worktree_remove(repo, wt)
    assert not wt.exists()
    await git.branch_delete(repo, "stem-1")
    with pytest.raises(GitError):
        await git.rev_parse(repo, "stem-1")

    # Untagged: describe --always falls back to the abbreviated HEAD sha.
    assert merged.startswith(await git.describe(repo))


async def test_real_repo_detached_worktree_roundtrip_leaves_no_registry_entry(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(SubprocessExec(), env=_git_env(tmp_path), timeout=60.0)
    await git.init(repo)
    (repo / "a.txt").write_text("base\n")
    await git.add(repo, ["a.txt"])
    base = await git.commit(repo, "base")
    wt = tmp_path / "worktrees" / "base"

    await git.worktree_add_detached(repo, wt, base)
    assert await git.rev_parse(wt, "HEAD") == base
    await git.worktree_remove(repo, wt)

    assert not wt.exists()
    registered = await git._run(repo, "worktree", "list", "--porcelain")
    assert str(wt) not in registered


async def test_real_repo_conflicted_rebase_is_aborted(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = Git(SubprocessExec(), env=_git_env(tmp_path), timeout=60.0)
    await git.init(repo)
    (repo / "a.txt").write_text("base\n")
    await git.add(repo, ["a.txt"])
    await git.commit(repo, "base")
    wt = tmp_path / "wt"
    await git.worktree_add(repo, wt, "stem-1", "main")
    (wt / "a.txt").write_text("branch\n")
    await git.add(wt, ["a.txt"])
    head = await git.commit(wt, "branch change")
    (repo / "a.txt").write_text("main\n")
    await git.add(repo, ["a.txt"])
    await git.commit(repo, "main change")

    with pytest.raises(RebaseConflict):
        await git.rebase(wt, "main")
    # Aborted: the worktree sits on its own branch head, no rebase in progress.
    assert await git.rev_parse(wt, "HEAD") == head
    assert await git.status(wt) == []
    assert not (repo / ".git" / "worktrees" / "wt" / "rebase-merge").exists()
