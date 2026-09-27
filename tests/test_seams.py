"""seams.py `SubprocessExec`: the production process seam (plan section 15)."""

import asyncio
import os
import stat
import sys
from pathlib import Path

import pytest

from squatch.seams import ExecutableNotFound, SubprocessExec, SubprocessNotifications

PY = sys.executable
ENV = {"PATH": os.environ["PATH"]}


async def test_runs_argv_and_captures_streams(tmp_path):
    rc, out, err = await SubprocessExec().run(
        [PY, "-c", "import sys; print('o'); print('e', file=sys.stderr); sys.exit(3)"],
        cwd=tmp_path, env=ENV, timeout=30)
    assert (rc, out, err) == (3, "o\n", "e\n")


async def test_stdout_line_callback_observes_arrival_order_and_unterminated_tail(tmp_path):
    seen = []
    first_line = asyncio.Event()
    release = tmp_path / "release"
    code = (
        "import pathlib, sys, time\n"
        "sys.stdout.write('first\\nsecond\\n'); sys.stdout.flush()\n"
        f"release = pathlib.Path({str(release)!r})\n"
        "while not release.exists(): time.sleep(.01)\n"
        "sys.stdout.write('tail'); sys.stdout.flush()\n"
    )

    def observe(line):
        seen.append(line)
        first_line.set()

    task = asyncio.create_task(SubprocessExec().run(
        [PY, "-c", code], cwd=tmp_path, env=ENV, timeout=30, on_stdout_line=observe))
    await first_line.wait()
    assert seen == ["first", "second"]
    release.touch()
    rc, out, err = await task
    assert (rc, out, err) == (0, "first\nsecond\ntail", "")
    assert seen == ["first", "second", "tail"]


async def test_stdout_callback_preserves_long_lines_with_and_without_a_consumer(tmp_path):
    code = "import sys; sys.stdout.write('x' * 70000 + '\\nend'); sys.stdout.flush()"
    uncaptured = await SubprocessExec().run(
        [PY, "-c", code], cwd=tmp_path, env=ENV, timeout=30)
    seen = []
    captured = await SubprocessExec().run(
        [PY, "-c", code], cwd=tmp_path, env=ENV, timeout=30, on_stdout_line=seen.append)
    assert captured == uncaptured == (0, "x" * 70000 + "\nend", "")
    assert seen == ["x" * 70000, "end"]


async def test_callback_failure_kills_the_whole_group(tmp_path):
    marker = tmp_path / "grandchild.pid"
    code = (
        "import pathlib, subprocess, sys, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(marker)!r}).write_text(str(p.pid))\n"
        "print('ready', flush=True)\n"
        "time.sleep(60)\n"
    )

    def fail(_line):
        raise RuntimeError("observer failed")

    with pytest.raises(RuntimeError, match="observer failed"):
        await SubprocessExec().run(
            [PY, "-c", code], cwd=tmp_path, env=ENV, timeout=30, on_stdout_line=fail)
    grandchild = int(marker.read_text())
    await asyncio.sleep(.2)
    with pytest.raises(ProcessLookupError):
        os.kill(grandchild, 0)


async def test_child_sees_only_the_declared_env(tmp_path):
    rc, out, _ = await SubprocessExec().run(
        [PY, "-c", "import os; print(sorted(os.environ))"],
        cwd=tmp_path, env={**ENV, "SQUATCH_X": "1"}, timeout=30)
    seen = set(eval(out))
    # The child interpreter adds its own LC_CTYPE under locale coercion; what
    # matters is that nothing from the parent's environment leaked.
    assert {"PATH", "SQUATCH_X"} <= seen
    assert not seen & (set(os.environ) - {"PATH", "LC_CTYPE"})


async def test_stdin_path_is_the_childs_standard_input(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("hello prompt")
    seen = []
    _, out, _ = await SubprocessExec().run(
        [PY, "-c", "import sys; print(sys.stdin.read())"],
        cwd=tmp_path, env=ENV, timeout=30, stdin_path=prompt, on_stdout_line=seen.append)
    assert out == "hello prompt\n"
    assert seen == ["hello prompt"]


async def test_stdout_callback_does_not_change_inherited_stdio_mode(tmp_path, capfd):
    seen = []
    result = await SubprocessExec().run(
        [PY, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        cwd=tmp_path, env=ENV, timeout=None, on_stdout_line=seen.append)
    inherited = capfd.readouterr()
    assert result == (0, "", "")
    assert (inherited.out, inherited.err) == ("out\n", "err\n")
    assert seen == []


async def test_child_runs_in_its_own_process_group(tmp_path):
    _, out, _ = await SubprocessExec().run(
        [PY, "-c", "import os; print(os.getpgrp() == os.getpid())"],
        cwd=tmp_path, env=ENV, timeout=30)
    assert out.strip() == "True"


async def test_unresolvable_argv0_is_the_declared_error(tmp_path):
    with pytest.raises(ExecutableNotFound):
        await SubprocessExec().run(["/nonexistent/binary"], cwd=tmp_path, env=ENV, timeout=5)


async def test_timeout_kills_the_whole_group(tmp_path):
    marker = tmp_path / "grandchild.pid"
    # Parent spawns a grandchild sleeper then sleeps itself; both must die.
    code = (
        "import subprocess, sys, time, pathlib\n"
        f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        f"pathlib.Path({str(marker)!r}).write_text(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    with pytest.raises(TimeoutError):
        await SubprocessExec().run([PY, "-c", code], cwd=tmp_path, env=ENV, timeout=2)
    grandchild = int(marker.read_text())
    await asyncio.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(grandchild, 0)


async def test_cancellation_routes_through_the_same_kill(tmp_path):
    marker = tmp_path / "grandchild.pid"
    # Same shape as the timeout test: a cancellation that skips the group kill
    # leaves the grandchild alive in a worktree the driver believes frozen.
    code = (
        "import subprocess, sys, time, pathlib\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
        f"pathlib.Path({str(marker)!r}).write_text(str(p.pid))\n"
        "time.sleep(60)\n"
    )
    task = asyncio.ensure_future(SubprocessExec().run(
        [PY, "-c", code], cwd=tmp_path, env=ENV, timeout=60))
    while not marker.exists():
        await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    grandchild = int(marker.read_text())
    await asyncio.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(grandchild, 0)


# --- LocalFilesystem --------------------------------------------------------


def test_local_filesystem_write_is_whole_file_and_creates_parents(tmp_path):
    from squatch.seams import LocalFilesystem

    fs = LocalFilesystem()
    target = tmp_path / "spools" / "t" / "1" / "prompt.md"
    fs.write(target, b"first")
    fs.write(target, b"second")
    assert target.read_bytes() == b"second"
    # No temp file is left beside the target.
    assert sorted(p.name for p in target.parent.iterdir()) == ["prompt.md"]
    fs.replace(target, tmp_path / "moved.md")
    assert (tmp_path / "moved.md").read_bytes() == b"second" and not target.exists()


def test_local_filesystem_publish_is_durable_and_never_overwrites(tmp_path):
    from squatch.seams import LocalFilesystem

    fs = LocalFilesystem()
    target = tmp_path / "control" / "request.json"
    fs.publish(target, b"first")
    with pytest.raises(FileExistsError):
        fs.publish(target, b"second")

    assert fs.read(target) == b"first"
    assert fs.list(target.parent, "*.json") == (target,)
    assert sorted(path.name for path in target.parent.iterdir()) == [target.name]
    fs.remove(target)
    assert not target.exists()


@pytest.mark.parametrize("failure", ["link", "file_fsync", "directory_fsync"])
def test_local_filesystem_publish_cleans_every_failure_path(tmp_path, monkeypatch, failure):
    from squatch.seams import LocalFilesystem

    fs = LocalFilesystem()
    target = tmp_path / "control" / "request.json"
    if failure == "link":
        monkeypatch.setattr(os, "link", lambda *args: (_ for _ in ()).throw(
            OSError("link interrupted")))
    else:
        real_fsync = os.fsync
        calls = 0

        def interrupt_directory_sync(fd):
            nonlocal calls
            calls += 1
            if calls == (2 if failure == "file_fsync" else 3):
                raise OSError("directory fsync interrupted")
            return real_fsync(fd)

        monkeypatch.setattr(os, "fsync", interrupt_directory_sync)

    with pytest.raises(OSError):
        fs.publish(target, b"whole request")

    assert list(target.parent.iterdir()) == []


def test_publication_syncs_content_before_visibility_and_directory_before_return(
        tmp_path, monkeypatch):
    from squatch.seams import LocalFilesystem

    fs = LocalFilesystem()
    target = tmp_path / "control" / "request.json"
    events = []
    real_fsync, real_link = os.fsync, os.link

    def sync(fd):
        kind = "directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        events.append((kind, target.exists()))
        return real_fsync(fd)

    def link(src, dst):
        assert Path(src).read_bytes() == b"complete"
        assert events[-1] == ("file", False)
        result = real_link(src, dst)
        events.append(("link", target.exists()))
        return result

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "link", link)
    fs.publish(target, b"complete")
    assert events == [
        ("directory", False), ("file", False), ("link", True),
        ("directory", True), ("directory", True)]
    events.clear()
    fs.remove(target)
    assert events == [("directory", False)]


async def test_on_spawn_publishes_the_childs_process_group_at_spawn(tmp_path):
    seen = []
    _, out, _ = await SubprocessExec().run(
        [PY, "-c", "import os; print(os.getpgrp())"],
        cwd=tmp_path, env=ENV, timeout=30, on_spawn=seen.append)
    assert seen == [int(out.strip())]


async def test_notifications_own_private_executor_and_preserve_argv(tmp_path):
    active = SubprocessExec()
    notify = SubprocessNotifications(cwd=tmp_path, env=ENV)
    other = SubprocessNotifications(cwd=tmp_path, env=ENV)
    assert isinstance(notify._process, SubprocessExec)
    assert notify._process is not active and notify._process is not other._process
    marker = tmp_path / "args"
    literal = "hello ; $(touch unwanted)"
    await notify.notify([PY, "-c", "import pathlib, sys; "
                         "pathlib.Path(sys.argv[1]).write_text(sys.argv[2])",
                         str(marker), literal])
    assert marker.read_text() == literal
    assert not (tmp_path / "unwanted").exists()


async def test_notification_missing_nonzero_timeout_and_launch_errors(tmp_path):
    notify = SubprocessNotifications(cwd=tmp_path, env=ENV, timeout=.1)
    with pytest.raises(ExecutableNotFound):
        await notify.notify(["/nonexistent/notify"])
    with pytest.raises(RuntimeError, match="exited 7"):
        await notify.notify([PY, "-c", "raise SystemExit(7)"])
    with pytest.raises(RuntimeError, match="timed out"):
        await notify.notify([PY, "-c", "import time; time.sleep(60)"])
    path = tmp_path / "not-executable"
    path.write_text("not executable")
    path.chmod(0o600)
    for argv in ([str(path)], [str(tmp_path)]):
        with pytest.raises(RuntimeError, match="could not be launched"):
            await notify.notify(argv)
