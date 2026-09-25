"""The LLM call behind `@effect` (plan sections 2, 6, 19 Phase 1).

Every model call the driver makes is one journaled effect keyed
`llm/<stem>/<run_seq>/<surface>/<attempt>/<call_seq>`: intent before the
call, ONE completion carrying the scrubbed result and its cost after it. A
replay of a completed key returns the recorded result and never reaches the
LLM seam; a fresh run sequence takes fresh keys. `run_sequence` is the
read-time fold that derives the sequence: the count of the stem's prior
terminal `state_transition` events.
"""

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from squatch.artifacts import Artifact, Finding
from squatch.config import parse
from squatch.driver import Driver, LLMStage, Spool
from squatch.effects import Effects, effect, effect_key, run_sequence
from squatch.enginelog import EngineLog
from squatch.journal import Journal
from squatch.llm import FakeLLM, LLMResult
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)
SHA = "0123abcd"
SECRET_NAME = "FAKE_PROVIDER_KEY"
SECRET = "sk-fake-9f8e7d6c5b4a-VALUE"


class TickingClock:
    def __init__(self, start=T0):
        self.now = start

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class Echo(Artifact):
    text: str


def render(inputs: Echo, findings) -> str:
    return f"say: {inputs.text}" + "".join(f"\nFINDING {f.code}: {f.message}" for f in findings)


def stage(surface="review"):
    return LLMStage(name="review", surface=surface, spec_version="echo@1.0", tier="medium",
                    effort="low", consumes=Echo, emits=Echo, gates=(), render=render)


def echo_json(text):
    return json.dumps({"text": text})


def metered(text, *, usd=0.25, input_tokens=10, output_tokens=5):
    return LLMResult(text=text, input_tokens=input_tokens, output_tokens=output_tokens,
                     provider="fake", model="fake-1", usd=usd)


def redactor():
    config = parse({
        "schema_version": 1, "state_dir": "state",
        "providers": [{"name": "fake", "kind": "cli", "auth": SECRET_NAME,
                       "models_by_tier": {"low": "f", "medium": "f", "high": "f", "max": "f"},
                       "limits": {"concurrency": 1, "est_cost_per_call_usd": 0.5}}],
        "routing": [],
    }, source="test")
    return Redactor.from_config(config, {SECRET_NAME: SECRET})


def driver(tmp_path, llm, journal, **kw):
    redact = redactor()
    clock = TickingClock()
    state = tmp_path / "state"
    return Driver(llm=llm, effects=Effects(journal), clock=clock, redact=redact,
                  spool=Spool(state, fs=LocalFilesystem(), redact=redact),
                  log=EngineLog(state, clock=clock, redact=redact), **kw)


async def run(d, *, text="hi", ticket="t-1", run_seq=0, attempt=1, surface="review"):
    return await d.run(stage(surface), Echo(produced_by_spec_version="stub", produced_at_sha=SHA,
                                            text=text),
                       ticket=ticket, run_seq=run_seq, attempt=attempt,
                       workspace=Path("/wt"), sha=SHA)


def journal(tmp_path):
    return Journal(tmp_path / "state", clock=TickingClock())


def llm_events(j):
    return [(e.type, e.key, e.ticket, e.body) for e in j.read()
            if e.type in ("effect_intent", "effect_completion")]


def completions(j):
    return [e for e in j.read() if e.type == "effect_completion"]


def transition(j, stem, to):
    j.append("state_transition", {"to": to}, ticket=stem)


# --- one call, one intent, one completion carrying result and cost ----------


async def test_call_is_journaled_under_the_run_scoped_key_with_result_and_cost(tmp_path):
    fake = FakeLLM(metered(echo_json("hi")))
    with journal(tmp_path) as j:
        result = await run(driver(tmp_path, fake, j), ticket="t-1", run_seq=2, attempt=3)
        assert result.outcome == "ok"
        assert llm_events(j) == [
            ("effect_intent", "llm/t-1/2/review/3/1", "t-1", {}),
            ("effect_completion", "llm/t-1/2/review/3/1", "t-1", {
                "result": asdict(metered(echo_json("hi"))),
                "cost": {"usd": 0.25, "input_tokens": 10, "output_tokens": 5,
                         "provider": "fake", "model": "fake-1"},
            }),
        ]


async def test_exactly_one_cost_event_per_call_across_a_reprompt(tmp_path):
    fake = FakeLLM(metered("not json", usd=0.10), metered(echo_json("hi"), usd=0.30))
    with journal(tmp_path) as j:
        result = await run(driver(tmp_path, fake, j))
        assert result.outcome == "ok"
        done = completions(j)
    assert [e.key for e in done] == ["llm/t-1/0/review/1/1", "llm/t-1/0/review/1/2"]
    assert [e.body["cost"]["usd"] for e in done] == [0.10, 0.30]
    assert len(fake.requests) == 2
    assert result.cost.usd == pytest.approx(0.40)


async def test_unmetered_cli_result_records_null_tokens_and_the_flat_estimate(tmp_path):
    fake = FakeLLM(LLMResult(text=echo_json("hi"), input_tokens=None, output_tokens=None,
                             provider="fake", model="fake-1", usd=0.5))
    with journal(tmp_path) as j:
        await run(driver(tmp_path, fake, j))
        (done,) = completions(j)
    assert done.body["cost"] == {"usd": 0.5, "input_tokens": None, "output_tokens": None,
                                 "provider": "fake", "model": "fake-1"}


async def test_ticketless_call_keys_on_the_surface_with_a_null_ticket(tmp_path):
    fake = FakeLLM(echo_json("hi"))
    with journal(tmp_path) as j:
        await run(driver(tmp_path, fake, j), ticket=None, surface="triage")
        (done,) = completions(j)
    assert (done.key, done.ticket) == ("llm/triage/0/triage/1/1", None)


# --- replay: the recorded result, never a second call -----------------------


async def test_replay_returns_the_recorded_result_and_does_not_call_the_llm(tmp_path):
    with journal(tmp_path) as j:
        first = await run(driver(tmp_path, FakeLLM(metered(echo_json("recorded"))), j))
    # A restart over the same state dir: the fake would raise if reached.
    never = FakeLLM(RuntimeError("the seam must not be called on replay"))
    with journal(tmp_path) as j:
        replayed = await run(driver(tmp_path, never, j))
        assert len(completions(j)) == 1
    assert never.requests == []
    assert replayed.outcome == first.outcome == "ok"
    assert replayed.artifact == first.artifact
    assert replayed.cost.usd == first.cost.usd == 0.25
    assert (replayed.cost.provider, replayed.cost.model) == ("fake", "fake-1")


async def test_replay_within_one_process_does_not_call_the_llm(tmp_path):
    fake = FakeLLM(echo_json("once"), RuntimeError("must not be reached"))
    with journal(tmp_path) as j:
        d = driver(tmp_path, fake, j)
        first = await run(d)
        again = await run(d)
        assert len(completions(j)) == 1
    assert len(fake.requests) == 1
    assert again.artifact == first.artifact


async def test_a_fresh_run_sequence_takes_fresh_keys_and_really_calls(tmp_path):
    fake = FakeLLM(echo_json("run 0"), echo_json("run 1"))
    with journal(tmp_path) as j:
        d = driver(tmp_path, fake, j)
        first = await run(d, run_seq=0)
        second = await run(d, run_seq=1)
        assert [e.key for e in completions(j)] == [
            "llm/t-1/0/review/1/1", "llm/t-1/1/review/1/1"]
    assert len(fake.requests) == 2
    assert (first.artifact.text, second.artifact.text) == ("run 0", "run 1")


async def test_a_reprompt_takes_a_fresh_call_seq_never_a_replayed_result(tmp_path):
    fake = FakeLLM("not json", echo_json("fixed"))
    with journal(tmp_path) as j:
        result = await run(driver(tmp_path, fake, j))
    assert result.outcome == "ok"
    assert len(fake.requests) == 2
    assert result.artifact.text == "fixed"


async def test_intent_only_window_re_calls(tmp_path):
    with journal(tmp_path) as j:
        with pytest.raises(RuntimeError):
            # The driver terminals infra_error rather than raising; the raw
            # effect surface is exercised to leave an intent with no completion.
            await Effects(j).run(_raise, key="llm/t-1/0/review/1/1", ticket="t-1")
    fake = FakeLLM(echo_json("hi"))
    with journal(tmp_path) as j:
        result = await run(driver(tmp_path, fake, j))
        assert [e.type for e in j.read()] == [
            "effect_intent", "effect_intent", "effect_completion"]
    assert result.outcome == "ok"
    assert len(fake.requests) == 1


async def _raise():
    raise RuntimeError("boom")


# --- failures leave intent only; the record is scrubbed once ----------------


async def test_failed_call_journals_intent_and_no_completion(tmp_path):
    fake = FakeLLM(RuntimeError("provider down"))
    with journal(tmp_path) as j:
        result = await run(driver(tmp_path, fake, j))
        assert [e.type for e in j.read()] == ["effect_intent"]
    assert result.outcome == "infra_error"


async def test_recorded_result_is_scrubbed_before_it_is_journaled_and_replays_the_same_bytes(tmp_path):
    leak = echo_json(f"token {SECRET} leaked")
    with journal(tmp_path) as j:
        first = await run(driver(tmp_path, FakeLLM(leak), j))
        (done,) = completions(j)
        assert SECRET not in json.dumps(done.body)
        assert done.body["result"]["text"] == echo_json(f"token [REDACTED:{SECRET_NAME}] leaked")
    segment_bytes = b"".join(p.read_bytes() for p in (tmp_path / "state" / "journal").iterdir())
    assert SECRET.encode() not in segment_bytes
    with journal(tmp_path) as j:
        replayed = await run(driver(tmp_path, FakeLLM(RuntimeError("no call")), j))
    assert replayed.artifact.text == first.artifact.text == f"token [REDACTED:{SECRET_NAME}] leaked"


# --- run_sequence: the read-time fold over the stem's terminals -------------


def test_run_sequence_counts_the_stems_prior_terminal_transitions(tmp_path):
    with journal(tmp_path) as j:
        assert run_sequence(j, "t-1") == 0
        transition(j, "t-1", "running")
        assert run_sequence(j, "t-1") == 0
        transition(j, "t-1", "gate_failed")
        assert run_sequence(j, "t-1") == 1
        transition(j, "t-2", "merged")
        transition(j, "t-1", "abandoned")
        transition(j, "t-1", "running")
        assert run_sequence(j, "t-1") == 2
        assert run_sequence(j, "t-2") == 1
        assert run_sequence(j, "t-3") == 0


def test_run_sequence_refuses_a_state_outside_the_run_state_vocabulary(tmp_path):
    with journal(tmp_path) as j:
        transition(j, "t-1", "finished")
        with pytest.raises(ValueError, match="finished"):
            run_sequence(j, "t-1")


def test_run_sequence_ignores_other_event_types(tmp_path):
    with journal(tmp_path) as j:
        j.append("effect_completion", {"result": 1}, ticket="t-1", key="llm/t-1/0/review/1/1")
        j.append("cap_consumed", {"cap": "retry"}, ticket="t-1")
        assert run_sequence(j, "t-1") == 0


async def test_derived_sequence_keys_the_next_run_fresh_after_a_terminal(tmp_path):
    fake = FakeLLM(echo_json("first"), echo_json("second"))
    with journal(tmp_path) as j:
        d = driver(tmp_path, fake, j)
        await run(d, run_seq=run_sequence(j, "t-1"))
        transition(j, "t-1", "gate_failed")
        result = await run(d, run_seq=run_sequence(j, "t-1"))
        assert [e.key for e in completions(j)] == [
            "llm/t-1/0/review/1/1", "llm/t-1/1/review/1/1"]
    assert result.artifact.text == "second"


# --- the decorator and key join ---------------------------------------------


def test_effect_key_joins_components_with_slash():
    assert effect_key("llm", "t-1", 0, "review", 1, 1) == "llm/t-1/0/review/1/1"


@pytest.mark.parametrize("bad", ["", "a/b", None])
def test_effect_key_refuses_empty_or_slashed_components(bad):
    with pytest.raises(ValueError):
        effect_key("llm", bad)


class Notifier:
    def __init__(self, effects):
        self.effects = effects
        self.sent = []

    @effect(key=lambda stem, event: effect_key("notify", stem, event),
            ticket=lambda stem, event: stem)
    async def notify(self, stem, event):
        self.sent.append((stem, event))
        return {"sent": event}

    @effect(key="retro/1", cost=lambda result: {"usd": result["usd"]})
    async def retro(self):
        self.sent.append(("retro", None))
        return {"usd": 1.5}


async def test_decorator_keys_from_the_effects_own_arguments(tmp_path):
    with journal(tmp_path) as j:
        n = Notifier(Effects(j))
        assert await n.notify("t-1", "spiral") == {"sent": "spiral"}
        assert await n.notify("t-1", "spiral") == {"sent": "spiral"}
        assert await n.notify("t-2", "spiral") == {"sent": "spiral"}
        assert [(e.key, e.ticket) for e in completions(j)] == [
            ("notify/t-1/spiral", "t-1"), ("notify/t-2/spiral", "t-2")]
    assert n.sent == [("t-1", "spiral"), ("t-2", "spiral")]


async def test_decorator_bare_string_key_is_a_singleton_with_cost(tmp_path):
    with journal(tmp_path) as j:
        n = Notifier(Effects(j))
        await n.retro()
        await n.retro()
        (done,) = completions(j)
    assert (done.key, done.ticket, done.body) == (
        "retro/1", None, {"result": {"usd": 1.5}, "cost": {"usd": 1.5}})
    assert n.sent == [("retro", None)]
