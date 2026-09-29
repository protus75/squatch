import json
from datetime import datetime, timezone

import pytest

from squatch.box import Box, BoxCorruption
from squatch.config import Config
from squatch.inbox import Inbox, LOG_EXCERPT_LIMIT, REPLAY_LIMIT
from squatch.redact import Redactor
from squatch.seams import LocalFilesystem


def _report(**updates):
    values = {
        "schema_version": 1, "origin": "player", "summary": "reproduced defect",
        "signature": "fixture:escape", "app_commit": "abc", "app_version": "1",
        "implicated_paths": ["app.py"], "replay_file": "replay.json",
        "replay_bytes": 2, "log_excerpt": "ok", "log_excerpt_bytes": 2,
    }
    values.update(updates)
    return values


class RecordingFilesystem(LocalFilesystem):
    def __init__(self):
        self.reads = []

    def read(self, path):
        self.reads.append(path)
        return super().read(path)


class VanishingReplayFilesystem(LocalFilesystem):
    def __init__(self, replay):
        self.replay = replay

    def read(self, path):
        if path == self.replay:
            raise OSError("replay disappeared")
        return super().read(path)


def _inbox(tmp_path, fs=None, redact=None):
    fs = fs or LocalFilesystem()
    box = Box(tmp_path / "state", fs=fs, clock=lambda: datetime.now(timezone.utc))
    path = tmp_path / "inbox"
    path.mkdir()
    return path, box, Inbox(path, box=box, fs=fs, redact=redact or Redactor({}))


def _configured_redactor(secret):
    config = Config.model_validate({
        "schema_version": 1, "state_dir": "state", "routing": [],
        "providers": [{"name": "host", "kind": "cli", "auth": "HOST_KEY",
                       "models_by_tier": dict.fromkeys(
                           ("low", "medium", "high", "max"), "model"),
                       "limits": {"concurrency": 1}}],
    })
    return Redactor.from_config(config, {"HOST_KEY": secret})


def test_invalid_metadata_is_rejected_before_replay_read(tmp_path):
    fs = RecordingFilesystem()
    path, box, inbox = _inbox(tmp_path, fs)
    replay = path / "replay.json"
    replay.write_bytes(b"{}")
    report = path / "bad.report.json"
    report.write_text(json.dumps(_report(schema_version=2)))

    assert inbox.consume().rejected == 1
    assert replay not in fs.reads
    assert not box.messages()
    assert (path / "bad.report.rejected").is_file()


def test_replay_and_excerpt_caps_precede_box_recording(tmp_path):
    path, box, inbox = _inbox(tmp_path)
    (path / "large-replay.json").write_bytes(b"x" * (REPLAY_LIMIT + 1))
    (path / "too-big.report.json").write_text(json.dumps(_report(
        replay_file="large-replay.json", replay_bytes=REPLAY_LIMIT)))
    (path / "small-replay.json").write_bytes(b"{}")
    (path / "excerpt.report.json").write_text(json.dumps(_report(
        signature="excerpt", replay_file="small-replay.json", replay_bytes=2,
        log_excerpt="x" * (LOG_EXCERPT_LIMIT + 1),
        log_excerpt_bytes=LOG_EXCERPT_LIMIT + 1)))

    assert inbox.consume().rejected == 2
    assert not box.messages()


def test_copies_bounded_evidence_before_recording_bug_message(tmp_path):
    path, box, inbox = _inbox(tmp_path)
    (path / "replay.json").write_bytes(b"{}")
    (path / "good.report.json").write_text(json.dumps(_report()))

    assert inbox.consume().filed == 1
    [message] = box.messages()
    assert message.message_class == "bug_report" and message.evidence is not None
    assert (tmp_path / "state" / message.evidence.replay_path).read_bytes() == b"{}"
    assert (path / "good.report.filed").is_file()


def test_escape_heavy_excerpt_at_limit_is_filed(tmp_path):
    path, box, inbox = _inbox(tmp_path)
    (path / "replay.json").write_bytes(b"{}")
    excerpt = "\x1b" * LOG_EXCERPT_LIMIT
    (path / "escaped.report.json").write_text(json.dumps(_report(
        log_excerpt=excerpt, log_excerpt_bytes=LOG_EXCERPT_LIMIT)))

    assert inbox.consume().filed == 1
    [message] = box.messages()
    assert message.evidence is not None
    assert message.evidence.log_excerpt == excerpt
    assert (path / "escaped.report.filed").is_file()


@pytest.mark.parametrize("at_limit", [False, True])
def test_configured_secrets_are_redacted_before_box_custody(tmp_path, at_limit):
    secret = "private-key"
    redact = _configured_redactor(secret)
    path, box, inbox = _inbox(tmp_path, redact=redact)
    excerpt = (secret * (LOG_EXCERPT_LIMIT // len(secret))).ljust(
        LOG_EXCERPT_LIMIT, "x") if at_limit else f"failed with {secret}"
    replay_file = f"{secret}.json"
    (path / replay_file).write_bytes(b"{}")
    (path / "secret.report.json").write_text(json.dumps(_report(
        summary=f"failure {secret}", signature=f"fixture:{secret}",
        app_commit=f"commit-{secret}", app_version=f"version-{secret}",
        implicated_paths=[f"src/{secret}.py", f"tests/test_{secret}.py"],
        replay_file=replay_file,
        log_excerpt=excerpt, log_excerpt_bytes=len(excerpt.encode()))))

    assert inbox.consume().filed == 1
    [message] = box.messages()
    assert secret not in message.model_dump_json()
    assert "[REDACTED:HOST_KEY]" in message.summary
    assert message.evidence.app_commit == "commit-[REDACTED:HOST_KEY]"
    assert message.evidence.app_version == "version-[REDACTED:HOST_KEY]"
    assert message.evidence.implicated_paths == (
        "src/[REDACTED:HOST_KEY].py", "tests/test_[REDACTED:HOST_KEY].py")
    assert "[REDACTED:HOST_KEY]" in message.evidence.log_excerpt
    assert len(message.evidence.log_excerpt.encode()) <= LOG_EXCERPT_LIMIT
    assert all(secret.encode() not in file.read_bytes()
               for file in box.dir.rglob("*") if file.is_file())
    assert (path / "secret.report.filed").is_file()


@pytest.mark.parametrize("prefix", [b"", b"\xff"])
def test_replay_with_configured_secret_is_rejected_before_box_custody(tmp_path, prefix):
    secret = "private-key-\u00e9"
    path, box, inbox = _inbox(tmp_path, redact=_configured_redactor(secret))
    replay = prefix + json.dumps({"token": secret}, ensure_ascii=False).encode()
    (path / "replay.json").write_bytes(replay)
    (path / "secret.report.json").write_text(json.dumps(_report(
        app_version=secret, replay_bytes=len(replay))))

    assert inbox.consume().rejected == 1
    assert (path / "secret.report.rejected").is_file()
    assert not box.messages()
    assert not list(box.dir.rglob("*.replay"))
    assert all(secret.encode() not in file.read_bytes()
               for file in box.dir.rglob("*") if file.is_file())
    (path / "good-replay.json").write_bytes(b"{}")
    (path / "good.report.json").write_text(json.dumps(_report(
        signature="good", replay_file="good-replay.json")))
    assert inbox.consume().filed == 1


@pytest.mark.parametrize("operation", ["store_evidence", "enqueue"])
@pytest.mark.parametrize("failure", [OSError, ValueError, BoxCorruption])
def test_box_failure_preserves_report_for_retry(tmp_path, monkeypatch, operation, failure):
    path, box, inbox = _inbox(tmp_path)
    (path / "replay.json").write_bytes(b"{}")
    report = path / "first.report.json"
    report.write_text(json.dumps(_report()))
    later = path / "later.report.json"
    later.write_text(json.dumps(_report(signature="later")))
    original = getattr(box, operation)
    failed = False

    def fail_once(**kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise failure("Box custody unavailable")
        return original(**kwargs)

    monkeypatch.setattr(box, operation, fail_once)
    with pytest.raises(failure, match="Box custody unavailable"):
        inbox.consume()

    assert report.is_file() and later.is_file()
    assert not list(path.glob("*.rejected"))
    assert not box.messages()
    assert inbox.consume().filed == 2
    assert report.with_suffix(".filed").is_file()
    assert later.with_suffix(".filed").is_file()
    assert [message.reports for message in box.messages()] == [1, 1]


@pytest.mark.parametrize("replay_file", ["missing.json", "bad\x00replay.json"])
def test_invalid_replay_path_is_quarantined_without_stalling_later_reports(
        tmp_path, replay_file):
    path, box, inbox = _inbox(tmp_path)
    (path / "bad.report.json").write_text(json.dumps(_report(replay_file=replay_file)))
    (path / "good-replay.json").write_bytes(b"{}")
    (path / "good.report.json").write_text(json.dumps(_report(
        signature="good", replay_file="good-replay.json")))

    result = inbox.consume()
    assert (result.rejected, result.filed) == (1, 1)
    assert (path / "bad.report.rejected").is_file()
    assert (path / "good.report.filed").is_file()
    assert len(box.messages()) == 1


def test_unreadable_replay_is_quarantined_without_stalling_later_reports(tmp_path):
    path = tmp_path / "inbox"
    path.mkdir()
    replay = path / "replay.json"
    replay.write_bytes(b"{}")
    fs = VanishingReplayFilesystem(replay)
    box = Box(tmp_path / "state", fs=fs, clock=lambda: datetime.now(timezone.utc))
    inbox = Inbox(path, box=box, fs=fs, redact=Redactor({}))
    (path / "bad.report.json").write_text(json.dumps(_report()))
    (path / "good-replay.json").write_bytes(b"{}")
    (path / "good.report.json").write_text(json.dumps(_report(
        signature="good", replay_file="good-replay.json")))

    assert inbox.consume().rejected == 1
    assert (path / "bad.report.rejected").is_file()
    assert (path / "good.report.filed").is_file()
    assert len(box.messages()) == 1


def test_repeat_report_records_a_rereport(tmp_path):
    path, box, inbox = _inbox(tmp_path)
    (path / "replay.json").write_bytes(b"{}")
    (path / "first.report.json").write_text(json.dumps(_report()))
    assert inbox.consume().filed == 1
    (path / "second.report.json").write_text(json.dumps(_report()))

    assert inbox.consume().duplicates == 1
    assert box.messages()[0].reports == 2


@pytest.mark.parametrize("rereport", [False, True])
def test_failed_filed_rename_replays_without_counting_again(tmp_path, rereport):
    class FailedRenameFilesystem(LocalFilesystem):
        fail = False

        def replace(self, src, dst):
            if self.fail and dst.suffix == ".filed":
                self.fail = False
                raise OSError("crash before filed rename")
            super().replace(src, dst)

    fs = FailedRenameFilesystem()
    path, box, inbox = _inbox(tmp_path, fs)
    (path / "replay.json").write_bytes(b"{}")
    if rereport:
        (path / "first.report.json").write_text(json.dumps(_report()))
        assert inbox.consume().filed == 1
        box.resolve(box.messages()[0].id, status="tombstoned", link="existing",
                    note="already covered")
    arrival = path / "arrival.report.json"
    arrival.write_text(json.dumps(_report()))
    fs.fail = True

    with pytest.raises(OSError, match="crash before filed rename"):
        inbox.consume()

    assert arrival.is_file()
    expected_count = 2 if rereport else 1
    assert box.messages()[0].reports == expected_count
    restarted_box = Box(tmp_path / "state", fs=fs,
                        clock=lambda: datetime.now(timezone.utc))
    restarted = Inbox(path, box=restarted_box, fs=fs, redact=Redactor({}))
    assert restarted.consume().duplicates == 1
    [message] = restarted_box.messages()
    assert message.reports == expected_count
    assert len(message.rereport_ids) == expected_count
    assert message.status == ("tombstoned" if rereport else "pending")
    assert not arrival.exists()
    assert arrival.with_suffix(".filed").is_file()
    assert restarted.consume().duplicates == 0
