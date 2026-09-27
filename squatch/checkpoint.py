"""Durable checkpoint publication through the Git seam."""

from pathlib import Path

from squatch.effects import Effects, effect_key
from squatch.git import Git
from squatch.journal import Journal


class Checkpoint:
    """Push one ticket run once its completion has been durably recorded."""

    def __init__(self, *, repo: Path, git: Git, journal: Journal) -> None:
        self._repo = Path(repo)
        self._git = git
        self._effects = Effects(journal)

    async def push(self, stem: str, run_seq: int) -> None:
        async def action() -> None:
            await self._git.push(self._repo)

        await self._effects.run(action, key=effect_key("git", stem, run_seq, "push"),
                                ticket=stem)
