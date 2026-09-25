"""effects.py: once-per-key effect execution over the journal (plan sections 2, 6).

Once-semantics is COMPLETION-keyed: a key with an `effect_completion` event in
the surviving journal replays its recorded result and never re-executes. A key
with only an `effect_intent` (the intent-only crash window) re-executes here;
closing that window is Phase 1 reconcile-on-entry (section 11), not this
primitive.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from squatch.effects import Effects
from squatch.journal import Journal, render_ts

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)


def fixed_clock(when=T0):
    return lambda: when


class TickingClock:
    def __init__(self, start=T0):
        self.now = start

    def __call__(self):
        self.now += timedelta(seconds=1)
        return self.now


class FakeProcessExec:
    """Records every spawn; the seam an action's side effect crosses."""

    def __init__(self):
        self.calls = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None):
        self.calls.append(list(argv))
        return 0, f"ran {argv[-1]} #{len(self.calls)}", ""


class FakeFilesystem:
    def __init__(self):
        self.files = {}
        self.writes = 0

    def write(self, path, data):
        self.writes += 1
        self.files[Path(path)] = data

    def replace(self, src, dst):
        self.files[Path(dst)] = self.files.pop(Path(src))


def git_action(px, name):
    async def action():
        rc, out, err = await px.run(["git", "-C", "/wt", name], cwd=Path("/wt"),
                                    env={}, timeout=30)
        return {"rc": rc, "out": out}
    return action


def segment(state_dir):
    return state_dir / "journal" / "000001-20260804.jsonl"


def events(journal):
    return [(e.type, e.key, e.ticket, e.body) for e in journal.read()]


# --- execute once, journal intent then completion ---------------------------


async def test_first_run_journals_intent_executes_then_journals_completion(tmp_path):
    px = FakeProcessExec()
    clock = TickingClock()
    with Journal(tmp_path, clock=clock) as j:
        result = await Effects(j).run(git_action(px, "status"), key="git/T-1/1/status",
                                      ticket="T-1")
        assert result == {"rc": 0, "out": "ran status #1"}
        assert px.calls == [["git", "-C", "/wt", "status"]]
        recorded = list(j.read())
    assert [(e.type, e.key, e.ticket, e.body) for e in recorded] == [
        ("effect_intent", "git/T-1/1/status", "T-1", {}),
        ("effect_completion", "git/T-1/1/status", "T-1",
         {"result": {"rc": 0, "out": "ran status #1"}}),
    ]
    assert recorded[0].ts < recorded[1].ts


async def test_intent_is_durable_before_the_action_runs(tmp_path):
    seen = []
    with Journal(tmp_path, clock=fixed_clock()) as j:
        async def action():
            seen.extend(events(j))
            return "done"
        await Effects(j).run(action, key="k", ticket=None)
    assert seen == [("effect_intent", "k", None, {})]
    # And the same line is on disk (write-ahead), not merely buffered.
    lines = segment(tmp_path).read_bytes().splitlines()
    assert json.loads(lines[0])["type"] == "effect_intent"


async def test_same_key_within_process_replays_without_executing(tmp_path):
    px = FakeProcessExec()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        fx = Effects(j)
        first = await fx.run(git_action(px, "status"), key="k", ticket="T-1")
        again = await fx.run(git_action(px, "status"), key="k", ticket="T-1")
    assert again == first
    assert len(px.calls) == 1


async def test_distinct_keys_each_execute(tmp_path):
    px = FakeProcessExec()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        fx = Effects(j)
        a = await fx.run(git_action(px, "status"), key="git/T-1/1/status", ticket="T-1")
        b = await fx.run(git_action(px, "status"), key="git/T-1/2/status", ticket="T-1")
    assert a != b
    assert len(px.calls) == 2


# --- restart: completion-keyed replay ---------------------------------------


async def test_completed_key_is_not_re_executed_on_restart(tmp_path):
    px = FakeProcessExec()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        first = await Effects(j).run(git_action(px, "status"), key="k", ticket="T-1")
    # "Restart": fresh Journal and Effects over the same state dir.
    with Journal(tmp_path, clock=fixed_clock()) as j:
        replayed = await Effects(j).run(git_action(px, "status"), key="k", ticket="T-1")
        assert events(j) == [
            ("effect_intent", "k", "T-1", {}),
            ("effect_completion", "k", "T-1", {"result": first}),
        ]
    assert replayed == first
    assert len(px.calls) == 1


class CrashAfter(Exception):
    pass


class CrashingJournal:
    """Dies the instant the named event type has been fsync'd."""

    def __init__(self, inner, after_type):
        self._inner = inner
        self._after = after_type

    def append(self, type, body, **kw):
        event = self._inner.append(type, body, **kw)
        if type == self._after:
            raise CrashAfter(type)
        return event

    def read(self):
        return self._inner.read()


async def test_crash_after_completion_journaled_does_not_double_execute(tmp_path):
    px = FakeProcessExec()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(CrashAfter):
            await Effects(CrashingJournal(j, "effect_completion")).run(
                git_action(px, "status"), key="k", ticket="T-1")
    assert len(px.calls) == 1
    with Journal(tmp_path, clock=fixed_clock()) as j:
        replayed = await Effects(j).run(git_action(px, "status"), key="k", ticket="T-1")
    assert replayed == {"rc": 0, "out": "ran status #1"}
    assert len(px.calls) == 1


async def test_replay_returns_the_recorded_result_not_a_fresh_one(tmp_path):
    fs = FakeFilesystem()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        async def action():
            fs.write(Path("/out/run.md"), b"attempt 1")
            return {"path": "/out/run.md", "bytes": 9}
        first = await Effects(j).run(action, key="run-record/T-1/1", ticket="T-1")
    with Journal(tmp_path, clock=fixed_clock()) as j:
        async def different_action():
            fs.write(Path("/out/run.md"), b"attempt 2 -- must never land")
            return {"path": "/out/run.md", "bytes": 99}
        replayed = await Effects(j).run(different_action, key="run-record/T-1/1",
                                        ticket="T-1")
    assert replayed == first == {"path": "/out/run.md", "bytes": 9}
    assert fs.writes == 1
    assert fs.files[Path("/out/run.md")] == b"attempt 1"


async def test_completed_keys_are_scanned_from_every_segment(tmp_path):
    jd = tmp_path / "journal"
    jd.mkdir()
    old = {"v": 1, "type": "effect_completion", "ts": render_ts(T0), "ticket": "T-0",
           "key": "notify/T-0/spiral", "body": {"result": "sent"}}
    (jd / "000001-20260801.jsonl").write_text(json.dumps(old) + "\n")
    (jd / "000002-20260804.jsonl").write_text("")
    executed = []
    with Journal(tmp_path, clock=fixed_clock()) as j:
        async def action():
            executed.append(1)
            return "sent again"
        assert await Effects(j).run(action, key="notify/T-0/spiral", ticket="T-0") == "sent"
    assert executed == []


# --- the intent-only window stays open here (Phase 1 reconcile closes it) ----


async def test_intent_without_completion_re_executes(tmp_path):
    px = FakeProcessExec()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(CrashAfter):
            await Effects(CrashingJournal(j, "effect_intent")).run(
                git_action(px, "status"), key="k", ticket="T-1")
    assert px.calls == []
    with Journal(tmp_path, clock=fixed_clock()) as j:
        result = await Effects(j).run(git_action(px, "status"), key="k", ticket="T-1")
        assert [t for t, *_ in events(j)] == [
            "effect_intent", "effect_intent", "effect_completion"]
    assert result == {"rc": 0, "out": "ran status #1"}
    assert len(px.calls) == 1


async def test_torn_completion_line_is_not_a_completion(tmp_path):
    px = FakeProcessExec()
    with Journal(tmp_path, clock=fixed_clock()) as j:
        await Effects(j).run(git_action(px, "status"), key="k", ticket="T-1")
    seg = segment(tmp_path)
    data = seg.read_bytes()
    seg.write_bytes(data[:-20])  # crash mid-write of the completion record
    with Journal(tmp_path, clock=fixed_clock()) as j:
        await Effects(j).run(git_action(px, "status"), key="k", ticket="T-1")
    assert len(px.calls) == 2


async def test_failed_action_journals_no_completion_and_propagates(tmp_path):
    class Boom(Exception):
        pass

    with Journal(tmp_path, clock=fixed_clock()) as j:
        fx = Effects(j)

        async def failing():
            raise Boom()
        with pytest.raises(Boom):
            await fx.run(failing, key="k", ticket="T-1")
        assert [t for t, *_ in events(j)] == ["effect_intent"]

        async def recovered():
            return "ok"
        assert await fx.run(recovered, key="k", ticket="T-1") == "ok"
        assert [t for t, *_ in events(j)] == [
            "effect_intent", "effect_intent", "effect_completion"]


# --- key discipline ----------------------------------------------------------


@pytest.mark.parametrize("bad", ["", None, 7])
async def test_key_must_be_a_nonempty_string(tmp_path, bad):
    async def action():
        return 1
    with Journal(tmp_path, clock=fixed_clock()) as j:
        with pytest.raises(ValueError):
            await Effects(j).run(action, key=bad, ticket=None)
        assert events(j) == []
