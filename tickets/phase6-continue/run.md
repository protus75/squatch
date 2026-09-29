## Outcome
ok

## Surprises / judgment calls
The three row-one seeds were already present, but the numbered proof was
absent from the branch. Preserved both feature seeds and rewrote the carried
continuation contract with complete behavior and explicit partitions.

The review and retry notes proposed conflicting predecessor mappings. The
contract prohibits new and sibling-new Context, so "immediately preceding
merged" is evaluated at authoring time: 02 -> core, 03 -> 01, 04 -> 02,
through 08 -> 06. The sibling-new test cannot be Context merely because it
will exist when the continuation runs. This matches the supplied Phase 5
continue-03 -> seeded-01 precedent. The authored continuation states that
rule explicitly and passes it forward; the proof rejects the former mixed
core/n-1 mapping. Every row-one Context path was verified to exist on main.

The committed proof pins all five acceptance criteria: row-one identity,
edges, budgets, tiers, fences, partitions, and complete behavior; all remaining
payload contracts and partitions; continuation custody and shrinking rows;
KNOWN-DEEP/KNOWN-HARD custody; max-effort headroom and terminal closure.
Actual live renders measured 118436 chars for core-drift-activation, 107848
for migrate-config, and 113157 for phase6-continue-02, against 120000. The
historical proof freezes those real Context and section-20 sizes so later
payload/plan growth cannot retroactively invalidate admission. No section-19
snapshot or render is used.

Only tests/test_seeded_phase6_01.py is committed (af48f70). The continuation
seed and this record remain uncommitted for engine lift.

## Dead ends
An initial formatting pass accidentally emitted empty continuation dependency
lists. The focused edge check rejected them; restored all six exact row
edges before verification and commit.

In-memory mutation checks rejected a dropped escape parent, missing behavior,
Context moved to on-demand, dropped on-demand exception, removed generic
continuation rule, sibling-new predecessor, and altered continuation fence.
No mutated fixture was left in the tree.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving variant unavailable.

## Predicted vs actual
Expected 75 minutes; actual approximately 15 minutes. Focused verification:
7 passed. Full verification: 1555 passed. The final full run on the
committed version also passed: 1555 tests in 92.89 seconds.
