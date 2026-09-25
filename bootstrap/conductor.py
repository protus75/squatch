#!/usr/bin/env python3
"""Bootstrap conductor -- ONE-TIME operator tooling that drives the phase prompt
playbooks in SQUATCH_PLAN.md to their exit gates so the human never hand-pastes.

Section-0 cold-start convenience, NOT engine code: it exists only until the
Phase 1 walking skeleton lands and squatch runs its own tickets, and D1 governs the
engine, not these conveniences. It still obeys the argv-list rule (subprocess.run
with lists, never shell=True, never string-assembled commands).

Automation is the DEFAULT, in three rungs the operator picks between -- coarser
rungs just run the finer one in order and gate every deliverable the same way:
  (no --phase)               -- run every conductor-owned phase (0 then 1) end
                                to end; this is the one command for the whole
                                bootstrap.
  --phase N                  -- run all of phase N's deliverables.
  --phase N --deliverable K  -- run exactly that one deliverable, commit it,
                                then stop.
`--auto` removes the designed real-model verdict pauses for a fully unattended
run. The rungs compose through bootstrap/state.json, so hand-stepping a few
deliverables then letting the default finish the rest resumes correctly.
Every rung SKIPS deliverables already recorded done; to redo the whole
bootstrap after editing the plan, delete bootstrap/state.json first. Rungs
REFUSE to run ahead of recorded progress -- a skipped phase or deliverable
would otherwise be ratcheted done without ever running.

Per deliverable: parse the next unrun prompt from this phase's playbook in
SQUATCH_PLAN.md (the single source -- no copied checklist), run it in a FRESH
`claude -p` process (a separate scoped context, the anti-wander property; a
standing PREAMBLE carries the verify-in-place and file-don't-ask rules into
every context), then gate by the prompt's own stop-condition. Two checks bind
EVERY gate kind: the `claude` call must exit zero (transient failures are
retried with backoff; a persisting nonzero -- a dead or unauthenticated CLI --
halts, never a silent phantom completion), and the playbook item's
`expects:` files must exist on disk afterward (the agent-did-nothing check;
`-` waives it for journal-gated deliverables). Then per kind:
  pytest  -- re-run `uv run pytest` (never trust the agent's claim), then have
             a SECOND fresh context adversarially review the uncommitted diff
             against the good-enough bar's spine-breaking classes ONLY (state
             corruption, deadlock/stall, secret exposure, false-green tests
             that mirror the implementation -- the builder's own tests are
             not the last word on the builder); every other finding files to
             bootstrap/suggestions.md and passes. Verdict via
             bootstrap/review.json, missing/unparseable = fail closed. Gate
             findings (red suite or review fail) are fed back up to
             MAX_FIX_ATTEMPTS times, then halt. On pass commit + advance.
  verdict -- a real-model deliverable whose exit is a recorded verdict, not a
             green suite (Phase 1 prompts 2 and 9): run, then VERIFY in the
             journal that the artifact the stop-condition names appeared since
             the deliverable started -- a `signal` event when the prompt says
             verdict, a transition to `merged` when it says merged (the
             `state_transition` body's `to` field is a promoted envelope
             contract, section 6); on evidence
             commit, then pause for the operator to read the verdict (--auto
             continues without pausing; GO is not earnable during the
             bootstrap -- the --record-go mode is Phase 6's, section 19); on
             none, halt WITHOUT committing.
  none    -- no test and no verdict (the seed-files step): run, check
             expects, commit, advance.
Guards, all halt-for-operator: a preflight refuses to start without git, uv,
and claude on PATH; each phase's parsed deliverable count must match the
plan's stated count (a playbook format drift halts -- never a short parse
silently declared complete); a deliverable REFUSES to
start on a dirty tree (the commit sweeps `git add -A`, so anything already
dirty would splice into this deliverable's commit -- the halt names the
commit-then-rerun paved road; recovery is git revert, never stash or
reset); and a verdict deliverable
REFUSES to record done
until the journal carries its named artifact, never the context's claim.
Progress is bootstrap/state.json ({"phase": N, "done": K} -- phases below N are
complete, phase N has K deliverables done) so a halt resumes where it stopped;
delete it to start the whole bootstrap over from the first deliverable.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "SQUATCH_PLAN.md"
STATE = ROOT / "bootstrap" / "state.json"
CONDUCTOR_PHASES = (0, 1)   # the phases the conductor owns; 2+ run via `squatch drain`
MAX_FIX_ATTEMPTS = 2
MAX_ATTEMPT_CALLS = 500   # per-launch model-call ceiling (section 19 bootstrap contract)
ATTEMPT_ID = datetime.now(timezone.utc).strftime("bs-%Y%m%dT%H%M%SZ")  # durable per-launch id (section 19)
CLAUDE_TRANSIENT_RETRIES = 2   # bounded backoff before a nonzero exit halts
EXPECTED_DELIVERABLES = {0: 11, 1: 17}   # playbook counts; a parse drift halts
REVIEW_FILE = ROOT / "bootstrap" / "review.json"
PREAMBLE = """\
Bootstrap deliverable for the squatch repo; SQUATCH_PLAN.md is canonical.
If this deliverable's output already exists (a re-run over prior work),
VERIFY it against the plan and its stop-condition and change only what
fails them -- never rebuild green work. An out-of-scope problem is
appended to bootstrap/suggestions.md and left alone; never stop to ask.

"""

CALLS = 0


def count_call():
    # section 19 bootstrap contract: every model call draws the attempt's
    # MAX_ATTEMPT_CALLS ceiling; the next no-flag launch is a fresh attempt.
    global CALLS
    CALLS += 1
    if CALLS > MAX_ATTEMPT_CALLS:
        sys.exit("attempt %s exceeded MAX_ATTEMPT_CALLS=%d -- halting; "
                 "re-run python3 bootstrap/conductor.py to start a fresh "
                 "attempt with a fresh ceiling" % (ATTEMPT_ID, MAX_ATTEMPT_CALLS))



def parse_deliverables(phase):
    text = PLAN.read_text()
    marker = "**Phase %d prompt playbook.**" % phase
    start = text.find(marker)
    if start == -1:
        sys.exit("no playbook for phase %d in SQUATCH_PLAN.md" % phase)
    tail = text[start + len(marker):]
    stops = [m.start() for m in re.finditer(r"\*\*Phase \d+ prompt playbook\.\*\*", tail)]
    sec = re.search(r"\n## \d+\. ", tail)
    if sec:
        stops.append(sec.start())
    block = tail[:min(stops)] if stops else tail
    items = re.findall(
        r"\n(\d+) -- ([^\n]+):\nexpects: ([^\n]+)\n+```\n(.*?)\n```",
        block, re.S)
    parsed = [(title.strip(), expects.split(), prompt.strip())
              for _num, title, expects, prompt in items]
    want = EXPECTED_DELIVERABLES.get(phase)
    if want is not None and len(parsed) != want:
        sys.exit("phase %d playbook parsed %d deliverables, expected %d -- "
                 "the playbook format drifted ('N -- Title:' line, 'expects:' "
                 "line, one fenced prompt); fix SQUATCH_PLAN.md, never skip"
                 % (phase, len(parsed), want))
    return parsed


def gate_of(prompt):
    low = re.sub(r"\s+", " ", prompt.lower())
    if "pytest" in low:
        return "pytest"
    if "verdict" in low or "merged" in low:
        return "verdict"
    return "none"


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=str(ROOT), **kw)


def journal_evidence(prompt, started_at):
    """The mechanical half of a verdict gate: the artifact the stop-condition
    names must be IN the journal since `started_at`, never the context's
    claim. Returns the set of still-missing evidence kinds."""
    state_dir = ROOT / ".squatch" / "state"
    cfg = ROOT / "config.yaml"
    if cfg.exists():
        m = re.search(r"^state_dir:\s*(\S+)", cfg.read_text(), re.M)
        if m:
            state_dir = ROOT / m.group(1)
    low = re.sub(r"\s+", " ", prompt.lower())
    need = set()
    if "verdict" in low:
        need.add("signal")
    if "merged" in low:
        need.add("merged")
    seen = set()
    for seg in sorted((state_dir / "journal").glob("*.jsonl")):
        for line in seg.read_text().splitlines():
            try:
                e = json.loads(line)
            except ValueError:
                continue        # torn tail is the reader's normal case
            if e.get("ts", "") < started_at:
                continue
            if e.get("type") == "signal":
                seen.add("signal")
            if (e.get("type") == "state_transition"
                    and (e.get("body") or {}).get("to") == "merged"):
                seen.add("merged")
    return need - seen


def preflight():
    missing = [b for b in ("git", "uv", "claude") if not shutil.which(b)]
    if missing:
        sys.exit("missing required binaries: %s -- see the prerequisites table "
                 "(SQUATCH_PLAN.md section 0)" % ", ".join(missing))


def claude(prompt):
    # fresh one-shot context per deliverable; operator-owned bootstrap repo.
    # Transient nonzero exits (overload, network) get bounded retries with
    # backoff -- machine-retryable work never waits on an operator rerun.
    for attempt in range(CLAUDE_TRANSIENT_RETRIES + 1):
        count_call()
        r = run(["claude", "-p", PREAMBLE + prompt, "--dangerously-skip-permissions"])
        if r.returncode == 0:
            return
        if attempt < CLAUDE_TRANSIENT_RETRIES:
            wait = 30 * (attempt + 1)
            print("claude exited %d -- retrying in %ds (%d/%d)"
                  % (r.returncode, wait, attempt + 1, CLAUDE_TRANSIENT_RETRIES))
            time.sleep(wait)
    sys.exit("claude exited %d after %d retries -- persistent failure (auth? "
             "quota?); fix it and re-run the same command to continue; nothing "
             "gated, nothing committed, state not advanced"
             % (r.returncode, CLAUDE_TRANSIENT_RETRIES))


def adversarial_review(title, frozen=None):
    """Second fresh context reviews the builder's uncommitted work against
    the section 19 good-enough bar: FAIL only spine-breaking classes; every
    other finding files to bootstrap/suggestions.md and passes. New and
    untracked files are part of the
    review surface (git diff alone misses them). Transient failures --
    nonzero exit or an unparseable verdict file -- get bounded retries;
    a persisting one halts fail-closed. Returns [] on pass, findings on fail.
    A re-review pass receives the FROZEN first-pass blocking set; a NEW
    objection on a later pass is advisory (the section 0 freeze law)."""
    verdict = None
    for attempt in range(CLAUDE_TRANSIENT_RETRIES + 1):
        if REVIEW_FILE.exists():
            REVIEW_FILE.unlink()
        count_call()
        r = run(["claude", "-p",
                 "You are the adversarial reviewer for one squatch bootstrap "
                 "deliverable; SQUATCH_PLAN.md is canonical. Review the working "
                 "tree's UNCOMMITTED work -- git status for the file set, git "
                 "diff for tracked changes, and READ each new/untracked file "
                 "in full (the diff does not show them) -- against the "
                 "plan sections the deliverable cites. FAIL only for the "
                 "bootstrap contract's spine-breaking classes (SQUATCH_PLAN.md "
                 "section 19): state corruption, deadlock or permanent stall, "
                 "secret exposure, or false-green verification -- tests that "
                 "mirror the implementation instead of pinning real behavior "
                 "(orderings, refusals, crash points). A blocking finding "
                 "must be REPRODUCIBLE and must attach to THIS deliverable's "
                 "uncommitted diff -- never pre-existing code or later-phase "
                 "scope. Append every OTHER "
                 "finding (conformance drift, style, scope) as one-line items "
                 "to bootstrap/suggestions.md and still pass. Write EXACTLY "
                 "bootstrap/review.json: "
                 '{"verdict": "pass"} or {"verdict": "fail", "findings": '
                 '["..."]}. Change no file other than those two. '
                 + ("" if frozen is None else
                    "RE-REVIEW: the blocking set is FROZEN to the findings "
                    "listed after the deliverable name -- fail ONLY if one "
                    "of them is still unresolved; any NEW problem, whatever "
                    "its class, files to bootstrap/suggestions.md and never "
                    "fails. Frozen findings: " + "; ".join(frozen) + ". ")
                 + "Deliverable: " + title,
                 "--dangerously-skip-permissions"])
        if r.returncode != 0:
            if attempt < CLAUDE_TRANSIENT_RETRIES:
                wait = 30 * (attempt + 1)
                print("review context exited %d -- retrying in %ds"
                      % (r.returncode, wait))
                time.sleep(wait)
                continue
            sys.exit("review context exited %d after retries -- fix and "
                     "re-run the same command to continue" % r.returncode)
        try:
            verdict = json.loads(REVIEW_FILE.read_text())
            break
        except (OSError, ValueError):
            if attempt < CLAUDE_TRANSIENT_RETRIES:
                print("no parseable bootstrap/review.json -- re-asking the reviewer")
                continue
            sys.exit("no parseable bootstrap/review.json after %d asks -- "
                     "fail closed, halting for operator"
                     % (CLAUDE_TRANSIENT_RETRIES + 1))
    REVIEW_FILE.unlink()
    if verdict.get("verdict") == "pass":
        return []
    return verdict.get("findings") or ["review verdict: fail (no findings listed)"]


def pytest_green():
    return run(["uv", "run", "pytest", "-q"]).returncode == 0


def ensure_ignored():
    gi = ROOT / ".gitignore"
    txt = gi.read_text() if gi.exists() else ""
    add = [e for e in ("bootstrap/state.json", "bootstrap/review.json")
           if e not in txt]
    if add:
        sep = "" if (not txt or txt.endswith("\n")) else "\n"
        gi.write_text(txt + sep + "\n".join(add) + "\n")
        return True
    return False


def require_clean(phase, n):
    # the commit below sweeps `git add -A`, so a dirty tree at start would
    # splice unrelated work into this deliverable's commit -- halt instead.
    dirty = run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if dirty:
        sys.exit("phase %d deliverable %d: tree is dirty (a prior halt leaves "
                 "its partial work uncommitted). To continue: commit it "
                 "(`git add -A` + a wip commit), then re-run the same command "
                 "-- verify-in-place converges over committed partial work, "
                 "and recovery is git revert, never stash or reset:\n%s"
                 % (phase, n, dirty))


def commit(msg):
    ensure_ignored()
    dirty = run(["git", "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    if not dirty:
        return
    run(["git", "add", "-A"], check=True)
    run(["git", "commit", "-m", msg], check=True)


def load_state():
    # (phase, done): phases below `phase` are complete, `phase` has `done` done.
    if STATE.exists():
        s = json.loads(STATE.read_text())
        return int(s.get("phase", 0)), int(s.get("done", 0))
    return 0, 0


def save_state(phase, done):
    # Ratchet: an explicit rerun of an earlier deliverable must never rewind
    # the resume point past completed work.
    phase, done = max(load_state(), (phase, done))
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(
        {"phase": phase, "done": done, "attempt_id": ATTEMPT_ID}))


def run_deliverable(phase, items, i, auto):
    """Run one deliverable (0-based index i). Return True to keep going, False to
    pause on a verdict. Halts the process on a failed gate. Commits + records
    state on success."""
    title, expects, prompt = items[i]
    n = i + 1
    gate = gate_of(prompt)
    require_clean(phase, n)
    print("=== phase %d deliverable %d/%d (%s): %s ===" % (
        phase, n, len(items), gate, title))
    started_at = datetime.now(timezone.utc).isoformat()
    claude(prompt)
    missing = [] if expects == ["-"] else [p for p in expects
                                           if not (ROOT / p).exists()]
    if missing:
        save_state(phase, i)
        sys.exit("phase %d deliverable %d: expected outputs missing: %s -- the "
                 "agent run did not produce its deliverable; nothing committed"
                 % (phase, n, ", ".join(missing)))
    if gate == "verdict":
        missing_ev = journal_evidence(prompt, started_at)
        if missing_ev:
            save_state(phase, i)
            sys.exit("phase %d deliverable %d: journal shows no %s since start "
                     "-- halting for operator, nothing committed"
                     % (phase, n, "/".join(sorted(missing_ev))))
    if gate == "pytest":
        attempt = 0
        frozen = None
        while True:
            if not pytest_green():
                findings = ["uv run pytest is red"]
            else:
                findings = adversarial_review(title, frozen)
                if findings and frozen is None:
                    frozen = list(findings)   # the section 0 freeze law
            if not findings:
                break
            attempt += 1
            if attempt > MAX_FIX_ATTEMPTS:
                save_state(phase, i)
                sys.exit("phase %d deliverable %d still failing its gate after "
                         "%d fix attempts -- halting. Paved road: narrow or "
                         "split this deliverable's playbook prompt in "
                         "SQUATCH_PLAN.md, then re-run exactly it:  python3 "
                         "bootstrap/conductor.py --phase %d --deliverable %d"
                         % (phase, n, MAX_FIX_ATTEMPTS, phase, n))
            claude("The last change failed its gate. Findings:\n- "
                   + "\n- ".join(findings) + "\n"
                   "Read them, fix the code (not the test, unless the test is "
                   "wrong per SQUATCH_PLAN.md), keep the change minimal. Stop "
                   "when uv run pytest is green.")
    commit("bootstrap: phase %d deliverable %d -- %s" % (phase, n, title))
    save_state(phase, n)
    if gate == "verdict" and not auto and n < len(items):
        print("deliverable %d is a real-model step -- read its recorded verdict, "
              "then re-run to continue (--auto skips these pauses)." % n)
        return False
    return True


def run_phase(phase, start, auto):
    """Run phase `phase` from deliverable index `start`. Return True if the phase
    fully completed, False if it paused on a verdict (halts exit on red)."""
    items = parse_deliverables(phase)
    for i in range(start, len(items)):
        if not run_deliverable(phase, items, i, auto):
            return False
    print("phase %d complete." % phase)
    return True


def main():
    preflight()
    ap = argparse.ArgumentParser(description="squatch bootstrap conductor")
    ap.add_argument("--phase", type=int,
                    help="run one phase (default: every conductor phase, %s)"
                         % "->".join(map(str, CONDUCTOR_PHASES)))
    ap.add_argument("--deliverable", type=int,
                    help="with --phase: run exactly this deliverable "
                         "(1-based), then stop")
    ap.add_argument("--auto", action="store_true",
                    help="do not pause on real-model (verdict) deliverables")
    args = ap.parse_args()

    # ignore + commit the conductor's state files up front, so a halt before
    # the first deliverable commit can never dirty the tree with them.
    if ensure_ignored():
        changed = run(["git", "status", "--porcelain", "--", ".gitignore"],
                      capture_output=True, text=True).stdout.strip()
        if changed:
            run(["git", "add", ".gitignore"], check=True)
            run(["git", "commit", "-m",
                 "bootstrap: ignore conductor state files"], check=True)

    # finest rung: one named deliverable, then stop
    if args.deliverable is not None:
        if args.phase is None:
            ap.error("--deliverable requires --phase")
        items = parse_deliverables(args.phase)
        n = args.deliverable
        if not 1 <= n <= len(items):
            ap.error("phase %d has deliverables 1..%d, not %d"
                     % (args.phase, len(items), n))
        cur, done = load_state()
        if args.phase > cur:
            ap.error("phase %d is ahead of recorded progress (phase %d, %d "
                     "done) -- finish earlier phases first, or delete "
                     "bootstrap/state.json to start over"
                     % (args.phase, cur, done))
        if args.phase == cur and n > done + 1:
            ap.error("deliverable %d is ahead of recorded progress (%d "
                     "done) -- deliverables run in order; %d is next, or "
                     "delete bootstrap/state.json to start over"
                     % (n, done, done + 1))
        run_deliverable(args.phase, items, n - 1, args.auto)
        return

    # middle rung: one whole phase
    if args.phase is not None:
        cur, done = load_state()
        if args.phase > cur:
            ap.error("phase %d is ahead of recorded progress (phase %d, %d "
                     "done) -- finish earlier phases first, or delete "
                     "bootstrap/state.json to start over"
                     % (args.phase, cur, done))
        start = done if cur == args.phase else 0
        run_phase(args.phase, start, args.auto)
        return

    # default rung: every conductor-owned phase, end to end
    cur, done = load_state()
    for phase in CONDUCTOR_PHASES:
        if phase < cur:
            continue
        start = done if phase == cur else 0
        if not run_phase(phase, start, args.auto):
            return
        save_state(phase + 1, 0)
    print("conductor phases complete -- from here run `uv run python -m squatch "
          "drain` ONCE; it carries every remaining phase to quiescence "
          "(section 19).")


if __name__ == "__main__":
    main()
