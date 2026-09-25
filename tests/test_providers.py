"""providers.py: registry, routing, key scoping, and both `cli` adapters'
LIVE contracts against a scripted fake subprocess (plan section 6).

The contract under test: the per-surface write grant reaches the argv; the
invocation runs in the passed worktree with the prompt on stdin (never
argv); usage/cost is parsed from the event stream with the flat estimate
as the floor; exactly the serving provider's key reaches the child and no
other; both captured sinks are scrubbed; a placeholder row is refused
before any subprocess; `abort_current` kills the published group. No real
CLI is ever invoked.
"""

import asyncio
import copy
from pathlib import Path

import pytest

from squatch import providers
from squatch.config import ConfigError, Provider, load, parse
from squatch.llm import LLM_SURFACES, WRITING_SURFACES, LLMRequest
from squatch.providers import (
    ADAPTERS, PLACEHOLDER, CliClient, ProviderError, Registry, RoutingError, child_env)
from squatch.redact import Redactor

ROOT = Path(__file__).resolve().parent.parent
CLAUDE_KEY, CODEX_KEY = "FAKE_CLAUDE_KEY", "FAKE_CODEX_KEY"
CLAUDE_SECRET, CODEX_SECRET = "sk-claude-0123456789-VALUE", "sk-codex-9876543210-VALUE"
ENV = {"PATH": "/usr/bin", "HOME": "/home/op", CLAUDE_KEY: CLAUDE_SECRET, CODEX_KEY: CODEX_SECRET,
       "UNRELATED": "kept"}

CONFIG = {
    "schema_version": 1,
    "state_dir": "/state",
    "providers": [
        {"name": "claude", "kind": "cli", "auth": CLAUDE_KEY,
         "models_by_tier": {"low": "c-low", "medium": "c-med", "high": "c-high", "max": "c-max"},
         "limits": {"concurrency": 1}},
        {"name": "codex", "kind": "cli", "auth": CODEX_KEY,
         "models_by_tier": {"low": "x-low", "medium": "x-med", "high": "x-high", "max": "x-max"},
         "limits": {"concurrency": 1, "est_cost_per_call_usd": 1.0}},
    ],
    "routing": [
        {"tier": "medium", "surface": "implement",
         "candidates": [{"provider": "codex"}, {"provider": "claude"}]},
        {"tier": "medium", "surface": "review",
         "candidates": [{"provider": "claude", "model": "c-max"}]},
        {"tier": "medium", "surface": "author", "candidates": [{"provider": "claude"}]},
        {"tier": "high", "surface": "implement", "candidates": [{"provider": "claude"}]},
    ],
    "review": {"surfaces": [{"name": "arch", "trigger": "always", "rules_doc": "docs/arch.md",
                             "severity": "soft"}]},
}


def config(**overrides):
    data = copy.deepcopy(CONFIG)
    data.update(overrides)
    return parse(data, source="test")


def registry(**overrides) -> Registry:
    return Registry(config(**overrides), source="test")


class ScriptedExec:
    """The scripted fake subprocess: records each spawn, answers in order."""

    def __init__(self, *responses, pgid=4242):
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.pgid = pgid

    async def run(self, argv, *, cwd, env, timeout, stdin_path=None, on_spawn=None):
        self.calls.append({"argv": list(argv), "cwd": Path(cwd), "env": dict(env),
                           "timeout": timeout, "stdin_path": stdin_path,
                           "stdin": Path(stdin_path).read_text() if stdin_path else None})
        if on_spawn is not None:
            on_spawn(self.pgid)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class RealFs:
    def write(self, path, data):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(data)

    def replace(self, src, dst):
        Path(src).replace(dst)


def client(tmp_path, exec_, *, reg=None, env=ENV, redact=None):
    reg = reg or registry()
    redact = redact or Redactor.from_config(config(), env)
    return CliClient(reg, process=exec_, fs=RealFs(), env=env, redact=redact,
                     state_dir=tmp_path / "state", cwd=tmp_path / "checkout")


def request(surface="review", *, tier="medium", effort="high", ticket="t-1",
            worktree=None, rendered="do the thing"):
    return LLMRequest(surface=surface, rendered=rendered, tier=tier, effort=effort,
                      ticket=ticket, worktree=worktree)


def claude_stream(text="done", *, usd=0.42, in_tokens=100, out_tokens=20, subtype="success",
                  is_error=False, extra_lines=()):
    result = {"type": "result", "subtype": subtype, "is_error": is_error, "result": text,
              "total_cost_usd": usd, "usage": {"input_tokens": in_tokens,
                                               "output_tokens": out_tokens}}
    lines = ['{"type":"system","subtype":"init","model":"c-max"}',
             '{"type":"assistant","message":{"content":[{"type":"text","text":"working"}]}}',
             *extra_lines, providers.json.dumps(result)]
    return "\n".join(lines) + "\n"


def codex_stream(*texts, in_tokens=300, out_tokens=40, failed=None, error=None, completed=True):
    lines = ['{"type":"thread.started","thread_id":"th_1"}', '{"type":"turn.started"}',
             '{"type":"item.completed","item":{"id":"i0","type":"reasoning","text":"hmm"}}']
    for i, t in enumerate(texts):
        lines.append(providers.json.dumps(
            {"type": "item.completed", "item": {"id": f"i{i + 1}", "type": "agent_message",
                                                "text": t}}))
    if error is not None:
        lines.append(providers.json.dumps({"type": "error", "message": error}))
    if failed is not None:
        lines.append(providers.json.dumps({"type": "turn.failed", "error": {"message": failed}}))
    if completed:
        lines.append(providers.json.dumps({"type": "turn.completed", "usage": {
            "input_tokens": in_tokens, "cached_input_tokens": 0, "output_tokens": out_tokens}}))
    return "\n".join(lines) + "\n"


# --- registry validation ----------------------------------------------------


def test_registry_accepts_the_valid_config_and_names_the_shipped_adapters():
    reg = registry()
    assert set(ADAPTERS) == {"claude", "codex"}
    assert reg.auth_names == {CLAUDE_KEY, CODEX_KEY}
    assert reg.surfaces == LLM_SURFACES | {"arch"}


def test_cli_provider_name_must_be_a_shipped_adapter():
    data = copy.deepcopy(CONFIG)
    data["providers"][1]["name"] = "gemini"
    data["routing"] = [r for r in data["routing"] if r["surface"] != "implement"]
    with pytest.raises(ConfigError) as info:
        Registry(parse(data, source="test"), source="test")
    assert info.value.key == "providers[1].name"
    assert "gemini" in str(info.value) and "claude" in str(info.value)


def test_no_cost_stream_provider_must_declare_the_flat_estimate():
    data = copy.deepcopy(CONFIG)
    del data["providers"][1]["limits"]["est_cost_per_call_usd"]
    with pytest.raises(ConfigError) as info:
        Registry(parse(data, source="test"), source="test")
    assert info.value.key == "providers[1].limits.est_cost_per_call_usd"


def test_cost_reporting_provider_needs_no_flat_estimate():
    assert registry().provider("claude").limits.est_cost_per_call_usd is None


def test_routing_surface_must_be_an_llm_surface_or_a_host_review_surface():
    data = copy.deepcopy(CONFIG)
    data["routing"].append({"tier": "low", "surface": "check",
                            "candidates": [{"provider": "claude"}]})
    with pytest.raises(ConfigError) as info:
        Registry(parse(data, source="test"), source="test")
    assert info.value.key == "routing[4].surface"
    data["routing"][-1]["surface"] = "arch"
    Registry(parse(data, source="test"), source="test")


def test_routing_row_needs_at_least_one_candidate():
    data = copy.deepcopy(CONFIG)
    data["routing"][2]["candidates"] = []
    with pytest.raises(ConfigError) as info:
        Registry(parse(data, source="test"), source="test")
    assert info.value.key == "routing[2].candidates"


def _with_api_provider(cfg, name):
    # The loader refuses `kind: api` outright until its client ships, so the
    # implement-requires-cli rule is exercised on a constructed provider.
    api = Provider.model_construct(**{**cfg.providers[0].model_dump(), "name": name, "kind": "api"})
    return cfg.model_copy(update={"providers": [*cfg.providers, api]})


def test_implement_routed_to_a_non_cli_provider_is_refused():
    cfg = _with_api_provider(config(), "hosted")
    cfg.routing[0].candidates[0].provider = "hosted"
    with pytest.raises(ConfigError) as info:
        Registry(cfg, source="test")
    assert info.value.key == "routing[0].candidates[0].provider"
    assert "implement" in str(info.value) and "cli" in str(info.value)


def test_implement_inheriting_a_non_cli_review_row_is_refused_too():
    cfg = _with_api_provider(config(), "hosted")
    cfg.routing[1].candidates[0].provider = "hosted"  # medium review
    cfg.routing.pop(0)  # medium implement now inherits it
    with pytest.raises(ConfigError) as info:
        Registry(cfg, source="test")
    assert "implement" in str(info.value)
    assert info.value.key == "routing[0].candidates[0].provider"


def test_review_on_a_non_cli_provider_is_fine_when_implement_has_its_own_row():
    cfg = _with_api_provider(config(), "hosted")
    cfg.routing[1].candidates[0].provider = "hosted"
    Registry(cfg, source="test")


# --- routing resolution -----------------------------------------------------


def test_resolve_takes_the_first_candidate_only():
    r = registry().resolve("medium", "implement")
    assert (r.provider.name, r.model) == ("codex", "x-med")


def test_candidate_without_a_model_inherits_models_by_tier():
    assert registry().resolve("medium", "author").model == "c-med"
    assert registry().resolve("high", "implement").model == "c-high"


def test_pinned_model_overrides_models_by_tier():
    assert registry().resolve("medium", "review").model == "c-max"


@pytest.mark.parametrize("surface", ["diagnose", "rework", "arch", "requisition_review"])
def test_surface_without_a_row_inherits_the_review_row(surface):
    r = registry().resolve("medium", surface)
    assert (r.provider.name, r.model) == ("claude", "c-max")


def test_routing_hole_is_a_routing_error_naming_the_row():
    with pytest.raises(RoutingError, match="`max`.*`author`"):
        registry().resolve("max", "author")


# --- key scoping --------------------------------------------------------------


def test_child_env_inherits_everything_minus_every_configured_key():
    env = child_env(ENV, registry().auth_names)
    assert env == {"PATH": "/usr/bin", "HOME": "/home/op", "UNRELATED": "kept"}


async def test_exactly_the_serving_providers_key_reaches_its_call(tmp_path):
    ex = ScriptedExec((0, codex_stream("ok"), ""), (0, claude_stream("ok"), ""))
    c = client(tmp_path, ex)
    await c.call(request("implement", worktree=tmp_path / "wt"))
    await c.call(request("review"))
    codex_env, claude_env = ex.calls[0]["env"], ex.calls[1]["env"]
    assert codex_env[CODEX_KEY] == CODEX_SECRET and CLAUDE_KEY not in codex_env
    assert claude_env[CLAUDE_KEY] == CLAUDE_SECRET and CODEX_KEY not in claude_env
    for env in (codex_env, claude_env):
        assert env["PATH"] == "/usr/bin" and env["HOME"] == "/home/op" and env["UNRELATED"] == "kept"


async def test_ambient_login_provider_gets_no_key_and_needs_none_set(tmp_path):
    data = copy.deepcopy(CONFIG)
    del data["providers"][0]["auth"]
    reg = Registry(parse(data, source="test"), source="test")
    ex = ScriptedExec((0, claude_stream("ok"), ""))
    env = {k: v for k, v in ENV.items() if k != CLAUDE_KEY}
    await client(tmp_path, ex, reg=reg, env=env).call(request("review"))
    child = ex.calls[0]["env"]
    # The other provider's key is stripped; the ambient login's HOME survives.
    assert child == {"PATH": "/usr/bin", "HOME": "/home/op", "UNRELATED": "kept"}


async def test_declared_but_unset_key_is_refused_before_any_subprocess(tmp_path):
    ex = ScriptedExec()
    env = {k: v for k, v in ENV.items() if k != CLAUDE_KEY}
    with pytest.raises(RoutingError, match=CLAUDE_KEY):
        await client(tmp_path, ex, env=env).call(request("review"))
    assert ex.calls == []


# --- placeholder refusal ------------------------------------------------------


@pytest.mark.parametrize("where", ["pinned_model", "tier_model"])
async def test_placeholder_on_the_resolved_row_is_refused_pre_call(tmp_path, where):
    # `auth` cannot carry the placeholder (the loader's env-var-name shape
    # check refuses it); an ambient-login provider simply omits `auth`.
    data = copy.deepcopy(CONFIG)
    if where == "pinned_model":
        data["routing"][1]["candidates"][0]["model"] = PLACEHOLDER
    else:
        del data["routing"][1]["candidates"][0]["model"]
        data["providers"][0]["models_by_tier"]["medium"] = PLACEHOLDER
    reg = Registry(parse(data, source="test"), source="test")
    ex = ScriptedExec()
    with pytest.raises(RoutingError, match=PLACEHOLDER) as info:
        await client(tmp_path, ex, reg=reg).call(request("review"))
    assert "section 0" in str(info.value)
    assert ex.calls == []


async def test_placeholder_on_an_unresolved_row_does_not_block_other_routes(tmp_path):
    data = copy.deepcopy(CONFIG)
    data["providers"][0]["models_by_tier"]["max"] = PLACEHOLDER
    reg = Registry(parse(data, source="test"), source="test")
    ex = ScriptedExec((0, claude_stream("ok"), ""))
    result = await client(tmp_path, ex, reg=reg).call(request("author"))
    assert result.model == "c-med"


# --- the claude adapter's live contract ---------------------------------------


async def test_claude_implement_gets_the_write_grant_and_runs_in_the_worktree(tmp_path):
    ex = ScriptedExec((0, claude_stream("wrote it"), ""))
    wt = tmp_path / "wt"
    result = await client(tmp_path, ex).call(
        request("implement", tier="high", worktree=wt, rendered="edit foo.py"))
    [call] = ex.calls
    argv = call["argv"]
    assert argv[:7] == ["claude", "-p", "--output-format", "stream-json", "--verbose",
                        "--model", "c-high"]
    assert argv[7:] == ["--permission-mode", "bypassPermissions"]
    assert "--allowedTools" not in argv
    assert call["cwd"] == wt
    assert (result.text, result.provider, result.model) == ("wrote it", "claude", "c-high")


@pytest.mark.parametrize("surface", sorted(LLM_SURFACES - WRITING_SURFACES))
async def test_claude_every_other_surface_gets_the_read_tool_allowlist(tmp_path, surface):
    ex = ScriptedExec((0, claude_stream("read it"), ""))
    c = client(tmp_path, ex)
    await c.call(request(surface, ticket=None if surface in ("triage", "retro") else "t-1"))
    [call] = ex.calls
    argv = call["argv"]
    assert argv[argv.index("--allowedTools"):] == ["--allowedTools", "Read", "Grep", "Glob", "LS"]
    assert "bypassPermissions" not in argv and "--permission-mode" not in argv
    # No worktree: read-only surfaces run at the client's checkout root.
    assert call["cwd"] == tmp_path / "checkout"


async def test_prompt_reaches_the_cli_on_stdin_and_never_in_argv(tmp_path):
    ex = ScriptedExec((0, claude_stream(), ""))
    prompt = "a prompt long enough to matter " * 50
    await client(tmp_path, ex).call(request("review", rendered=prompt))
    [call] = ex.calls
    assert call["stdin"] == prompt
    assert call["stdin_path"].is_relative_to(tmp_path / "state" / "spools" / "t-1")
    assert not any(prompt in a or "long enough" in a for a in call["argv"])
    assert call["timeout"] == providers.CALL_TIMEOUT_SECONDS


async def test_claude_text_usage_and_cost_come_from_the_result_event(tmp_path):
    ex = ScriptedExec((0, claude_stream("the answer", usd=0.37, in_tokens=1234, out_tokens=56), ""))
    result = await client(tmp_path, ex).call(request("review"))
    assert result.text == "the answer"
    assert (result.input_tokens, result.output_tokens) == (1234, 56)
    assert result.usd == 0.37


async def test_claude_last_result_event_wins_and_chatter_is_ignored(tmp_path):
    stream = "warning: something\n" + claude_stream("first") + claude_stream("second", usd=0.1)
    ex = ScriptedExec((0, stream, ""))
    result = await client(tmp_path, ex).call(request("review"))
    assert (result.text, result.usd) == ("second", 0.1)


async def test_claude_result_without_usage_still_charges_the_reported_cost(tmp_path):
    line = '{"type":"result","subtype":"success","is_error":false,"result":"x","total_cost_usd":0.2}'
    ex = ScriptedExec((0, line + "\n", ""))
    result = await client(tmp_path, ex).call(request("review"))
    assert (result.input_tokens, result.output_tokens, result.usd) == (None, None, 0.2)


async def test_claude_result_without_cost_and_no_estimate_is_a_provider_error(tmp_path):
    line = '{"type":"result","subtype":"success","is_error":false,"result":"x"}'
    ex = ScriptedExec((0, line + "\n", ""))
    with pytest.raises(ProviderError, match="est_cost_per_call_usd"):
        await client(tmp_path, ex).call(request("review"))


async def test_claude_error_result_is_a_provider_error(tmp_path):
    ex = ScriptedExec((0, claude_stream("hit the turn limit", subtype="error_max_turns",
                                        is_error=True), ""))
    with pytest.raises(ProviderError, match="error_max_turns"):
        await client(tmp_path, ex).call(request("review"))


async def test_claude_stream_without_a_result_event_is_a_provider_error(tmp_path):
    ex = ScriptedExec((0, '{"type":"system","subtype":"init"}\n', ""))
    with pytest.raises(ProviderError, match="result"):
        await client(tmp_path, ex).call(request("review"))


async def test_non_zero_exit_is_a_provider_error_carrying_the_stderr_tail(tmp_path):
    ex = ScriptedExec((1, "", "x" * 5000 + "\nNot logged in\n"))
    with pytest.raises(ProviderError) as info:
        await client(tmp_path, ex).call(request("review"))
    assert info.value.rc == 1 and info.value.provider == "claude"
    assert "Not logged in" in str(info.value) and "x" * 5000 not in str(info.value)


# --- the codex adapter's live contract ----------------------------------------


async def test_codex_implement_gets_the_bypass_grant_and_runs_in_the_worktree(tmp_path):
    ex = ScriptedExec((0, codex_stream("patched"), ""))
    wt = tmp_path / "wt"
    result = await client(tmp_path, ex).call(request("implement", effort="low", worktree=wt))
    [call] = ex.calls
    assert call["argv"] == ["codex", "exec", "--json", "-m", "x-med", "-c",
                            "model_reasoning_effort=low",
                            "--dangerously-bypass-approvals-and-sandbox", "-"]
    assert call["cwd"] == wt
    assert call["stdin"] == "do the thing"
    assert (result.text, result.provider, result.model) == ("patched", "codex", "x-med")


async def test_codex_read_only_surfaces_get_the_read_only_sandbox_and_never_approve(tmp_path):
    data = copy.deepcopy(CONFIG)
    data["routing"][1]["candidates"] = [{"provider": "codex"}]
    reg = Registry(parse(data, source="test"), source="test")
    ex = ScriptedExec((0, codex_stream("looks fine"), ""))
    await client(tmp_path, ex, reg=reg).call(request("review", effort="max"))
    [call] = ex.calls
    assert call["argv"] == ["codex", "exec", "--json", "-m", "x-med", "-c",
                            "model_reasoning_effort=max", "--sandbox", "read-only",
                            "-c", "approval_policy=never", "-"]
    assert "--dangerously-bypass-approvals-and-sandbox" not in call["argv"]
    assert call["cwd"] == tmp_path / "checkout"


async def test_codex_text_is_the_last_agent_message_and_usage_from_turn_completed(tmp_path):
    ex = ScriptedExec((0, codex_stream("draft", "final", in_tokens=900, out_tokens=70), ""))
    result = await client(tmp_path, ex).call(request("implement", worktree=tmp_path / "wt"))
    assert result.text == "final"
    assert (result.input_tokens, result.output_tokens) == (900, 70)


async def test_codex_reports_no_cost_so_the_declared_flat_estimate_charges(tmp_path):
    ex = ScriptedExec((0, codex_stream("ok"), ""))
    result = await client(tmp_path, ex).call(request("implement", worktree=tmp_path / "wt"))
    assert result.usd == 1.0


async def test_codex_turn_failed_with_exit_zero_is_a_provider_error(tmp_path):
    ex = ScriptedExec((0, codex_stream("partial", failed="context window exceeded",
                                       completed=False), ""))
    with pytest.raises(ProviderError, match="turn.failed: context window exceeded"):
        await client(tmp_path, ex).call(request("implement", worktree=tmp_path / "wt"))


async def test_codex_error_event_with_exit_zero_is_a_provider_error(tmp_path):
    ex = ScriptedExec((0, codex_stream(error="rate limited", completed=False), ""))
    with pytest.raises(ProviderError, match="error: rate limited"):
        await client(tmp_path, ex).call(request("implement", worktree=tmp_path / "wt"))


async def test_codex_stream_without_an_agent_message_is_a_provider_error(tmp_path):
    ex = ScriptedExec((0, codex_stream(), ""))
    with pytest.raises(ProviderError, match="agent_message"):
        await client(tmp_path, ex).call(request("implement", worktree=tmp_path / "wt"))


# --- the shared base ----------------------------------------------------------


async def test_writing_surface_without_a_worktree_is_refused(tmp_path):
    ex = ScriptedExec()
    with pytest.raises(ValueError, match="worktree"):
        await client(tmp_path, ex).call(request("implement", worktree=None))
    assert ex.calls == []


async def test_both_sinks_are_scrubbed_before_result_or_error(tmp_path):
    ex = ScriptedExec((0, claude_stream(f"key {CLAUDE_SECRET} and {CODEX_SECRET}"), ""),
                      (2, "", f"auth failed for {CLAUDE_SECRET}"))
    c = client(tmp_path, ex)
    result = await c.call(request("review"))
    assert result.text == f"key [REDACTED:{CLAUDE_KEY}] and [REDACTED:{CODEX_KEY}]"
    with pytest.raises(ProviderError) as info:
        await c.call(request("review"))
    assert CLAUDE_SECRET not in str(info.value)
    assert f"[REDACTED:{CLAUDE_KEY}]" in info.value.stderr


async def test_prompt_file_on_disk_is_scrubbed(tmp_path):
    ex = ScriptedExec((0, claude_stream(), ""))
    await client(tmp_path, ex).call(request("review", rendered=f"secret {CLAUDE_SECRET}"))
    assert ex.calls[0]["stdin"] == f"secret [REDACTED:{CLAUDE_KEY}]"


async def test_each_call_gets_its_own_prompt_file(tmp_path):
    ex = ScriptedExec((0, claude_stream(), ""), (0, claude_stream(), ""))
    c = client(tmp_path, ex)
    await c.call(request("review", rendered="one"))
    await c.call(request("review", rendered="two"))
    paths = [call["stdin_path"] for call in ex.calls]
    assert paths[0] != paths[1]
    assert [p.read_text() for p in paths] == ["one", "two"]


async def test_abort_current_kills_the_published_group_and_only_while_active(tmp_path, monkeypatch):
    killed = []
    monkeypatch.setattr(providers, "kill_group", killed.append)
    release = asyncio.Event()

    class Hanging(ScriptedExec):
        async def run(self, argv, *, on_spawn=None, **kw):
            on_spawn(777)
            await release.wait()
            return (-9, "", "")

    c = client(tmp_path, Hanging())
    c.abort_current()
    assert killed == []  # nothing active yet
    task = asyncio.ensure_future(c.call(request("review")))
    await asyncio.sleep(0.01)
    c.abort_current()
    assert killed == [777]
    release.set()
    with pytest.raises(ProviderError):
        await task
    c.abort_current()
    assert killed == [777]  # cleared at call return


async def test_seam_error_propagates_and_clears_the_binding(tmp_path):
    from squatch.seams import ExecutableNotFound

    ex = ScriptedExec(ExecutableNotFound("claude"))
    c = client(tmp_path, ex)
    with pytest.raises(ExecutableNotFound):
        await c.call(request("review"))
    assert c._pgid is None


# --- the authored instance config ---------------------------------------------


def test_checkout_config_yaml_loads_and_builds_a_registry():
    cfg = load(cwd=ROOT)
    assert cfg.state_dir == Path(".squatch/state")
    reg = Registry(cfg, source="config.yaml")
    assert {p.name for p in cfg.providers} == {"claude", "codex"}


@pytest.mark.parametrize("tier", ["low", "medium", "high", "max"])
def test_checkout_config_routes_review_author_implement_at_every_tier(tier):
    reg = Registry(load(cwd=ROOT), source="config.yaml")
    review, author, implement = (reg.resolve(tier, s) for s in ("review", "author", "implement"))
    assert implement.provider.name == "codex" and implement.provider.kind == "cli"
    assert author.provider.name == "claude"
    assert review.provider.name == "claude"
    # Author and implement inherit models_by_tier; review pins the strongest.
    assert author.model == getattr(reg.provider("claude").models_by_tier, tier)
    assert implement.model == getattr(reg.provider("codex").models_by_tier, tier)
    assert review.model == reg.provider("claude").models_by_tier.max


def test_checkout_config_pins_review_explicitly_and_leaves_the_rest_inheriting():
    cfg = load(cwd=ROOT)
    for route in cfg.routing:
        [candidate] = route.candidates
        if route.surface == "review":
            assert candidate.model is not None
        else:
            assert candidate.model is None
