---
id: tombstone-000130
kind: tombstone
link: decision-000128
reopen_after_days: 90
message: box-000130-53618f17
---
This message reports that the earlier intake-test suggestion is now satisfied. decision-000128 already records that outcome. It closed box-000128 because `test_hand_authored_shape_is_refused_at_the_front_door_not_crashed` covers the structural and non-scalar refusals through `Intake.run`. I checked the tree: tests/test_tickets.py:391-402 confirms the staged-debris case in `test_intake_commit_is_the_ticket_plane_lane`. `squatch/staged.py` is pre-staged and asserted to stay in the index as `A `, never committed. The test at :411 also exists. The message asks for no new work, so it duplicates the closure in decision-000128. Reopen if either test is removed or weakened, or if a hand-authored shape crashes `Intake.run` instead of being refused.
