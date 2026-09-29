"""The live-drain retrospective boundary."""

import asyncio
import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import squatch.__main__ as main_module
from squatch import artifacts, stages
from squatch.__main__ import main
from squatch.box import Box
from squatch.driver import Driver, Spool
from squatch.drain import Drain, Plane
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.git import Git
from squatch.journal import Journal
from squatch.llm import FakeLLM
from squatch.llmeffect import LLMEffect
from squatch.lockfile import LockHeld, Lockfile
from squatch.redact import Redactor
from squatch.retro import (
    ORIGIN_BOUNDARY,
    RETRO_AGE,
    RETRO_COUNT,
    RETRO_SPIKE,
    TRIGGER_AGE,
    TRIGGER_COUNT,
    TRIGGER_GATE_FAILURE,
    TRIGGER_INTEGRATION_RED,
    TRIGGER_OVERRIDE,
    TRIGGER_REWORK,
    Retro,
    RetroArtifact,
    RetroConstructionError,
    RetroProposal,
    RetroWindow,
    Window,
    render_report,
    retro_stage,
)
from squatch.seams import LocalFilesystem, SubprocessExec
from squatch.specs import load_spec

from test_drain import Scripted, committed, retro_stages
from test_drain_reentry import Real, checkout
from test_stages import (Agent, GREEN, WIDGET, answer as stage_answer, git_env,
                         implementer, review)

ROOT = Path(__file__).resolve().parent.parent
T0 = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
SHA = "0123abcd"


class Clock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def artifact(**updates):
    return RetroArtifact(
        summary="The window is healthy.", observations=("One useful observation.",),
        proposals=(RetroProposal(
            fixed_failure="A repeated rejection is too vague.",
            overcorrection_risk="Extra prose could dilute the prompt.",
            proposed_spec_paths=("specs/review.md",)),),
        produced_by_spec_version="1.0", produced_at_sha=SHA, **updates)


def projection(**updates):
    values = dict(
        boundary=ORIGIN_BOUNDARY, started_at=T0.isoformat(), ended_at=T0.isoformat(),
        merged_tickets=("one",), signal_counts={TRIGGER_OVERRIDE: 1},
        event_counts={"state_transition": 1}, gate_failures=(), spend_usd=1.25,
        tokens=42, produced_by_spec_version="1.0", produced_at_sha=SHA)
    values.update(updates)
    return RetroWindow(**values)


def answer():
    return json.dumps({
        "summary": "The window is healthy.",
        "observations": ["One useful observation."],
        "proposals": [{
            "fixed_failure": "A repeated rejection is too vague.",
            "overcorrection_risk": "Extra prose could dilute the prompt.",
            "proposed_spec_paths": ["specs/review.md"],
        }],
    })


def init_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
           "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test"}
    subprocess.run(["git", "-C", str(repo), "init", "-q", "-b", "main"], env=env, check=True)
    (repo / "seed").write_text("seed\n")
    subprocess.run(["git", "-C", str(repo), "add", "--", "seed"], env=env, check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "seed"], env=env,
                   check=True)
    return repo, env


def retro(tmp_path, journal, clock, llm, *, retry_cap=0):
    repo, env = init_repo(tmp_path)
    fs = LocalFilesystem()
    redact = Redactor({})
    effects = Effects(journal)
    driver = Driver(
        llm=LLMEffect(llm=llm, effects=effects, redact=redact),
        spool=Spool(tmp_path / "state", fs=fs, redact=redact),
        log=EngineLog(tmp_path / "state", clock=clock, redact=redact),
        clock=clock, retry_cap=retry_cap)
    value = Retro(
        repo=repo, journal=journal, clock=clock, fs=fs,
        git=Git(SubprocessExec(), env=env, timeout=60), effects=effects,
        box=Box(tmp_path / "state", fs=fs, clock=clock), driver=driver,
        providers=object(), spec=load_spec(ROOT / "specs/retro.md"), redact=redact)
    return value, repo


def test_closed_local_artifact_stage_prompt_and_markdown_renderer():
    spec = load_spec(ROOT / "specs/retro.md")
    stage = retro_stage(spec)
    assert (stage.name, stage.surface, stage.consumes, stage.emits) == (
        "retro", "retro", RetroWindow, RetroArtifact)
    prompt = stage.render(projection(), ())
    assert "surface=retro spec_version=1.0" in prompt
    assert 'name="window" origin="engine"' in prompt
    assert not hasattr(artifacts, "RetroArtifact")
    assert "RetroArtifact" not in getattr(stages, "KNOWN_ARTIFACTS", {})
    assert "CliClient" not in (ROOT / "squatch/retro.py").read_text()
    assert isinstance(stages.Stages.driver, property)
    assert stages.Stages.driver.fset is None
    with pytest.raises(ValidationError):
        RetroArtifact.model_validate({**artifact().model_dump(), "extra": True})
    with pytest.raises(ValidationError):
        RetroProposal(fixed_failure="x\ny", overcorrection_risk="z",
                      proposed_spec_paths=("src/x.py",))

    report = render_report("000001", "quiescence", projection(), artifact())
    assert report.startswith("# Retro 000001\n")
    assert "- Window boundary: `origin`" in report
    assert "- Fixed failure: A repeated rejection is too vague." in report
    assert "- Overcorrection risk: Extra prose could dilute the prompt." in report


def test_exact_unforced_thresholds_and_per_kind_spikes(tmp_path):
    clock = Clock()
    with Journal(tmp_path / "state", clock=clock) as journal:
        journal.append("signal", {"kind": "start"})
        for n in range(RETRO_COUNT - 1):
            journal.append("state_transition", {"to": "merged"}, ticket=f"m{n}")
        assert Window(tuple(journal.read()), clock()).due() is None
        journal.append("state_transition", {"to": "merged"}, ticket="last")
        assert Window(tuple(journal.read()), clock()).due() == TRIGGER_COUNT

    for kind in (TRIGGER_GATE_FAILURE, TRIGGER_INTEGRATION_RED, TRIGGER_OVERRIDE,
                 TRIGGER_REWORK):
        state = tmp_path / kind
        with Journal(state, clock=clock) as journal:
            for n in range(RETRO_SPIKE - 1):
                _signal(journal, kind, n)
            assert Window(tuple(journal.read()), clock()).due() is None
            _signal(journal, kind, RETRO_SPIKE)
            window = Window(tuple(journal.read()), clock())
            assert window.signal_counts[kind] == RETRO_SPIKE
            assert window.due() == kind

    state = tmp_path / "age"
    old = Clock(T0 - RETRO_AGE)
    with Journal(state, clock=old) as journal:
        journal.append("signal", {"kind": "start"})
        assert Window(tuple(journal.read()), T0 - timedelta(microseconds=1)).due() is None
        assert Window(tuple(journal.read()), T0).due() == TRIGGER_AGE


def _signal(journal, kind, n):
    if kind == TRIGGER_GATE_FAILURE:
        journal.append("state_transition", {"to": "gate_failed"}, ticket=f"g{n}")
    elif kind == TRIGGER_INTEGRATION_RED:
        journal.append("signal", {"kind": "merge_conflict_facts",
                                   "integration_red_paths": [f"p{n}"]}, ticket=f"i{n}")
    elif kind == TRIGGER_OVERRIDE:
        journal.append("effect_completion", {"result": {"invoice": {"checks": [
            {"bypassed": True}]}}}, ticket=f"o{n}", key=f"check/o{n}/0")
    else:
        journal.append("effect_completion", {"result": {}}, ticket=f"r{n}",
                       key=f"llm/r{n}/0/rework/0/1")


@pytest.mark.parametrize("trigger", ["quiescence", "phase-exit"])
def test_forced_run_commits_one_zero_padded_markdown_report_and_advances_boundary(
        tmp_path, trigger):
    clock = Clock()
    state = tmp_path / "state"
    with Journal(state, clock=clock) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
        llm = FakeLLM(answer())
        value, repo = retro(tmp_path, journal, clock, llm)
        assert asyncio.run(value.run(trigger, forced=True))
        assert not asyncio.run(value.run(trigger, forced=True))
        report = repo / "tickets/retro/000001.md"
        assert report.is_file() and "# Retro 000001" in report.read_text()
        events = tuple(journal.read())
        completions = [event for event in events
                       if event.type == "effect_completion" and event.key == "retro/000001"]
        assert len(completions) == 1
        assert Window(events, clock()).boundary == "retro/000001"
        assert len(llm.requests) == 1 and llm.requests[0].surface == "retro"
        paths = subprocess.run(
            ["git", "-C", str(repo), "diff-tree", "--no-commit-id", "--name-only", "-r",
             "HEAD"], capture_output=True, text=True, check=True).stdout.splitlines()
        assert paths == ["tickets/retro/000001.md"]


def test_unforced_not_due_is_silent_and_never_invents_a_trigger(tmp_path):
    clock = Clock()
    state = tmp_path / "state"
    with Journal(state, clock=clock) as journal:
        llm = FakeLLM("must not run")
        value, _repo = retro(tmp_path, journal, clock, llm)
        assert not asyncio.run(value.run())
        assert llm.requests == []
        assert tuple(journal.read()) == ()
        assert Box(state, fs=LocalFilesystem(), clock=clock).pending() == []


def test_manual_retro_without_a_merge_prints_the_quiescent_operator_result(tmp_path):
    repo = checkout(tmp_path)
    scripted = Scripted({})
    out = StringIO()
    before = {path.relative_to(repo): path.read_bytes()
              for path in repo.rglob("*") if path.is_file()}

    rc = main(["retro"], cwd=repo, env=git_env(tmp_path), out=out,
              pipeline=scripted, clock=Clock())

    assert rc == 0
    assert out.getvalue() == "retro: no merge since the latest completed report\n"
    assert scripted.retro_llm is None
    after = {path.relative_to(repo): path.read_bytes()
             for path in repo.rglob("*") if path.is_file()
             and path.name != "squatch.lock"}
    assert after == before


def test_manual_retro_commits_through_the_governed_retro_path(tmp_path):
    repo = checkout(tmp_path)
    with Journal(repo / ".squatch/state", clock=Clock()) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
    scripted = Scripted({})
    out = StringIO()

    rc = main(["retro"], cwd=repo, env=git_env(tmp_path), out=out,
              pipeline=scripted, clock=Clock())

    assert rc == 0
    assert out.getvalue() == "retro: committed tickets/retro/000001.md\n"
    assert [request.surface for request in scripted.retro_llm.requests] == ["retro"]
    assert (repo / "tickets/retro/000001.md").is_file()
    events = tuple(main_module.read_events(repo / ".squatch/state"))
    completions = [event for event in events
                   if event.type == "effect_completion" and event.key == "retro/000001"]
    assert len(completions) == 1
    report = repo / completions[0].body["result"]["path"]
    assert "- Trigger: `manual`" in report.read_text()
    out = StringIO()
    assert main(["retro"], cwd=repo, env=git_env(tmp_path), out=out,
                pipeline=scripted, clock=Clock()) == 0
    assert out.getvalue() == "retro: no merge since the latest completed report\n"
    assert tuple(main_module.read_events(repo / ".squatch/state")) == events
    assert len(scripted.retro_llm.requests) == 1


def test_manual_retro_selected_model_failure_is_exit_one_and_commits_no_report(tmp_path):
    repo = checkout(tmp_path)
    with Journal(repo / ".squatch/state", clock=Clock()) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
    scripted = Scripted({})

    def failing_retro(journal):
        value = scripted(journal)
        scripted.retro_llm._script = ["not json"]
        return value

    out = StringIO()
    rc = main(["retro"], cwd=repo, env=git_env(tmp_path), out=out,
              pipeline=failing_retro, clock=Clock())

    assert rc == 1
    assert out.getvalue() == (
        "retro: no report committed; inspect status and the Suggestion Box\n")
    assert [request.surface for request in scripted.retro_llm.requests] == ["retro"]
    assert not (repo / "tickets/retro").exists()


def test_manual_retro_prior_git_suppression_is_not_this_runs_refusal(tmp_path):
    repo = checkout(tmp_path)
    with Journal(repo / ".squatch/state", clock=Clock()) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
        journal.append("signal", {
            "kind": "retro_failed", "window_boundary": "origin",
            "trigger": "quiescence", "error_code": "GitError",
        }, key="retro-failed/origin/quiescence")
    scripted = Scripted({})
    out = StringIO()

    rc = main(["retro"], cwd=repo, env=git_env(tmp_path), out=out,
              pipeline=scripted, clock=Clock())

    assert rc == 1
    assert out.getvalue() == (
        "retro: no report committed; inspect status and the Suggestion Box\n")
    assert scripted.retro_llm.requests == []
    assert not (repo / "tickets/retro").exists()


class FailingRetroCommitProcess:
    def __init__(self):
        self._real = SubprocessExec()

    async def run(self, argv, **kwargs):
        if argv[0] == "git" and "commit" in argv and "tickets/retro/000001.md" in argv:
            return 1, "", "scripted retro commit failure"
        return await self._real.run(argv, **kwargs)


def test_manual_retro_git_failure_retains_refusal_rendering_and_exit_two(tmp_path):
    repo = checkout(tmp_path)
    with Journal(repo / ".squatch/state", clock=Clock()) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
    out = StringIO()

    rc = main(["retro"], cwd=repo, env=git_env(tmp_path), out=out,
              pipeline=Scripted({}), clock=Clock(), process=FailingRetroCommitProcess())

    assert rc == 2
    assert out.getvalue().startswith("refused: git: retrospective report operation failed\n")
    assert "paved road:" in out.getvalue()


def test_failure_is_exactly_once_boxed_and_suppresses_the_window(tmp_path):
    clock = Clock()
    state = tmp_path / "state"
    with Journal(state, clock=clock) as journal:
        journal.append("state_transition", {"to": "merged"}, ticket="feature")
        llm = FakeLLM("not json", "must not run")
        value, _ = retro(tmp_path, journal, clock, llm)
        assert not asyncio.run(value.run("quiescence", forced=True))
        assert not asyncio.run(value.run("quiescence", forced=True))
        failures = [event for event in journal.read()
                    if event.body.get("kind") == "retro_failed"]
        assert len(failures) == 1
        assert failures[0].key == "retro-failed/origin/quiescence"
        assert failures[0].body == {
            "kind": "retro_failed", "window_boundary": "origin",
            "trigger": "quiescence", "error_code": "invalid_artifact"}
        [message] = Box(state, fs=LocalFilesystem(), clock=clock).pending()
        assert message.message_class == "failure_report"
        assert message.origin == failures[0].key and message.reports == 1
        assert len(llm.requests) == 1


def test_a_later_completion_is_the_only_suppression_release(tmp_path):
    clock = Clock()
    with Journal(tmp_path / "state", clock=clock) as journal:
        journal.append("signal", {
            "kind": "retro_failed", "window_boundary": "origin",
            "trigger": "quiescence", "error_code": "infra_error",
        }, key="retro-failed/origin/quiescence")
        journal.append("state_transition", {"to": "merged"}, ticket="before")
        assert Window(tuple(journal.read()), clock()).suppressed
        journal.append("effect_completion", {"result": {"commit": SHA}}, key="retro/000001")
        journal.append("state_transition", {"to": "merged"}, ticket="after")
        window = Window(tuple(journal.read()), clock())
        assert not window.suppressed and window.merged == ("after",)


def test_drain_hook_boundaries_and_default_off_construction(tmp_path):
    class Runner:
        def provider_hold(self, ticket, journal):
            return None

        async def dispatch(self, ticket, journal):
            calls.append(("dispatch", ticket.stem))
            journal.append("state_transition", {"to": "merged"}, ticket=ticket.stem)
            return SimpleNamespace(settled=True)

    async def exercise(with_hook):
        state = tmp_path / ("bound" if with_hook else "off")
        with Journal(state, clock=clock) as journal:
            journal.append("state_transition", {"to": "merged"}, ticket="prior")
            ticket = SimpleNamespace(
                stem="phase5-exit", priority="P1", depends=(), agent_tier="medium",
                agent_effort="medium")
            session = SimpleNamespace(journal=journal, intake=object(), providers=object())
            drain = Drain(
                runner=Runner(), repo=tmp_path, config=SimpleNamespace(
                    drain=SimpleNamespace(max_runtime_hours=1)), git=object(), clock=clock,
                process=object(), env={}, report=lambda _: None,
                retro_factory=(lambda _session: hook) if with_hook else None)

            async def scan(facts):
                tickets = {} if "phase5-exit" in facts.merged else {ticket.stem: ticket}
                return Plane(tickets=tickets, held={}, pending=())

            drain._scan = scan
            assert await drain._drain(session) == 0

    async def hook(trigger, forced):
        calls.append((trigger, forced))
        return False

    clock = Clock()
    calls = []
    asyncio.run(exercise(True))
    assert calls == [
        (None, False), ("phase-exit", True), ("dispatch", "phase5-exit"),
        (None, False), ("quiescence", True)]
    calls.clear()
    asyncio.run(exercise(False))
    assert calls == [("dispatch", "phase5-exit")]


class LockCheckingProcess:
    def __init__(self, state_dir, clock):
        self._state_dir = state_dir
        self._clock = clock
        self._real = SubprocessExec()
        self.retro_commits = 0

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        if (argv[0] == "git" and "commit" in argv
                and "tickets/retro/000001.md" in argv):
            probe = Lockfile(self._state_dir, instance_id="retro-probe", clock=self._clock)
            try:
                probe.acquire()
            except LockHeld:
                self.retro_commits += 1
            else:
                probe.release()
                raise AssertionError("retro commit escaped the drain writer lock")
        return await self._real.run(
            argv, cwd=cwd, env=env, timeout=timeout,
            stdin_path=stdin_path, on_spawn=on_spawn)


def _host_only_real(tmp_path):
    repo = checkout(tmp_path, verify=GREEN)
    ticket = repo / "tickets/widget-module/ticket.md"
    ticket.write_text(ticket.read_text().replace("squatch/widget.py", "README.md"))
    agent = Agent(
        stage_answer("implemented"), review("approve"), answer(),
        actions=[implementer(git_env(tmp_path), ("README.md", "host change\n")), None, None])
    real = Real(repo, agent)
    return real


def test_main_drain_binds_shared_driver_and_commits_retro_under_writer_lock(tmp_path):
    real = _host_only_real(tmp_path)
    process = LockCheckingProcess(real.repo / real.config.state_dir, real.clock)
    out = StringIO()

    rc = main(["drain"], cwd=real.repo, env=real.env, out=out,
              pipeline=real, clock=real.clock, process=process)

    assert rc == 0, out.getvalue()
    assert [request.surface for request in real.agent.requests] == [
        "implement", "review", "retro"]
    report = real.repo / "tickets/retro/000001.md"
    assert report.is_file() and "# Retro 000001" in report.read_text()
    events = tuple(Journal(real.repo / real.config.state_dir, clock=real.clock).read())
    completions = [event for event in events
                   if event.type == "effect_completion" and event.key == "retro/000001"]
    assert len(completions) == 1
    assert completions[0].body["result"]["path"] == "tickets/retro/000001.md"
    assert process.retro_commits == 1


@pytest.mark.parametrize("verb", ["drain", "retro"])
def test_production_retro_pipeline_shares_the_session_provider_payload(
        tmp_path, monkeypatch, verb):
    repo = checkout(tmp_path)
    ticket = repo / "tickets/widget-module/ticket.md"
    ticket.unlink()
    ticket.parent.rmdir()
    ticket.parent.parent.rmdir()
    if verb == "retro":
        with Journal(repo / ".squatch/state", clock=Clock()) as journal:
            journal.append("state_transition", {"to": "merged"}, ticket="feature")
    captured = {"compose": [], "runs": []}

    def compose(**kwargs):
        stage_shape, _llm = retro_stages(kwargs["journal"])
        captured["compose"].append((kwargs["providers"], stage_shape.driver))
        return SimpleNamespace(stages=stage_shape)

    class RecordingRetro:
        def __init__(self, **kwargs):
            captured["retro"] = (kwargs["providers"], kwargs["driver"])

        async def run(self, trigger, *, forced):
            captured["runs"].append((trigger, forced))
            return False

    monkeypatch.setattr(main_module, "compose_" + "pipeline", compose)
    monkeypatch.setattr(main_module, "Retro", RecordingRetro)
    assert main(
        [verb], cwd=repo, env=git_env(tmp_path), out=StringIO(),
        clock=Clock()) == (0 if verb == "drain" else 1)

    [(providers, driver)] = captured["compose"]
    assert captured["retro"] == (providers, driver)
    assert captured["runs"] == ([(None, False), ("quiescence", True)] if verb == "drain"
                                else [("manual", True)])


def test_runner_composes_retro_once_and_a_fresh_pipeline_for_every_dispatch(tmp_path):
    repo = checkout(tmp_path)
    committed(repo, "second")
    scripted = Scripted({"widget-module": ["ok"], "second": ["ok"]})
    compositions = []

    def factory(journal):
        compositions.append(journal)
        return scripted(journal)

    assert main(
        ["drain"], cwd=repo, env=git_env(tmp_path), out=StringIO(),
        pipeline=factory, clock=Clock()) == 0
    assert len(compositions) == 3  # one retro pipeline, then one per dispatch
    assert all(journal is compositions[0] for journal in compositions)
    assert [request.surface for request in scripted.retro_llm.requests] == ["retro"]
    main_source = Path(main_module.__file__).read_text()
    driver_source = (ROOT / "squatch/driver.py").read_text()
    assert "_retro_pipelines" not in main_source and "_retro_prebuilt" not in main_source
    assert "ContextVar" not in driver_source and "capture_driver" not in driver_source


def test_production_composition_without_a_driver_fails_closed(tmp_path, monkeypatch):
    repo = checkout(tmp_path, verify=GREEN)

    class StagesWithoutDriver:
        async def abort_active(self):
            pass

    monkeypatch.setattr(
        main_module, "compose_" + "pipeline",
        lambda **_kwargs: SimpleNamespace(stages=StagesWithoutDriver()))

    with pytest.raises(RetroConstructionError, match="production retro requires") as raised:
        main_module.main(
            ["drain"], cwd=repo, env=git_env(tmp_path), out=StringIO(), clock=Clock())
    assert "paved road:" in str(raised.value)


def test_self_upgrade_child_rebinds_the_retro_hook(tmp_path):
    real = Real(
        checkout(tmp_path),
        Agent(stage_answer("implemented"), review("approve"), answer(),
              actions=[implementer(git_env(tmp_path), WIDGET), None, None]))
    class Reexec(LockCheckingProcess):
        def __init__(self):
            super().__init__(real.repo / real.config.state_dir, real.clock)
            self.children = 0

        async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
            if argv[0] == "uv":
                self.children += 1
                rc = await asyncio.to_thread(
                    main, argv[5:], cwd=real.repo, env=real.env, out=StringIO(),
                    pipeline=real, clock=real.clock, process=self)
                return rc, "", ""
            return await super().run(
                argv, cwd=cwd, env=env, timeout=timeout,
                stdin_path=stdin_path, on_spawn=on_spawn)

    process = Reexec()
    out = StringIO()
    rc = main(["drain"], cwd=real.repo, env=real.env, out=out,
              pipeline=real, clock=real.clock, process=process)

    assert rc == 0, out.getvalue()
    assert process.children == 1 and process.retro_commits == 1
    assert [request.surface for request in real.agent.requests] == [
        "implement", "review", "retro"]
    assert (real.repo / "tickets/retro/000001.md").is_file()
