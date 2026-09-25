"""drain.py: the self-upgrade handoff and the premise park (SQUATCH_PLAN.md
section 18; section 19, Phase 1).

Every test drives `python -m squatch drain` in-process against a temp
checkout through a scripted stage-dispatch factory whose `ok` lands a real
commit on main (so the admission's diff is git's, never a fake's) and a
process-exec seam that passes git through to the real seam while recording
the one `uv` spawn -- with what was TRUE at spawn time: whether the lock was
free and the journal closed -- because the claims are about the handoff's
ORDER, its argv form, and what the journal carries across it.
"""

import subprocess
import sys
from dataclasses import dataclass
from datetime import timedelta
from io import StringIO
from pathlib import Path

from test_cli import (  # noqa: F401 -- `checkout` is a fixture
    GOOD,
    STATE,
    T0,
    author,
    checkout,
    git_env,
)
from test_drain import FakeClock, committed, configure, draws, git, states

from squatch.__main__ import main
from squatch.artifacts import Cost
from squatch.diagnose import DiagnosisRecord
from squatch.git import Git
from squatch.journal import Journal, read_events
from squatch.lockfile import LockHeld, Lockfile
from squatch.runner import EXIT_OK, EXIT_REFUSED
from squatch.seams import ExecutableNotFound, LocalFilesystem, SubprocessExec
from squatch.stages import Delivery
from squatch.tickets import Intake, stamp

UV_FORM = ["uv", "run", "python", "-m", "squatch"]


class Landing:
    """Per-stem scripted outcomes behind the factory seam. `ok` journals the
    `to: merged` transition as the admission does, carrying the commit it put
    on main when `touches` names a path for the stem (a real commit, so the
    self-upgrade trigger reads git, never a fake's claim)."""

    def __init__(self, repo: Path, outcomes: dict[str, list[str]],
                 touches: dict[str, str] | None = None, on_run=None):
        self._repo = repo
        self._outcomes = {stem: list(o) for stem, o in outcomes.items()}
        self._touches = touches or {}
        self._on_run = on_run
        self.calls: list[tuple[str, int]] = []
        self.journal: Journal | None = None

    def __call__(self, journal: Journal):
        self.journal = journal
        return self

    async def run(self, ticket, *, run_seq: int) -> Delivery:
        self.calls.append((ticket.stem, run_seq))
        if self._on_run is not None:
            await self._on_run(ticket.stem, run_seq, self.journal)
        outcome = self._outcomes[ticket.stem].pop(0)
        if outcome == "ok":
            commit = None
            path = self._touches.get(ticket.stem)
            if path is not None:
                target = self._repo / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(f"# landed by {ticket.stem}\n")
                git(self._repo, "add", "--", path)
                git(self._repo, "commit", "-q", "-m", f"squatch({ticket.stem}): land", "--", path)
                commit = git(self._repo, "rev-parse", "HEAD").strip()
            self.journal.append("state_transition",
                                {"to": "merged", "run_seq": run_seq, "commit": commit},
                                ticket=ticket.stem)
        return Delivery(outcome, [], None, None, None, Path("/squatch-no-workspace"),
                        "HEAD", "implement", outcome if outcome != "ok" else None,
                        Cost(tokens=0, seconds=0.0, attempts=0))

    async def diagnose(self, ticket, delivery, *, run_seq):
        detail = f"workspace missing: {delivery.worktree}"
        return DiagnosisRecord(run_seq=run_seq, outcome=delivery.outcome, call="synthetic",
                               verdict="abandon-human", lessons=(detail,), reason=detail,
                               detail=None)


@dataclass(frozen=True)
class Spawn:
    argv: list[str]
    cwd: Path
    timeout: float | None
    lock_free: bool
    journal_closed: bool


class Handoffs:
    """The process-exec seam under test: git passes through to the real seam;
    a `uv` spawn is the handoff, recorded with the lock and journal state at
    that instant and never run."""

    def __init__(self, state_dir: Path, fake: Landing, *, rc: int = 0,
                 raising: Exception | None = None):
        self._real = SubprocessExec()
        self._state_dir = state_dir
        self._fake = fake
        self._rc = rc
        self._raising = raising
        self.spawns: list[Spawn] = []

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        if argv[0] != "uv":
            return await self._real.run(argv, cwd=cwd, env=env, timeout=timeout,
                                        stdin_path=stdin_path, on_spawn=on_spawn)
        probe = Lockfile(self._state_dir, instance_id="probe", clock=FakeClock())
        try:
            probe.acquire()
        except LockHeld:
            lock_free = False
        else:
            probe.release()
            lock_free = True
        self.spawns.append(Spawn(list(argv), Path(cwd), timeout, lock_free,
                                 self._fake.journal.closed))
        if self._raising is not None:
            raise self._raising
        return self._rc, "", ""


def drain(checkout: Path, fake: Landing, process: Handoffs | None = None,
          argv: tuple[str, ...] = ("drain",)) -> tuple[int, str]:
    out = StringIO()
    rc = main(list(argv), cwd=checkout, env=git_env(checkout.parent), out=out,
              pipeline=fake, clock=FakeClock(), process=process)
    return rc, out.getvalue()


def handoffs(repo: Path) -> list[dict]:
    return [e.body for e in read_events(repo / STATE)
            if e.type == "signal" and e.body.get("kind") == "drain_handoff"]


def lock_is_free(repo: Path) -> bool:
    try:
        Lockfile(repo / STATE, instance_id="after", clock=FakeClock()).acquire()
    except LockHeld:
        return False
    return True


# --- the handoff ---------------------------------------------------------------------

def test_a_self_upgrading_admission_hands_off_before_the_next_dispatch(checkout):
    committed(checkout, "red", signal_at=T0 - timedelta(hours=3))
    committed(checkout, "upgrader", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "after", signal_at=T0 - timedelta(hours=1))
    fake = Landing(checkout, {"red": ["gate_failed"], "upgrader": ["ok"], "after": ["ok"]},
                   touches={"upgrader": "squatch/new.py"})
    process = Handoffs(checkout / STATE, fake, rc=3)
    rc, out = drain(checkout, fake, process)
    assert rc == 3, "the parent exits with the child's exit code"
    assert fake.calls == [("red", 0), ("upgrader", 0)], "nothing dispatches after the upgrade"
    assert states(checkout, "after") == []
    [spawn] = process.spawns
    assert spawn.argv == [*UV_FORM, "drain", "--parked", "red"]
    assert spawn.timeout is None and spawn.cwd == checkout
    # The handoff order: journal closed and lock released BEFORE the spawn.
    assert spawn.journal_closed and spawn.lock_free
    [signal] = handoffs(checkout)
    assert signal["admitted"] == "upgrader" and signal["parked"] == ["red"]
    assert signal["touched"] == ["squatch/new.py"] and signal["argv"] == spawn.argv
    assert "self-upgrade: upgrader" in out and "squatch/new.py" in out
    assert "quiescence" not in out, "the parent does nothing after the spawn"
    assert lock_is_free(checkout)


def test_a_specs_diff_upgrades_and_a_host_only_diff_drains_on(checkout):
    committed(checkout, "host-only", signal_at=T0 - timedelta(hours=2))
    committed(checkout, "spec-change", signal_at=T0 - timedelta(hours=1))
    fake = Landing(checkout, {"host-only": ["ok"], "spec-change": ["ok"]},
                   touches={"host-only": "README.md", "spec-change": "specs/implement.md"})
    process = Handoffs(checkout / STATE, fake)
    rc, _ = drain(checkout, fake, process)
    assert rc == EXIT_OK
    assert fake.calls == [("host-only", 0), ("spec-change", 0)]
    [spawn] = process.spawns
    assert spawn.argv == [*UV_FORM, "drain"], "an empty parked set carries no flag"
    assert [h["admitted"] for h in handoffs(checkout)] == ["spec-change"]


def test_the_config_flag_is_carried_to_the_child(checkout, tmp_path):
    (checkout / "config.yaml").rename(tmp_path / "elsewhere.yaml")
    committed(checkout, "upgrader")
    fake = Landing(checkout, {"upgrader": ["ok"]}, touches={"upgrader": "squatch/new.py"})
    process = Handoffs(checkout / STATE, fake)
    rc, _ = drain(checkout, fake, process,
                  argv=("--config", str(tmp_path / "elsewhere.yaml"), "drain"))
    assert rc == EXIT_OK
    [spawn] = process.spawns
    assert spawn.argv == [*UV_FORM, "--config", str(tmp_path / "elsewhere.yaml"), "drain"]


def test_a_missing_uv_is_a_named_refusal_that_leaves_the_lock_free(checkout):
    committed(checkout, "upgrader")
    fake = Landing(checkout, {"upgrader": ["ok"]}, touches={"upgrader": "squatch/new.py"})
    process = Handoffs(checkout / STATE, fake, raising=ExecutableNotFound("uv"))
    rc, out = drain(checkout, fake, process)
    assert rc == EXIT_REFUSED
    assert "refused: " in out and "`uv` is not on PATH" in out
    assert "paved road:" in out and "uv run python -m squatch drain" in out
    assert lock_is_free(checkout)


def test_retry_budget_spent_before_the_re_exec_stays_spent_in_the_child(checkout):
    committed(checkout, "red")
    configure(checkout, "caps: {retry: 1}\n")
    git_ = Git(SubprocessExec(), env=git_env(checkout.parent), timeout=60.0)

    async def seed(stem, run_seq, journal):
        if (stem, run_seq) != ("red", 1):
            return
        # The re-offer's run commits the upgrader through the ticket-plane
        # lane, so the retry unit is drawn BEFORE the self-upgrade lands.
        author(checkout, "upgrader")
        await Intake(repo=checkout, git=git_, journal=journal, fs=LocalFilesystem()).commit(
            "upgrader", source="human", state="confirmed")

    parent = Landing(checkout, {"red": ["gate_failed", "gate_failed"], "upgrader": ["ok"]},
                     touches={"upgrader": "squatch/new.py"}, on_run=seed)
    process = Handoffs(checkout / STATE, parent)
    rc, _ = drain(checkout, parent, process)
    assert rc == EXIT_OK
    assert parent.calls == [("red", 0), ("red", 1), ("upgrader", 0)]
    assert len(draws(checkout, "red")) == 1
    [spawn] = process.spawns
    assert spawn.argv[-2:] == ["--parked", "red"]

    # The child: the same journal, the carried parked set, upgraded code. The
    # one unit drawn is still drawn -- the fold is the journal's, never the
    # exec's -- so red is never re-dispatched.
    child = Landing(checkout, {"red": ["ok"]})
    rc, out = drain(checkout, child, Handoffs(checkout / STATE, child),
                    argv=("drain", "--parked", "red"))
    assert rc == EXIT_OK, out
    assert child.calls == []
    assert len(draws(checkout, "red")) == 1
    assert "parked: red ended `gate_failed`" in out and "retry cap spent (1 of 1 drawn)" in out


def test_the_child_form_is_the_cli_verb(checkout):
    proc = subprocess.run([sys.executable, "-m", "squatch", "drain", "--parked", "ghost",
                           "--parked", "other"], cwd=checkout,
                          capture_output=True, text=True, env=git_env(checkout.parent))
    assert proc.returncode == EXIT_OK, proc.stderr
    assert "quiescence" in proc.stdout


# --- the premise park ----------------------------------------------------------------

def test_a_premise_failed_stem_is_parked_without_a_draw_and_runs_again_after_its_edit_lands(checkout):
    committed(checkout, "rma")
    fake = Landing(checkout, {"rma": ["premise_failed"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    assert fake.calls == [("rma", 0)]
    assert states(checkout, "rma") == ["running", "premise_failed"]
    assert draws(checkout, "rma") == [], "a judgment replay draws no retry unit"
    assert "parked: rma ended `premise_failed`" in out
    assert "edit tickets/rma/ticket.md" in out and "never re-offers" in out

    # The next invocation skips it: the verdict answered the ticket as written.
    again = Landing(checkout, {"rma": ["ok"]})
    rc, out = drain(checkout, again)
    assert rc == EXIT_OK
    assert again.calls == [] and draws(checkout, "rma") == []
    assert "parked: rma ended `premise_failed`" in out

    # A ticket edit lands through intake; the stem is eligible work again.
    path = checkout / "tickets" / "rma" / "ticket.md"
    path.write_text(path.read_text().replace("The widget parser lands.",
                                             "The widget parser lands, premise fixed."))
    released = Landing(checkout, {"rma": ["ok"]})
    rc, out = drain(checkout, released)
    assert rc == EXIT_OK, out
    assert "intake: committed rma" in out
    assert released.calls == [("rma", 1)]
    assert states(checkout, "rma") == ["running", "premise_failed", "running", "merged"]
    assert draws(checkout, "rma") == []


def test_a_seed_sourced_premise_park_names_the_plan_first(checkout):
    text = stamp(GOOD.replace("## Goal", "## Plan contract\n- section 13\n\n## Goal"),
                 source="seed", state="confirmed")
    author(checkout, "seed-rma", text)
    git(checkout, "add", "--", "tickets/seed-rma/ticket.md")
    git(checkout, "commit", "-q", "-m", "squatch(seed-rma): ticket", "--",
        "tickets/seed-rma/ticket.md")
    fake = Landing(checkout, {"seed-rma": ["premise_failed"]})
    rc, out = drain(checkout, fake)
    assert rc == EXIT_OK, out
    line = next(l for l in out.splitlines() if l.startswith("parked: seed-rma"))
    assert "SQUATCH_PLAN.md" in line and "tickets/seed-rma/ticket.md" in line
    assert line.index("SQUATCH_PLAN.md") < line.index("tickets/seed-rma/ticket.md")
