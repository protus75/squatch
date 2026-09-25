## Outcome
premise_failed

## Surprises / judgment calls
Base HEAD and main were both e0741f90a4c00b3b9e262f828f1851b161d53f4d, with a clean worktree and no branch diff. The Phase 3 Seeding partition exists and names the required three core stems; the plan defect is render feasibility, not a missing partition. No previously lifted core seed files exist in this checkout.

The untouched base passed `uv run pytest -q`: 820 passed in 40.52s. `uv run python -m eval.shakeout check tickets/shakeout-ladder/shakeout-report.json` exited 0 with all 19 members green. The auditor artifact validates as Invoice with passed true. Both artifacts were confirmed byte-identical to their main blobs through Git.rev_parse and blob_sha. No exit artifact was written.

## Dead ends
The required `phase3-continue` seed cannot meet section 19's authoring-time render-feasibility contract while clearing the prior review's read-closure findings. Its required existing Context files are squatch/tickets.py (38,775 characters), squatch/config.py (10,110), config.yaml (3,106), squatch/merge.py (19,735), and tests/test_seeded_phase2.py (10,325). Each was verified byte-identical to its main blob; no branch-created file was included.

Committed section 19 is 98,820 characters. Section 19 plus squatch/tickets.py alone is 137,595 characters, already above the 120,000-character authoring ceiling: squatch/requisition.py uses REQ_RENDER_HEADROOM = 0.75 against squatch/specs.py's max-effort bound of 160,000. The production implement spec rendered with all five required Context files, section 19 alone, the continuation workspace block, and an EMPTY ticket yields 186,586 characters at medium effort. The same inputs at max effort raise RenderRefused(over_bound), reporting 186,586 against 160,000. This is a lower bound; writing any actual ticket only increases it. RequisitionReview._measure evaluates full Context bytes at max effort, not its separately truncated review excerpts.

Removing the required reads repeats the prior false-green read-closure defect. Shortening the seed cannot fix a render already over-bound with no ticket text. The owning plan/material contract must be repaired first in SQUATCH_PLAN.md, or its rendering machinery changed in squatch/specs.py / squatch/requisition.py / squatch/stages.py; all are outside this ticket's fence. No shim, seed, test, report, or commit was authored. The two requested new test files therefore remain absent; their focused verification and exact-two-file diff criterion cannot be satisfied in this attempt.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6-based Codex; exact serving model identifier not exposed.

## Predicted vs actual
Expected 90m; actual about 2 minutes. Seeds authored: none. The blocked core batch is daemon-scheduler, seed-successor-proof, and phase3-continue.
