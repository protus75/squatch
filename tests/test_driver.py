"""llm.py + driver.py + enginelog.py + redact.py: the one LLM-stage driver
(plan section 5 invariant 2, section 6).

The contract under test: the rendered prompt is on disk BEFORE the model is
called; every attempt's streams land in the spool and the engine log (never
the journal) already scrubbed of configured secret VALUES, wired from the
CONFIG, never a secret passed in by hand; a schema-invalid artifact or a
hard-gate failure re-prompts the SAME workspace with the findings fed back,
bounded by the retry cap; a stuck call is aborted BEFORE its timeout terminal
is recorded.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from squatch import enginelog
from squatch.artifacts import SUBSTEP_NAMES, STAGE_NAMES, Artifact, Finding
from squatch.config import Caps, parse
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects
from squatch.enginelog import EngineLog
from squatch.journal import Journal
from squatch.llmeffect import LLMEffect, llm_key
from squatch.gates import GateReport
from squatch.llm import LLM_SURFACES, FakeLLM, Hang, LLMRequest, LLMResult
from squatch.providers import ProviderError
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)
SHA = "0123abcd"
SECRET_NAME = "FAKE_PROVIDER_KEY"
SECRET = "sk-fake-9f8e7d6c5b4a-VALUE"


class TickingClock:
    def __init__(self, start=T0, step=1):
        self.now = start
        self.step = timedelta(seconds=step)

    def __call__(self):
        self.now += self.step
        return self.now


class Echo(Artifact):
    """The toy artifact: what goes in comes back out."""

    text: str


class Renders:
    """A stand-in spec renderer that records the findings each render saw."""

    def __init__(self, prompt="say: {text}"):
        self.prompt = prompt
        self.seen: list[tuple[Finding, ...]] = []

    def __call__(self, inputs: Echo, findings) -> str:
        self.seen.append(tuple(findings))
        return self.prompt.format(text=inputs.text) + "".join(
            f"\nFINDING {f.code}: {f.message}" for f in findings)


class StubGate:
    code = "run_record"
    paved_road = "write run_record.json per section 13"

    def __init__(self, *verdicts: str):
        self.verdicts = list(verdicts)
        self.workspaces: list[Path] = []

    async def check(self, artifact, workspace):
        self.workspaces.append(workspace)
        verdict = self.verdicts.pop(0)
        if verdict == "pass":
            return GateReport(code=self.code, verdict="pass")
        return GateReport(code=self.code, verdict="fail", findings=(Finding(
            code=self.code, message=f"run record missing ({len(self.workspaces)})",
            paved_road=self.paved_road),))


def config(*, auth=SECRET_NAME):
    provider = {
        "name": "fake", "kind": "cli",
        "models_by_tier": {"low": "f", "medium": "f", "high": "f", "max": "f"},
        "limits": {"concurrency": 1, "est_cost_per_call_usd": 0.5},
    }
    if auth is not None:
        provider["auth"] = auth
    return parse({"schema_version": 1, "state_dir": "/unused",
                  "providers": [provider], "routing": []}, source="test")


def redactor(env=None):
    return Redactor.from_config(config(), {SECRET_NAME: SECRET} if env is None else env)


def stage(*gates, render=None, spec_version="echo@1.0", surface="review"):
    return LLMStage(name="review", surface=surface, spec_version=spec_version,
                    tier="medium", effort="low", consumes=Echo, emits=Echo,
                    gates=tuple(gates), render=render or Renders())


def test_diagnose_is_an_llm_substep_but_not_a_stage_name():
    diagnose = LLMStage(name="diagnose", surface="diagnose", spec_version="1.0",
                        tier="medium", effort="medium", consumes=Echo, emits=Echo,
                        gates=(), render=Renders())
    assert diagnose.name in SUBSTEP_NAMES and diagnose.name not in STAGE_NAMES
    with pytest.raises(ValueError):
        LLMStage(name="unknown", surface="review", spec_version="1.0", tier="medium",
                 effort="medium", consumes=Echo, emits=Echo, gates=(), render=Renders())


def driver(tmp_path, llm, *, clock=None, redact=None, stuck_seconds=None,
           sleep=asyncio.sleep, **kw):
    redact = redact or redactor()
    clock = clock or TickingClock()
    state = tmp_path / "state"
    call = LLMEffect(llm=llm, effects=Effects(Journal(state, clock=clock)), redact=redact,
                     stuck_seconds=stuck_seconds, clock=clock, sleep=sleep)
    return Driver(llm=call, clock=clock, spool=Spool(state, fs=LocalFilesystem(), redact=redact),
                  log=EngineLog(state, clock=clock, redact=redact), **kw)


def echo_json(text):
    return json.dumps({"text": text})


def spool_dir(tmp_path, stem="t-1", attempt=1):
    return tmp_path / "state" / "spools" / stem / str(attempt)


def log_events(tmp_path):
    path = tmp_path / "state" / "engine.log"
    return [json.loads(line) for line in path.read_text().splitlines()]


def everything_written(tmp_path):
    return "".join(p.read_text() for p in (tmp_path / "state").rglob("*") if p.is_file())


async def run(d, st, *, text="hi", ticket="t-1", attempt=1, workspace=Path("/wt")):
    return await d.run(st, Echo(text=text, produced_by_spec_version="in@1", produced_at_sha=SHA),
                       ticket=ticket, run_seq=0, attempt=attempt, workspace=workspace, sha=SHA)


# --- redact.py --------------------------------------------------------------


def test_redactor_replaces_each_resolved_value_with_its_name_token():
    r = Redactor({"A_KEY": "aaa", "B_KEY": "bbbb"})
    assert r("x aaa y bbbb z aaa") == "x [REDACTED:A_KEY] y [REDACTED:B_KEY] z [REDACTED:A_KEY]"


def test_redactor_resolves_names_from_config_against_the_env():
    r = Redactor.from_config(config(), {SECRET_NAME: SECRET, "OTHER": "other"})
    assert r(f"key={SECRET} other=other") == f"key=[REDACTED:{SECRET_NAME}] other=other"


def test_redactor_skips_unset_and_empty_values():
    # An empty value matched as a substring would replace between every
    # character; an unset name has no value to match.
    assert Redactor.from_config(config(), {})("plain") == "plain"
    assert Redactor.from_config(config(), {SECRET_NAME: ""})("plain") == "plain"
    assert Redactor.from_config(config(auth=None), {SECRET_NAME: SECRET})(SECRET) == SECRET


def test_redactor_longest_value_wins_when_one_secret_contains_another():
    r = Redactor({"SHORT": "abc", "LONG": "abcdef"})
    assert r("abcdef abc") == "[REDACTED:LONG] [REDACTED:SHORT]"


# --- enginelog.py -----------------------------------------------------------


def test_engine_log_writes_one_scrubbed_json_line_per_event(tmp_path):
    log = EngineLog(tmp_path, clock=TickingClock(), redact=Redactor({"K": SECRET}))
    log.event("call", stage="review", note=f"token {SECRET}")
    log.event("terminal", outcome="ok")
    lines = (tmp_path / "engine.log").read_text().splitlines()
    assert [json.loads(l)["event"] for l in lines] == ["call", "terminal"]
    first = json.loads(lines[0])
    assert first["ts"] == "2026-08-04T12:30:16+00:00"
    assert first["note"] == "token [REDACTED:K]"
    assert SECRET not in (tmp_path / "engine.log").read_text()


def test_engine_log_scrubs_before_json_escaping_rewrites_the_secret(tmp_path):
    secret = 'sk"quo\\back\u00e9uni'  # a quote, a backslash, a non-ASCII char
    log = EngineLog(tmp_path, clock=TickingClock(), redact=Redactor({"K": secret}))
    log.event("call", note=f"token {secret}", nested={"k": [secret], secret: 1}, path=Path(secret))
    raw = (tmp_path / "engine.log").read_text()
    assert secret not in raw
    rec = json.loads(raw)
    assert rec["note"] == "token [REDACTED:K]"
    assert rec["nested"] == {"k": ["[REDACTED:K]"], "[REDACTED:K]": 1}
    assert rec["path"] == "[REDACTED:K]"
    assert secret not in json.dumps(rec, ensure_ascii=False)


def test_engine_log_rotates_by_size_keeping_a_bounded_set(tmp_path, monkeypatch):
    monkeypatch.setattr(enginelog, "MAX_BYTES", 120)
    log = EngineLog(tmp_path, clock=TickingClock(), redact=Redactor({}))
    for n in range(40):
        log.event("call", n=n, pad="x" * 40)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == ["engine.log", "engine.log.1", "engine.log.2", "engine.log.3"]
    for p in tmp_path.iterdir():
        assert len(p.read_bytes()) <= 120
        for line in p.read_text().splitlines():
            json.loads(line)  # rotation never tears a line
    # The newest event is in the active file; the oldest survivors are in .3.
    assert json.loads((tmp_path / "engine.log").read_text().splitlines()[-1])["n"] == 39
    oldest = json.loads((tmp_path / "engine.log.3").read_text().splitlines()[0])["n"]
    newest_in_3 = json.loads((tmp_path / "engine.log.3").read_text().splitlines()[-1])["n"]
    assert oldest <= newest_in_3 < 39


# --- llm.py -----------------------------------------------------------------


def test_llm_surfaces_are_the_llm_stages_plus_diagnose_and_requisition_review():
    assert LLM_SURFACES == {"author", "implement", "review", "rework", "triage", "retro",
                            "diagnose", "requisition_review"}


def test_llm_request_refuses_values_outside_the_closed_vocabularies():
    ok = dict(rendered="p", tier="medium", effort="low", ticket=None, worktree=None)
    LLMRequest(surface="review", **ok)
    with pytest.raises(ValueError):
        LLMRequest(surface="check", **ok)
    with pytest.raises(ValueError):
        LLMRequest(surface="review", **{**ok, "tier": "huge"})
    with pytest.raises(ValueError):
        LLMRequest(surface="review", **{**ok, "effort": "none"})


async def test_fake_llm_returns_scripted_responses_in_order_and_records_requests():
    fake = FakeLLM("one", LLMResult(text="two", input_tokens=3, output_tokens=4,
                                    provider="p", model="m", usd=0.25))
    req = LLMRequest(surface="review", rendered="p", tier="medium", effort="low",
                     ticket="t", worktree=None)
    a = await fake.call(req)
    b = await fake.call(req)
    assert (a.text, a.provider, a.model, a.input_tokens) == ("one", "fake", "fake-1", None)
    assert (b.text, b.usd) == ("two", 0.25)
    assert fake.requests == [req, req]


async def test_fake_llm_raises_a_scripted_exception():
    fake = FakeLLM(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        await fake.call(LLMRequest(surface="review", rendered="p", tier="medium",
                                   effort="low", ticket=None, worktree=None))


# --- driver: the happy path -------------------------------------------------


async def test_ok_run_emits_the_validated_artifact_with_provenance(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    result = await run(driver(tmp_path, fake), stage())
    assert result.outcome == "ok"
    assert result.artifact == Echo(text="hi", produced_by_spec_version="echo@1.0",
                                   produced_at_sha=SHA)
    assert result.findings == []
    assert result.cost.attempts == 1


async def test_request_carries_surface_tier_effort_ticket_and_no_worktree_for_readers(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    await run(driver(tmp_path, fake), stage(), workspace=Path("/wt"))
    [req] = fake.requests
    assert (req.surface, req.tier, req.effort, req.ticket) == ("review", "medium", "low", "t-1")
    assert req.rendered == "say: hi"
    # Review runs the tree read-only; only Implement is granted the worktree.
    assert req.worktree is None


async def test_implement_is_the_one_surface_granted_the_worktree(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    await run(driver(tmp_path, fake), stage(surface="implement"), workspace=Path("/wt"))
    assert fake.requests[0].worktree == Path("/wt")


async def test_inputs_are_checked_against_the_consumed_type(tmp_path):
    class Other(Artifact):
        n: int = 0

    d = driver(tmp_path, FakeLLM(echo_json("hi")))
    with pytest.raises(TypeError):
        await d.run(stage(), Other(produced_by_spec_version="x", produced_at_sha=SHA),
                    ticket="t-1", run_seq=0, attempt=1, workspace=Path("/wt"), sha=SHA)


# --- driver: spool and engine log -------------------------------------------


async def test_prompt_and_response_land_in_the_attempt_spool(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    await run(driver(tmp_path, fake), stage(), attempt=3)
    spool = spool_dir(tmp_path, attempt=3)
    assert (spool / "001-prompt.md").read_text() == "say: hi"
    assert (spool / "001-response.md").read_text() == echo_json("hi")


async def test_prompt_is_on_disk_before_a_raising_call(tmp_path):
    seen = {}

    class Peek(FakeLLM):
        async def call(self, req):
            seen["prompt_on_disk"] = (spool_dir(tmp_path) / "001-prompt.md").read_text()
            return await super().call(req)

    result = await run(driver(tmp_path, Peek(RuntimeError("provider down"))), stage())
    assert seen["prompt_on_disk"] == "say: hi"
    assert result.outcome == "infra_error"
    assert result.artifact is None
    assert not (spool_dir(tmp_path) / "001-response.md").exists()
    terminal = log_events(tmp_path)[-1]
    assert terminal["event"] == "terminal"
    assert terminal["outcome"] == "infra_error"
    assert "provider down" in terminal["reason"]


async def test_classified_provider_error_becomes_one_infra_finding(tmp_path):
    error = ProviderError(
        "claude", "login expired", failure_class="auth_error",
        paved_road="run `claude login` in the operator's shell")
    result = await run(driver(tmp_path, FakeLLM(error)), stage())
    assert result.outcome == "infra_error"
    assert len(result.findings) == 1
    [finding] = result.findings
    assert finding.code == "auth_error"
    assert finding.message == str(error)
    assert finding.paved_road == "run `claude login` in the operator's shell"


async def test_unclassified_provider_error_has_no_infra_findings(tmp_path):
    result = await run(driver(tmp_path, FakeLLM(
        ProviderError("claude", "provider crashed"))), stage())
    assert result.outcome == "infra_error"
    assert result.findings == []


async def test_engine_log_carries_structured_call_and_terminal_events(tmp_path):
    fake = FakeLLM(LLMResult(text=echo_json("hi"), input_tokens=10, output_tokens=5,
                             provider="fake", model="fake-1", usd=0.5))
    await run(driver(tmp_path, fake), stage(), attempt=2)
    events = log_events(tmp_path)
    assert [e["event"] for e in events] == ["call", "response", "terminal"]
    call, response, terminal = events
    assert (call["ticket"], call["attempt"], call["call_seq"], call["surface"]) == \
        ("t-1", 2, 1, "review")
    assert call["prompt"] == str(spool_dir(tmp_path, attempt=2) / "001-prompt.md")
    assert (response["provider"], response["model"], response["usd"]) == ("fake", "fake-1", 0.5)
    assert response["input_tokens"] == 10 and response["output_tokens"] == 5
    assert (terminal["outcome"], terminal["attempts"]) == ("ok", 1)
    # The engine log is the diagnostic sink; the journal carries only the
    # call's effect pair, never the diagnostic events.
    with Journal(tmp_path / "state", clock=TickingClock()) as j:
        assert [e.type for e in j.read()] == ["effect_intent", "effect_completion"]


async def test_ticketless_calls_spool_under_the_surface_name(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    await run(driver(tmp_path, fake), stage(surface="triage"), ticket=None)
    assert (spool_dir(tmp_path, stem="triage") / "001-prompt.md").exists()
    assert fake.requests[0].ticket is None


# --- driver: redaction, wired config -> writer ------------------------------


async def test_secret_value_never_reaches_spool_or_log(tmp_path):
    # The prompt AND the response carry the configured secret's VALUE; the
    # redactor is built from the config's `auth` name resolved in the env.
    # Response 1 is schema-invalid with the secret as the stray field's NAME,
    # so the validation finding would echo it; response 2 raises with it.
    fake = FakeLLM(json.dumps({"text": f"leaked {SECRET}", SECRET: 1}),
                   RuntimeError(f"auth failed for {SECRET}"))
    d = driver(tmp_path, fake, redact=redactor({SECRET_NAME: SECRET}))
    renders = Renders(prompt="key is " + SECRET + " for {text}")
    result = await run(d, stage(render=renders))
    assert result.outcome == "infra_error"
    written = everything_written(tmp_path)
    assert SECRET not in written
    assert f"[REDACTED:{SECRET_NAME}]" in written
    # Scrubbed once at receipt: the fed-back finding and the re-rendered
    # prompt inherit the scrubbed text.
    [fed] = renders.seen[1]
    assert f"[REDACTED:{SECRET_NAME}]" in fed.message and SECRET not in fed.message
    assert SECRET not in (spool_dir(tmp_path) / "002-prompt.md").read_text()


async def test_result_text_is_scrubbed_before_it_becomes_the_artifact(tmp_path):
    fake = FakeLLM(json.dumps({"text": f"got {SECRET}"}))
    result = await run(driver(tmp_path, fake), stage())
    assert result.artifact.text == f"got [REDACTED:{SECRET_NAME}]"


# --- driver: the bounded re-prompt loop -------------------------------------


async def test_invalid_artifact_reprompts_the_same_workspace_with_findings(tmp_path):
    fake = FakeLLM("not json at all", json.dumps({"text": 5, "extra": 1}), echo_json("ok"))
    renders = Renders()
    result = await run(driver(tmp_path, fake), stage(render=renders))
    assert result.outcome == "ok"
    assert result.cost.attempts == 3
    assert renders.seen[0] == ()
    [first] = renders.seen[1]
    assert first.code == "invalid_artifact" and "JSON" in first.message and first.paved_road
    second = renders.seen[2]
    assert {f.code for f in second} == {"invalid_artifact"}
    assert any("extra" in f.message for f in second)
    assert "FINDING invalid_artifact" in (spool_dir(tmp_path) / "002-prompt.md").read_text()
    reprompts = [e for e in log_events(tmp_path) if e["event"] == "reprompt"]
    assert [e["reason"] for e in reprompts] == ["invalid_artifact", "invalid_artifact"]
    assert [e["call_seq"] for e in reprompts] == [1, 2]


async def test_single_json_markdown_fence_is_only_a_transport_wrapper(tmp_path):
    fenced = f"```json\n{echo_json('ok')}\n```"
    result = await run(driver(tmp_path, FakeLLM(fenced)), stage())

    assert result.outcome == "ok"
    assert result.artifact.text == "ok"
    assert result.cost.attempts == 1


@pytest.mark.parametrize("response", [
    f"prose\n```json\n{echo_json('no')}\n```",
    f"```json\n{echo_json('no')}\n```\nmore",
])
async def test_one_json_fence_may_have_cli_status_prose(tmp_path, response):
    result = await run(driver(tmp_path, FakeLLM(response)), stage())

    assert result.outcome == "ok"
    assert result.artifact.text == "no"
    assert result.cost.attempts == 1


@pytest.mark.parametrize("response", [
    f"```JSON\n{echo_json('no')}\n```",
    f"```json\n{echo_json('no')}\n```\n```json\n{echo_json('extra')}\n```",
])
async def test_json_fence_does_not_admit_prose_or_other_wrappers(tmp_path, response):
    result = await run(driver(tmp_path, FakeLLM(response), retry_cap=0), stage())

    assert result.outcome == "invalid_artifact"
    assert result.cost.attempts == 1


async def test_hard_gate_failure_reprompts_then_passes(tmp_path):
    gate = StubGate("fail", "pass")
    renders = Renders()
    fake = FakeLLM(echo_json("v1"), echo_json("v2"))
    result = await run(driver(tmp_path, fake), stage(gate, render=renders), workspace=Path("/wt"))
    assert result.outcome == "ok"
    assert result.artifact.text == "v2"
    assert result.cost.attempts == 2
    assert gate.workspaces == [Path("/wt"), Path("/wt")]
    [fed] = renders.seen[1]
    assert fed.code == "run_record"
    assert [e["reason"] for e in log_events(tmp_path) if e["event"] == "reprompt"] == ["gate_failed"]


async def test_async_gate_can_make_its_own_driver_call(tmp_path):
    fake = FakeLLM(echo_json("outer"), echo_json("inner"))
    d = driver(tmp_path, fake)

    class NestedGate:
        code = "run_record"
        paved_road = "make the nested review pass"

        async def check(self, artifact, workspace):
            nested = await d.run(
                stage(), Echo(text="inner", produced_by_spec_version="in@1",
                              produced_at_sha=SHA),
                ticket="nested", run_seq=0, attempt=1, workspace=workspace, sha=SHA)
            assert nested.outcome == "ok" and nested.artifact.text == "inner"
            return GateReport(code=self.code, verdict="pass")

    result = await run(d, stage(NestedGate()))

    assert result.outcome == "ok" and result.artifact.text == "outer"
    assert [request.ticket for request in fake.requests] == ["t-1", "nested"]


async def test_terminal_findings_stop_without_changing_the_every_gate_rule(tmp_path):
    class FenceGate(StubGate):
        code = "scope_fence"
        paved_road = "list the path in the ticket's scope fence"

    first = StubGate("fail")
    second = FenceGate("fail")
    fake = FakeLLM(echo_json("outer"), echo_json("unused"))

    result = await run(
        driver(tmp_path, fake, retry_cap=1), stage(first, second), workspace=Path("/wt"))
    assert result.outcome == "gate_failed" and len(fake.requests) == 2
    assert first.workspaces == [Path("/wt"), Path("/wt")]
    assert second.workspaces == [Path("/wt"), Path("/wt")]

    first = StubGate("fail")
    second = FenceGate("fail")
    fake = FakeLLM(echo_json("outer"), echo_json("unused"))
    result = await driver(tmp_path, fake).run(
        stage(first, second), Echo(text="hi", produced_by_spec_version="in@1",
                                  produced_at_sha=SHA),
        ticket="t-2", run_seq=0, attempt=1, workspace=Path("/wt"), sha=SHA,
        terminal_findings=lambda findings: bool(findings))
    assert result.outcome == "gate_failed" and len(fake.requests) == 1
    assert [finding.code for finding in result.findings] == ["run_record", "scope_fence"]
    assert first.workspaces == [Path("/wt")]
    assert second.workspaces == [Path("/wt")]


async def test_soft_gate_failure_continues_and_returns_its_findings(tmp_path):
    gate = StubGate("fail")
    fake = FakeLLM(echo_json("v1"))
    d = driver(tmp_path, fake, severity={"run_record": "soft"})
    result = await run(d, stage(gate))
    assert result.outcome == "ok"
    assert [f.code for f in result.findings] == ["run_record"]
    assert result.cost.attempts == 1
    assert [e["event"] for e in log_events(tmp_path)] == ["call", "response", "soft_findings",
                                                          "terminal"]


async def test_retry_cap_bounds_reprompts_and_names_the_spent_cap(tmp_path):
    fake = FakeLLM(*["nope"] * 10)
    result = await run(driver(tmp_path, fake, retry_cap=2), stage())
    # One call plus `retry_cap` re-prompts, then the terminal.
    assert result.cost.attempts == 3
    assert len(fake.requests) == 3
    assert result.outcome == "invalid_artifact"
    assert result.artifact is None
    assert [f.code for f in result.findings] == ["invalid_artifact"]
    terminal = log_events(tmp_path)[-1]
    assert (terminal["outcome"], terminal["reason"]) == ("invalid_artifact", "retry cap spent")
    assert terminal["cap"] == "retry"

    with Journal(tmp_path / "state", clock=TickingClock()) as journal:
        completions = [event.key for event in journal.read()
                       if event.type == "effect_completion"]
    assert completions == [llm_key("t-1", 0, "review", 1, call_seq)
                           for call_seq in range(1, 4)]


async def test_gate_failed_at_the_cap_is_the_terminal_outcome(tmp_path):
    gate = StubGate("fail", "fail")
    fake = FakeLLM(echo_json("a"), echo_json("b"))
    result = await run(driver(tmp_path, fake, retry_cap=1), stage(gate))
    assert result.outcome == "gate_failed"
    assert result.cost.attempts == 2
    assert [f.code for f in result.findings] == ["run_record"]


async def test_retry_cap_zero_means_no_reprompt(tmp_path):
    fake = FakeLLM("nope", echo_json("ok"))
    result = await run(driver(tmp_path, fake, retry_cap=0), stage())
    assert result.outcome == "invalid_artifact"
    assert len(fake.requests) == 1


def test_retry_cap_defaults_to_the_shipped_caps_retry(tmp_path):
    d = driver(tmp_path, FakeLLM())
    assert d.retry_cap == Caps().retry == 6


# --- driver: cost -----------------------------------------------------------


async def test_cost_folds_tokens_usd_seconds_and_stamps_the_serving_identity(tmp_path):
    fake = FakeLLM(
        LLMResult(text="nope", input_tokens=None, output_tokens=None,
                  provider="fake", model="m0", usd=0.5),
        LLMResult(text=echo_json("ok"), input_tokens=100, output_tokens=20,
                  provider="fake", model="m1", usd=0.25))
    result = await run(driver(tmp_path, fake, clock=TickingClock(step=10)), stage())
    assert result.cost.attempts == 2
    # Unreported usage counts as zero tokens (the cli est_cost fallback still charges usd).
    assert result.cost.tokens == 120
    assert result.cost.usd == 0.75
    assert result.cost.seconds > 0
    assert (result.cost.provider, result.cost.model) == ("fake", "m1")


async def test_cost_without_a_completed_call_has_no_serving_identity(tmp_path):
    result = await run(driver(tmp_path, FakeLLM(RuntimeError("down"))), stage())
    assert result.cost.attempts == 1
    assert (result.cost.provider, result.cost.model, result.cost.usd) == (None, None, 0.0)


# --- driver: the stuck-budget kill ------------------------------------------


async def test_stuck_call_is_aborted_before_the_timeout_terminal_is_recorded(tmp_path):
    log_at_abort = {}
    log_path = tmp_path / "state" / "engine.log"

    class Resistant(FakeLLM):
        # Ignores cancellation: only abort_current releases it, like a CLI
        # subprocess that outlives a dropped await.
        def abort_current(self):
            log_at_abort["events"] = [json.loads(l)["event"]
                                      for l in log_path.read_text().splitlines()]
            super().abort_current()

    fake = Resistant(Hang(resist=True))
    result = await asyncio.wait_for(
        run(driver(tmp_path, fake, stuck_seconds=0.05), stage()), timeout=5)
    assert result.outcome == "timeout"
    assert result.artifact is None
    assert fake.aborted == 1
    assert log_at_abort["events"] == ["call"]
    assert (spool_dir(tmp_path) / "001-prompt.md").read_text() == "say: hi"
    terminal = log_events(tmp_path)[-1]
    assert terminal["outcome"] == "timeout" and "stuck" in terminal["reason"]


async def test_injected_sleep_elapses_the_clock_derived_stuck_budget_without_wall_time(tmp_path):
    clock = TickingClock(step=0)
    slept = []

    async def expire(seconds):
        slept.append(seconds)
        clock.now += timedelta(seconds=seconds)
        await asyncio.sleep(0)

    fake = FakeLLM(Hang(resist=True))
    result = await run(driver(tmp_path, fake, clock=clock, stuck_seconds=60, sleep=expire),
                       stage())

    assert result.outcome == "timeout"
    assert slept == [60]
    assert clock.now == T0 + timedelta(seconds=60)
    assert fake.aborted == 1


async def test_call_within_the_stuck_budget_is_not_aborted(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    result = await run(driver(tmp_path, fake, stuck_seconds=5), stage())
    assert result.outcome == "ok" and fake.aborted == 0


async def test_outer_cancellation_aborts_the_active_call(tmp_path):
    fake = FakeLLM(Hang(resist=True))
    task = asyncio.ensure_future(run(driver(tmp_path, fake, stuck_seconds=None), stage()))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=5)
    assert fake.aborted == 1
