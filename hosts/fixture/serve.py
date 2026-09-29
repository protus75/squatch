"""Zero-spend launcher support for the fixture host."""

import os
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parent
PROVIDER_KEYS = frozenset({"ANTHROPIC_API_KEY", "CODEX_API_KEY", "OPENAI_API_KEY"})


def launch_environment(source: Mapping[str, str]) -> dict[str, str]:
    env = {key: value for key, value in source.items() if key not in PROVIDER_KEYS}
    current = env.get("PATH", "")
    env["PATH"] = str(ROOT / "bin") + (os.pathsep + current if current else "")
    return env
