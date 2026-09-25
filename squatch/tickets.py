"""Ticket contract and runner intake (SQUATCH_PLAN.md section 13; section 19, Phase 1).

A ticket is one markdown file: closed YAML frontmatter a script schedules plus
a body of fixed sections an agent executes. `lint_ticket` is the section 13
grammar as one fail-closed pass: every defect is a `ticket_schema` finding
with a paved road, reported all at once. Frontmatter carries only what the
scheduler, a gate, or authoring/triage policy reads; ordering lives in
`Depends on` and `priority`, never prose.

`Intake` is the Phase 1 stand-in for the watcher: at invocation it finds the
hand-authored `tickets/<stem>/ticket.md` files git does not yet hold, stamps
`source` and `state` fail-closed (a new stem is `human`; an established
machine source is never demoted; only the machine writes `seed`/`box:*`),
lints, commits each through the ticket-plane lane (that one path, no
trailers), and journals the per-stem intake signal the scheduler's age term
and `status` read. A refused file is left in place, uncommitted, with its
findings; validation is never silent.
"""

import re
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from squatch.artifacts import GATE_CODES, Finding
from squatch.git import Git
from squatch.gates import GateReport
from squatch.journal import EVENT_TYPES, Journal
from squatch.llm import EFFORTS, TIERS
from squatch.seams import Filesystem
from squatch.specs import PlanContractError, resolve_plan_sections

CODE = "ticket_schema"
TICKETS_DIR = "tickets"
TICKET_FILE = "ticket.md"
PLAN_FILE = "SQUATCH_PLAN.md"
SPECS_DIR = "specs"
INTAKE_SIGNAL = "ticket_intake"

STEM = re.compile(r"\A[a-z0-9][a-z0-9-]{1,63}\Z")
RESERVED_STEMS = frozenset({"decisions", "retro"})
STATES = frozenset({"draft", "confirmed", "rejected", "merged"})
# Intake materializes `confirmed`; `rejected` is a Reject-queue kill and
# `merged` is journal-recorded at settle, so neither is intake's to write.
INTAKE_STATES = frozenset({"draft", "confirmed"})
SOURCE = re.compile(r"\A(human|seed|box:[a-z][a-z0-9_]*)\Z")
PRIORITIES = frozenset({"P0", "P1", "P2", "P3"})
KINDS = frozenset({"bug", "feature", "chore"})
FRONTMATTER_KEYS = frozenset(
    {"state", "source", "priority", "kind", "agent_tier", "agent_effort", "gate_bypass"})

SECTIONS: tuple[str, ...] = (
    "Depends on", "Context", "Plan contract", "Goal", "Why", "Scope in", "Scope out",
    "Scope fence", "Acceptance criteria", "Verification", "Regression",
    "Definition of rejected", "Time budget", "Exit-read window")
# `Regression` is conditional on `kind: bug`; the other two are optional.
OPTIONAL_SECTIONS = frozenset({"Plan contract", "Regression", "Exit-read window"})
PROSE_SECTIONS = ("Goal", "Why", "Scope in", "Scope out", "Definition of rejected")

BANNED_ADJECTIVES = re.compile(r"\b(improved|better|cleaner)\b", re.IGNORECASE)
SHELL_OPERATORS = frozenset({"|", "||", "&&", ";", "&", ">", ">>", "<", "2>", "2>&1"})
_H2 = re.compile(r"^## (.+?)\s*$")
_BULLET = re.compile(r"^- (.*\S)\s*$")
_SECTION_REF = re.compile(r"\Asection (\d+)\Z")
_MINUTES = re.compile(r"\A(expected|stuck): (\d+)m\Z")
_WINDOW = re.compile(r"\A([a-z_]+): (.+\S)\s*\Z")
_CARRIES = re.compile(r"\Acarries: (\S+)\Z")
_BACKTICK = re.compile(r"`([^`]+)`")
_STEM_ROAD = ("name the ticket dir a lowercase kebab-case stem matching "
              "^[a-z0-9][a-z0-9-]{1,63}$ that is not `decisions` or `retro`")
_PLAN_ROAD = ("cite plan prose through `## Plan contract` (`- section N` bullets); `Context` "
              "takes only ordinary repo files")


class TicketLintError(Exception):
    def __init__(self, stem: str, findings: list[Finding]):
        self.stem = stem
        self.findings = findings
        super().__init__(f"{stem}: " + "; ".join(f.message for f in findings))


class TicketSchemaGate:
    """Run the section 13 grammar over an Author-emitted ticket."""

    code = CODE
    paved_road = "repair every ticket-schema finding and emit the complete ticket again"

    async def check(self, artifact, workspace: Path) -> GateReport:
        repo = Path(workspace)
        findings: list[Finding] = []
        stem = artifact.stem
        path = repo / TICKETS_DIR / stem / TICKET_FILE
        if path.is_file() or stem in RESERVED_STEMS:
            findings.append(_finding(
                f"stem {stem!r} already exists on disk or is reserved",
                "choose a new valid stem that does not collide with the ticket plane"))
        plan_path = repo / PLAN_FILE
        try:
            lint_ticket(
                artifact.ticket, stem=stem, repo=repo,
                plan=plan_path.read_text() if plan_path.is_file() else None,
                resolve_stem=lambda candidate: (
                    repo / TICKETS_DIR / candidate / TICKET_FILE).is_file())
        except TicketLintError as e:
            findings.extend(e.findings)
        return GateReport(code=self.code, verdict="fail" if findings else "pass",
                          findings=tuple(findings))


@dataclass(frozen=True)
class Regression:
    command: tuple[str, ...]
    carries: tuple[str, ...]


@dataclass(frozen=True)
class Ticket:
    stem: str
    state: str | None
    source: str | None
    priority: str
    kind: str
    agent_tier: str
    agent_effort: str
    gate_bypass: tuple[tuple[str, str], ...]
    depends: tuple[str, ...]
    context: tuple[str, ...]
    plan_sections: tuple[str, ...]
    goal: str
    scope_fence: tuple[str, ...]
    verification: tuple[tuple[str, ...], ...]
    regression: Regression | None
    expected_minutes: int
    stuck_minutes: int
    exit_read_window: tuple[tuple[str, str], ...]


ResolveStem = Callable[[str], bool]


def _finding(message: str, paved_road: str, line: int | None = None) -> Finding:
    return Finding(code=CODE, line=line, message=message, paved_road=paved_road)


# ---- frontmatter ----------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, list[str]]:
    """Split the `---` fences and `safe_load` the YAML between them; returns
    (mapping, body lines). A ValueError names the structural defect."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter: the file must open with a `---` fence")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            try:
                meta = yaml.safe_load("\n".join(lines[1:i])) or {}
            except yaml.YAMLError as e:
                raise ValueError(f"frontmatter is not valid YAML: {e}") from None
            if not isinstance(meta, dict):
                raise ValueError("frontmatter is not a mapping")
            return meta, lines[i + 1:]
    raise ValueError("unterminated frontmatter: no closing `---` fence")


def _lint_frontmatter(meta: dict, findings: list[Finding]) -> dict:
    road = "declare only the closed keys: " + ", ".join(sorted(FRONTMATTER_KEYS))
    for key in sorted(set(meta) - FRONTMATTER_KEYS):
        findings.append(_finding(f"frontmatter key {key!r} is not in the closed schema", road, 1))
    for key in ("priority", "kind"):
        if meta.get(key) is None:  # a bare `key:` is YAML null: as absent as no key
            findings.append(_finding(
                f"frontmatter key {key!r} is missing",
                f"set {key} explicitly; it is never inferred from prose", 1))

    def vocab(key: str, allowed: Iterable[str]) -> None:
        v = meta.get(key)
        if v is not None and not (isinstance(v, str) and v in allowed):
            findings.append(_finding(f"{key} {v!r} is not one of {sorted(allowed)}",
                                     f"set {key} to a value from the closed vocabulary", 1))

    vocab("state", STATES)
    vocab("priority", PRIORITIES)
    vocab("kind", KINDS)
    vocab("agent_tier", TIERS)
    vocab("agent_effort", EFFORTS)
    source = meta.get("source")
    if source is not None and not (isinstance(source, str) and SOURCE.match(source)):
        findings.append(_finding(f"source {source!r} is not `human`, `seed`, or `box:<class>`",
                                 "omit source on a hand-authored ticket; intake stamps it", 1))
    bypass = meta.get("gate_bypass", [])
    road = "write gate_bypass as a list of {code: <gate code>, reason: <why>} entries"
    if not isinstance(bypass, list):
        findings.append(_finding(f"gate_bypass {bypass!r} is not a list", road, 1))
        bypass = []
    for entry in bypass:
        if not (isinstance(entry, dict) and set(entry) == {"code", "reason"}
                and isinstance(entry["code"], str) and entry["code"] in GATE_CODES
                and isinstance(entry["reason"], str) and entry["reason"].strip()):
            findings.append(_finding(f"gate_bypass entry {entry!r} is not {{code, reason}} "
                                     f"with an engine gate code", road, 1))
    return meta


# ---- body -----------------------------------------------------------------------

def _split_sections(body: list[str], findings: list[Finding]) -> dict[str, tuple[int, list[str]]]:
    """Map section name -> (heading line, content lines). A `## ` inside a
    code fence is content."""
    out: dict[str, tuple[int, list[str]]] = {}
    current: str | None = None
    fenced = False
    for offset, line in enumerate(body):
        n = offset + 1
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and (h := _H2.match(line)):
            name = h.group(1)
            if name not in SECTIONS:
                findings.append(_finding(f"section {name!r} is not a ticket section",
                                         f"use only the fixed sections: {list(SECTIONS)}", n))
                current = None
                continue
            if name in out:
                findings.append(_finding(f"section {name!r} appears twice",
                                         "keep one of each section", n))
                current = None
                continue
            out[name] = (n, [])
            current = name
            continue
        if current is not None:
            out[current][1].append(line)
        elif line.strip():
            findings.append(_finding(f"line {n} sits outside every section",
                                     "put every line under one of the fixed `## ` sections", n))
    return out


def _bullets(name: str, section: tuple[int, list[str]], findings: list[Finding],
             road: str) -> list[str] | None:
    """The bullet items of a bullet-list section; None (one finding) when any
    non-blank line is not a bullet."""
    n, lines = section
    items = []
    for line in lines:
        if not line.strip():
            continue
        m = _BULLET.match(line)
        if not m:
            findings.append(_finding(f"`## {name}` must be a bullet list: {line.strip()!r}", road, n))
            return None
        items.append(m.group(1).strip())
    return items


def _fenced(name: str, section: tuple[int, list[str]], findings: list[Finding],
            road: str) -> tuple[list[str], list[str]] | None:
    """(fenced lines, remaining non-blank lines) of a section holding one
    fenced code block; None (one finding) without exactly one block."""
    n, lines = section
    inside: list[str] = []
    rest: list[str] = []
    fences = 0
    for line in lines:
        if line.startswith("```"):
            fences += 1
        elif fences == 1:
            inside.append(line)
        elif line.strip():
            rest.append(line.strip())
    if fences != 2:
        findings.append(_finding(f"`## {name}` needs exactly one fenced ``` block", road, n))
        return None
    return inside, rest


def _argv(line: str) -> tuple[str, ...]:
    """One argv-parseable command, never a shell (D1)."""
    argv = tuple(shlex.split(line, posix=True))
    if not argv:
        raise ValueError("empty command")
    if SHELL_OPERATORS & set(argv):
        raise ValueError("carries shell syntax (pipes, redirects, chaining); commands run "
                         "as argv, never through a shell")
    return argv


def _repo_relative(path: str) -> str | None:
    """The normalized repo-relative form of a Context or fence path, or None
    when it escapes the checkout."""
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or not p.parts:
        return None
    return str(p)


def _lint_context(section, repo: Path, findings: list[Finding]) -> tuple[str, ...]:
    items = _bullets("Context", section, findings, "one repo-relative existing path per bullet")
    if items is None:
        return ()
    out = []
    for raw in items:
        rel = _repo_relative(raw)
        if rel is None:
            findings.append(_finding(f"Context path {raw!r} is not repo-relative",
                                     "name a path relative to the checkout root, inside it",
                                     section[0]))
        elif rel == PLAN_FILE:
            findings.append(_finding(f"Context refuses the plan file {PLAN_FILE}", _PLAN_ROAD,
                                     section[0]))
        elif PurePosixPath(rel).parts[0] == SPECS_DIR and rel.endswith(".md"):
            findings.append(_finding(f"Context refuses the prompt-spec file {rel}", _PLAN_ROAD,
                                     section[0]))
        elif not (repo / rel).exists():
            findings.append(_finding(
                f"Context path {rel!r} does not exist",
                "Context is read-first EXISTING material; a file this ticket creates is named "
                "in `## Scope fence` and `## Verification` only", section[0]))
        else:
            out.append(rel)
    return tuple(out)


def _lint_plan_contract(section, plan: str | None, findings: list[Finding]) -> tuple[str, ...]:
    road = "cite plan sections as `- section N` bullets, one numeric id each"
    items = _bullets("Plan contract", section, findings, road)
    if items is None:
        return ()
    ids = []
    for raw in items:
        m = _SECTION_REF.match(raw)
        if not m:
            findings.append(_finding(f"Plan contract bullet {raw!r} is not `section N`", road,
                                     section[0]))
            return ()
        ids.append(m.group(1))
    if not ids:
        return ()
    if plan is None:
        findings.append(_finding(f"Plan contract cited but no {PLAN_FILE} exists to resolve it",
                                 road, section[0]))
        return ()
    try:
        return tuple(sid for sid, _ in resolve_plan_sections(plan, ids))
    except PlanContractError as e:
        findings.append(_finding(str(e), e.paved_road, section[0]))
        return ()


def _lint_prose(name: str, section, findings: list[Finding]) -> str:
    text = [line.strip() for line in section[1] if line.strip()]
    if not text:
        findings.append(_finding(f"`## {name}` is empty", f"write the {name} in one short paragraph",
                                 section[0]))
        return ""
    return text[0]


def _lint_fence(section, findings: list[Finding]) -> tuple[str, ...]:
    items = _bullets("Scope fence", section, findings, "one path prefix per bullet")
    if items is None:
        return ()
    out = []
    for raw in items:
        rel = _repo_relative(raw)
        if rel is None or " " in raw:
            findings.append(_finding(f"Scope fence entry {raw!r} is not a repo-relative path prefix",
                                     "one path prefix per bullet, relative to the checkout root",
                                     section[0]))
        else:
            out.append(rel)
    return tuple(out)


def _lint_verification(section, findings: list[Finding]) -> tuple[tuple[str, ...], ...]:
    road = ("write `## Verification` as one fenced ``` block, one argv-parseable command per "
            "line, no shell syntax")
    parsed = _fenced("Verification", section, findings, road)
    if parsed is None:
        return ()
    inside, rest = parsed
    if rest:
        findings.append(_finding(f"`## Verification` carries prose outside the fence: {rest[0]!r}",
                                 road, section[0]))
    commands = []
    for line in inside:
        if not line.strip():
            continue
        try:
            commands.append(_argv(line))
        except ValueError as e:
            findings.append(_finding(f"Verification command {line!r} is not argv-parseable: {e}",
                                     road, section[0]))
    if not commands:
        findings.append(_finding("`## Verification` names no command", road, section[0]))
    return tuple(commands)


def _lint_criteria(section, verification: tuple[tuple[str, ...], ...], fence: tuple[str, ...],
                   context: tuple[str, ...], repo: Path, findings: list[Finding]) -> None:
    road = ("quote, in backticks, the `Verification` command or the observable artifact path "
            "that checks this criterion")
    items = _bullets("Acceptance criteria", section, findings, "one measurable criterion per bullet")
    if items is None:
        return
    if not items:
        findings.append(_finding("`## Acceptance criteria` is empty", road, section[0]))
    commands = [" ".join(argv) for argv in verification]
    for item in items:
        if m := BANNED_ADJECTIVES.search(item):
            findings.append(_finding(
                f"acceptance criterion uses the banned adjective {m.group(1)!r}: {item!r}",
                "state the measurable post-merge observation instead", section[0]))
        if not any(_checks(span, commands, fence, context, repo) for span in _BACKTICK.findall(item)):
            findings.append(_finding(
                f"acceptance criterion names no `Verification` command or observable artifact: "
                f"{item!r}", road, section[0]))


def _checks(span: str, commands: list[str], fence: tuple[str, ...], context: tuple[str, ...],
            repo: Path) -> bool:
    if any(span in cmd for cmd in commands):
        return True
    rel = _repo_relative(span)
    if rel is None:
        return False
    return (rel in context or (repo / rel).exists()
            or any(rel == prefix or rel.startswith(prefix.rstrip("/") + "/") for prefix in fence))


def _lint_regression(sections, kind: str | None, findings: list[Finding]) -> Regression | None:
    road = ("`## Regression` is present exactly when `kind: bug`: one fenced argv command that "
            "reproduces the defect, then `- carries: <path-prefix>` bullets naming the "
            "branch-added test or fixture files it needs")
    section = sections.get("Regression")
    if kind == "bug" and section is None:
        findings.append(_finding("`## Regression` is required when `kind: bug`", road))
        return None
    if section is None:
        return None
    if kind != "bug":
        findings.append(_finding("`## Regression` is present but the ticket is not `kind: bug`",
                                 road, section[0]))
        return None
    parsed = _fenced("Regression", section, findings, road)
    if parsed is None:
        return None
    inside, rest = parsed
    lines = [line for line in inside if line.strip()]
    if len(lines) != 1:
        findings.append(_finding("`## Regression` needs exactly ONE reproducing command", road,
                                 section[0]))
        return None
    try:
        command = _argv(lines[0])
    except ValueError as e:
        findings.append(_finding(f"Regression command {lines[0]!r} is not argv-parseable: {e}",
                                 road, section[0]))
        return None
    carries = []
    for line in rest:
        m = _BULLET.match(line)
        c = _CARRIES.match(m.group(1)) if m else None
        if not c:
            findings.append(_finding(f"`## Regression` line {line!r} is not `- carries: <prefix>`",
                                     road, section[0]))
            return None
        carries.append(c.group(1))
    if not carries:
        findings.append(_finding("`## Regression` names no `carries:` prefix", road, section[0]))
        return None
    return Regression(command, tuple(carries))


def _lint_budget(section, findings: list[Finding]) -> tuple[int, int]:
    road = "write `## Time budget` as exactly two bullets: `- expected: <int>m` and `- stuck: <int>m`"
    items = _bullets("Time budget", section, findings, road)
    if items is None:
        return (0, 0)
    got: dict[str, int] = {}
    for item in items:
        m = _MINUTES.match(item)
        if m and m.group(1) not in got:
            got[m.group(1)] = int(m.group(2))
        else:
            findings.append(_finding(f"`## Time budget` bullet {item!r} is not the grammar", road,
                                     section[0]))
            return (0, 0)
    if set(got) != {"expected", "stuck"}:
        findings.append(_finding("`## Time budget` must carry both `expected` and `stuck`", road,
                                 section[0]))
        return (0, 0)
    return got["expected"], got["stuck"]


def _lint_window(section, findings: list[Finding]) -> tuple[tuple[str, str], ...]:
    road = ("write each `## Exit-read window` bullet as `- <journal event type>: <bounding "
            f"criterion>` with a type from {sorted(EVENT_TYPES)}")
    items = _bullets("Exit-read window", section, findings, road)
    if items is None:
        return ()
    out = []
    for item in items:
        m = _WINDOW.match(item)
        if not m or m.group(1) not in EVENT_TYPES:
            findings.append(_finding(f"`## Exit-read window` declaration {item!r} does not parse",
                                     road, section[0]))
            return ()
        out.append((m.group(1), m.group(2)))
    return tuple(out)


def _lint_depends(section, stem: str, resolve_stem: ResolveStem,
                  findings: list[Finding]) -> tuple[str, ...]:
    road = "list one existing ticket stem per bullet, or the single bullet `- none`"
    items = _bullets("Depends on", section, findings, road)
    if items is None:
        return ()
    if items == ["none"]:
        return ()
    out = []
    for item in items:
        if item == "none" or not STEM.match(item):
            findings.append(_finding(f"`## Depends on` entry {item!r} is not a stem", road,
                                     section[0]))
        elif item == stem:
            findings.append(_finding(f"`## Depends on` names the ticket itself", road, section[0]))
        elif not resolve_stem(item):
            findings.append(_finding(
                f"`## Depends on` stem {item!r} does not resolve to an existing ticket",
                "depend only on stems already on the ticket plane (or intaken alongside this one)",
                section[0]))
        else:
            out.append(item)
    return tuple(out)


def lint_ticket(text: str, *, stem: str, repo: Path, plan: str | None,
                resolve_stem: ResolveStem) -> Ticket:
    """The section 13 grammar; every defect at once, or the parsed Ticket.
    `plan` is the plan's bytes (None when no plan file exists); `resolve_stem`
    answers whether a `Depends on` stem exists."""
    findings: list[Finding] = []
    if not STEM.match(stem) or stem in RESERVED_STEMS:
        findings.append(_finding(f"stem {stem!r} is not a valid ticket stem", _STEM_ROAD))
    try:
        meta, body = parse_frontmatter(text)
    except ValueError as e:
        findings.append(_finding(str(e), "open the ticket with YAML frontmatter between `---` "
                                 "fences carrying at least `priority` and `kind`", 1))
        raise TicketLintError(stem, findings) from None
    _lint_frontmatter(meta, findings)
    sections = _split_sections(body, findings)
    for name in SECTIONS:
        if name not in sections and name not in OPTIONAL_SECTIONS:
            findings.append(_finding(f"section `## {name}` is missing", f"add a `## {name}` section"))
    # Every section present is linted even when another is missing or the
    # frontmatter is off: the author sees all defects in one refusal.
    kind = meta.get("kind")
    depends = context = plan_sections = fence = verification = window = ()
    prose: dict[str, str] = {}
    expected = stuck = 0
    if "Depends on" in sections:
        depends = _lint_depends(sections["Depends on"], stem, resolve_stem, findings)
    if "Context" in sections:
        context = _lint_context(sections["Context"], repo, findings)
    if "Plan contract" in sections:
        plan_sections = _lint_plan_contract(sections["Plan contract"], plan, findings)
    if meta.get("source") == "seed" and not plan_sections:
        findings.append(_finding(
            "a `source: seed` ticket must carry a `## Plan contract`",
            "cite the plan sections that own the machinery the seed's deliverable states"))
    for name in PROSE_SECTIONS:
        if name in sections:
            prose[name] = _lint_prose(name, sections[name], findings)
    if "Scope fence" in sections:
        fence = _lint_fence(sections["Scope fence"], findings)
    if "Verification" in sections:
        verification = _lint_verification(sections["Verification"], findings)
    if "Acceptance criteria" in sections:
        _lint_criteria(sections["Acceptance criteria"], verification, fence, context, repo, findings)
    regression = _lint_regression(sections, kind, findings)
    if "Time budget" in sections:
        expected, stuck = _lint_budget(sections["Time budget"], findings)
    if "Exit-read window" in sections:
        window = _lint_window(sections["Exit-read window"], findings)
    if findings:
        raise TicketLintError(stem, findings)
    return Ticket(
        stem=stem, state=meta.get("state"), source=meta.get("source"),
        priority=meta["priority"], kind=kind,
        agent_tier=meta.get("agent_tier", "medium"), agent_effort=meta.get("agent_effort", "medium"),
        gate_bypass=tuple((e["code"], e["reason"]) for e in meta.get("gate_bypass", [])),
        depends=depends, context=context, plan_sections=plan_sections, goal=prose["Goal"],
        scope_fence=fence, verification=verification, regression=regression,
        expected_minutes=expected, stuck_minutes=stuck, exit_read_window=window)


def stamp(text: str, **fields: str) -> str:
    """Set frontmatter scalars in place: an existing `key:` line is replaced,
    a missing one is appended before the closing fence. The authored bytes
    are otherwise untouched."""
    lines = text.splitlines(keepends=True)
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if not lines or lines[0].strip() != "---" or close is None:
        raise ValueError("stamp needs frontmatter between `---` fences")
    for key, value in fields.items():
        line = f"{key}: {value}\n"
        for i in range(1, close):
            if re.match(rf"\A{re.escape(key)}\s*:", lines[i]):
                lines[i] = line
                break
        else:
            lines.insert(close, line)
            close += 1
    return "".join(lines)


def depends_of(text: str) -> tuple[str, ...]:
    """The `Depends on` stems of a ticket file, read leniently (graph
    construction over committed tickets, not validation)."""
    try:
        _, body = parse_frontmatter(text)
    except ValueError:
        return ()
    sections = _split_sections(body, [])
    if "Depends on" not in sections:
        return ()
    items = _bullets("Depends on", sections["Depends on"], [], "") or []
    return tuple(i for i in items if i != "none" and STEM.match(i))


# ---- intake ---------------------------------------------------------------------

@dataclass(frozen=True)
class Committed:
    stem: str
    sha: str
    source: str
    state: str


@dataclass(frozen=True)
class Refused:
    stem: str
    findings: tuple[Finding, ...]


@dataclass(frozen=True)
class IntakeResult:
    committed: tuple[Committed, ...]
    refused: tuple[Refused, ...]


class Intake:
    def __init__(self, *, repo: Path, git: Git, journal: Journal, fs: Filesystem):
        self._repo = Path(repo)
        self._git = git
        self._journal = journal
        self._fs = fs

    def _path(self, stem: str) -> Path:
        return self._repo / TICKETS_DIR / stem / TICKET_FILE

    def _rel(self, stem: str) -> str:
        return f"{TICKETS_DIR}/{stem}/{TICKET_FILE}"

    def _plan(self) -> str | None:
        path = self._repo / PLAN_FILE
        return path.read_text() if path.is_file() else None

    def _stems(self) -> list[str]:
        return on_disk_stems(self._repo)

    async def pending(self) -> list[str]:
        return await pending_stems(self._repo, self._git)

    def _predecessor_source(self, stem: str) -> str | None:
        """The stem's source per its latest intake signal (journal-derived)."""
        source = None
        for event in self._journal.read():
            if (event.type == "signal" and event.ticket == stem
                    and event.body.get("kind") == INTAKE_SIGNAL):
                source = event.body["source"]
        return source

    def _human_stamps(self, stem: str, meta: Mapping) -> tuple[dict[str, str], list[Finding]]:
        """The fail-closed `source`/`state` stamp of section 13 touchpoint 1."""
        findings: list[Finding] = []
        declared = meta.get("source")
        predecessor = self._predecessor_source(stem)
        if predecessor is not None and predecessor != "human":
            source = predecessor  # an established machine source is never demoted
        elif declared in (None, "human"):
            source = "human"
        else:
            source = "human"
            findings.append(_finding(
                f"a new stem claims `source: {declared}`",
                "only the machine writes `seed` or `box:<class>`; hand-authored intake commits "
                "`source: human` -- omit `source` and let intake stamp it"))
        state = meta.get("state")
        if state is not None and not (isinstance(state, str) and state in INTAKE_STATES):
            findings.append(_finding(
                f"`state: {state}` is not intake's to write",
                "leave `state` unset: intake materializes `confirmed`; `merged` is recorded by "
                "the merge admission's journal transition and `rejected` by a Reject-queue kill"))
        return {"source": source, "state": "confirmed"}, findings

    async def run(self) -> IntakeResult:
        """Validate and ticket-plane-commit every pending hand-authored ticket,
        dependencies before dependents; refused files stay in place."""
        pending = await self.pending()
        graph = {stem: depends_of(self._path(stem).read_text()) for stem in self._stems()}
        committed: list[Committed] = []
        refused: list[Refused] = []
        done: set[str] = set()
        for stem in _topological(pending, graph):
            cycle = cycle_through(stem, graph)
            if cycle:
                refused.append(Refused(stem, (_finding(
                    f"dependency cycle: {' -> '.join(cycle)}",
                    "break the cycle so `Depends on` stays acyclic across the ticket plane"),)))
                continue
            text = self._path(stem).read_text()
            resolve = self._resolver(exclude=set(pending) - done)
            try:
                meta, _ = parse_frontmatter(text)
            except ValueError:
                # No fences means nothing to stamp; lint names the structural defect.
                refused.append(Refused(stem, tuple(self._lint_findings(text, stem, resolve))))
                continue
            stamps, findings = self._human_stamps(stem, meta)
            if findings:
                findings.extend(self._lint_findings(text, stem, resolve))
                refused.append(Refused(stem, tuple(findings)))
                continue
            try:
                committed.append(await self.commit(stem, resolve_stem=resolve, **stamps))
            except TicketLintError as e:
                refused.append(Refused(stem, tuple(e.findings)))
                continue
            done.add(stem)
        return IntakeResult(tuple(committed), tuple(refused))

    def _resolver(self, *, exclude: set[str]) -> ResolveStem:
        return lambda s: s not in exclude and self._path(s).is_file()

    def _lint_findings(self, text: str, stem: str, resolve: ResolveStem) -> list[Finding]:
        try:
            lint_ticket(text, stem=stem, repo=self._repo, plan=self._plan(), resolve_stem=resolve)
        except TicketLintError as e:
            return e.findings
        return []

    async def commit(self, stem: str, *, resolve_stem: ResolveStem | None = None,
                     **stamps: str) -> Committed:
        """Stamp, lint, commit `tickets/<stem>/ticket.md` through the
        ticket-plane lane, and journal the intake signal. The machine's own
        authoring paths call this with their declared source; `run` is the
        human front door over it."""
        resolve = resolve_stem or self._resolver(exclude={stem})
        text = stamp(self._path(stem).read_text(), **stamps) if stamps else self._path(stem).read_text()
        ticket = lint_ticket(text, stem=stem, repo=self._repo, plan=self._plan(),
                             resolve_stem=resolve)
        if ticket.source is None or ticket.state is None:
            raise ValueError(f"{stem}: a ticket commits with both `source` and `state` set")
        return await self.commit_lane(stem, text, source=ticket.source, state=ticket.state)

    async def commit_lane(self, stem: str, text: str, *, source: str | None,
                          state: str) -> Committed:
        """The one ticket-plane write, pathspec commit, and intake signal.

        Callers validate before entering this lane when the operation requires
        validation.  A reject stamp deliberately does not: killing an invalid
        ticket must remain possible.
        """
        self._fs.write(self._path(stem), text.encode())
        await self._git.add(self._repo, [self._rel(stem)])
        # Pathspec commit: the lane is fenced to this one path, so operator
        # pre-staged bytes never ride a ticket-plane commit onto main.
        sha = await self._git.commit(self._repo, f"squatch({stem}): ticket", [self._rel(stem)])
        self._journal.append("signal", {
            "kind": INTAKE_SIGNAL, "source": source, "state": state,
            "commit": sha, "path": self._rel(stem)}, ticket=stem)
        return Committed(stem, sha, source or "", state)


def on_disk_stems(repo: Path) -> list[str]:
    """Every `tickets/<stem>/ticket.md` the working tree holds, in stem order."""
    root = Path(repo) / TICKETS_DIR
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if (d / TICKET_FILE).is_file())


async def pending_stems(repo: Path, git: Git) -> list[str]:
    """Stems whose `ticket.md` the working tree holds but HEAD does not
    (untracked or modified), in stem order."""
    dirty = [e.path.split(" -> ")[-1] for e in await git.status(repo)]
    return [stem for stem in on_disk_stems(repo)
            if any(f"{TICKETS_DIR}/{stem}/{TICKET_FILE}" == p
                   or (p.endswith("/") and f"{TICKETS_DIR}/{stem}/{TICKET_FILE}".startswith(p))
                   for p in dirty)]


def _topological(stems: list[str], graph: Mapping[str, tuple[str, ...]]) -> list[str]:
    """Dependencies before dependents, stem order as the tiebreak; a cycle
    member falls through in stem order (refused separately)."""
    order: list[str] = []
    placed: set[str] = set()
    remaining = list(stems)
    while remaining:
        ready = [s for s in remaining
                 if all(d in placed or d not in stems for d in graph.get(s, ()))]
        if not ready:
            ready = remaining[:1]
        for s in ready:
            order.append(s)
            placed.add(s)
            remaining.remove(s)
    return order


def cycle_through(stem: str, graph: Mapping[str, tuple[str, ...]]) -> list[str] | None:
    """A dependency path from `stem` back to itself, or None."""
    stack: list[tuple[str, list[str]]] = [(stem, [stem])]
    seen: set[str] = set()
    while stack:
        node, path = stack.pop()
        for dep in graph.get(node, ()):
            if dep == stem:
                return path + [stem]
            if dep not in seen:
                seen.add(dep)
                stack.append((dep, path + [dep]))
    return None


# ---- `squatch new` --------------------------------------------------------------

# The templated front door (section 13 touchpoint 1): every section of the
# grammar, lint-clean as written so the first `run` is a decision about
# content, never a fight with the schema. Placeholders are prose the author
# replaces; the fence and verification are the self-host's defaults.
TEMPLATE = """\
---
priority: P2
kind: feature
---
## Depends on
- none

## Context

## Goal
State the one observable post-merge outcome.

## Why
State the judgment fuel for the fork the spec did not anticipate.

## Scope in
Name what changes.

## Scope out
Name the adjacent cleanups that must NOT change.

## Scope fence
- tests/

## Acceptance criteria
- `uv run pytest` exits 0.

## Verification
```
uv run pytest
```

## Definition of rejected
State when to stop and throw the branch away rather than churn.

## Time budget
- expected: 30m
- stuck: 60m
"""


def new_ticket(repo: Path, stem: str, *, fs: Filesystem) -> tuple[Path, list[Finding]]:
    """Template `tickets/<stem>/ticket.md` in the working tree and lint it
    synchronously (validation is never silent). Never overwrites: an existing
    file is the author's. Outside the lock fence by design: intake commits it
    on the next `run`/`drain`."""
    if not STEM.match(stem) or stem in RESERVED_STEMS:
        raise ValueError(f"stem {stem!r} is not a valid ticket stem; {_STEM_ROAD}")
    path = Path(repo) / TICKETS_DIR / stem / TICKET_FILE
    if path.exists():
        raise FileExistsError(f"{path} already exists; edit it, or pick another stem")
    fs.write(path, TEMPLATE.encode())
    plan = Path(repo) / PLAN_FILE
    try:
        lint_ticket(TEMPLATE, stem=stem, repo=Path(repo),
                    plan=plan.read_text() if plan.is_file() else None,
                    resolve_stem=lambda s: (Path(repo) / TICKETS_DIR / s / TICKET_FILE).is_file())
    except TicketLintError as e:
        return path, e.findings
    return path, []
