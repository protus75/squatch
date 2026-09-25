"""seams.py `SubprocessExec`: the production process seam (plan section 15)."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

from squatch.seams import ExecutableNotFound, SubprocessExec

PY = sys.executable
ENV = {"PATH": os.environ["PATH"]}


async def test_runs_argv_and_captures_streams(tmp_path):
    rc, out, err = await SubprocessExec().run(
        [PY, "-c", "import sys; print('o'); print('e', file=sys.stderr); sys.exit(3)"],
        cwd=tmp_path, env=ENV, timeout=30)
    assert (rc, out, err) == (3, "o\n", "e\n")


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
    _, out, _ = await SubprocessExec().run(
        [PY, "-c", "import sys; print(sys.stdin.read())"],
        cwd=tmp_path, env=ENV, timeout=30, stdin_path=prompt)
    assert out == "hello prompt\n"


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
