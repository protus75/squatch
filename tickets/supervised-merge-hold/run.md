## Outcome
premise_failed

## Surprises / judgment calls
The branch started clean at 64bfbeb6b06db614df3e58a5e4a3e532ce740c1b without the prior implementation. Inspected and recovered only fenced files from reviewed commit fd271211d0fabd0a2554194fcb7f115b3bca9801, then reproduced the release through the real offline confirm CLI. The plan already specifies rebase/regate on moved main; this is a ticket scope-closure defect, not a plan behavior defect. Restored all implementation/test edits and committed nothing, following the explicit authoring-defect rule.

## Dead ends
An unconditional candidate-base regate identity fixes stale replay but invalidates the exact regate/<stem>/<run> readers in eval/daemon_soak.py:_passed_invoice and tests/test_daemon_soak_runner.py:passed_invoice. Both paths are outside the scope fence. The full Verification command failed with StopIteration in test_every_closed_field_comes_from_its_member_local_production_evidence; the production reader also returns False for the new identity. Those two readers must migrate with the effect identity. Preserving a parallel legacy key or selecting keys by supervision mode would introduce the prohibited compatibility/dual path.
The full suite initially reported 8 failures and 1679 passes: five additional failures came from unchanged mergequeue test doubles rejecting the added effect_identity keyword; deriving the identity directly from PackingSlip.base fixed those without changing their files. Two remaining failures were committed-artifact checks on uncommitted changes, not pre-existing failures.
The first exact focused Verification command passed 183 tests. Expanded focused coverage passed 6 tests (offline and live operator/machine confirm, stale identities and resume refusal, moved-main gate failure and rework conflict, escalation routing, custody, dispatch exclusion, bootstrap exemption). The subsequent mergequeue/merge/focused run passed 91 tests. These results were on the now-restored candidate, not the untouched base. The full Verification command never passed, so no implementation is claimed.

## Second problems filed

## Resolved engine/model
OpenAI / GPT-6 (Codex); exact serving model identifier unavailable.

## Predicted vs actual
Expected 75m; actual approximately 9m, ending at the verified scope-fence blocker.
