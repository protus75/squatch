"""Durable quota cooldowns and the one session-owned provider payload."""

import asyncio
import copy
import inspect
from datetime import timedelta
from io import StringIO

import pytest

import squatch.__main__ as main_module
import squatch.daemon as daemon_module
from squatch.config import parse
from squatch.journal import Journal
from squatch.providers import (
    COOLDOWN_PREFIX,
    CliClient,
    ProviderError,
    ProviderRuntime,
    Registry,
)
from squatch.redact import Redactor
from squatch.serve import ServeGraph
from squatch.timers import Timers
from test_cli import STATE, T0, checkout, git_env  # noqa: F401
from test_providers import (
    CONFIG,
    ENV,
    RealFs,
    ScriptedExec,
    claude_stream,
    codex_stream,
    request,
)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now


def failover_config(*, candidates=("codex", "claude")):
    data = copy.deepcopy(CONFIG)
    data["providers"][0]["limits"]["quota_window_minutes"] = 60
    data["providers"][1]["limits"]["quota_window_minutes"] = 60
    data["routing"][1]["candidates"] = [
        {"provider": provider} for provider in candidates]
    return parse(data, source="cooldown-test")


def runtime(config, journal, clock):
    timers = Timers(journal=journal, clock=clock)
    timers.rearm()
    return ProviderRuntime(Registry(config), timers=timers, clock=clock)


def client(tmp_path, config, providers, process):
    return CliClient(
        providers, process=process, fs=RealFs(), env=ENV,
        redact=Redactor.from_config(config, ENV), state_dir=tmp_path / "state",
        cwd=tmp_path / "checkout")


def cooldown_events(journal):
    return [event for event in journal.read()
            if event.key is not None and event.key.startswith(COOLDOWN_PREFIX)]


async def test_quota_cooldown_fails_over_in_order_rearms_and_resets_on_the_clock(tmp_path):
    config = failover_config()
    configured = tuple(provider.name for provider in config.providers)
    clock = Clock()
    process = ScriptedExec(
        (1, "", "You've hit your usage limit"),
        (0, claude_stream("served by fallback"), ""),
        (0, codex_stream("served after reset"), ""),
    )

    with Journal(tmp_path / "state", clock=clock) as journal:
        providers = runtime(config, journal, clock)
        routed = client(tmp_path, config, providers, process)
        with pytest.raises(ProviderError) as exhausted:
            await routed.call(request("review"))
        assert exhausted.value.failure_class == "quota_exhausted"
        assert [(event.type, event.body["deadline"]) for event in cooldown_events(journal)] == [
            ("timer_armed", (T0 + timedelta(minutes=60)).isoformat())]

        fallback = await routed.call(request("review"))
        assert (fallback.provider, fallback.model, fallback.text) == (
            "claude", "c-med", "served by fallback")
        assert tuple(provider.name for provider in config.providers) == configured
        await providers.timers.shutdown()

    clock.now += timedelta(minutes=30)
    with Journal(tmp_path / "state", clock=clock) as journal:
        providers = runtime(config, journal, clock)
        assert providers.resolve("medium", "review").provider.name == "claude"
        assert [event.type for event in cooldown_events(journal)] == ["timer_armed"]

        clock.now += timedelta(minutes=30)
        renewed = await client(tmp_path, config, providers, process).call(request("review"))
        assert (renewed.provider, renewed.model, renewed.text) == (
            "codex", "x-med", "served after reset")
        assert [event.type for event in cooldown_events(journal)] == [
            "timer_armed", "timer_fired"]
        assert cooldown_events(journal)[-1].ts == clock.now.isoformat()
        await providers.timers.shutdown()

    assert [call["argv"][0] for call in process.calls] == ["codex", "claude", "codex"]


@pytest.mark.parametrize("stderr,failure_class", [
    ("Rate limit reached for this account", "rate_limited"),
    ("some new and unknown CLI failure", "unclassified"),
])
async def test_non_quota_failures_keep_their_error_and_do_not_fail_over(
        tmp_path, stderr, failure_class):
    config = failover_config()
    clock = Clock()
    process = ScriptedExec((1, "", stderr), (0, claude_stream("must not run"), ""))
    with Journal(tmp_path / failure_class, clock=clock) as journal:
        providers = runtime(config, journal, clock)
        with pytest.raises(ProviderError) as failure:
            await client(tmp_path, config, providers, process).call(request("review"))
        assert failure.value.failure_class == failure_class
        assert process.calls[0]["argv"][0] == "codex" and len(process.calls) == 1
        assert cooldown_events(journal) == []
        await providers.timers.shutdown()


async def test_single_candidate_quota_parks_without_inventing_a_provider(tmp_path):
    config = failover_config(candidates=("codex",))
    clock = Clock()
    process = ScriptedExec((1, "", "You've hit your usage limit"))
    with Journal(tmp_path / "state", clock=clock) as journal:
        providers = runtime(config, journal, clock)
        routed = client(tmp_path, config, providers, process)
        with pytest.raises(ProviderError, match="usage limit"):
            await routed.call(request("review"))
        with pytest.raises(ProviderError, match="no eligible candidate.*codex"):
            await routed.call(request("review"))
        assert len(process.calls) == 1
        assert [item.provider.name for item in providers.registry.candidates(
            "medium", "review")] == ["codex"]
        assert [event.type for event in cooldown_events(journal)] == ["timer_armed"]
        await providers.timers.shutdown()


@pytest.mark.parametrize("verb", ["drain", "serve"])
def test_drain_and_serve_each_use_the_one_restart_session_timer(
        checkout, monkeypatch, verb):
    made, constructed, registries, observed = [], [], [], []
    original_timers = daemon_module.compose_daemon_timers
    init_timer, init_registry, init_client = Timers.__init__, Registry.__init__, CliClient.__init__

    def timer_init(self, **kwargs):
        constructed.append(self)
        init_timer(self, **kwargs)

    def registry_init(self, *args, **kwargs):
        registries.append(self)
        init_registry(self, *args, **kwargs)

    def client_init(self, providers, **kwargs):
        observed.append(providers)
        init_client(self, providers, **kwargs)

    def timers(**kwargs):
        value = original_timers(**kwargs)
        made.append(value)
        return value

    monkeypatch.setattr(Timers, "__init__", timer_init)
    monkeypatch.setattr(Registry, "__init__", registry_init)
    monkeypatch.setattr(CliClient, "__init__", client_init)
    monkeypatch.setattr(daemon_module, "compose_daemon_timers", timers)
    process = None
    if verb == "drain":
        prepare_quota_checkout(checkout, ("codex",))
        process = QuotaProcess(("codex",))
        original_drain = main_module.Drain._drain

        async def drain(self, session):
            observed.append(session.providers)
            return await original_drain(self, session)

        monkeypatch.setattr(main_module.Drain, "_drain", drain)
    else:
        async def inspect_graph(self):
            observed.extend((self.pipeline.stages._llm._llm.client._providers,
                             self.rework._driver._llm._llm._providers,
                             self.triage._llm._providers))
            return 0

        monkeypatch.setattr(ServeGraph, "run", inspect_graph)

    result = main_module.main(
        [verb], cwd=checkout, env=git_env(checkout.parent), out=StringIO(),
        clock=lambda: T0, process=process)
    assert result == 0
    assert len(made) == len(constructed) == len(registries) == 1
    assert made == constructed
    assert len(observed) >= 2 and all(payload is observed[0] for payload in observed)
    assert observed[0].registry is registries[0]
    assert observed[0].timers is made[0]
    assert made[0]._closed and made[0]._journal.closed


def test_triage_and_composition_signatures_require_the_shared_payload(
        checkout, monkeypatch):
    captured = []
    original = main_module.CliClient

    def cli(providers, **kwargs):
        captured.append(providers)
        return original(providers, **kwargs)

    monkeypatch.setattr(main_module, "CliClient", cli)
    result = main_module.main(
        ["triage"], cwd=checkout, env=git_env(checkout.parent), out=StringIO(), clock=lambda: T0)
    assert result == 0 and len(captured) == 1
    assert isinstance(captured[0], ProviderRuntime)

    from squatch.merge import compose_pipeline
    from squatch.stages import compose

    for callable_ in (compose, compose_pipeline):
        parameter = inspect.signature(callable_).parameters["providers"]
        assert parameter.default is inspect.Parameter.empty
    assert "Registry(" not in inspect.getsource(main_module._triage_pass)


@pytest.mark.parametrize("verb", ["triage", "drain", "serve"])
def test_invalid_routing_row_is_the_existing_paved_road_refusal(checkout, verb):
    (checkout / "config.yaml").write_text("""\
schema_version: 1
state_dir: .squatch/state
providers: []
routing:
  - {tier: medium, surface: review, candidates: []}
""")
    out = StringIO()

    result = main_module.main(
        [verb], cwd=checkout, env=git_env(checkout.parent), out=out, clock=lambda: T0)

    assert result == 2
    assert "refused: config: config.yaml: routing[0].candidates" in out.getvalue()
    assert "paved road: fix the named provider or routing row in config.yaml" in out.getvalue()


async def test_watchdog_and_client_keep_one_resolution_across_initial_sample_expiry(
        tmp_path, monkeypatch):
    from types import SimpleNamespace
    from squatch.watchdog import WatchdogLLM

    config, clock = failover_config(), Clock()
    process = ScriptedExec((0, claude_stream("fallback", usd=0.37), ""))
    with Journal(tmp_path / "state", clock=clock) as journal:
        providers = runtime(config, journal, clock)
        providers.cool_down(providers.provider("codex"))
        chosen = []
        resolve = providers.resolve

        def resolving(tier, surface):
            result = resolve(tier, surface)
            chosen.append(result)
            return result

        monkeypatch.setattr(providers, "resolve", resolving)
        watched = WatchdogLLM(
            client(tmp_path, config, providers, process), registry=providers,
            journal=journal, clock=clock, git=None)
        watched.bind(SimpleNamespace(
            stem="candidate", expected_minutes=75, stuck_minutes=150,
            scope_fence=("output.txt",)), 0)

        async def sample():
            clock.now = T0 + timedelta(minutes=60)
            providers.timers.pending(COOLDOWN_PREFIX)

        monkeypatch.setattr(watched, "_sample", sample)
        result = await watched.call(request("implement", worktree=tmp_path / "wt"))
        assert len(chosen) == 1
        assert result.provider == chosen[0].provider.name == "claude"
        assert result.model == chosen[0].model == "c-med"
        assert process.calls[0]["argv"][0] == "claude"
        assert watched._basis == {("claude", "c-med"): 0.37}
        assert watched._detector._cost_basis_usd == 0.37
        assert {event.provider for event in watched._detector.events} == {"claude"}
        assert [event.type for event in cooldown_events(journal)] == [
            "timer_armed", "timer_fired"]
        await asyncio.sleep(0)
        assert [event.type for event in cooldown_events(journal)].count("timer_fired") == 1
        await providers.timers.shutdown()


class QuotaProcess:
    """Real git, with one classified quota hit per configured CLI candidate."""

    def __init__(self, candidates):
        from squatch.seams import SubprocessExec
        self.real = SubprocessExec()
        self.failures = list(candidates)
        self.calls = []

    async def run(self, argv, **kwargs):
        from pathlib import Path
        from test_stages import answer, run_record

        if argv[0] == "git":
            return await self.real.run(argv, **kwargs)
        provider = argv[0]
        assert provider in {"codex", "claude"}
        self.calls.append(provider)
        if self.failures:
            assert provider == self.failures.pop(0)
            return 1, "", ("You've hit your usage limit" if provider == "codex"
                           else "You've hit your limit")
        worktree = Path(kwargs["cwd"])
        (worktree / "tickets/candidate/run.md").write_text(run_record("premise_failed"))
        stream = codex_stream if provider == "codex" else claude_stream
        return 0, stream(answer("premise_failed")), ""


def prepare_quota_checkout(checkout, candidates):
    import yaml
    from test_cli import author

    config = failover_config(candidates=candidates).model_dump(mode="json", exclude_none=True)
    config["state_dir"] = str(STATE)
    config.pop("worktree_root")
    config["routing"] = [{"tier": "medium", "surface": "review",
                          "candidates": [{"provider": name} for name in candidates]}]
    config["providers"] = [row for row in config["providers"] if row["name"] in candidates]
    for row in config["providers"]:
        row.pop("auth")
    (checkout / "config.yaml").write_text(yaml.safe_dump(config))
    author(checkout, "candidate")


def assert_cooldown_park(checkout, count):
    from squatch.journal import read_events

    events = tuple(read_events(checkout / STATE))
    assert not [e for e in events if e.type == "cap_consumed"]
    assert not [e for e in events if e.body.get("routed") in {"ladder", "reject_queue"}]
    assert len([e for e in events if e.body.get("to") == "running"]) == count
    terminals = [e for e in events if e.body.get("provider_cooldown")]
    assert len(terminals) == count
    assert all(e.body["finding_codes"] == ["quota_exhausted"] for e in terminals)
    assert all(e.body["harvest"] is not None for e in terminals)
    assert not [e for e in events if e.key and "/diagnose/" in e.key]
    return events


@pytest.mark.parametrize("candidates", [("codex",), ("codex", "claude")])
@pytest.mark.parametrize("verb", ["drain", "serve"])
def test_real_runner_parks_cost_free_and_resumes_after_timer_fired(
        checkout, monkeypatch, candidates, verb):
    import squatch.serve as serve_module
    from squatch.journal import read_events

    prepare_quota_checkout(checkout, candidates)
    clock, process = Clock(), QuotaProcess(candidates)
    out = StringIO()

    def invoke():
        return main_module.main([verb], cwd=checkout, env=git_env(checkout.parent),
                                out=out, clock=clock, process=process)

    if verb == "serve":
        monkeypatch.setattr(serve_module, "POLL_SECONDS", 0)

        async def exercise(graph):
            async def poll():
                await graph.tasks._callbacks[0]()
                await graph.dispatch.scheduler.join()

            for count in range(1, len(candidates) + 1):
                await poll()
                # A quota hit ends the whole run before the next candidate is tried.
                assert process.calls == list(candidates[:count])
                assert_cooldown_park(checkout, count)
            for _ in range(3):
                await poll()
                assert process.calls == list(candidates)
                assert_cooldown_park(checkout, len(candidates))
            clock.now += timedelta(minutes=60)
            await poll()
            return 0

        monkeypatch.setattr(ServeGraph, "run", exercise)
        assert invoke() == 0, out.getvalue()
    else:
        assert invoke() == 0, out.getvalue()
        assert process.calls == list(candidates)
        assert_cooldown_park(checkout, len(candidates))
        for _ in range(2):
            assert invoke() == 0, out.getvalue()
            assert process.calls == list(candidates)
            assert_cooldown_park(checkout, len(candidates))
        clock.now += timedelta(minutes=60)
        assert invoke() == 0, out.getvalue()

    assert process.calls == [*candidates, "codex"]
    events = tuple(read_events(checkout / STATE))
    assert not [e for e in events if e.type == "cap_consumed"
                and e.body["cap"] in {"infra", "retry", "diagnosis"}]
    fired = [index for index, e in enumerate(events) if e.type == "timer_fired"
             and e.key and e.key.startswith(COOLDOWN_PREFIX)]
    resumed = next(index for index, e in enumerate(events)
                   if e.body.get("to") == "running" and e.body["run_seq"] == len(candidates))
    assert len(fired) == len(candidates) and max(fired) < resumed
    completions = [e for e in events if e.type == "effect_completion" and e.key
                   and e.key.startswith("llm/")]
    assert completions[-1].body["result"]["provider"] == "codex"
