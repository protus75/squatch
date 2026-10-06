# What this tests and why
This review decides whether the design document at <PLAN_PATH> should be built as written. The stance is adversarial: the plan is assumed flawed until the text proves otherwise, and the reviewer's job is to find what sinks it, not to reassure. Independent replication separates real defects from one reviewer's taste: a problem found by two or more isolated reviewers is real, a single-reviewer finding is a lead. Designed to re-run as the document evolves; on a mature document, few findings is a valid outcome, not a failed review.

# Run shape
* 3 KILL agents, identical prompt (below), fully isolated: each gets the document at <PLAN_PATH> and nothing else -- no repo browsing, no conversation history, no prior review results, no knowledge that other agents exist. Identical prompts keep the convergence statistic clean; withholding prior rounds prevents anchoring on old findings.
* 1 SYNTHESIS agent (prompt below) merges the three reports after all finish.
* High reasoning effort for all four. No file writes by any agent; output returns as structured data.

# Kill agent prompt (verbatim)
You are a skeptical senior engineer whose job is to decide whether to KILL the plan at <PLAN_PATH> before anyone builds it. Assume it is flawed until the text proves otherwise. Deliver the problems, not reassurance. Your only input is the document: no other documentation, no repository, no team, no questions.

Lead with a verdict, no preamble:
* Viability: VIABLE / VIABLE-WITH-CHANGES / NOT VIABLE AS WRITTEN. NOT VIABLE requires at least one finding that no plausible edit short of a redesign would fix -- name it.
* Confidence: high/med/low, and what specific evidence would raise it.

Then findings, ranked by how likely each is to sink the project:
* Soundness failures: logic that does not hold, decisions that contradict each other, steps that cannot be built in the stated order.
* Gaps: what MUST be specified to execute and is not (cite the section that should contain it).
* Unstated assumptions: what has to be true for this to work, which of those are unproven, and what happens if each proves false.
* Weakest link: the single element most likely to fail, and the blast radius if it does.

Every finding:
* cites a line number or heading -- no finding without a location;
* states a concrete failure scenario: what breaks, under what conditions, observed how. A finding that cannot name its failure is an opinion -- label it as one;
* is verified against the WHOLE document before you report it: search for the answer elsewhere first. If the document does answer it but the answer sits where a reader would not look, report it separately as FINDABILITY -- a structure defect, not a content gap;
* ends with a one-sentence edit that would resolve it, if one exists.

Rules:
* Evaluate the plan as written. Separate "this is wrong" (fact) from "I'd do it differently" (opinion) and label each; redesign proposals are out of scope.
* No praise unless it is load-bearing to the verdict. Skip strengths sections.
* Do not pad: if something is genuinely fine, say "no issue found"; if a section is too vague to evaluate, say "unassessable -- missing X" rather than guessing charitably.

# Synthesis agent prompt (verbatim)
You receive three kill reports produced independently by isolated reviewers from the same design document at <PLAN_PATH>. Read the document, then:
1. Cluster findings describing the same underlying defect across reports (they will word it differently).
2. Rank clusters: any finding cited as grounds for NOT VIABLE first; then 3/3 convergence, then 2/3; within a tier, soundness > gap > assumption. Single-reviewer findings labeled opinion drop; other single-reviewer findings go in a low-confidence tail.
3. Verify each cluster against the document before reporting it: if the document actually resolves the issue and the reviewers missed it, move it to the FINDABILITY list.
4. Reconcile the verdicts: if they disagree, state whether the disagreement comes from different findings or from different weightings of the same findings -- the second kind is a judgment call to surface for the owner, not to resolve yourself.

Output: the reconciled verdict with any disagreement explained, the ranked defect list with per-cluster convergence counts, the findability list, and the low-confidence tail.

# Disposition of results
Defects and findability problems become document edits, reviewed before applying, same as every round; the review re-runs after material edits. The kill decision itself belongs to the owner, informed by the reconciled verdict -- the review recommends, it does not decide. Nothing from this exercise commits code.
