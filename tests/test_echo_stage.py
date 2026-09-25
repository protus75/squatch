"""Phase 0 exit read 1 (plan section 19): a toy echo stage -- consumes a stub
artifact, emits one -- runs end-to-end under the LLM-stage driver with the
fake LLM. Emitter: the driver.

The stage is the real composition, not a stand-in: a linted prompt spec
(specs.py) renders through the data-block form, the LLMStage is derived from
that spec's frontmatter, and the driver spools, logs, redacts, parses, and
gates exactly as a production stage would. Every exit claim below is READ
from the emitter's artifacts -- the StageResult, the attempt spool, the
engine log -- never asserted from the script that produced them.
"""

import json
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

from squatch.artifacts import Artifact
from squatch.config import parse
from squatch.driver import INVALID_ARTIFACT, Driver, LLMStage, Spool
from squatch.enginelog import EngineLog
from squatch.llm import FakeLLM
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem
from squatch.specs import DATA_MARKER, DataBlock, lint_spec

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)
SHA = "0123abcd"
TICKET = "T-echo"


class Echo(Artifact):
    """The stub artifact: consumed and emitted alike."""

    text: str


ECHO_SPEC = textwrap.dedent("""\
    ---
    llm_surface: review
    consumes: Echo
    emits: Echo
    tier: medium
    effort: low
    gates: []
    version: "1.0"
    ---
    ## Role
    You are an echo.
    ## Task
    Return the text in the data block below, unchanged.
    <<<squatch:data name="echo">>>
    ## Inputs
    echo: the text to return.
    ## Output format
    Exactly one JSON object with the fields of Echo: {"text": <the text>}.
    ## On-failure
    Return {"text": ""} and nothing else.
    """)


class TickingClock:
    def __init__(self, start=T0):
        self.now = start

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


def stub(text: str) -> Echo:
    return Echo(produced_by_spec_version="stub@0", produced_at_sha="stub", text=text)


def echo_stage() -> LLMStage:
    """The stage as the spec declares it: surface, tier, effort, version and
    gate list come from the linted frontmatter; the render adapter puts the
    consumed artifact into the spec's one slot."""
    spec = lint_spec(ECHO_SPEC, source="specs/echo.md")

    def render(inputs: Echo, findings) -> str:
        return spec.render({"echo": DataBlock("untrusted", inputs.text)}, findings=findings)

    return LLMStage(name="review", surface=spec.surface, spec_version=spec.version,
                    tier=spec.tier, effort=spec.effort, consumes=Echo, emits=Echo,
                    gates=spec.gates, render=render)


def driver(tmp_path: Path, llm: FakeLLM) -> tuple[Driver, Path]:
    config = parse({
        "schema_version": 1, "state_dir": str(tmp_path / "state"),
        "providers": [{"name": "fake", "kind": "cli", "auth": "FAKE_PROVIDER_KEY",
                       "models_by_tier": {"low": "f", "medium": "f", "high": "f", "max": "f"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 0.5}}],
        "routing": [],
    }, source="test")
    state = Path(config.state_dir)
    redact = Redactor.from_config(config, {"FAKE_PROVIDER_KEY": "sk-unused-in-echo"})
    clock = TickingClock()
    return Driver(llm=llm, clock=clock, redact=redact,
                  spool=Spool(state, fs=LocalFilesystem(), redact=redact),
                  log=EngineLog(state, clock=clock, redact=redact)), state


def log_events(state: Path) -> list[dict]:
    return [json.loads(line) for line in (state / "engine.log").read_text().splitlines()]


def spool(state: Path, attempt: int = 1) -> Path:
    return state / "spools" / TICKET / str(attempt)


async def test_echo_stage_runs_end_to_end_under_the_driver(tmp_path):
    llm = FakeLLM(json.dumps({"text": "what goes in"}))
    drv, state = driver(tmp_path, llm)

    result = await drv.run(echo_stage(), stub("what goes in"), ticket=TICKET, attempt=1,
                           workspace=tmp_path / "ws", sha=SHA)

    # The emitted artifact: the input echoed, provenance stamped by the driver.
    assert result.outcome == "ok"
    assert isinstance(result.artifact, Echo)
    assert result.artifact.text == "what goes in"
    assert result.artifact.produced_by_spec_version == "1.0"
    assert result.artifact.produced_at_sha == SHA
    assert result.findings == []
    assert result.cost.attempts == 1

    # One call, shaped by the spec's frontmatter; a read-only surface has no worktree.
    [req] = llm.requests
    assert (req.surface, req.tier, req.effort, req.ticket, req.worktree) == (
        "review", "medium", "low", TICKET, None)
    assert req.rendered.startswith("squatch prompt: surface=review spec_version=1.0\n")
    assert f'{DATA_MARKER}data name="echo" origin="untrusted"' in req.rendered
    assert "\nwhat goes in\n" in req.rendered

    # The attempt spool holds exactly what was sent and what came back.
    assert sorted(p.name for p in spool(state).iterdir()) == [
        "001-prompt.md", "001-response.md"]
    assert (spool(state) / "001-prompt.md").read_text() == req.rendered
    assert (spool(state) / "001-response.md").read_text() == json.dumps({"text": "what goes in"})

    # The engine log carries the run; the journal is untouched by a stage.
    events = log_events(state)
    assert [e["event"] for e in events] == ["call", "response", "terminal"]
    assert all(e["ticket"] == TICKET and e["stage"] == "review" for e in events)
    assert events[-1]["outcome"] == "ok" and events[-1]["attempts"] == 1
    assert not (state / "journal").exists()


async def test_echo_stage_reprompts_an_invalid_artifact_through_the_findings_block(tmp_path):
    """Invariant 2's in-stage loop, exercised with the echo stage's empty gate
    list: a schema-invalid reply is fed back as findings in the DATA channel
    of the next render, and the stage still reaches `ok`."""
    llm = FakeLLM("not json at all", json.dumps({"text": "second time"}))
    drv, state = driver(tmp_path, llm)

    result = await drv.run(echo_stage(), stub("second time"), ticket=TICKET, attempt=1,
                           workspace=tmp_path / "ws", sha=SHA)

    assert result.outcome == "ok"
    assert result.artifact.text == "second time"
    assert result.cost.attempts == 2

    first, second = llm.requests
    assert f'{DATA_MARKER}data name="findings"' not in first.rendered
    assert f'{DATA_MARKER}data name="findings" origin="engine"' in second.rendered
    assert f"- {INVALID_ARTIFACT}: output is not JSON" in second.rendered

    assert sorted(p.name for p in spool(state).iterdir()) == [
        "001-prompt.md", "001-response.md", "002-prompt.md", "002-response.md"]
    events = log_events(state)
    assert [e["event"] for e in events] == [
        "call", "response", "reprompt", "call", "response", "terminal"]
    assert events[2]["reason"] == INVALID_ARTIFACT
    assert events[2]["findings"][0]["code"] == INVALID_ARTIFACT
    assert events[-1]["outcome"] == "ok" and events[-1]["attempts"] == 2


async def test_echo_stage_leaves_the_sent_prompt_when_the_call_dies(tmp_path):
    """The prompt is on disk BEFORE the model is called: a call that raises
    leaves exactly what was sent, and nothing else, in the spool."""
    llm = FakeLLM(ConnectionError("provider gone"))
    drv, state = driver(tmp_path, llm)

    result = await drv.run(echo_stage(), stub("never answered"), ticket=TICKET, attempt=1,
                           workspace=tmp_path / "ws", sha=SHA)

    assert result.outcome == "infra_error"
    assert result.artifact is None
    assert [p.name for p in spool(state).iterdir()] == ["001-prompt.md"]
    assert (spool(state) / "001-prompt.md").read_text() == llm.requests[0].rendered
    assert log_events(state)[-1]["reason"] == "ConnectionError: provider gone"
