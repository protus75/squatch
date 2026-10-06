# What this tests and why
A design document accretes prose: rationale and rhetoric earn their keep during review rounds, but the document's standing audience is the implementer, and prose taxes them -- every sentence of motivation is a sentence they must read to confirm it contains no requirement. This exercise compresses the document at <PLAN_PATH> to specification form: every technical fact survives at full strength, everything addressed to a reviewer rather than an implementer goes. It is designed to be re-run whenever prose has accreted; on an already-compressed document the correct outcome is little or no change, and that is a valid result, not a failed run. Compression is only trustworthy if loss is measured, so an independent agent audits the result against the original. The compressor changes how things are said, never what is specified.

# Run shape
* 1 COMPRESSOR agent (prompt below): gets the document at <PLAN_PATH>, writes the draft spec to a scratch path (`<SPEC_PATH>`), returns its ledger and metrics as structured data. No other file writes.
* 1 FIDELITY agent (prompt below): runs after the compressor finishes; gets the original, the draft, and the compressor's judgment-call ledger. Independent -- it did not see the compressor's reasoning, only its output.
* High reasoning effort for both. The fidelity agent may use read-only tools (diff, grep) to check verbatim blocks mechanically.

# Compressor prompt (verbatim)
You are rewriting the design document at <PLAN_PATH> into a specification, written to <SPEC_PATH>. The document's content is settled; your job is form only: remove rhetoric and narrative prose, retain every technical fact at full strength. You change how things are said, never what is specified. The document may have been compressed before -- do not force changes where none are needed; passages already in spec form pass through untouched.

Classify every sentence into one of three classes:

1. NORMATIVE -- contracts, invariants, interfaces, event shapes, schemas, names, defaults, limits, thresholds, orderings, deliverables, commands, refusals ("not building X"), anything an implementer could violate or get wrong. Keep, verbatim or tightened. Tightening may not weaken, strengthen, generalize, narrow, or reorder a requirement.

2. RATIONALE -- why a decision was made, alternatives considered and rejected, failure history. Compress each to a one-line "Why:" note attached to the decision it justifies. Rationale that names a rejected alternative or a past failure survives -- it prevents re-litigating the decision. Rationale that only motivates or reassures is rhetoric.

3. RHETORIC -- persuasion, motivation, analogy, hedging, restatement that adds nothing to a statement already made (normative content repeated across sections falls under the deduplication rule below, not here), throat-clearing, anything whose audience is a reviewer rather than an implementer. Delete.

Form rules:
* Spec voice: declarative, present tense, no first person, no rhetorical questions. Use MUST / MUST NOT / SHOULD / MAY exactly where the original expresses that level of obligation -- do not upgrade a "should" to a MUST or downgrade a "must" to a SHOULD.
* Prefer tables and lists over paragraphs wherever content is enumerable.
* Section numbers and heading text stay exactly as in the original -- other documents and tooling may cite sections by number or heading, and every internal cross-reference must still resolve.
* VERBATIM-PROTECTED, byte-for-byte: all fenced code blocks, commands, file paths, config examples, schemas, and any region delimited by extraction markers (paired BEGIN_X / END_X lines or equivalent), including the markers themselves -- tooling may extract these regions literally and any edit breaks it.
* Deduplication: when the same normative content appears in more than one section, keep one canonical statement in the section that owns the topic and replace every other occurrence with a cross-reference to it. Merge only duplicates that are identical in substance: if two occurrences differ in any substantive way -- obligation force, scope, a name, a default, a condition -- they are not duplicates but a latent contradiction; keep both verbatim, do not reconcile them, and record the pair under DIVERGENT DUPLICATES. Choosing a winner is design, not compression.
* No new content: do not add requirements, defaults, clarifications, or examples the original does not state. If a passage is ambiguous, carry the ambiguity into the spec unresolved and flag it in the ledger -- compression must not smuggle in design.

Also produce, as structured output (not written into the spec):
* JUDGMENT-CALL LEDGER: every sentence that resisted classification -- quote, section, the class you chose, why. Include anything you kept despite it reading as rhetoric because it carried a fact, and anything you deleted despite it brushing against a requirement.
* FLAGGED AMBIGUITIES: passages carried forward unresolved, per the no-new-content rule.
* DUPLICATE MAP: every merge performed -- the location of each original occurrence and the canonical spec statement that now serves them all.
* DIVERGENT DUPLICATES: occurrences that repeat the same content but differ in substance, kept unreconciled -- both locations, both quotes, and the difference.
* METRICS: per-section line counts before and after, and the overall ratio.

Rules: content is settled -- if you disagree with a decision, compress it faithfully. When keep-vs-delete is in doubt, keep and flag: a fat spec is recoverable from the ledger, a silently dropped contract is not. Be exhaustive on classification before polishing wording; if effort runs short, leave a section verbatim and say so -- never summarize one from memory.

# Fidelity agent prompt (verbatim)
You receive an original design document at <PLAN_PATH>, a compressed specification at <SPEC_PATH>, and the compressor's judgment-call ledger and duplicate map. Assume the compression is lossy until the text proves otherwise. Work the ORIGINAL side, section by section: for every normative statement in the original, find its counterpart in the spec. Do not audit spec-side first -- that finds inventions but never drops.

Counterparts may be many-to-one: the duplicate map lists where the compressor merged repeated content into one canonical statement. Verify each canonical statement against EVERY original occurrence it serves -- a nuance present in one occurrence and absent from the canonical statement is DROPPED; if the occurrences diverged and the spec commits to one reading, that is RESOLVED AMBIGUITY. A merge absent from the duplicate map is still a merge -- audit it the same way, and note the missing map entry.

Report every instance of:
1. DROPPED -- a normative statement in the original with no surviving counterpart.
2. ALTERED -- obligation force changed (must vs should), a name, default, limit, or ordering changed, a condition's scope narrowed or broadened.
3. INVENTED -- the spec states something the original does not determine.
4. RESOLVED AMBIGUITY -- the original supports two readings and the spec commits to one.
5. VERBATIM VIOLATION -- any protected region (fenced code, commands, schemas, extraction-marker blocks) that is not byte-identical; check these mechanically with diff, not by eye.
6. BROKEN REFERENCE -- a section number, heading, or internal cross-reference that no longer resolves.

Every finding: original location, spec location (or "absent"), both quotes, class. Compressor ledger entries do not excuse a finding -- a flagged loss is still a loss; note the flag.

Verdict: LOSSLESS / LOSSY-MINOR (findings are recoverable wording issues) / LOSSY (a contract, default, or invariant was dropped or altered), with the finding count per class. An empty finding list is a valid answer only after a complete original-side pass -- say which sections you covered.

# Disposition of results
Findings become edits to the draft spec, reviewed before applying, same as every prior round; the fidelity pass re-runs after edits. DIVERGENT DUPLICATES are content defects, not compression defects: they route to the document's normal review process for the owner to reconcile, and stay unreconciled in the spec until then. Nothing replaces the original automatically: the draft is promoted only on a LOSSLESS verdict plus a human-reviewed diff, keeping the original's file name (other tooling may reference it) and with the prior version retained in git history. The judgment-call ledger and metrics are kept with the review record; the scratch draft is otherwise discarded.
