"""The pure managed conduct-block renderer (plan sections 8, 15, 20)."""

import hashlib
import re
from typing import Literal

VERSION = 1
# Section 17's seed becomes the first engine-owned template. Never read a
# host conduct file as the template: first adoption must also work on self.
CORE = """\
# squatch

squatch is a continuously running orchestration engine that authors and runs tickets against host project repos, including itself: it drafts the ticket set for a feature, wires dependencies, runs implement -> check -> review -> merge, harvests failures, and files follow-ups.
Two rule planes. **Engine plane** (this repo, squatch-owned): HOW work runs -- ticket schema and closed vocabularies, prompt specs, gate discipline, workspace/git rules, the run-record contract. **Host plane** (each target repo): WHAT to build -- architecture, stack, domain and review rules; it enters the pipeline only as rendered data and is never engine-edited.
Design goals, in priority order: simple and robust over feature-rich; automated with small, enumerated human touchpoints; a continuous queue, never batches; one pattern for every stage, gate, and handoff; every failure path designed.
Judgment goes in LLMs; verdicts go in scripts.

**Read first: `SQUATCH_PLAN.md` is canonical.** This file carries only the conduct an agent needs in-context every session; every design detail lives in the plan and is never duplicated here.

## A. Engine conduct

Each rule: the conduct, a one-line why, and the plan section that owns the design detail.

- **Pure Python.** No shell scripts, no `shell=True`, no string-assembled commands; external binaries only through argv wrapper modules; the squatch venv only.
  Why: shell glue as orchestration is a named anti-goal, and argv wrappers keep every exec auditable. [D1]
- **Build the simplest thing that satisfies the ticket.** No speculative features, gates, config knobs, or metadata; every addition cites the incident that earned it.
  Why: check/feature accretion is the primary failure mode this design exists to prevent. [goal 1, D10]
- **No dual-path code.** No compat shims, deprecation layers, or defensive parallel paths. Rename in place, update every call site in the same change; recover by revert.
  Why: a second path is a second thing to test and the place drift hides; git revert is the recovery. [section 2]
- **Fail closed.** Allowlists and closed vocabularies, never denylists; every prohibition and every gate finding ships a paved road.
  Why: a denylist admits whatever nobody thought of; a prohibition with no paved road is fail-stuck, not fail-closed. [sections 2, 7]
- **A hold ships with its release.** The Reject queue, a premise park, or a poison quarantine lands with or after its release path (same deliverable, or `depends`-after it); its paved road never names an unbuilt verb; a hold whose only release is a ticket change never precedes the machinery that machine-produces ticket changes.
  Why: a hold with no reachable release strands a ticket forever. [sections 2, 11]
- **Files + journal are the source of truth.** Derived views (status, backlog, ledger, scorecard) are projections, never authoritative: never hand-edit one or cite one as authority.
  Why: an edited projection silently diverges from the record it claims to summarize. [D3]
- **Generated files are render targets, never write targets.** `README.md` and `bootstrap/conductor.py` extract from the plan's appendix sentinel blocks; `CLAUDE.md` and `AGENTS.md` (its curated subset, loaded by the codex implement context) are authored from plan section 17. A change edits the plan and reruns the generator, never the rendered file.
  Why: an edit to a rendered file is lost at the next regeneration and forks the seed from its artifact. [section 1]
- **The plan is the seed.** A plan defect (gap, bug, wrong spec) is fixed in the plan, then regenerated from it: rerun the owning deliverable, deleting and regenerating the affected tickets or code. Hand-edit a ticket or code file ONLY for a defect provably not the plan's, OR under the blocking-defect fast path (a defect stopping the drain's forward progress: plan edited and committed FIRST, then the minimal congruent hand fix in the same session), and never before the plan's status is determined.
  Why: a fix outside the plan leaves the seed wrong and reproduces the defect on the next regeneration. [sections 1, 19]
- **All git through `git.py`.** Argv lists, dir-pinned; worktree cleanup is `worktree remove` + `prune`, never bare `rm -rf`; no `gh`, no PRs in the loop.
  Why: one wrapper is the only place exec, child env, and dir pinning are enforced; `rm -rf` leaves git's worktree registry lying. [section 10]
- **Second problems are filed, never folded in.** An adjacent bug, refactor itch, or pre-existing red goes to the Suggestion Box, not the current diff; a pre-existing failure is verified on the base commit first, then filed.
  Why: an inline fix widens scope past the fence and hides the cause from the queue; base-commit verification separates your regression from inherited red. [section 11]
- **Read before write.** No command, claim, or test is written until the artifact that owns that fact has been read.
  Why: a claim about an unread artifact is a guess dressed as a fact. [section 13]
- **Ticket frontmatter is minimal.** Only fields the scheduler, a gate, or the authoring/triage policy reads; execution ordering lives in `depends` and `priority`, never in prose.
  Why: metadata serving subsystems that do not exist yet is the anti-bloat law's named failure; ordering in prose is unschedulable. [section 13]
- **Use the injectable seams.** Clock, process exec, filesystem, and notifications go through the seams, never called raw in engine code.
  Why: a raw call makes engine code untestable without real time, real processes, or real disk. [section 15]
- **Executed work is fenced, not jailed.** v1 does not sandbox executed code; never rely on its goodwill, and never pass a provider key to a process that does not need it.
  Why: gates and review are the trust boundary, so executed code earns no trust and no key beyond its need. [section 16]
- **The journal is the record, never a debug log.** Diagnostics go to the engine log and attempt spools; configured secret values are redacted from every captured stream at the write seam.
  Why: the journal is versioned, corruption-strict, and never deleted, so chatter clutters it forever and a leaked secret persists forever. [section 6]
- **Do not start a phase until the previous phase's exit is met.**
  Why: a phase built on an unmet exit inherits the gap as its foundation. [section 19]

## B. Session conduct (interactive chat in this repo)

A human-present chat session is the one context the pipeline machinery does not govern; these rules are the governance. [section 17, proven in host #1's rule file]

- **Terse communication.** Lead with the answer; cut hedging, filler, and preamble; short sentences and tight lists.
  Why: preamble spends context every turn and buries the answer. [section 17]
- **Comments explain why, not what.** Comment only invariants, hazards, and deliberate-looking-wrong choices; match surrounding density.
  Why: a what-comment restates code and rots with it; a why-comment carries reasoning the code cannot. [section 17]
- **Plan prose is pure spec.** Rules stated tersely; no incident citations, session references, or change history in plan prose. Provenance lives in the Suggestion Box, the journal, and git history.
  Why: history embedded in spec is never pruned and reads as rule. [section 17]
- **Track open threads.** A reply that raises several questions or options owns that list until it is empty; restate unresolved threads every turn; the user engaging on one thread never closes the others.
  Why: a dropped thread is a decision the user never made. [section 17]
- **Announce unsolicited dives.** Name any investigation or authoring the user did not request in 1-2 sentences and get a now / after / skip decision before spending the time; the requested task always runs first. Autonomous pipeline stages are exempt: they file same-turn via the Suggestion Box.
  Why: unrequested work spends the user's budget without consent. [section 17]
- **Instance first, cause captured.** A reported problem yields the minimal unblock first and a separately filed cause ticket in the same session.
  Why: the chat form of the section 14 urgency/importance rule: never the unblock without the cause, never the cause instead of the unblock. [section 17]
- **Git session safety.** Respect the single-writer lockfile: a chat session never mutates git state in a checkout whose lock a daemon holds (authoring ticket FILES in the working tree is the sanctioned intake path and needs no git, section 13). Stage and commit only files authored this session, by explicit path; never a tree-wide destructive verb (`clean`, `reset --hard`, `checkout -- .`) in a shared checkout. Never push or remote-mutate from a chat session unless the user explicitly says push.
  Why: git state under a daemon's lock is dispatch state; pushes are the checkpoint Effect's job. [sections 10, 13]

## Maintaining this file

Every rule here is behavioral (no gates exist yet). When a rule gains its gate, compress it to one line -- rule + author-time actionable + gate code + link -- in the same change that lands the gate. Hard cap: 120 lines; a rule earns a line only if violating it is cheap to do and expensive to unwind. AGENTS.md exists (the curated subset for non-Claude agent CLIs): a rule add/change/remove touches both files in the same change; CLAUDE.md is canonical on conflict. [section 17]
"""

_MARKER_LIKE = re.compile(r"squatch:core", re.IGNORECASE)
_BEGIN = re.compile(
    r"^<!-- squatch:core begin version=([0-9]+) sha256=([0-9a-f]{64}) -->\n",
    re.MULTILINE,
)
_END = re.compile(r"^<!-- squatch:core end -->(?=\n|\Z)", re.MULTILINE)

DriftState = Literal["missing", "current", "drifted", "refused"]


class ManagedBlockRefusal(ValueError):
    """Corrupt or unsupported ownership markers cannot be safely rewritten."""


def managed_block(core: str = CORE) -> str:
    if _MARKER_LIKE.search(core):
        raise ManagedBlockRefusal("core template contains marker-like text; remove it from the template")
    body = core if core.endswith("\n") else core + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return (f"<!-- squatch:core begin version={VERSION} sha256={digest} -->\n"
            f"{body}<!-- squatch:core end -->")


def render(content: str, core: str = CORE) -> str:
    """Replace only the owned span, or prepend it without consuming host bytes."""
    block = managed_block(core)
    markers = list(_MARKER_LIKE.finditer(content))
    if not markers:
        return block + "\n" + content
    begins, ends = list(_BEGIN.finditer(content)), list(_END.finditer(content))
    if (len(markers) != 2 or len(begins) != 1 or len(ends) != 1
            or begins[0].end() > ends[0].start()):
        raise ManagedBlockRefusal(
            "malformed, partial, duplicate or stray core markers; repair the markers "
            "without deleting project-owned text, then rerun core")
    begin, end = begins[0], ends[0]
    if begin.group(1) != str(VERSION):
        raise ManagedBlockRefusal("unsupported core version; use the matching engine version")
    return content[:begin.start()] + block + content[end.end():]


def classify(content: str, core: str = CORE) -> DriftState:
    """Classify managed ownership without changing any host-file bytes."""
    try:
        rendered = render(content, core)
    except ManagedBlockRefusal:
        return "refused"
    if not _MARKER_LIKE.search(content):
        return "missing"
    return "current" if rendered == content else "drifted"
