---
verdict: snag
reviewed_sha: 05df6dec4453553f87990d3d82bb6077a40d9030
produced_by_spec_version: '1.0'
produced_at_sha: 05df6dec4453553f87990d3d82bb6077a40d9030
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The production code is sound. baseline.py is a closed, fail-closed reader, policy.go_binds is removed, and Author is the only caller, passing config, journal events, <repo>/specs and resolution.binds. The snag is that three acceptance criteria require tests to prove these properties, and the tests do not.

## Findings
- correctness_review at tests/test_author.py:325: Acceptance requires test_author.py and test_retro_box.py to prove Author is the sole caller and supplies config, journal events, the specs directory and resolution.binds. Both tests replace squatch.author.resolve_baseline with a lambda that ignores its arguments and always returns GO. Nothing checks that config is the current config, that events come from Journal.read(), that specs_dir == <repo>/specs, or that resolution.binds (not a constant) reaches starting_state. A regression that passed a global specs path or dropped the events would still pass. (paved road: Make the monkeypatched resolve_baseline record its arguments and assert on them: config is the Author's config, the events match the journal's events, and specs_dir == checkout / 'specs'. Add a case where the fake returns BaselineResolution('REVOKED', False) and assert the ticket is drafted. For sole-caller, assert that squatch.policy has no go_binds and that no other squatch module imports resolve_baseline, or cover this in test_retro_box.py.)
- correctness_review at tests/test_policy.py:1: Acceptance requires test_policy.py to prove policy.go_binds is removed. The diff only removes the import and the go_binds tests; no test asserts the removal, so a reintroduced second reader in policy.py would pass. (paved road: Add a test such as `import squatch.policy as policy; assert not hasattr(policy, 'go_binds')`. It may also assert that `binds` is a required keyword of starting_state.)
- correctness_review at tests/test_baseline.py:64: Acceptance requires test_baseline.py to prove 'all supervised fallbacks'. Four ticket-named fallbacks have no test. (1) An unresolved placeholder in the provider auth or model should give REVOKED. (2) A torn tail after a non-GO baseline, or before any baseline, should give NO_GO or ABSENT; only the GO-then-torn case is tested. (3) A malformed spec_major (non-dict, or a spec version not in X.Y form) is not tested. (4) A malformed identity row type (for example a non-dict identity) is not tested. The code appears to handle all four, but the criterion is unmet. (paved road: Add parametrized cases: a config whose models_by_tier or auth resolves to PLACEHOLDER gives REVOKED; a generator that yields a NO-GO signal then raises gives NO_GO; a generator that raises before any baseline gives ABSENT; a GO with spec_major='1' or identity=[] gives REVOKED; a specs_dir whose review.md has a malformed version gives REVOKED.)
