## Outcome

premise_failed

## Surprises / judgment calls

Section 20 now supplies the identity-bound flake clarification missing from the prior attempt. Authored flake-detection, flake-release, and phase3-continue-15 from it, excluding the former SHA-held substitute. Both hooks remain dormant by production call path; daemon import reachability is explicitly allowed. Release uses the existing authored Box message resolution.link as fix_stem. Sibling-new flake paths are excluded from release Context but remain its dependency-owned hooks. Existing daemon composition tests remain unchanged preservation evidence. The successor classifies tests/test_journal.py as read-only preservation for both forthcoming seeds.

The new contract suite passes: uv run pytest tests/test_seeded_phase3_14.py -q (8 passed). Max-effort synthetic renders: detection 77,493; release 62,788; continuation 54,158 characters, each below 120,000. Only tests/test_seeded_phase3_14.py was committed; all three authored seed tickets remain uncommitted for engine lift as required.

## Dead ends

Initial ticket lint rejected acceptance bullets without an explicit observable artifact. Added the relevant test path to each affected bullet; all eight new tests then passed.

uv run pytest -q exited 1: 1 failed, 1089 passed. The failure is tests/test_seeded_phase3_06.py::test_every_seed_render_fits_requisition_headroom_with_pinned_context: phase3-continue-07 renders 120,317 characters against 120,000 headroom. Reproduced the identical failure using uv run pytest tests/test_seeded_phase3_06.py::test_every_seed_render_fits_requisition_headroom_with_pinned_context -q in a detached worktree at untouched base 54368ab778cf17841a782344d50778d5db22a79f. Removed that proof worktree through Git.worktree_remove and prune. This older render contract is an adjacent problem; its plan/test repair involves SQUATCH_PLAN.md or tests/test_seeded_phase3_06.py outside the fence, and its old ticket must not be rewritten as part of this admission. Under the explicit on-failure instruction, retained the completed test commit but cannot report implemented while the required full-suite command exits nonzero.

## Second problems filed

- Base 54368ab778cf17841a782344d50778d5db22a79f already fails tests/test_seeded_phase3_06.py::test_every_seed_render_fits_requisition_headroom_with_pinned_context: phase3-continue-07 max-effort render is 120,317 characters, exceeding REQ_RENDER_HEADROOM by 317. Reproduced in a detached untouched-base worktree. Repair the canonical render/Context contract separately without weakening the 120,000-character limit or changing historical authoring-size fixtures to hide the overflow.

## Resolved engine/model

OpenAI Codex; exact serving model identifier not exposed.

## Predicted vs actual

Expected 75m; actual approximately 15m including authoring, both verification commands, and isolated base-failure reproduction.
