"""Checkpoint pushing is durable and crosses only the public Git seam."""

from datetime import datetime, timezone
from pathlib import Path

from squatch.daemon import compose_daemon_checkpoint
from squatch.journal import Journal


NOW = datetime(2026, 9, 27, 12, 0, tzinfo=timezone.utc)


class FakeGit:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    async def push(self, repo: Path) -> None:
        self.calls.append(repo)


async def test_daemon_composition_pushes_only_through_the_git_seam(tmp_path):
    git = FakeGit()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        checkpoint = compose_daemon_checkpoint(repo=tmp_path / "repo", git=git, journal=journal)
        await checkpoint.push("checkpoint-push", 1)

    assert git.calls == [tmp_path / "repo"]


async def test_restart_refires_an_incomplete_push_but_not_a_completed_one(tmp_path):
    repo = tmp_path / "repo"
    incomplete = FakeGit()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        checkpoint = compose_daemon_checkpoint(repo=repo, git=incomplete, journal=journal)
        original_push = incomplete.push

        async def interrupted_push(path: Path) -> None:
            await original_push(path)
            raise RuntimeError("interrupted after push")

        incomplete.push = interrupted_push  # type: ignore[method-assign]
        try:
            await checkpoint.push("checkpoint-push", 1)
        except RuntimeError:
            pass

    retried = FakeGit()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        checkpoint = compose_daemon_checkpoint(repo=repo, git=retried, journal=journal)
        await checkpoint.push("checkpoint-push", 1)

    completed = FakeGit()
    with Journal(tmp_path, clock=lambda: NOW) as journal:
        checkpoint = compose_daemon_checkpoint(repo=repo, git=completed, journal=journal)
        await checkpoint.push("checkpoint-push", 1)

    assert incomplete.calls == [repo]
    assert retried.calls == [repo]
    assert completed.calls == []
