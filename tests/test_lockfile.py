"""lockfile.py: the single-writer lockfile (SQUATCH_PLAN.md D2, sections 6, 15).

Correctness comes from `flock`, so contention is proven with a real second
open-file-description (a second handle in-process, and a real child process);
the identity record is diagnostics only and is asserted as such.
"""

import fcntl
import json
import os
import socket
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squatch.lockfile import Holder, Lockfile, LockHeld

T0 = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


def clock():
    return T0


def make(tmp_path, instance_id="v0.1.0", **kw):
    return Lockfile(tmp_path, instance_id=instance_id, clock=clock, **kw)


# --- acquire ------------------------------------------------------------------

def test_lock_path_is_squatch_lock_under_state_dir(tmp_path):
    lock = make(tmp_path)
    assert lock.path == tmp_path / "squatch.lock"


def test_acquire_takes_the_flock_and_records_identity(tmp_path):
    lock = make(tmp_path)
    lock.acquire()
    try:
        holder = Holder(**json.loads(lock.path.read_text()))
        assert holder == Holder(instance_id="v0.1.0", pid=os.getpid(),
                                host=socket.gethostname(), state_dir=str(tmp_path),
                                started_at=T0.isoformat())
        assert holder.started_at == "2026-08-04T12:00:00+00:00"
    finally:
        lock.release()


def test_acquire_creates_a_missing_state_dir(tmp_path):
    state_dir = tmp_path / "nested" / "state"
    lock = Lockfile(state_dir, instance_id="v0.1.0", clock=clock)
    lock.acquire()
    try:
        assert lock.path.is_file()
    finally:
        lock.release()


def test_acquire_twice_on_one_holder_is_refused(tmp_path):
    lock = make(tmp_path)
    lock.acquire()
    try:
        with pytest.raises(LockHeld):
            lock.acquire()
    finally:
        lock.release()


# --- contention ---------------------------------------------------------------

def test_second_handle_is_refused_and_told_who_holds_it(tmp_path):
    first = make(tmp_path, instance_id="v0.1.0")
    second = make(tmp_path, instance_id="v0.2.0-dev")
    first.acquire()
    try:
        with pytest.raises(LockHeld) as e:
            second.acquire()
        assert e.value.holder.instance_id == "v0.1.0"
        assert e.value.holder.pid == os.getpid()
        assert "v0.1.0" in str(e.value)
        # The loser never overwrote the winner's record.
        assert json.loads(first.path.read_text())["instance_id"] == "v0.1.0"
        assert not second.held
    finally:
        first.release()


def test_refusal_does_not_clobber_record_it_could_not_read(tmp_path):
    # A holder whose record is unreadable (mid-write, or a foreign writer)
    # still refuses: correctness is the flock, not the JSON.
    path = tmp_path / "squatch.lock"
    path.write_text("not json")
    raw = os.open(path, os.O_RDWR)
    fcntl.flock(raw, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(LockHeld) as e:
            make(tmp_path).acquire()
        assert e.value.holder is None
        assert path.read_text() == "not json"
    finally:
        os.close(raw)


def test_lock_held_by_another_process_is_refused(tmp_path):
    lock = make(tmp_path)
    child_code = (
        "import sys\n"
        "from datetime import UTC, datetime\n"
        "from squatch.lockfile import Lockfile\n"
        f"lock = Lockfile({str(tmp_path)!r}, instance_id='child', "
        "clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))\n"
        "lock.acquire()\n"
        "print('held', flush=True)\n"
        "sys.stdin.readline()\n"
        "lock.release()\n"
    )
    child = subprocess.Popen([sys.executable, "-c", child_code], cwd=Path(__file__).parents[1],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "held"
        with pytest.raises(LockHeld) as e:
            lock.acquire()
        assert e.value.holder.instance_id == "child"
        assert e.value.holder.pid == child.pid
    finally:
        child.stdin.write("\n")
        child.stdin.close()
        child.wait(timeout=30)
    # Once the child exits the kernel has dropped its lock: no stale reclaim.
    lock.acquire()
    lock.release()


def test_crashed_holders_lock_is_free(tmp_path):
    # A holder that dies without releasing leaves its record behind; the next
    # acquire succeeds because flock died with the process.
    subprocess.run(
        [sys.executable, "-c",
         "from datetime import UTC, datetime\n"
         "from squatch.lockfile import Lockfile\n"
         f"Lockfile({str(tmp_path)!r}, instance_id='crashed', "
         "clock=lambda: datetime(2026, 1, 1, tzinfo=UTC)).acquire()\n"],
        cwd=Path(__file__).parents[1], check=True)
    assert json.loads((tmp_path / "squatch.lock").read_text())["instance_id"] == "crashed"
    lock = make(tmp_path)
    lock.acquire()
    try:
        assert json.loads(lock.path.read_text())["instance_id"] == "v0.1.0"
    finally:
        lock.release()


# --- release ------------------------------------------------------------------

def test_release_then_reacquire(tmp_path):
    lock = make(tmp_path)
    lock.acquire()
    lock.release()
    assert not lock.held
    other = make(tmp_path, instance_id="next")
    other.acquire()
    try:
        assert json.loads(other.path.read_text())["instance_id"] == "next"
    finally:
        other.release()
    lock.acquire()
    lock.release()


def test_release_frees_the_lock_for_another_process(tmp_path):
    lock = make(tmp_path)
    lock.acquire()
    lock.release()
    probe = subprocess.run(
        [sys.executable, "-c",
         "from datetime import UTC, datetime\n"
         "from squatch.lockfile import Lockfile\n"
         f"lock = Lockfile({str(tmp_path)!r}, instance_id='probe', "
         "clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))\n"
         "lock.acquire(); lock.release(); print('ok')\n"],
        cwd=Path(__file__).parents[1], capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
    assert probe.stdout.strip() == "ok"


def test_release_when_not_held_is_an_error(tmp_path):
    lock = make(tmp_path)
    with pytest.raises(RuntimeError):
        lock.release()


def test_release_keeps_the_last_record_for_diagnostics(tmp_path):
    # The file is never deleted: unlinking while another process holds a
    # handle to it would let two processes lock different inodes.
    lock = make(tmp_path)
    lock.acquire()
    lock.release()
    assert lock.path.is_file()


def test_context_manager_releases_on_exit_and_on_error(tmp_path):
    lock = make(tmp_path)
    with lock:
        assert lock.held
    assert not lock.held
    with pytest.raises(ValueError):
        with lock:
            raise ValueError
    assert not lock.held
    with pytest.raises(LockHeld):
        with make(tmp_path):
            make(tmp_path, instance_id="other").acquire()


# --- identity -----------------------------------------------------------------

def test_instance_id_must_be_a_non_empty_string(tmp_path):
    with pytest.raises(ValueError):
        Lockfile(tmp_path, instance_id="", clock=clock)


def test_clock_is_the_seam_never_wall_time(tmp_path):
    calls = []

    def counting_clock():
        calls.append(1)
        return T0

    lock = Lockfile(tmp_path, instance_id="v0.1.0", clock=counting_clock)
    lock.acquire()
    lock.release()
    assert calls, "started_at must come from the injected clock"
