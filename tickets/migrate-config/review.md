---
verdict: snag
reviewed_sha: 9562e9ee2a8691f06296f0d8645c0c1b96bf2c14
produced_by_spec_version: '1.0'
produced_at_sha: 9562e9ee2a8691f06296f0d8645c0c1b96bf2c14
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The migration logic is sound: validation runs first, then the version scalar alone is replaced through the real loader, then an atomic replace runs with an exclusive adjacent backup. However, the tests do not cover the malformed and non-mapping refusal paths that the acceptance criteria require, and a leftover migration temporary file blocks every later run without saying how to clear it.

## Findings
- correctness_review at tests/test_config.py: The second acceptance criterion requires tests/test_config.py to prove that every malformed or invalid candidate is refused without a write. The refusal parametrization covers only a missing version, a string version, -1, 2, an unknown key and an explicit null. It has no case for syntactically invalid YAML (the `invalid YAML` branch), a non-mapping top level such as a list or scalar document, a boolean `schema_version: true` (the explicit `isinstance(version, bool)` guard), a float version such as `0.0`, or a version-1 file that fails the loader (the no-op path must refuse and leave no backup). tests/test_cli.py has the same gaps, so the third criterion ('all no-write boundaries') is also only partly met. (paved road: Extend test_migrate_refuses_invalid_inputs_without_a_write to write raw text for these cases: invalid YAML (e.g. `schema_version: 0\n  bad: [`), a list document, `schema_version: true`, `schema_version: 0.0`, and a version-1 config with an unknown key. For each case, assert that the config bytes are unchanged and that neither config.yaml.bak nor .config.yaml.migrate.tmp exists. Add at least the invalid-YAML and non-mapping cases to the CLI refusal parametrization.)
- correctness_review at squatch/config.py: A crash between `fs.publish(temporary, ...)` and cleanup leaves `.config.yaml.migrate.tmp` behind. Because publish never overwrites an existing path, every later migrate-config run refuses with 'cannot create migration temporary file'. The CLI then shows the generic paved road 'fix the named key in config.yaml', which does not name the real fix. This is a hold with no stated release. (The backup-exists case does say 'move it aside'.) (paved road: Make the FileExistsError message for the temporary file name the file and the release, e.g. f"stale {temporary.name} from an interrupted migration; remove it and rerun". Add a test that pre-creates the temporary file and asserts the refusal, the message, and that no config write or backup occurs.)
