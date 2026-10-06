# What this tests and why
A design document that claims to be self-contained -- an implementer needs no other document -- can pass any number of adversarial READINGS and still fail the first WRITING: reviewers evaluate arguments, implementers consume decisions, and only the second exposes what the text does not determine. This exercise tests the claim under writing. Fresh agents with no project context role-play the implementer for <PHASE_SCOPE> and must produce skeletons from the document at <PLAN_PATH> alone. Every decision the document forces them to invent is a measured self-containment gap. Convergence is the signal: a decision independently invented by two or more isolated agents is a real spec gap, not one agent's taste. Designed to re-run as the document evolves -- rescope <PHASE_SCOPE> to the earliest unbuilt phases each time -- and a near-empty ledger is a valid outcome, not a failed run.

# Run shape
* 3 DRY-RUN agents, identical prompt (below), fully isolated: each gets the document at <PLAN_PATH> and nothing else -- no repo browsing, no conversation history, no prior review results, no knowledge that other agents exist. Identical prompts keep the convergence statistic clean; withholding prior rounds prevents anchoring on old gaps.
* 1 SYNTHESIS agent (prompt below) compares the three ledgers after all finish.
* High reasoning effort for all four. No file writes by any agent; output returns as structured data.

# Dry-run agent prompt (verbatim)
You are the implementing engineer for the system specified by the design document at <PLAN_PATH>. Your ONLY input is that document. Read all of it. You cannot ask questions; there is no other documentation, no repository, and no team.

Produce three things for <PHASE_SCOPE> as defined in the document's implementation-phases section:

1. REPO SKELETON: the module/package layout you would create, one line of responsibility per module. Cover every deliverable the document names for <PHASE_SCOPE>.

1. INTERFACE STUBS: signatures in the document's implementation language (classes, functions, data shapes, event shapes, config-schema sketch) for the document's core contracts and the <PHASE_SCOPE> modules, faithful to the document. Stubs are evidence of your reading, not production code -- no bodies beyond a placeholder.

1. INVENTED-DECISIONS LEDGER -- the actual product of this exercise. Every place you had to make a choice the document did not determine for you, one entry each:
  * decision: what you had to decide, in one sentence.
  * section: the section (by number/heading) that should have determined it.
  * chose: what you picked, in one sentence, and why.
  * class: one of
    * missing (the document is silent),
    * ambiguous (two readings are defensible),
    * contradictory (two passages disagree),
    * deliberate-freedom (the document plausibly leaves this to the implementer on purpose -- naming these calibrates the other three).

Also produce a BLOCKED list: anything you could not even invent your way past -- where any choice you made would risk violating a stated contract.

Rules: implement AS SPECIFIED -- do not evaluate, improve, or redesign the system; if you disagree with a decision the document makes, follow the document. Filling a gap from your own experience with similar systems is still an invented decision -- ledger it; background knowledge masking a gap is exactly the failure this exercise measures. Do not pad the ledger: a genuinely determined decision does not belong in it, and an empty BLOCKED list is a valid answer. Be exhaustive on the ledger before polishing the stubs; if effort runs short, cut stub detail, never ledger entries.

# Synthesis agent prompt (verbatim)
You receive three invented-decisions ledgers plus blocked lists, produced independently by three isolated implementers from the same design document at <PLAN_PATH>. Read the document, then:

1. Cluster ledger entries describing the same underlying decision across ledgers (they will word it differently).
1. Rank clusters: (a) any BLOCKED entry first; (b) then decisions invented by 3/3 agents, then 2/3; (c) within a tier, contradictory > ambiguous > missing. Entries by a single agent classed deliberate-freedom are noise -- drop them; single-agent entries otherwise go in a low-confidence tail.
1. For each surviving cluster: name the decision, the document section that should own it, what the three implementers each chose (divergence matters -- three different inventions is worse than three matching ones), and a one-sentence proposed document edit that would have determined the decision.
1. Verify each cluster against the document before reporting it: if the document actually does determine the decision and the implementers missed it, report it separately as a FINDABILITY problem (the answer exists but implementers did not find it -- a structure defect, not a content gap).

Output, verdict first:
* Self-containment: SELF-CONTAINED (no verified BLOCKED entries, no multi-agent clusters beyond deliberate-freedom) / GAPS-FIXABLE (multi-agent clusters exist and every one has a determinable proposed edit) / NOT SELF-CONTAINED (any verified BLOCKED entry, or any contradictory cluster confirmed against the text) -- with one paragraph of justification.
* The ranked gap list with per-cluster convergence counts, the findability list, and the low-confidence tail.

# Disposition of results
Gaps and findability problems become document edits, reviewed before applying, same as every round; the exercise re-runs after material edits, rescoped to the phases now earliest-unbuilt. Skeletons and stubs are discarded -- they are measurement instruments, not the start of the implementation. Nothing from this exercise commits code.
