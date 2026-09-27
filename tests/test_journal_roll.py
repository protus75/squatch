"""Journal rolling keeps the full ordered event stream intact."""

from datetime import datetime, timedelta, timezone

import pytest

from squatch.journal import Journal, JournalCorruption

T0 = datetime(2026, 8, 4, 12, 30, 15, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, now=T0):
        self.now = now

    def __call__(self):
        return self.now


def test_size_roll_creates_next_active_segment_without_mutating_old_one(tmp_path):
    clock = FakeClock()
    with Journal(tmp_path, clock=clock) as journal:
        journal.append("signal", {"n": 1})
        old = journal.segments()[0]
        with old.open("r+b") as fh:
            fh.truncate(64 * 1024 * 1024)
        old_bytes = old.read_bytes()

        journal.append("signal", {"n": 2})

        assert [path.name for path in journal.segments()] == [
            "000001-20260804.jsonl", "000002-20260804.jsonl"]
        assert old.read_bytes() == old_bytes
        assert journal.segments()[-1].read_text().endswith("\n")


def test_age_roll_preserves_ordered_replay_across_immutable_segments(tmp_path):
    clock = FakeClock()
    with Journal(tmp_path, clock=clock) as journal:
        first = journal.append("signal", {"n": 1})
        old = journal.segments()[0]
        old_bytes = old.read_bytes()
        clock.now += timedelta(hours=24)
        second = journal.append("signal", {"n": 2})

        assert [path.name for path in journal.segments()] == [
            "000001-20260804.jsonl", "000002-20260805.jsonl"]
        assert old.read_bytes() == old_bytes
        assert list(journal.read()) == [first, second]


@pytest.mark.parametrize("first_line", [b"not json\n", b"\n"])
def test_opening_active_segment_with_bad_first_record_fails_closed(tmp_path, first_line):
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    (journal_dir / "000001-20260804.jsonl").write_bytes(first_line)

    with pytest.raises(JournalCorruption, match=r"000001-20260804\.jsonl:1:"):
        Journal(tmp_path, clock=FakeClock())
