"""Provider layer (SQUATCH_PLAN.md section 6): registry, routing, the `cli` client.

The registry validates the config's provider set and routing table beyond
what the loader can know (adapter facts: which names the engine can drive,
whose stream reports cost). Routing resolves `(tier, surface)` to the FIRST
candidate's concrete `(provider, model)` before every call. `CliClient` is
the one `kind: cli` implementation of the Phase 0 `LLM` interface: one
adapter per agent CLI (`claude`, `codex`), each owning only its argv
contract and event-stream parse, over a shared base that owns the trust
boundary ONCE -- the per-surface write grant, the key-scoped child
environment, the redaction of both captured sinks, and the cost floor.

Effort reaches an adapter as a plain pass-through; `claude` has no effort
flag, so for it effort is provenance only.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from squatch.config import Config, ConfigError, Provider
from squatch.llm import LLM_SURFACES, WRITING_SURFACES, LLMRequest, LLMResult
from squatch.redact import Redactor
from squatch.seams import Filesystem, ProcessExec, kill_group

# The section 0 placeholder an unset operator value carries; a resolved row
# still holding it is refused pre-call, never sent to a model.
PLACEHOLDER = "OPERATOR-SETS-THIS"
PREREQUISITE = ("set it in config.yaml per the Phase 1 prerequisites "
                "(SQUATCH_PLAN.md section 0) before a live call")
# The seam's backstop for a call; the driver's stuck budget is the real bound.
CALL_TIMEOUT_SECONDS = 4 * 3600
# A stderr tail is all an error carries: the full stream is spool material.
STDERR_TAIL = 2000

Grant = Literal["write", "read"]
FailureClass = Literal["auth_error"]


class RoutingError(Exception):
    """A config/setup refusal raised BEFORE any subprocess: no route, a
    placeholder on the resolved row, or an unset key."""


class ProviderError(Exception):
    """A call that ran and failed: non-zero exit, a failed-turn event, a
    stream with no result, or no cost to charge."""

    def __init__(self, provider: str, reason: str, *, rc: int | None = None, stderr: str = "",
                 failure_class: FailureClass | None = None, paved_road: str | None = None):
        self.provider, self.reason, self.rc, self.stderr = provider, reason, rc, stderr
        self.failure_class, self.paved_road = failure_class, paved_road
        tail = stderr[-STDERR_TAIL:].strip()
        super().__init__(f"{provider}: {reason}" + (f" (rc={rc})" if rc is not None else "")
                         + (f"\nstderr: {tail}" if tail else "")
                         + (f"\npaved road: {paved_road}" if paved_road else ""))


@dataclass(frozen=True)
class Resolved:
    provider: Provider
    model: str


@dataclass(frozen=True)
class Parsed:
    """What an adapter reads off its event stream; `failure` set means the
    turn failed regardless of exit code."""

    text: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None
    usd: float | None = None
    failure: str | None = None


def _events(out: str):
    """The JSON objects of a JSONL stream; a non-JSON line is CLI chatter,
    not an event, and the terminal event decides the verdict."""
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            yield obj


class _Adapter:
    auth_failure_signature: str
    auth_paved_road: str

    def error(self, reason: str, *, rc: int | None, stderr: str) -> ProviderError:
        authenticated = any(
            self.auth_failure_signature in channel for channel in (reason, stderr))
        return ProviderError(
            self.name, reason, rc=rc, stderr=stderr,
            failure_class="auth_error" if authenticated else None,
            paved_road=self.auth_paved_road if authenticated else None)


class ClaudeAdapter(_Adapter):
    name = "claude"
    reports_cost = True
    auth_failure_signature = "OAuth refresh token is no longer valid"
    auth_paved_road = "run `claude login` in the operator's shell"

    def argv(self, *, model: str, effort: str, grant: Grant) -> list[str]:
        # --verbose: print mode refuses stream-json without it.
        base = ["claude", "-p", "--output-format", "stream-json", "--verbose", "--model", model]
        if grant == "write":
            return base + ["--permission-mode", "bypassPermissions"]
        return base + ["--allowedTools", "Read", "Grep", "Glob", "LS"]

    def parse(self, out: str) -> Parsed:
        result = None
        for event in _events(out):
            if event.get("type") == "result":
                result = event
        if result is None:
            return Parsed(failure="stream carried no `result` event")
        if result.get("is_error") or result.get("subtype") != "success":
            detail = result.get("result") or result.get("errors") or ""
            return Parsed(failure=f"{result.get('subtype', 'error')}: {detail}")
        usage = result.get("usage") or {}
        return Parsed(text=result.get("result", ""),
                      input_tokens=_int(usage.get("input_tokens")),
                      output_tokens=_int(usage.get("output_tokens")),
                      usd=_float(result.get("total_cost_usd")))


class CodexAdapter(_Adapter):
    name = "codex"
    reports_cost = False
    auth_failure_signature = ("Your access token could not be refreshed because your refresh "
                              "token has expired.")
    auth_paved_road = "run `codex login` in the operator's shell"

    def argv(self, *, model: str, effort: str, grant: Grant) -> list[str]:
        base = ["codex", "exec", "--json", "-m", model, "-c", f"model_reasoning_effort={effort}"]
        if grant == "write":
            base += ["--dangerously-bypass-approvals-and-sandbox"]
        else:
            base += ["--sandbox", "read-only", "-c", "approval_policy=never"]
        return base + ["-"]  # the prompt arrives on stdin

    def parse(self, out: str) -> Parsed:
        # codex exits 0 even on a failed turn: the event stream is the verdict.
        text = None
        usage = {}
        for event in _events(out):
            kind = event.get("type")
            if kind == "item.completed" and (event.get("item") or {}).get("type") == "agent_message":
                text = event["item"].get("text", "")
            elif kind == "turn.completed":
                usage = event.get("usage") or {}
            elif kind in ("turn.failed", "error"):
                error = event.get("error") or {}
                message = error.get("message") if isinstance(error, dict) else error
                return Parsed(failure=f"{kind}: {message or event.get('message') or ''}")
        if text is None:
            return Parsed(failure="stream carried no `agent_message` item")
        return Parsed(text=text, input_tokens=_int(usage.get("input_tokens")),
                      output_tokens=_int(usage.get("output_tokens")), usd=None)


def _int(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _float(v) -> float | None:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# The closed set of agent CLIs the engine can drive; a cli provider's `name`
# selects its adapter, so an unknown name is a config refusal.
ADAPTERS: Mapping[str, ClaudeAdapter | CodexAdapter] = {
    a.name: a for a in (ClaudeAdapter(), CodexAdapter())}


class Registry:
    """The validated provider set + routing table of one config."""

    def __init__(self, config: Config, *, source: str = "config.yaml"):
        self._providers = {p.name: p for p in config.providers}
        self._routes = {(r.tier, r.surface): r for r in config.routing}
        self.auth_names: frozenset[str] = frozenset(p.auth for p in config.providers if p.auth)
        self.surfaces: frozenset[str] = LLM_SURFACES | {s.name for s in config.review.surfaces}
        findings: list[tuple[str, str]] = []
        for i, p in enumerate(config.providers):
            if p.kind != "cli":
                continue
            if p.name not in ADAPTERS:
                findings.append((f"providers[{i}].name",
                                 f"no shipped cli adapter is named `{p.name}`; "
                                 f"the engine drives {sorted(ADAPTERS)}"))
            elif not ADAPTERS[p.name].reports_cost and p.limits.est_cost_per_call_usd is None:
                findings.append((f"providers[{i}].limits.est_cost_per_call_usd",
                                 f"required: the `{p.name}` stream reports no cost, so a "
                                 f"flat per-call estimate is the only charge (section 6)"))
        for i, r in enumerate(config.routing):
            if r.surface not in self.surfaces:
                findings.append((f"routing[{i}].surface",
                                 f"`{r.surface}` is not an llm_surface; one of "
                                 f"{sorted(self.surfaces)}"))
            if not r.candidates:
                findings.append((f"routing[{i}].candidates", "at least one candidate is required"))
        if findings:
            raise ConfigError(source, findings)
        # A writing surface mutates the tree: only a cli provider can (an api
        # provider returns text and nothing applies it). Checked on the
        # RESOLVED row, so an implement surface inheriting `review` is covered.
        for (tier, surface), route in self._routes.items():
            for writing in WRITING_SURFACES:
                if surface not in (writing, "review"):
                    continue
                if surface == "review" and (tier, writing) in self._routes:
                    continue
                p = self._providers[route.candidates[0].provider]
                if p.kind != "cli":
                    i = config.routing.index(route)
                    findings.append((f"routing[{i}].candidates[0].provider",
                                     f"`{p.name}` is kind `{p.kind}` but serves `{writing}` at "
                                     f"tier `{tier}`, which requires `cli` (section 6)"))
        if findings:
            raise ConfigError(source, findings)

    def provider(self, name: str) -> Provider:
        return self._providers[name]

    def resolve(self, tier: str, surface: str) -> Resolved:
        """The FIRST candidate of the (tier, surface) row; a surface with no
        row of its own inherits the `review` row (section 5 invariant 6)."""
        route = self._routes.get((tier, surface)) or self._routes.get((tier, "review"))
        if route is None:
            raise RoutingError(f"no routing row for tier `{tier}` surface `{surface}` "
                               f"(nor a `review` row to inherit); add one to config.yaml")
        candidate = route.candidates[0]
        provider = self._providers[candidate.provider]
        model = candidate.model or getattr(provider.models_by_tier, tier)
        return Resolved(provider=provider, model=model)


def child_env(env: Mapping[str, str], auth_names: frozenset[str] | set[str]) -> dict[str, str]:
    """INHERIT-MINUS-SECRETS: the base for every child process. A provider
    key is added back only by the one call that needs it."""
    return {k: v for k, v in env.items() if k not in auth_names}


class CliClient:
    """The `kind: cli` LLM: routes, grants, scopes the key, runs the adapter."""

    kind: Literal["api", "cli"] = "cli"

    def __init__(self, registry: Registry, *, process: ProcessExec, fs: Filesystem,
                 env: Mapping[str, str], redact: Redactor, state_dir: Path, cwd: Path,
                 timeout: float = CALL_TIMEOUT_SECONDS):
        self._registry = registry
        self._process = process
        self._fs = fs
        self._env = env
        self._redact = redact
        self._spools = Path(state_dir) / "spools"
        self._cwd = Path(cwd)
        self._timeout = timeout
        self._seq = 0
        self._pgid: int | None = None

    async def call(self, req: LLMRequest) -> LLMResult:
        resolved = self._registry.resolve(req.tier, req.surface)
        provider, model = resolved.provider, resolved.model
        if PLACEHOLDER in (model, provider.auth):
            raise RoutingError(f"route ({req.tier}, {req.surface}) -> {provider.name} still "
                               f"carries the placeholder `{PLACEHOLDER}`; {PREREQUISITE}")
        adapter = ADAPTERS[provider.name]
        # The write grant is derived from the surface allowlist, never passed in.
        grant: Grant = "write" if req.surface in WRITING_SURFACES else "read"
        if grant == "write" and req.worktree is None:
            raise ValueError(f"surface `{req.surface}` writes a tree but the request "
                             f"carries no worktree")
        cwd = req.worktree if req.worktree is not None else self._cwd
        env = child_env(self._env, self._registry.auth_names)
        if provider.auth:
            if provider.auth not in self._env:
                raise RoutingError(f"provider `{provider.name}` reads its key from "
                                   f"${provider.auth}, which is not set; export it "
                                   f"({PREREQUISITE})")
            env[provider.auth] = self._env[provider.auth]
        # The prompt is unbounded and argv is capped: it reaches the CLI only
        # as a file on stdin. Written through the redactor: a spool write.
        self._seq += 1
        prompt = (self._spools / (req.ticket or req.surface) / "cli"
                  / f"{self._seq:06d}-{req.surface}-prompt.md")
        self._fs.write(prompt, self._redact(req.rendered).encode())
        argv = adapter.argv(model=model, effort=req.effort, grant=grant)
        try:
            rc, out, err = await self._process.run(
                argv, cwd=cwd, env=env, timeout=self._timeout, stdin_path=prompt,
                on_spawn=self._bind)
        finally:
            self._pgid = None
        # Both sinks are scrubbed before anything is parsed or raised from them.
        out, err = self._redact(out), self._redact(err)
        parsed = adapter.parse(out)
        if rc != 0:
            raise adapter.error(parsed.failure or "non-zero exit", rc=rc, stderr=err)
        if parsed.failure:
            raise adapter.error(parsed.failure, rc=rc, stderr=err)
        # Cost floor: metered when the stream reports it, else the declared
        # flat estimate; never unmetered.
        usd = parsed.usd if parsed.usd is not None else provider.limits.est_cost_per_call_usd
        if usd is None:
            raise ProviderError(provider.name, "stream reported no cost and the provider "
                                "declares no limits.est_cost_per_call_usd", rc=rc, stderr=err)
        return LLMResult(text=parsed.text, input_tokens=parsed.input_tokens,
                         output_tokens=parsed.output_tokens, provider=provider.name,
                         model=model, usd=usd)

    def _bind(self, pgid: int) -> None:
        self._pgid = pgid

    def abort_current(self) -> None:
        """SIGKILL the active child's whole group; the seam reaps it."""
        if self._pgid is not None:
            kill_group(self._pgid)
