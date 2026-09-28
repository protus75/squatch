---
verdict: snag
reviewed_sha: 5b322ce667ad081e6669158d20fcbe9ca6fabd11
produced_by_spec_version: '1.0'
produced_at_sha: 5b322ce667ad081e6669158d20fcbe9ca6fabd11
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
Both tickets match the registry, edges, tiers, budgets and ownership fences, the Context sizes match the files on disk, and checks are green. But the test does not prove two things acceptance criterion 2 asks for: that the on-demand exception was measured, and that no Context file contains the delimiter.

## Findings
- correctness_review at tests/test_seeded_phase4_02.py:38: Acceptance criterion 2 says the test must prove every existing fence path is either Context or an "explicitly measured on-demand exception", and the Scope in says the headroom exception must be measured. ON_DEMAND is a hardcoded set, and nothing measures it. The provider ticket claims that embedding drain.py, serve.py and __main__.py "would exceed requisition render headroom", but no test checks that. It does happen to be true today: 67,941 Context chars plus 58,236 on-demand chars is about 126K, over the 120,000 limit (160,000 * 0.75). Still, nothing pins it, so an exception that is no longer justified would pass unnoticed. (paved road: Add the authoring-time sizes of squatch/drain.py (26170), squatch/serve.py (11768) and squatch/__main__.py (20298) to a measured table. Render provider-cooldown-failover at max effort with Context plus the ON_DEMAND paths, and assert the result is larger than RENDER_BOUND_CHARS['max'] * REQ_RENDER_HEADROOM. Keep the existing assertion that the render without them fits.)
- correctness_review at tests/test_seeded_phase4_02.py:110: Delimiter-bearing Context exclusion is tested only by checking that Context is disjoint from two hardcoded paths ({squatch/specs.py, specs/implement.md}). The test never reads the Context files to look for the engine delimiter (specs.DATA_MARKER, "<<<squatch:"). The established pattern in tests/test_seeded_phase4_01.py:148-150 does read them. So a Context file containing the delimiter would pass here even though the ticket's Definition of rejected forbids it. The comment at lines 132-133 is also wrong: tests/test_seeded_phase4_01.py does not contain DATA_MARKER. (paved road: Follow the phase4_01 pattern. For each Context path not in any sibling's owns/hooks (here tests/test_seeded_phase4_01.py), read the file content and assert DATA_MARKER is not in it. Keep the explicit squatch/specs.py exclusion, and remove or correct the misleading comment.)
