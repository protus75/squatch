import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from squatch.box import (BOOTSTRAP_ORIGIN, MESSAGE_CLASSES, STATUSES, Box, Ingested, Message,
                         enqueue_second_problems, ingest, signature)
from squatch.seams import LocalFilesystem

T0 = datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        value = self.now
        self.now += timedelta(seconds=1)
        return value


def box(tmp_path):
    return Box(tmp_path / "state", fs=LocalFilesystem(), clock=Clock())


def test_closed_vocabularies_and_message_shape(tmp_path):
    assert MESSAGE_CLASSES == {
        "suggestion", "failure_report", "override_report", "retro_finding", "bug_report"}
    assert STATUSES == {"pending", "authored", "tombstoned", "decided"}
    valid = box(tmp_path).enqueue(message_class="suggestion", summary="x", detail="x",
                                  origin="stem")
    data = box(tmp_path).get(valid.id).model_dump()
    for field, value in (("message_class", "other"), ("status", "other")):
        with pytest.raises(ValidationError):
            Message.model_validate({**data, field: value})
    with pytest.raises(ValidationError):
        Message.model_validate({**data, "surprise": True})


def test_bug_policy_inputs_are_class_specific_and_backward_compatible(tmp_path):
    queue = box(tmp_path)
    for bug_origin, has_repro in (("self_diagnosed", False), ("player", True)):
        item = queue.enqueue(
            message_class="bug_report", summary="bug", detail=f"bug {bug_origin}",
            origin="host", bug_origin=bug_origin, has_repro=has_repro)
        message = queue.get(item.id)
        assert (message.bug_origin, message.has_repro) == (bug_origin, has_repro)

    base = queue.get(queue.enqueue(
        message_class="suggestion", summary="idea", detail="idea", origin="host").id)
    legacy = base.model_dump(exclude={"bug_origin", "has_repro"})
    loaded = Message.model_validate(legacy)
    assert loaded.bug_origin is None and loaded.has_repro is None

    bug = base.model_dump()
    bug["message_class"] = "bug_report"
    for update in ({}, {"bug_origin": "robot", "has_repro": True},
                   {"bug_origin": "player", "has_repro": 1}):
        with pytest.raises(ValidationError):
            Message.model_validate({**bug, **update})
    with pytest.raises(ValidationError, match="only on bug_report"):
        Message.model_validate({**base.model_dump(), "bug_origin": "player",
                                "has_repro": True})


def test_signature_normalizes_paths_digits_and_whitespace_but_keeps_dimensions():
    left = signature("suggestion", "stem", "check", "gate_failed",
                     "failed 123 at /tmp/a.py   nearby")
    right = signature("suggestion", "stem", "check", "gate_failed",
                      "failed 987 at /other/b.py\nnearby")
    assert left == right
    assert len({signature(*values, reason="same") for values in [
        ("suggestion", "one", "check", "gate_failed"),
        ("failure_report", "one", "check", "gate_failed"),
        ("suggestion", "two", "check", "gate_failed"),
        ("suggestion", "one", "review", "gate_failed"),
        ("suggestion", "one", "check", "timeout"),
    ]}) == 5


def test_enqueue_dedup_pending_get_and_resolve(tmp_path):
    queue = box(tmp_path)
    first = queue.enqueue(message_class="suggestion", summary="first", detail="reason 1",
                          origin="stem", stage="check", outcome="gate_failed", run_seq=0)
    sig8 = queue.get(first.id).signature[:8]
    assert first.id == f"box-000001-{sig8}" and not first.duplicate
    assert (queue.dir / f"000001-{sig8}.json").is_file()
    duplicate = queue.enqueue(message_class="suggestion", summary="again", detail="reason 9",
                              origin="stem", stage="check", outcome="gate_failed", run_seq=1)
    assert duplicate.id == first.id and duplicate.duplicate
    assert queue.get(first.id).reports == 2 and len(list(queue.dir.glob("*.json"))) == 1
    second = queue.enqueue(message_class="suggestion", summary="second", detail="different",
                           origin="stem")
    assert queue.get(second.id).seq == 2
    assert [message.id for message in queue.pending()] == [first.id, second.id]
    resolved = queue.resolve(first.id, status="tombstoned", link="existing-ticket",
                             note="already represented")
    assert resolved.status == "tombstoned" and resolved.resolution.link == "existing-ticket"
    with pytest.raises(ValueError, match="not pending"):
        queue.resolve(first.id, status="decided", link="decision", note="done")
    with pytest.raises(ValueError, match="not one of"):
        queue.resolve(second.id, status="unknown", link="x", note="x")


def test_enqueue_second_problems_and_empty_section(tmp_path):
    queue = box(tmp_path)
    record = """## Outcome
premise_failed

## Second problems filed
- first problem
- `box-000099-deadbeef`
* second problem

## Resolved engine/model
x
"""
    ids = enqueue_second_problems(queue, record, stem="ticket", stage="implement",
                                  outcome="premise_failed", run_seq=3)
    assert len(ids) == 2
    assert [(m.origin, m.detail) for m in queue.pending()] == [
        ("ticket", "first problem"), ("ticket", "second problem")]
    assert enqueue_second_problems(queue, "## Second problems filed\n\n## Dead ends\n",
                                   stem="ticket", stage="implement",
                                   outcome="premise_failed", run_seq=4) == []


def test_ingest_is_marker_aware_and_idempotent(tmp_path):
    queue = box(tmp_path)
    source = tmp_path / "suggestions.md"
    source.write_text("- first\n* second\n\n1. third\nfourth\nfifth\n")
    assert ingest(queue, source) == Ingested(5, 0)
    messages = queue.pending()
    assert [m.summary for m in messages] == ["first", "second", "third", "fourth", "fifth"]
    assert all(m.origin == BOOTSTRAP_ORIGIN for m in messages)
    assert ingest(queue, source) == Ingested(0, 5)


def test_module_entry_resolves_a_worktree_to_the_parent_checkout(tmp_path):
    parent = tmp_path / "repo"
    parent.mkdir()
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "squatch", "GIT_AUTHOR_EMAIL": "squatch@test",
           "GIT_COMMITTER_NAME": "squatch", "GIT_COMMITTER_EMAIL": "squatch@test"}
    subprocess.run(["git", "-C", str(parent), "init", "-q", "-b", "main"], env=env, check=True)
    (parent / "config.yaml").write_text(
        "schema_version: 1\nstate_dir: state\nproviders: []\nrouting: []\n")
    (parent / "seed").write_text("seed")
    subprocess.run(["git", "-C", str(parent), "add", "--", "config.yaml", "seed"], env=env,
                   check=True)
    subprocess.run(["git", "-C", str(parent), "commit", "-q", "-m", "seed"], env=env,
                   check=True)
    worktree = tmp_path / "worktree"
    subprocess.run(["git", "-C", str(parent), "worktree", "add", "-q", "-b", "item",
                    str(worktree)], env=env, check=True)
    source = worktree / "ideas.md"
    source.write_text("one\n")
    proc = subprocess.run([sys.executable, "-m", "squatch.box", "ingest", str(source)],
                          cwd=worktree, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert len(list((parent / "state" / "box").glob("*.json"))) == 1
    assert not (worktree / "state" / "box").exists()
    missing = subprocess.run([sys.executable, "-m", "squatch.box", "ingest", "missing.md"],
                             cwd=worktree, env=env, capture_output=True, text=True)
    assert missing.returncode == 2 and "paved road" in missing.stderr

    message = next((parent / "state" / "box").glob("*.json"))
    message.write_text("not json")
    corrupt = subprocess.run([sys.executable, "-m", "squatch.box", "ingest", str(source)],
                             cwd=worktree, env=env, capture_output=True, text=True)
    assert corrupt.returncode == 2
    assert str(message) in corrupt.stderr
    assert "repair or remove the named corrupt box message" in corrupt.stderr
    assert "cannot resolve the instance checkout" not in corrupt.stderr
