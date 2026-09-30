---
id: tombstone-000013
kind: tombstone
link: decision-000004
reopen_after_days: 1
message: box-000013-2ce36abc
---
This message only confirms that the earlier asyncio_mode note is resolved. It asks for no new work. decision-000004 already records the same fact: pyproject.toml sets `asyncio_mode = "auto"` under `[tool.pytest.ini_options]`, so async tests need no per-test mark. That setting is still at pyproject.toml line 17. The message duplicates a rendered decision, so it is closed against that decision.
