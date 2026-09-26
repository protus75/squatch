"""Host config loader (SQUATCH_PLAN.md section 15).

One `config.yaml` at the host checkout root (or the `--config` path), parsed
with PyYAML `safe_load` and validated fail-closed: unknown keys, explicit
nulls, and out-of-vocabulary values are refused, each naming the key by
dotted path. The `schema_version` handshake runs first and owns the first
verdict: newer is refused outright, older is refused with `migrate-config`
as the paved road, and only an equal version reaches the schema.
"""

from pathlib import Path
from typing import Literal

import re

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SCHEMA_VERSION = 1
DEFAULT_NAME = "config.yaml"

Tier = Literal["low", "medium", "high", "max"]
Severity = Literal["hard", "soft"]
Trigger = Literal["always"] | list[str]
Policy = Literal["draft", "confirmed"]


class ConfigError(Exception):
    """A refusal. `key` is the dotted path of the first offending key ("" when
    the defect is the file itself); `findings` is every (key, reason) pair."""

    def __init__(self, source: str, findings: list[tuple[str, str]]):
        self.source = source
        self.findings = findings
        self.key = findings[0][0]
        lines = [f"{key}: {reason}" if key else reason for key, reason in findings]
        super().__init__(f"{source}: " + "; ".join(lines))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelsByTier(_Strict):
    low: str
    medium: str
    high: str
    max: str


class Limits(_Strict):
    concurrency: int = Field(ge=1)
    # Required iff the cli's stream carries no usage; only the provider layer
    # knows that, so presence is checked there, not here (section 6).
    est_cost_per_call_usd: float | None = Field(default=None, ge=0)
    quota_window_minutes: int = Field(default=60, ge=1)


class Provider(_Strict):
    name: str = Field(min_length=1)
    kind: Literal["api", "cli"]
    auth: str | None = None
    models_by_tier: ModelsByTier
    limits: Limits

    @field_validator("auth")
    @classmethod
    def _auth_is_an_env_var_name(cls, v):
        # An env-var NAME, never a literal secret: the shape check is the allowlist.
        if v is not None and not re.fullmatch(r"[A-Z_][A-Z0-9_]*", v):
            raise ValueError(f"must be an env-var NAME like `ANTHROPIC_API_KEY`, "
                             f"never a literal secret; got {v!r}")
        return v

    @model_validator(mode="after")
    def _api_unshipped(self):
        if self.kind == "api":
            raise ValueError(_at("kind", "the api client has not shipped; "
                                        "only `cli` providers load (section 6)"))
        return self


class Candidate(_Strict):
    provider: str
    model: str | None = None


class Route(_Strict):
    tier: Tier
    surface: str
    candidates: list[Candidate]


class Mechanical(_Strict):
    code: str
    argv: list[str] = Field(min_length=1)
    trigger: Trigger
    severity: Severity


class Surface(_Strict):
    name: str
    trigger: Trigger
    rules_doc: Path
    severity: Severity


class Review(_Strict):
    mechanical: list[Mechanical] = []
    surfaces: list[Surface] = []
    trigger_map: dict[str, list[str]] = {}
    gate_severity: dict[str, Severity] = {}


class Strategy(_Strict):
    paths: list[str] = Field(min_length=1)
    strategy: Literal["regenerate", "union"]
    argv: list[str] | None = None

    @model_validator(mode="after")
    def _argv_matches_strategy(self):
        if self.strategy == "regenerate" and self.argv is None:
            raise ValueError(_at("argv", "required for strategy `regenerate`"))
        if self.strategy == "union" and self.argv is not None:
            raise ValueError(_at("argv", "not allowed for strategy `union`"))
        return self


class Merge(_Strict):
    safety_checks: list[str] = []
    strategies: list[Strategy] = []


class Scheduler(_Strict):
    max_unmerged: int = Field(default=2, ge=1)


class Caps(_Strict):
    diagnosis: int = Field(default=6, ge=0)
    retry: int = Field(default=6, ge=0)
    premise_bounce: int = Field(default=2, ge=0)
    infra: int = Field(default=6, ge=0)
    quarantine: int = Field(default=5, ge=0)
    poison: int = Field(default=2, ge=0)


class Seeding(_Strict):
    max_seeds_per_admission: int = Field(default=3, ge=1)


class CircuitBreaker(_Strict):
    k: int = Field(default=3, ge=1)
    cooldown_minutes: int = Field(default=10, ge=1)


class Drain(_Strict):
    max_runtime_hours: float = Field(default=12, gt=0)
    max_ticket_minutes: float = Field(default=90, gt=0)


class BoxPolicy(_Strict):
    # Shipped defaults are the section 12 policy table, one key per row.
    failure_report: Policy = "confirmed"
    retro_finding: Policy = "confirmed"
    override_report: Policy = "draft"
    suggestion: Policy = "draft"
    bug_report_self_diagnosed: Policy = "confirmed"
    bug_report_player_repro: Policy = "confirmed"
    bug_report_player_no_repro: Policy = "draft"


class Config(_Strict):
    schema_version: Literal[SCHEMA_VERSION]
    state_dir: Path
    # Defaults to <state_dir>/worktrees when ABSENT (filled after validation;
    # pydantic does not validate the placeholder default); an explicit null was
    # already refused by the null walk.
    worktree_root: Path = Field(default=None)
    providers: list[Provider]
    routing: list[Route]
    routing_default_tier: Tier = "medium"
    review: Review = Review()
    merge: Merge = Merge()
    scheduler: Scheduler = Scheduler()
    caps: Caps = Caps()
    seeding: Seeding = Seeding()
    circuit_breaker: CircuitBreaker = CircuitBreaker()
    drain: Drain = Drain()
    engine_plane_safety_inventory: list[str] = []
    box_policy: BoxPolicy = BoxPolicy()
    notify: list[str] | None = None
    report_inbox: Path | None = None
    context_files: list[Path] = []

    @model_validator(mode="after")
    def _cross_references(self):
        if self.worktree_root is None:
            self.worktree_root = self.state_dir / "worktrees"
        seen: set[str] = set()
        for i, p in enumerate(self.providers):
            if p.name in seen:
                raise ValueError(_at(f"providers[{i}].name", f"duplicate provider `{p.name}`"))
            seen.add(p.name)
        for i, route in enumerate(self.routing):
            for j, c in enumerate(route.candidates):
                if c.provider not in seen:
                    raise ValueError(_at(f"routing[{i}].candidates[{j}].provider",
                                         f"`{c.provider}` is not a declared provider"))
        if self.caps.retry > self.caps.diagnosis:
            raise ValueError(_at("caps.retry", "must not exceed caps.diagnosis"))
        return self


def snapshot(config: Config) -> Config:
    """Return a detached config value for one admitted dispatch."""
    return config.model_copy(deep=True)


# A validator raising for a key OTHER than the one pydantic is validating
# carries the true path in the message; `_finding` splits it back out.
_AT = "\x00"


def _at(key: str, reason: str) -> str:
    return f"{_AT}{key}{_AT}{reason}"


def _dotted(loc: tuple) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def _finding(err: dict) -> tuple[str, str]:
    key = _dotted(err["loc"])
    msg = err["msg"]
    if _AT in msg:
        _, sub, reason = msg.split(_AT, 2)
        return (f"{key}.{sub}" if key else sub), reason
    if err["type"] == "missing":
        return key, "required key is missing"
    if err["type"] == "value_error":
        return key, msg.removeprefix("Value error, ")
    if err["type"] == "extra_forbidden":
        return key, "unknown key"
    return key, msg


def _nulls(node, prefix: str, out: list[tuple[str, str]]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            if v is None:
                out.append((key, "explicit null is refused; omit the key to take its default"))
            else:
                _nulls(v, key, out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _nulls(v, f"{prefix}[{i}]", out)


def parse(data, *, source: str) -> Config:
    """Validate an already-parsed document. `source` names the file in errors."""
    if not isinstance(data, dict):
        raise ConfigError(source, [("", "top level must be a mapping of the section 15 keys")])
    if "schema_version" not in data:
        raise ConfigError(source, [("schema_version", "required key is missing")])
    version = data["schema_version"]
    if isinstance(version, bool) or not isinstance(version, int):
        raise ConfigError(source, [("schema_version", f"must be an integer, got {version!r}")])
    if version > SCHEMA_VERSION:
        raise ConfigError(source, [("schema_version",
                                    f"{version} is newer than this engine's {SCHEMA_VERSION}; "
                                    f"upgrade squatch")])
    if version < SCHEMA_VERSION:
        raise ConfigError(source, [("schema_version",
                                    f"{version} is older than this engine's {SCHEMA_VERSION}; "
                                    f"run `squatch migrate-config` to migrate it")])
    findings: list[tuple[str, str]] = []
    _nulls(data, "", findings)
    if findings:
        raise ConfigError(source, findings)
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        raise ConfigError(source, [_finding(err) for err in e.errors()]) from None


def load(path: Path | None = None, *, cwd: Path) -> Config:
    """Read the config: `path` (the `--config` flag) else `config.yaml` under `cwd`."""
    path = Path(path) if path is not None else Path(cwd) / DEFAULT_NAME
    try:
        text = path.read_text()
    except OSError as e:
        raise ConfigError(str(path), [("", f"cannot read: {e.strerror or e}")]) from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError(str(path), [("", f"invalid YAML: {e}")]) from None
    return parse(data, source=str(path))
