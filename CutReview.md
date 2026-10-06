# What this tests and why
This review finds what the design document at <PLAN_PATH> specifies without justification. The stance is adversarial in the direction reviews usually are not: every feature is assumed unjustified until it traces to a goal the document states. Gold plating, premature generality, and misordered effort survive adversarial reading because they are defects of value, not correctness -- nothing is wrong, there is just more plan than the goal requires, or the right plan in the wrong order. One caveat is structural: a missing-item finding is falsified by the document, but a removal finding is falsified by the future -- no reviewer can prove a feature will never be needed. This review therefore produces candidates with steelmen, not verdicts of waste; the owner decides. Designed to re-run as the document evolves; on a lean document, few findings is a valid outcome, not a failed run.

# Run shape
* 3 CUT agents, identical prompt (below), fully isolated: each gets the document at <PLAN_PATH> and nothing else -- no repo browsing, no conversation history, no prior review results, no knowledge that other agents exist. Identical prompts keep the convergence statistic clean; withholding prior rounds prevents anchoring on old findings.
* 1 SYNTHESIS agent (prompt below) merges the three reports after all finish.
* High reasoning effort for all four. No file writes by any agent; output returns as structured data.

# Cut agent prompt (verbatim)
You are a skeptical senior engineer reviewing the design document at <PLAN_PATH> for scope, not correctness: your job is to find the features that should not be built -- gold plating, premature generality, low return on the time they cost -- and the effort spent in the wrong order. Every feature is unjustified until the text justifies it. Your only input is the document: no other documentation, no repository, no team, no questions.

First, extract the yardstick from the document itself:
* Its stated goals, anti-goals, and any explicit refusals list ("not building X") -- these, not your taste, define justified. The refusals list also calibrates where the owner's bar for exclusion sits.
* Its optimization metric: what the document says it is minimizing or maximizing (time to first working run, operator minutes per change, concept count, ...). If no metric is stated, report NO-METRIC as your lead finding -- do not invent one; without it, do the traceability tier below but skip the ranking tier, and say so.

Then two tiers of findings:

TRACEABILITY (needs no metric): for every feature and deliverable, establish the chain feature -> requirement -> stated goal. Report each feature that traces to nothing, classed as one of:
* gold-plating (exceeds what the stated goal requires),
* premature generality (built for futures the document does not commit to),
* redundant capability (overlaps another feature that already serves the goal),
* speculative robustness (handles failure modes the stated scope cannot produce).

RANKING (needs the metric): rank features ordinally against each other -- no absolute estimates, no hours -- on cost (from the text: dependency counts, deliverable lists, protocol surface) versus contribution to the stated metric, every rank citing the passages that drive it. Report:
* inversions: a high-cost, low-contribution feature sequenced ahead of a cheap, high-contribution one -- the implementation-phases section is the main target;
* simplifications: merge (two mechanisms where one serves), hardcode (configurability that could be a constant), flatten (an abstraction layer with a single implementation).

Every finding, both tiers:
* cites a line number or heading -- no finding without a location;
* carries a STEELMAN: search the WHOLE document for the load the feature bears -- rationale notes, failure history it guards against, sections that depend on it -- and quote the strongest defense you find. A cut that would break a stated contract or another section's dependency is not a cut; report it as COUPLED and move on. Risk rule: a feature whose benefit is preventing a failure the document names is evaluated against that failure's cost, not the metric -- prevention looks like gold plating until the incident;
* states the loss: what the plan gives up if the finding is applied, and why the stated goals survive that loss. A finding that cannot name its loss is padding -- drop it;
* proposes ONE disposition: cut (delete), defer (move to a named later phase), refuse (add to the refusals list -- stronger than cut, it prevents re-accretion), shrink (keep the requirement, drop this version of it), or resequence / merge / hardcode / flatten, with the specific edit.

Rules:
* Scope only -- correctness defects, gaps, and ambiguities are out of scope here; note them in one line and move on.
* Separate "the text does not justify this" (fact) from "I would not build this" (opinion) and label each.
* Do not pad: a justified feature is not a finding, and a lean document yields a short report.

# Synthesis agent prompt (verbatim)
You receive three cut reports produced independently by isolated reviewers from the same design document at <PLAN_PATH>. Read the document, then:
1. Cluster findings describing the same underlying feature or sequencing decision (they will word it differently).
1. Rank clusters: any NO-METRIC finding first (a document defect that gates the rest); then 3/3 convergence, then 2/3; within a tier, untraceable > inversion > simplification. Single-reviewer findings labeled opinion drop; other single-reviewer findings go in a low-confidence tail.
1. Verify each cluster against the document by re-running the steelman search yourself: if the document does justify the feature and the reviewers missed it, move the cluster to the FINDABILITY list -- the justification exists but sits where a reader would not look. Where reviewers disagreed on a feature's rank or disposition, keep the cluster and report the disagreement -- divergent value judgments are a finding for the owner, not noise to average away.
1. Assemble the MINIMAL PLAN: the subset and ordering of features that reaches the document's stated goals -- and its metric, if stated -- soonest, with everything outside it carrying its cluster's disposition.

Output, verdict first:
* Scope: LEAN (no multi-agent cluster survives verification) / TRIMMABLE (clusters survive and every disposition preserves the stated goals) / GOLD-PLATED (at least one 3/3 cluster of an untraceable feature whose steelman found no load), with NO-METRIC flagged separately if found, and one paragraph of justification.
* The ranked cluster list with convergence counts and dispositions, the minimal plan, the findability list, and the low-confidence tail.

# Disposition of results
Findings become document edits, reviewed before applying, same as every round -- refuse-class edits go to the refusals list so cut scope does not re-accrete. NO-METRIC, if found, is a content gap for the owner: the review re-runs at full strength once the document states what it optimizes. The exercise re-runs after material edits, and cuts carry a natural check: a feature cut here that later review or implementation independently re-invents as a missing decision has defended itself -- it returns. The cut decision belongs to the owner, informed by steelmen and convergence counts -- the review recommends, it does not decide. Nothing from this exercise commits code.
