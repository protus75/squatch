---
id: decision-000004
kind: decision
link: box-000004-43649f30
reopen_after_days: 1
message: box-000004-43649f30
---
No action needed. The message says pyproject.toml has no asyncio_mode setting, but that is no longer true. pyproject.toml line 17 already sets `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`, so async tests without a marker already run. No ticket in the rendered work covers this, so there is nothing valid to tombstone against. Record it as a decision instead.

Evidence: pyproject.toml:16-17 contains `[tool.pytest.ini_options]` followed by `asyncio_mode = "auto"`. The tests/ directory has 491 `async def test_` or `pytest.mark.asyncio` occurrences across 48 files, and they run in the merged suite that every merged phase passed through. The message's origin is bootstrap-ingest, so it came from the pre-Phase-1 suggestions file and is older than the config line.
