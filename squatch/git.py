"""Thin typed git wrappers (SQUATCH_PLAN.md section 10, D1).

Every call is an argv list pinned with `git -C <dir>` and run through the
process-exec seam with the caller's explicit child `env`; nothing here knows
about shells or string-assembled commands. The op set is section 10's Phase-1
enumeration and grows only with that list. Worktree cleanup is
`worktree remove` + `worktree prune`: removing the directory any other way
leaves git's worktree registry pointing at nothing.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from squatch.seams import ProcessExec


class GitError(Exception):
    def __init__(self, argv: list[str], rc: int, stdout: str, stderr: str):
        self.argv = argv
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"{' '.join(argv)!s} -> rc {rc}: {stderr.strip()}")


class RebaseConflict(GitError):
    """The rebase stopped on conflicted paths.

    ``rebase`` aborts before raising this exception; ``rebase_stop_at_conflict``
    deliberately leaves the conflicted rebase in progress for inspection.
    """


@dataclass(frozen=True)
class StatusEntry:
    code: str   # the two porcelain status columns, verbatim (e.g. " M", "??")
    path: str


class Git:
    def __init__(self, process: ProcessExec, *, env: Mapping[str, str], timeout: float):
        self._process = process
        self._env = env
        self._timeout = timeout

    async def _run(self, cwd: Path, *args: str) -> str:
        argv = ["git", "-C", str(cwd), *args]
        rc, out, err = await self._process.run(argv, cwd=cwd, env=self._env,
                                               timeout=self._timeout)
        if rc != 0:
            raise GitError(argv, rc, out, err)
        return out

    async def init(self, repo: Path) -> None:
        # Local `main` is the blessed line (section 10); never the machine's
        # init.defaultBranch.
        await self._run(repo, "init", "-q", "-b", "main")

    async def status(self, cwd: Path) -> list[StatusEntry]:
        out = await self._run(cwd, "status", "--porcelain")
        return [StatusEntry(line[:2], line[3:]) for line in out.splitlines() if line]

    async def rev_parse(self, cwd: Path, rev: str) -> str:
        return (await self._run(cwd, "rev-parse", "--verify", rev)).strip()

    async def git_common_dir(self, cwd: Path) -> str:
        return (await self._run(cwd, "rev-parse", "--git-common-dir")).strip()

    async def diff_names(self, cwd: Path, base: str, branch: str) -> list[str]:
        out = await self._run(cwd, "diff", "--name-only", f"{base}...{branch}")
        return [line for line in out.splitlines() if line]

    async def diff(self, cwd: Path, base: str, branch: str) -> str:
        return await self._run(cwd, "diff", f"{base}...{branch}")

    async def untracked_names(self, cwd: Path) -> list[str]:
        out = await self._run(cwd, "ls-files", "--others", "--exclude-standard")
        return [line for line in out.splitlines() if line]

    async def ls_files(self, cwd: Path) -> list[str]:
        """The tracked paths in the named checkout."""
        out = await self._run(cwd, "ls-files")
        return [line for line in out.splitlines() if line]

    async def diff_stat(self, cwd: Path, base: str) -> str:
        """Names and counts from base through all worktree changes."""
        stat = await self._run(cwd, "diff", "--stat", base)
        untracked = await self.untracked_names(cwd)
        if not untracked:
            return stat
        new_files = "".join(f" {name} | untracked\n" for name in untracked)
        return stat + new_files

    async def add(self, cwd: Path, paths: Sequence[str | Path]) -> None:
        # Explicit paths only: `add -A` would sweep worktree debris into the
        # commit, and an empty list would silently add nothing.
        if not paths:
            raise ValueError("git add needs at least one explicit path")
        await self._run(cwd, "add", "--", *(str(p) for p in paths))

    async def commit(self, cwd: Path, message: str, paths: Sequence[str | Path] = ()) -> str:
        # A pathspec commits ONLY those paths: whatever else sits staged stays
        # staged, so a lane-fenced writer cannot sweep pre-staged bytes along.
        await self._run(cwd, "commit", "-q", "-m", message,
                        *(("--", *(str(p) for p in paths)) if paths else ()))
        return await self.rev_parse(cwd, "HEAD")

    async def branch(self, cwd: Path, name: str, start_point: str) -> None:
        await self._run(cwd, "branch", name, start_point)

    async def branch_delete(self, cwd: Path, name: str) -> None:
        await self._run(cwd, "branch", "-D", name)

    async def worktree_add(self, repo: Path, path: Path, branch: str, start_point: str) -> None:
        await self._run(repo, "worktree", "add", "-b", branch, str(path), start_point)

    async def worktree_add_detached(self, repo: Path, path: Path, commit: str) -> None:
        await self._run(repo, "worktree", "add", "--detach", str(path), commit)

    async def worktree_remove(self, repo: Path, path: Path) -> None:
        # --force: uncommitted debris is wiped with the worktree (section 10).
        await self._run(repo, "worktree", "remove", "--force", str(path))
        await self.worktree_prune(repo)

    async def worktree_prune(self, repo: Path) -> None:
        await self._run(repo, "worktree", "prune")

    async def rebase(self, cwd: Path, onto: str) -> None:
        try:
            await self._run(cwd, "rebase", onto)
        except GitError as e:
            # Abort before refusing so no rebase is left in progress; the
            # abort's own outcome never masks the conflict being reported.
            try:
                await self.rebase_abort(cwd)
            except GitError:
                pass
            raise RebaseConflict(e.argv, e.rc, e.stdout, e.stderr) from None

    async def rebase_stop_at_conflict(self, cwd: Path, onto: str) -> None:
        """Rebase while leaving a conflicted worktree available for inspection."""
        try:
            await self._run(cwd, "rebase", onto)
        except GitError as error:
            try:
                conflicted = await self.conflicted_paths(cwd)
            except GitError:
                conflicted = []
            if not conflicted:
                # Git can fail after entering rebase state without producing
                # unmerged paths.  Abort opportunistically: when it refused
                # before starting, the abort fails harmlessly.
                try:
                    await self.rebase_abort(cwd)
                except GitError:
                    pass
                raise error from None
            raise RebaseConflict(
                error.argv, error.rc, error.stdout, error.stderr) from None

    async def conflicted_paths(self, cwd: Path) -> list[str]:
        out = await self._run(cwd, "diff", "--name-only", "--diff-filter=U")
        return [line for line in out.splitlines() if line]

    async def rebase_continue(self, cwd: Path) -> None:
        await self._run(cwd, "-c", "core.editor=true", "rebase", "--continue")

    async def rebase_abort(self, cwd: Path) -> None:
        await self._run(cwd, "rebase", "--abort")

    async def restore(self, cwd: Path, paths: Sequence[str | Path], *, source: str) -> None:
        await self._run(cwd, "restore", "--source", source, "--staged", "--worktree",
                        "--", *(str(p) for p in paths))

    async def merge_squash(self, cwd: Path, branch: str) -> None:
        await self._run(cwd, "merge", "--squash", branch)

    async def push(self, cwd: Path) -> None:
        """Push the checkout's configured upstream through the Git seam."""
        await self._run(cwd, "push")

    async def describe(self, cwd: Path) -> str:
        return (await self._run(cwd, "describe", "--tags", "--always", "--dirty")).strip()
