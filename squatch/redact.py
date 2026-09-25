"""Redaction seam (SQUATCH_PLAN.md section 6).

One filter, built once from the config, wired at CONSTRUCTION into every
production writer of a captured stream. It replaces each configured secret
VALUE -- the env vars named by the provider registry's `auth` fields,
resolved against the process environment -- with `[REDACTED:<NAME>]`,
matched as a literal substring.

Writer-site checklist (every writer of a captured stream appears here; a
change adding a stream or a writer extends this list in the same change):
- engine-log writer: `squatch.enginelog.EngineLog`
- attempt-spool writer: `squatch.driver.Spool`
- LLM result, scrubbed once at receipt: `squatch.driver.Driver`
- journal writer: lands with the Phase 1 LLM effect, the first journal body
  that carries a captured stream
- harvest serialization: lands with the Phase 2 spine
"""

from collections.abc import Mapping

from squatch.config import Config


class Redactor:
    def __init__(self, secrets: Mapping[str, str]):
        # Longest value first, so a secret that contains another is replaced
        # whole rather than leaving its tail behind. Empty values are dropped:
        # an empty substring matches between every character.
        self._pairs = sorted(((value, name) for name, value in secrets.items() if value),
                             key=lambda p: -len(p[0]))

    @classmethod
    def from_config(cls, config: Config, env: Mapping[str, str]) -> "Redactor":
        names = {p.auth for p in config.providers if p.auth}
        return cls({name: env[name] for name in names if name in env})

    def __call__(self, text: str) -> str:
        for value, name in self._pairs:
            text = text.replace(value, f"[REDACTED:{name}]")
        return text
