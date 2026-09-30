"""Prompt specs: lint, render, and the Plan contract resolver (SQUATCH_PLAN.md
sections 8, 13).

A spec is one engine-plane file per `llm_surface`: closed YAML frontmatter
plus the fixed prose sections. Injected content enters a rendered prompt only
through the delimited data-block form -- the data/instruction boundary is
this module's rendering contract, never stage-local vigilance -- so lint
refuses a template that interpolates outside the form, and render refuses
content that carries the delimiter (a break-out is refused, never escaped).
Every rendered prompt is measured against ONE engine-owned character bound
keyed by the resolved effort. Plan prose reaches a prompt only through the
`Plan contract` resolver: numeric section ids resolved verbatim against the
plan's `## N.` headings, deduplicated, an unknown id refused.
"""

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from squatch.artifacts import GATE_CODES, Finding
from squatch.config import Tier
from squatch.llm import EFFORTS, LLM_SURFACES, TIERS, Effort

LINT_CODE = "spec_lint"
DEFAULT_MAX_LINES = 200
SPEC_SECTIONS: tuple[str, ...] = ("Role", "Task", "Inputs", "Output format", "On-failure")
FRONTMATTER_KEYS: frozenset[str] = frozenset(
    {"llm_surface", "consumes", "emits", "tier", "effort", "gates", "version"})

# The engine's own data-block delimiter. Any occurrence in injected content
# is a render refusal: this is why section 13 refuses `specs/*.md` as Context.
DATA_MARKER = "<<<squatch:"
# An `optional` slot renders only when its input is supplied (a re-entry's
# prior-attempts block); every other slot is required, missing means refused.
_DIRECTIVE = re.compile(r'^<<<squatch:data name="([a-z][a-z0-9_]*)"( optional)?>>>$')
_BARE = re.compile(r"\{\{\s*([^}]*?)\s*\}\}")
_H2 = re.compile(r"^## (.+?)\s*$")
_PLAN_H2 = re.compile(r"^## (\d+)\. ")
_VERSION = re.compile(r"^\d+\.\d+$")
_SECTION_ID = re.compile(r"^\d+$")

# One conservative character-count bound per resolved effort (section 8):
# ~4 chars/token against a 200k-token context, less thinking headroom that
# grows with effort. Stage-local bounds are forbidden.
RENDER_BOUND_CHARS: Mapping[Effort, int] = {
    "low": 400_000, "medium": 320_000, "high": 240_000, "max": 160_000}

Origin = Literal["engine", "host", "untrusted"]
ORIGINS: frozenset[str] = frozenset(Origin.__args__)


@dataclass(frozen=True)
class DataBlock:
    """One injected input: the origin marking the block carries and the bytes."""

    origin: Origin
    content: str

    def __post_init__(self):
        if self.origin not in ORIGINS:
            raise ValueError(f"origin {self.origin!r} is not one of {sorted(ORIGINS)}")


class SpecLintError(Exception):
    def __init__(self, source: str, findings: list[Finding]):
        self.source = source
        self.findings = findings
        super().__init__(f"{source}: " + "; ".join(f.message for f in findings))


class RenderRefused(Exception):
    """A render the contract refuses before any model call."""

    def __init__(self, reason: str, message: str, paved_road: str):
        self.reason = reason
        self.paved_road = paved_road
        super().__init__(f"{message} (paved road: {paved_road})")


class PlanContractError(Exception):
    def __init__(self, message: str, paved_road: str):
        self.paved_road = paved_road
        super().__init__(f"{message} (paved road: {paved_road})")


@dataclass(frozen=True)
class Spec:
    surface: str
    consumes: str
    emits: str | Mapping[str, str]
    tier: Tier
    effort: Effort
    gates: tuple[str, ...]
    version: str
    slots: tuple[str, ...]
    optional: frozenset[str]
    template: tuple[str, ...]
    source: str

    def render(self, inputs: Mapping[str, DataBlock], *, findings: Sequence[Finding] = (),
               plan: str | None = None, plan_sections: Iterable[int | str] = (),
               effort: Effort | None = None) -> str:
        effort = effort or self.effort
        missing = [s for s in self.slots if s not in inputs and s not in self.optional]
        extra = sorted(set(inputs) - set(self.slots))
        if missing or extra:
            raise RenderRefused(
                "inputs", f"{self.source}: inputs do not match the spec's slots "
                f"(missing {missing}, unreferenced {extra})",
                f"supply exactly the slots the template names: {list(self.slots)} "
                f"(optional: {sorted(self.optional)})")
        blocks = dict(inputs)
        plan_sections = tuple(plan_sections)
        if plan_sections and plan is None:
            raise RenderRefused("plan", f"{self.source}: Plan contract cited without plan text",
                                "pass the plan's bytes alongside the cited section ids")
        if plan_sections:
            sections = resolve_plan_sections(plan, plan_sections)
            blocks["plan_contract"] = DataBlock("engine", "".join(body for _, body in sections))
        if findings:
            blocks["findings"] = DataBlock("engine", _findings_text(findings))
        for name, block in blocks.items():
            if DATA_MARKER in block.content:
                raise RenderRefused(
                    "delimiter", f"{self.source}: input {name!r} carries the data-block "
                    f"delimiter {DATA_MARKER!r}",
                    "inject content that does not contain the engine delimiter; a prompt-spec "
                    "or rendered prompt is never an input")
        out = [f"squatch prompt: surface={self.surface} spec_version={self.version}\n\n"]
        for line in self.template:
            m = _DIRECTIVE.match(line)
            if m is None:
                out.append(line + "\n")
            elif m.group(1) in blocks:
                out.append(_block(m.group(1), blocks[m.group(1)]))
        for name in ("plan_contract", "findings"):
            if name in blocks:
                out.append("\n" + _block(name, blocks[name]))
        text = "".join(out)
        bound = RENDER_BOUND_CHARS[effort]
        if len(text) > bound:
            raise RenderRefused(
                "over_bound", f"{self.source}: rendered prompt is {len(text)} chars, over the "
                f"{bound}-char bound at effort {effort}",
                "shrink the inputs or split the ticket")
        return text


def _block(name: str, block: DataBlock) -> str:
    sha = hashlib.sha256(block.content.encode()).hexdigest()[:12]
    body = block.content if block.content.endswith("\n") else block.content + "\n"
    return (f'<<<squatch:data name="{name}" origin="{block.origin}" sha="{sha}">>>\n'
            f"{body}<<<squatch:end name=\"{name}\">>>\n")


def _findings_text(findings: Sequence[Finding]) -> str:
    # Findings are fed back into the next model call.  A mechanical finding can
    # legitimately quote the prompt delimiter while explaining why an earlier
    # render was refused; keep the stored finding exact, but quote that marker in
    # its model-visible re-entry representation so it cannot break out of this
    # engine-owned data block.
    def visible(value: object) -> str:
        return str(value).replace(DATA_MARKER, "[squatch-data:")

    lines = []
    for f in findings:
        where = (f" at {visible(f.path)}" + (f":{f.line}" if f.line else "")
                 if f.path else "")
        lines.append(
            f"- {visible(f.code)}{where}: {visible(f.message)} "
            f"(paved road: {visible(f.paved_road)})")
    return "\n".join(lines) + "\n"


# ---- lint ---------------------------------------------------------------

def load_spec(path: Path, *, surfaces: Iterable[str] = LLM_SURFACES,
              max_lines: int = DEFAULT_MAX_LINES) -> Spec:
    try:
        text = Path(path).read_text()
    except OSError as e:
        raise SpecLintError(str(path), [_finding(
            f"cannot read: {e.strerror or e}", "ship one spec file per llm_surface at specs/<surface>.md")]) from None
    return lint_spec(text, surfaces=surfaces, max_lines=max_lines, source=str(path))


def lint_spec(text: str, *, surfaces: Iterable[str] = LLM_SURFACES,
              max_lines: int = DEFAULT_MAX_LINES, source: str = "<spec>") -> Spec:
    """Validate frontmatter schema and vocab, section presence, size budget,
    and the data-block form; every defect is reported at once."""
    findings: list[Finding] = []
    lines = text.splitlines()
    if len(lines) > max_lines:
        findings.append(_finding(f"spec is {len(lines)} lines, over the {max_lines}-line budget",
                                 "cut prose; move host content to inputs"))
    head, body, body_start = _split_frontmatter(lines, findings)
    meta = _lint_frontmatter(head, set(surfaces), findings)
    slots, optional = _lint_body(body, body_start, findings)
    if findings:
        raise SpecLintError(source, findings)
    return Spec(surface=meta["llm_surface"], consumes=meta["consumes"], emits=meta["emits"],
                tier=meta["tier"], effort=meta["effort"], gates=tuple(meta["gates"]),
                version=meta["version"], slots=slots, optional=optional, template=tuple(body),
                source=source)


def _finding(message: str, paved_road: str, line: int | None = None) -> Finding:
    return Finding(code=LINT_CODE, line=line, message=message, paved_road=paved_road)


def _split_frontmatter(lines: list[str], findings: list[Finding]) -> tuple[str, list[str], int]:
    if not lines or lines[0].strip() != "---":
        findings.append(_finding("missing frontmatter: the file must open with a `---` fence",
                                 "open the spec with a YAML frontmatter block between `---` fences", 1))
        return "", lines, 1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), lines[i + 1:], i + 2
    findings.append(_finding("unterminated frontmatter: no closing `---` fence",
                             "close the frontmatter with a `---` line", 1))
    return "\n".join(lines[1:]), [], len(lines) + 1


def _lint_frontmatter(head: str, surfaces: set[str], findings: list[Finding]) -> dict:
    road = "declare exactly the closed keys: " + ", ".join(sorted(FRONTMATTER_KEYS))
    try:
        meta = yaml.safe_load(head) if head.strip() else None
    except yaml.YAMLError as e:
        findings.append(_finding(f"frontmatter is not valid YAML: {e}", road, 1))
        return {}
    if not isinstance(meta, dict):
        findings.append(_finding("frontmatter is not a mapping", road, 1))
        return {}
    for key in sorted(set(meta) - FRONTMATTER_KEYS):
        findings.append(_finding(f"frontmatter key {key!r} is not in the closed schema", road, 1))
    for key in sorted(FRONTMATTER_KEYS - set(meta)):
        findings.append(_finding(f"frontmatter key {key!r} is missing", road, 1))

    def vocab(key: str, allowed: Iterable[str]) -> None:
        if key in meta and meta[key] not in allowed:
            findings.append(_finding(f"{key} {meta[key]!r} is not one of {sorted(allowed)}",
                                     f"set {key} to a value from the closed vocabulary", 1))

    vocab("llm_surface", surfaces)
    vocab("tier", TIERS)
    vocab("effort", EFFORTS)
    gates = meta.get("gates")
    if "gates" in meta and (not isinstance(gates, list)
                            or any(g not in GATE_CODES for g in gates)):
        findings.append(_finding(f"gates {gates!r} is not a list of engine gate codes",
                                 f"list gate codes from {sorted(GATE_CODES)}", 1))
    version = meta.get("version")
    if "version" in meta and not (isinstance(version, str) and _VERSION.match(version)):
        findings.append(_finding(f"version {version!r} is not a quoted MAJOR.MINOR string",
                                 'write version as a quoted string, e.g. version: "1.0"', 1))
    if "consumes" in meta and not _nonempty(meta["consumes"]):
        findings.append(_finding("consumes must name one artifact type",
                                 "set consumes to the consumed artifact type name", 1))
    emits = meta.get("emits")
    if "emits" in meta and not (_nonempty(emits) or (
            isinstance(emits, dict) and emits
            and all(_nonempty(k) and _nonempty(v) for k, v in emits.items()))):
        findings.append(_finding("emits must name one artifact type or a verdict -> type map",
                                 "set emits to a type name, or {verdict: TypeName, ...}", 1))
    return meta


def _nonempty(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _lint_body(body: list[str], start: int, findings: list[Finding]
               ) -> tuple[tuple[str, ...], frozenset[str]]:
    seen: list[str] = []
    slots: list[str] = []
    optional: set[str] = set()
    for offset, line in enumerate(body):
        n = start + offset
        if h := _H2.match(line):
            name = h.group(1)
            if name not in SPEC_SECTIONS:
                findings.append(_finding(f"section {name!r} is not a spec section",
                                         f"use only the fixed sections: {list(SPEC_SECTIONS)}", n))
            elif name in seen:
                findings.append(_finding(f"section {name!r} appears twice",
                                         "keep one of each fixed section", n))
            seen.append(name)
            continue
        for m in _BARE.finditer(line):
            findings.append(_finding(
                f"`{m.group(0)}` interpolates {m.group(1)!r} outside the data-block form "
                "(data folded into the instruction channel)",
                f'inject it on its own line as <<<squatch:data name="{m.group(1)}">>>', n))
        if DATA_MARKER in line:
            d = _DIRECTIVE.match(line)
            if not d:
                findings.append(_finding(
                    f"malformed data-block marker: {line.strip()!r}",
                    'a data directive is exactly <<<squatch:data name="<slot>">>> (or '
                    '<<<squatch:data name="<slot>" optional>>>) alone on its line; the end '
                    "marker is renderer-owned", n))
            elif d.group(1) in slots:
                findings.append(_finding(f"slot {d.group(1)!r} is injected twice",
                                         "inject each input once", n))
            else:
                slots.append(d.group(1))
                if d.group(2):
                    optional.add(d.group(1))
    for name in SPEC_SECTIONS:
        if name not in seen:
            findings.append(_finding(f"section {name!r} is missing",
                                     f"add a `## {name}` section", None))
    return tuple(slots), frozenset(optional)


# ---- Plan contract -------------------------------------------------------

def resolve_plan_sections(plan: str, ids: Iterable[int | str]) -> tuple[tuple[str, str], ...]:
    """Resolve numeric section ids against the plan's `## N.` headings:
    verbatim bytes from the heading to the next H2, deduplicated in first-cite
    order. An unknown or non-numeric id refuses fail-closed."""
    road = "cite a numeric plan section id that exists, e.g. `section 11`"
    wanted: list[str] = []
    for raw in ids:
        sid = str(raw).strip()
        if not _SECTION_ID.match(sid):
            raise PlanContractError(f"Plan contract id {raw!r} is not a numeric section id", road)
        if sid not in wanted:
            wanted.append(sid)
    sections = _plan_sections(plan)
    unknown = [sid for sid in wanted if sid not in sections]
    if unknown:
        raise PlanContractError(f"Plan contract ids {unknown} resolve to no `## N.` heading", road)
    return tuple((sid, sections[sid]) for sid in wanted)


def _plan_sections(plan: str) -> dict[str, str]:
    lines = plan.splitlines(keepends=True)
    starts: list[tuple[int, str | None]] = []
    fenced = False
    for i, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced  # a `## ` inside a code fence is content, not a heading
        elif not fenced and line.startswith("## "):
            m = _PLAN_H2.match(line)
            starts.append((i, m.group(1) if m else None))
    out: dict[str, str] = {}
    for k, (i, sid) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(lines)
        if sid is not None and sid not in out:
            out[sid] = "".join(lines[i:end])
    return out
