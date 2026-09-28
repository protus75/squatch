"""Watchdog evidence through the real CLI roots and Stages-owned Driver."""

import asyncio
import json
from collections import Counter
from datetime import timedelta
from io import StringIO
from pathlib import Path

import pytest
import yaml

import squatch.__main__ as main_module
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.notify import NotificationReconciler
from squatch.seams import LocalFilesystem, SubprocessExec, SubprocessNotifications
from squatch.serve import ServeGraph
from squatch.watchdog import WatchdogDetector, WatchdogLLM
from test_cli import STATE, T0, author, checkout, git_env  # noqa: F401
from test_notify import RecordingNotifications
from test_providers import claude_stream, codex_stream
from test_drain import RETRO_ANSWER
from test_stages import CONFIG, TICKET, answer, review, run_record


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


def prepare(repo, *, notify=True, provider="codex", stems=("candidate",), fence="output.txt"):
    config = yaml.safe_load(CONFIG)
    row = config["providers"][0]
    row["name"] = provider
    row["limits"]["est_cost_per_call_usd"] = 2.0
    for route in config["routing"]:
        route["candidates"][0]["provider"] = provider
    config["caps"] = {"retry": 4}
    if notify:
        config["notify"] = ["notify", "literal argument"]
    (repo / "config.yaml").write_text(yaml.safe_dump(config))
    for stem in stems:
        text = TICKET.format(frontmatter="", verify="uv run pytest tests/test_widget.py")
        text = text.replace("squatch/widget.py", fence)
        text = text.replace("expected: 20m", "expected: 1m").replace("stuck: 40m", "stuck: 10m")
        author(repo, stem, text)
    env = git_env(repo.parent)
    env["FAKE_PROVIDER_KEY"] = "secret-only-for-model"
    return env


class StageProcess:
    def __init__(self, clock, notifications, *, soft=False, provider="codex",
                 mutate_review=False, output="output.txt"):
        self.clock = clock
        self.notifications = notifications
        self.soft = soft
        self.provider = provider
        self.mutate_review = mutate_review
        self.output = output
        self.real = SubprocessExec()
        self.calls = []
        self.counts = Counter()
        self.pages_at_implement = []
        self.worktree = None

    async def run(self, argv, **kwargs):
        if argv[0] == "git":
            if argv[-1] == "push":
                return 0, "", ""
            return await self.real.run(argv, **kwargs)
        if argv[0] == "uv":
            return 0, "verified", ""
        assert argv[0] == self.provider
        prompt = Path(kwargs["stdin_path"]).read_text()
        surface = next(
            value for value in ("implement", "review", "retro")
            if f"surface={value}" in prompt)
        assert f"surface={surface}" in prompt
        self.calls.append(surface)
        self.counts[surface] += 1
        if surface == "implement":
            self.counts["review"] = 0
            self.pages_at_implement.append(len(self.notifications.calls))
            self.worktree = Path(kwargs["cwd"])
            stem = self.worktree.name
            (self.worktree / self.output).write_text(stem + "\n")
            (self.worktree / "tickets" / stem / "run.md").write_text(run_record())
            git = Git(self.real, env=kwargs["env"], timeout=60)
            await git.add(self.worktree, [self.output])
            await git.commit(self.worktree, "implement output", [self.output])
            text = answer("implemented")
        elif surface == "review":
            if self.soft:
                self.clock.advance(25)
            if self.mutate_review:
                # A committed mutation is still progress, irrespective of porcelain.
                (self.worktree / self.output).write_text(str(self.counts["review"]))
                git = Git(self.real, env=kwargs["env"], timeout=60)
                await git.add(self.worktree, [self.output])
                await git.commit(self.worktree, "progress", [self.output])
            text = "invalid" if self.counts["review"] < 4 else review("approve")
        else:
            text = RETRO_ANSWER
        line = (json.dumps({"type": "item.started", "item": {"type": "command_execution"}})
                if self.provider == "codex" else json.dumps({"type": "assistant", "message": {
                    "content": [{"type": "tool_use"}], "usage": {"input_tokens": 10}}}))
        kwargs["on_stdout_line"](line)
        result = (codex_stream(text) if self.provider == "codex"
                  else claude_stream(text, usd=2.0))
        for line in result.splitlines():
            kwargs["on_stdout_line"](line)
        return 0, result, ""


def bounded_serve(monkeypatch):
    async def run(self):
        await self.tasks._callbacks[0]()
        await self.dispatch.scheduler.join()
        await self.tasks._callbacks[0]()
        await self.dispatch.scheduler.join()
        return 0

    monkeypatch.setattr(ServeGraph, "run", run)


@pytest.mark.parametrize("verb", ["drain", "serve"])
@pytest.mark.parametrize("soft", [False, True])
@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_roots_watch_implement_and_review_and_deliver_one_soft_page(
        checkout, monkeypatch, verb, soft, provider):
    env = prepare(checkout, provider=provider)
    clock, notifications = Clock(), RecordingNotifications()
    process = StageProcess(clock, notifications, soft=soft, provider=provider)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)
    bounded_serve(monkeypatch)
    observed, mutations, waits, aborts = [], [], [], []
    original_event = WatchdogDetector.observe_event
    original_mutation = WatchdogDetector.observe_mutation
    original_wait = WatchdogDetector.observe_cap_wait
    original_abort = WatchdogLLM.abort_current

    def event(self, event):
        observed.append((event, self._cost_basis_usd, self._scope_fence))
        return original_event(self, event)

    def mutation(self, path):
        mutations.append(path)
        return original_mutation(self, path)

    def wait(self, elapsed):
        waits.append(elapsed)
        return original_wait(self, elapsed)

    def abort(self):
        aborts.append(True)
        return original_abort(self)

    monkeypatch.setattr(WatchdogDetector, "observe_event", event)
    monkeypatch.setattr(WatchdogDetector, "observe_mutation", mutation)
    monkeypatch.setattr(WatchdogDetector, "observe_cap_wait", wait)
    monkeypatch.setattr(WatchdogLLM, "abort_current", abort)
    out = StringIO()
    assert main_module.main([verb], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    expected = ["implement", "review", "review", "review", "review"]
    assert process.calls == expected + (["retro"] if verb == "drain" else [])
    assert len([e for e, _, _ in observed if e.kind == "tool_call"]) >= 5
    assert all(basis == 2.0 and fence == (("output.txt",),) for _, basis, fence in observed)
    assert "output.txt" in mutations
    assert waits == []
    assert aborts == []
    signals = [e for e in read_events(checkout / STATE) if e.body.get("kind") == "watchdog"]
    assert len(signals) == int(soft)
    if soft:
        assert signals[0].ticket == "candidate"
        assert signals[0].body == dict(kind="watchdog", ticket="candidate",
                                       spiral="spend_without_progress", run_seq=0)
    assert len(notifications.calls) == int(soft)
    events = tuple(read_events(checkout / STATE))
    if soft:
        assert events.index(signals[0]) < next(i for i, e in enumerate(events)
                                               if e.key and e.key.startswith("notify/"))
    with Journal(checkout / STATE, clock=clock) as journal:
        asyncio.run(NotificationReconciler(journal=journal, notifications=notifications,
                    argv=["notify"], report=lambda _: None).reconcile())
    assert len(notifications.calls) == int(soft)


def test_drain_reconciles_startup_and_every_dispatch_before_next_offer(checkout, monkeypatch):
    env = prepare(checkout, stems=("first-ticket", "second-ticket"))
    clock, notifications = Clock(), RecordingNotifications()
    with Journal(checkout / STATE, clock=clock) as journal:
        journal.append("signal", dict(kind="watchdog", ticket="old-ticket",
                                      spiral="stuck", run_seq=7), ticket="old-ticket")
    process = StageProcess(clock, notifications, soft=True)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)
    out = StringIO()
    assert main_module.main(["drain"], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    assert process.calls[-1] == "retro"
    assert process.pages_at_implement == [1, 2]
    assert len(notifications.calls) == 3
    assert "second-ticket" in notifications.calls[-1][-1]


def test_drain_configures_private_transport_without_provider_auth(checkout, monkeypatch):
    env = prepare(checkout, stems=())
    active = SubprocessExec()
    original = main_module.NotificationReconciler
    seen = []

    def reconcile(**kwargs):
        notifier = kwargs["notifications"]
        assert isinstance(notifier, SubprocessNotifications)
        assert isinstance(notifier._process, SubprocessExec)
        assert notifier._process is not active
        assert notifier._env == {k: v for k, v in env.items() if k != "FAKE_PROVIDER_KEY"}
        assert notifier._cwd == checkout
        assert list(kwargs["argv"]) == ["notify", "literal argument"]
        seen.append(notifier)
        return original(**kwargs)

    monkeypatch.setattr(main_module, "NotificationReconciler", reconcile)
    assert main_module.main(["drain"], cwd=checkout, env=env, process=active,
                            clock=Clock(), out=StringIO()) == 0
    assert len(seen) == 1


def test_drain_unset_notify_warns_once_and_keeps_signals_status_only(checkout, monkeypatch):
    env = prepare(checkout, notify=False, stems=("first-ticket", "second-ticket"))
    clock, notifications = Clock(), RecordingNotifications()
    process = StageProcess(clock, notifications, soft=True)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)
    out = StringIO()
    assert main_module.main(["drain"], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    assert process.calls[-1] == "retro"
    assert out.getvalue().count("push notifications are off") == 1
    assert notifications.calls == []
    events = tuple(read_events(checkout / STATE))
    assert sum(e.body.get("kind") == "watchdog" for e in events) == 2
    assert not any(e.key and e.key.startswith("notify/") for e in events)


def test_fresh_runs_page_again_but_committed_mutations_reset_spend(checkout, monkeypatch):
    from squatch.tickets import lint_ticket

    env = prepare(checkout)
    clock, notifications = Clock(), RecordingNotifications()
    process = StageProcess(clock, notifications, soft=True)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)
    outcomes = []

    async def run(self):
        path = checkout / "tickets/candidate/ticket.md"
        ticket = lint_ticket(path.read_text(), stem="candidate", repo=checkout,
                             plan=(checkout / "SQUATCH_PLAN.md").read_text(),
                             resolve_stem=lambda _: False)
        journal = self.control._journal
        reconciler = NotificationReconciler(journal=journal, notifications=notifications,
                                            argv=["notify"], report=lambda _: None)
        for seq in (3, 4, 5):
            process.mutate_review = seq == 5
            delivery = await self.pipeline.stages.run(ticket, run_seq=seq)
            outcomes.append(delivery.outcome)
            assert self.pipeline.stages._watchdog._ticket is None
            await reconciler.reconcile()
            assert len(notifications.calls) == min(seq - 2, 2)
        return 0

    monkeypatch.setattr(ServeGraph, "run", run)
    out = StringIO()
    assert main_module.main(["serve"], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    assert outcomes == ["ok", "ok", "ok"]
    signals = [e.body for e in read_events(checkout / STATE)
               if e.body.get("kind") == "watchdog"]
    assert [s["run_seq"] for s in signals] == [3, 4]


@pytest.mark.parametrize("deadline_mode", ["exact", "early", "real", "cancel"])
def test_stuck_root_aborts_same_client_group_and_unwinds_stages(
        checkout, monkeypatch, deadline_mode):
    import os
    import sys
    from dataclasses import replace
    import squatch.providers as providers_module
    import squatch.stages as stages_module
    from squatch.tickets import lint_ticket

    env = prepare(checkout)
    clock = main_module._now if deadline_mode == "real" else Clock()
    notifications = RecordingNotifications()
    ready = asyncio.Event()
    groups, children, killed = [], [], []
    real_kill = providers_module.kill_group
    real_effect = stages_module.LLMEffect

    async def deadline(seconds):
        await ready.wait()
        if deadline_mode == "cancel":
            await asyncio.Future()
        # LLMEffect starts its timer before the wrapper task runs, and the
        # event loop may wake slightly early. Exact elapsed equality is unsafe.
        clock.advance(seconds - (.001 if deadline_mode == "early" else 0))

    def effect(**kwargs):
        if deadline_mode == "real":
            return real_effect(**kwargs)
        return real_effect(**kwargs, sleep=deadline)

    def kill(pgid):
        killed.append(pgid)
        real_kill(pgid)

    class HangingProcess(StageProcess):
        async def run(self, argv, **kwargs):
            if argv[0] != "codex":
                return await super().run(argv, **kwargs)
            spawn, event = kwargs["on_spawn"], kwargs["on_stdout_line"]

            def on_spawn(pgid):
                groups.append(pgid)
                spawn(pgid)

            def on_line(line):
                children.append(int(line))
                event(json.dumps({"type": "item.started", "item": {"type": "command_execution"}}))
                ready.set()

            kwargs.update(on_spawn=on_spawn, on_stdout_line=on_line)
            script = ("import subprocess,sys,time; "
                      "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                      "print(p.pid,flush=True); time.sleep(60)")
            try:
                return await self.real.run([sys.executable, "-c", script], **kwargs)
            finally:
                self.unwound = True

    process = HangingProcess(clock, notifications)
    process.unwound = False
    monkeypatch.setattr(providers_module, "kill_group", kill)
    monkeypatch.setattr(stages_module, "LLMEffect", effect)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)

    async def run(self):
        ticket = lint_ticket((checkout / "tickets/candidate/ticket.md").read_text(),
                             stem="candidate", repo=checkout,
                             plan=(checkout / "SQUATCH_PLAN.md").read_text(),
                             resolve_stem=lambda _: False)
        stages = self.pipeline.stages
        if deadline_mode == "real":
            ticket = replace(ticket, stuck_minutes=.5 / 60)
        if deadline_mode == "cancel":
            work = asyncio.create_task(stages.run(ticket, run_seq=8))
            await ready.wait()
            await stages.abort_active()
            with pytest.raises(asyncio.CancelledError):
                await work
        else:
            delivery = await stages.run(ticket, run_seq=8)
            assert delivery.outcome == "timeout"
            assert delivery.stage == "implement"
        assert process.unwound
        assert stages._watchdog._ticket is None
        assert stages._driver._active is None
        assert stages._watchdog.client._pgid is None
        await NotificationReconciler(
            journal=self.control._journal, notifications=notifications,
            argv=["notify"], report=lambda _: None).reconcile()
        assert len(notifications.calls) == int(deadline_mode != "cancel")
        return 0

    monkeypatch.setattr(ServeGraph, "run", run)
    out = StringIO()
    assert main_module.main(["serve"], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    assert len(groups) == len(children) == 1
    assert killed == groups
    with pytest.raises(ProcessLookupError):
        os.kill(groups[0], 0)
    # A killed grandchild can await init's reap, but must never be runnable.
    stat = Path(f"/proc/{children[0]}/stat")
    assert not stat.exists() or stat.read_text().split()[2] == "Z"
    signals = [e for e in read_events(checkout / STATE) if e.body.get("kind") == "watchdog"]
    assert len(signals) == int(deadline_mode != "cancel")
    if signals:
        assert signals[0].ticket == "candidate"
        assert signals[0].body == dict(kind="watchdog", ticket="candidate", spiral="stuck", run_seq=8)
    assert not any(e.type == "effect_completion" and e.key.startswith("llm/candidate/8/")
                   for e in read_events(checkout / STATE))


def test_observation_failure_cannot_mask_provider_failure_and_binding_clears(checkout, monkeypatch):
    from squatch.tickets import lint_ticket

    env = prepare(checkout)
    clock, notifications = Clock(), RecordingNotifications()
    sampled = []

    class BrokenProvider(StageProcess):
        async def run(self, argv, **kwargs):
            if (argv[0] == "git" and argv[-2:] == ["status", "--porcelain"]
                    and Path(kwargs["cwd"]).name == "candidate"):
                sampled.append(kwargs["cwd"])
                return 1, "", "observation unavailable"
            if argv[0] == "codex":
                kwargs["on_stdout_line"](json.dumps({
                    "type": "item.started", "item": {"type": "command_execution"}}))
                raise RuntimeError("original provider failure")
            return await super().run(argv, **kwargs)

    process = BrokenProvider(clock, notifications)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)

    async def run(self):
        ticket = lint_ticket((checkout / "tickets/candidate/ticket.md").read_text(),
                             stem="candidate", repo=checkout,
                             plan=(checkout / "SQUATCH_PLAN.md").read_text(),
                             resolve_stem=lambda _: False)
        delivery = await self.pipeline.stages.run(ticket, run_seq=9)
        assert delivery.outcome == "infra_error"
        assert self.pipeline.stages._watchdog._ticket is None
        return 0

    monkeypatch.setattr(ServeGraph, "run", run)
    out = StringIO()
    assert main_module.main(["serve"], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    assert len(sampled) >= 2
    log = (checkout / STATE / "engine.log").read_text()
    assert "original provider failure" in log
    assert "observation unavailable" not in log


@pytest.mark.parametrize("verb", ["drain", "serve"])
@pytest.mark.parametrize("sample_at", ["boundary", "tick"])
def test_directory_fence_stream_cost_is_constant_and_mutations_are_observed(
        checkout, monkeypatch, verb, sample_at):
    env = prepare(checkout, fence="outputs")
    directory = checkout / "outputs"
    directory.mkdir()
    paths = [f"outputs/{index:04d}.txt" for index in range(1024)]
    for path in paths:
        (checkout / path).write_bytes(b"unchanged\n" * 1024)

    async def seed():
        git = Git(SubprocessExec(), env=env, timeout=60)
        await git.add(checkout, paths)
        await git.commit(checkout, "large output directory", paths)

    asyncio.run(seed())
    clock, notifications = Clock(), RecordingNotifications()
    counts = Counter()
    mutations, sleeps = [], []
    tick, observed = asyncio.Event(), asyncio.Event()
    original_init = WatchdogLLM.__init__
    original_mutation = WatchdogDetector.observe_mutation

    class CountingFilesystem(LocalFilesystem):
        def read(self, path):
            counts["reads"] += 1
            if "outputs" in Path(path).parts:
                counts["fence_reads"] += 1
            return super().read(path)

        def list(self, directory, pattern):
            counts["walks"] += 1
            if "outputs" in Path(directory).parts:
                counts["fence_walks"] += 1
            return super().list(directory, pattern)

    async def sleep(seconds):
        sleeps.append(seconds)
        await tick.wait()
        tick.clear()
        clock.advance(seconds)

    def construct(self, *args, **kwargs):
        original_init(self, *args, **kwargs, sleep=sleep)

    def mutation(self, path):
        accepted = original_mutation(self, path)
        if accepted:
            mutations.append(path)
            if path == "outputs/result.txt":
                observed.set()
        return accepted

    class StreamingDirectoryProcess(StageProcess):
        async def run(self, argv, **kwargs):
            if argv[0] == "git":
                counts["git"] += 1
            if argv[0] != "codex":
                return await super().run(argv, **kwargs)
            callback = kwargs.get("on_stdout_line")
            if callback is None:
                return await super().run(argv, **kwargs)

            def stream(line):
                for _ in range(1000):
                    before = counts.copy()
                    callback(line)
                    # A single callback must do no observation I/O, even with
                    # thousands of declared output files and streamed events.
                    assert counts == before
                    counts["events"] += 1

            kwargs["on_stdout_line"] = stream
            result = await super().run(argv, **kwargs)
            if self.calls[-1] == "implement":
                CountingFilesystem().write(self.worktree / "outputs/pending.txt", b"pending")
                assert not observed.is_set()
                if sample_at == "tick":
                    tick.set()
                    await asyncio.wait_for(observed.wait(), timeout=5)
            return result

    process = StreamingDirectoryProcess(clock, notifications, output="outputs/result.txt")
    monkeypatch.setattr(main_module, "LocalFilesystem", CountingFilesystem)
    monkeypatch.setattr(main_module, "SubprocessNotifications", lambda **kw: notifications)
    monkeypatch.setattr(WatchdogLLM, "__init__", construct)
    monkeypatch.setattr(WatchdogDetector, "observe_mutation", mutation)
    bounded_serve(monkeypatch)
    out = StringIO()
    assert main_module.main([verb], cwd=checkout, env=env, process=process,
                            clock=clock, out=out) == 0, out.getvalue()
    expected = ["implement", "review", "review", "review", "review"]
    assert process.calls == expected + (["retro"] if verb == "drain" else [])
    assert counts["events"] >= 5000
    assert counts["fence_reads"] == counts["fence_walks"] == 0
    assert sorted(mutations) == ["outputs/pending.txt", "outputs/result.txt"]
    assert sleeps and all(seconds == 10 for seconds in sleeps)
    assert notifications.calls == []
