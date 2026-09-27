"""A disposable checkout driven through the production runner composition."""

import asyncio
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from squatch.config import Config, load
from squatch.daemon import compose_daemon_control
from squatch.drain import Drain
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Event, Journal, read_events
from squatch.llm import FakeLLM
from squatch.llmeffect import LLMEffect
from squatch.merge import compose_pipeline
from squatch.mergequeue import AdmissionHold
from squatch.providers import child_env
from squatch.redact import Redactor
from squatch.runner import Runner
from squatch.seams import Clock, LocalFilesystem, Sleep, SubprocessExec

GIT_TIMEOUT = 60.0

_CONFIG = """\
schema_version: 1
state_dir: .squatch/state
providers:
  - name: codex
    kind: cli
    models_by_tier: {low: fake, medium: fake, high: fake, max: fake}
    limits: {concurrency: 1, est_cost_per_call_usd: 0}
routing:
  - {tier: low, surface: implement, candidates: [{provider: codex}]}
  - {tier: medium, surface: implement, candidates: [{provider: codex}]}
  - {tier: high, surface: implement, candidates: [{provider: codex}]}
  - {tier: max, surface: implement, candidates: [{provider: codex}]}
  - {tier: low, surface: review, candidates: [{provider: codex}]}
  - {tier: medium, surface: review, candidates: [{provider: codex}]}
  - {tier: high, surface: review, candidates: [{provider: codex}]}
  - {tier: max, surface: review, candidates: [{provider: codex}]}
"""


def _run(awaitable):
    return asyncio.run(awaitable)


class Bench:
    """One real git checkout with the production Runner/Drain/Pipeline graph."""

    def __init__(self, repo: Path, *, fake: FakeLLM, clock: Clock,
                 env: Mapping[str, str], sleep: Sleep = asyncio.sleep):
        self.repo = Path(repo)
        self.fake = fake
        self.clock = clock
        self.sleep = sleep
        self.env = dict(env)
        self.config = load(None, cwd=self.repo)
        self.state_dir = self.repo / self.config.state_dir
        self.process = SubprocessExec()
        self.fs = LocalFilesystem()
        self.git = Git(self.process, env=child_env(self.env, set()), timeout=GIT_TIMEOUT)
        self.lines: list[str] = []
        self._last_run: tuple[str, int] | None = None
        self._configure_runtime()

    def _configure_runtime(self) -> None:
        """Rebuild the production object graph around the selected seams."""
        redact = Redactor.from_config(self.config, self.env)
        log = EngineLog(self.state_dir, clock=self.clock, redact=redact)

        controls = {}

        def factory(journal):
            if journal not in controls:
                inbox = compose_daemon_control(
                    state_dir=self.state_dir, journal=journal, fs=self.fs)
                controls[journal] = inbox, AdmissionHold(inbox, journal)
            inbox, hold = controls[journal]
            pipeline = compose_pipeline(
                repo=self.repo, config=self.config, env=self.env, journal=journal,
                clock=self.clock, process=self.process, fs=self.fs, git=self.git,
                control_inbox=inbox, admission_hold=hold)
            effect = LLMEffect(llm=self.fake, effects=Effects(journal), redact=redact,
                               clock=self.clock, sleep=self.sleep)
            pipeline.stages._llm = effect
            pipeline.stages._effects = effect.effects
            pipeline.stages._driver._llm = effect
            pipeline.diagnoser._llm = effect
            pipeline.diagnoser._effects = effect.effects
            pipeline.diagnoser._driver._llm = effect
            return pipeline

        self.runner = Runner(
            repo=self.repo, config=self.config, git=self.git, fs=self.fs, clock=self.clock,
            instance_id="shakeout", pipeline=factory, log=log, report=self.lines.append)
        self._drain = Drain(
            runner=self.runner, repo=self.repo, config=self.config, git=self.git,
            clock=self.clock, process=self.process, env=self.env, report=self.lines.append)

    @classmethod
    def make(cls, tmp: Path, *, fake: FakeLLM, clock: Clock,
             sleep: Sleep = asyncio.sleep) -> "Bench":
        repo = Path(tmp)
        repo.mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(repo.parent),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "squatch",
            "GIT_AUTHOR_EMAIL": "squatch@shakeout",
            "GIT_COMMITTER_NAME": "squatch",
            "GIT_COMMITTER_EMAIL": "squatch@shakeout",
            "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+00:00",
        }
        (repo / "config.yaml").write_text(_CONFIG)
        (repo / "SQUATCH_PLAN.md").write_text("# shakeout fixture plan\n")
        (repo / "fixture").mkdir()
        (repo / "fixture" / "context.txt").write_text("shakeout fixture context\n")
        process = SubprocessExec()
        git = Git(process, env=env, timeout=GIT_TIMEOUT)

        async def seed() -> None:
            await git.init(repo)
            await git.add(repo, ("config.yaml", "SQUATCH_PLAN.md", "fixture/context.txt"))
            await git.commit(repo, "shakeout fixture")

        _run(seed())
        bench = cls(repo, fake=fake, clock=clock, env=env, sleep=sleep)
        with Journal(bench.state_dir, clock=clock):
            pass
        return bench

    def write_ticket(self, stem: str, text: str) -> Path:
        path = self.repo / "tickets" / stem / "ticket.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def configure(self, *, fake: FakeLLM | None = None, sleep: Sleep | None = None,
                  config: Config | None = None) -> None:
        """Select model, timing, and routing seams for the next public run."""
        if config is not None:
            configured_state = (self.repo / config.state_dir).resolve()
            if configured_state != self.state_dir.resolve():
                raise ValueError("replacement config must preserve the bench state_dir")
            self.config = config
        if fake is not None:
            self.fake = fake
        if sleep is not None:
            self.sleep = sleep
        self._configure_runtime()

    def commit(self, paths: Sequence[str | Path], subject: str) -> str:
        rels = tuple(str(path) for path in paths)

        async def action() -> str:
            await self.git.add(self.repo, rels)
            return await self.git.commit(self.repo, subject, rels)

        return _run(action())

    def drain(self) -> int:
        rc = _run(self._drain.run())
        self._remember_last_run()
        return rc

    def run(self, stem: str) -> int:
        rc = _run(self.runner.run(stem))
        self._remember_last_run(stem)
        return rc

    def events(self) -> tuple[Event, ...]:
        return tuple(read_events(self.state_dir))

    def terminal(self, stem: str, run_seq: int) -> str | None:
        return next((event.body["to"] for event in reversed(self.events())
                     if event.type == "state_transition" and event.ticket == stem
                     and event.body.get("run_seq") == run_seq
                     and event.body.get("to") != "running"), None)

    def artifact(self, stem: str, name: str) -> bytes:
        return (self.repo / "tickets" / stem / name).read_bytes()

    @property
    def producing_run(self) -> str:
        if self._last_run is None:
            return "bench/0"
        return f"{self._last_run[0]}/{self._last_run[1]}"

    def head(self) -> str:
        return _run(self.git.rev_parse(self.repo, "HEAD"))

    def _remember_last_run(self, stem: str | None = None) -> None:
        terminal = next((event for event in reversed(self.events())
                         if event.type == "state_transition"
                         and event.body.get("to") != "running"
                         and (stem is None or event.ticket == stem)), None)
        if terminal is not None and terminal.ticket is not None:
            self._last_run = (terminal.ticket, terminal.body["run_seq"])
