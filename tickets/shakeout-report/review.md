---
verdict: snag
reviewed_sha: 501b66422a25fa635992351b6854669142df454c
produced_by_spec_version: '1.0'
produced_at_sha: 501b66422a25fa635992351b6854669142df454c
provider: claude
model: opus
artifact_schema_version: 1
---
## Summary
The schema, the lift registry and refusal, the bench, the registry, the runner, the double gate and check all meet the acceptance criteria, and every changed path is inside the fence. One logic defect remains: the report's produced_at_sha is the HEAD of a temporary bench checkout that is deleted after the run, not the commit the battery actually ran at.

## Findings
- correctness_review at eval/shakeout/__main__.py:82: `produced_at_sha = bench.head()` records the HEAD of the last member's throwaway fixture repo, which is created under `tempfile.TemporaryDirectory` and deleted before the report is written. That SHA exists in no repository. Across the codebase `produced_at_sha` names the commit the artifact was produced at (for example, `PackingSlip.produced_at_sha=head`), so the committed report would claim provenance nobody can verify. The value also varies between identical runs: the bench's commits get wall-clock author and committer dates, because `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE` are not pinned. When no group is registered it falls back to forty zeros. I am fairly but not fully sure this counts as a defect, because the ticket names the field without defining it; it is reported because the report's custody exists to prevent false provenance. (paved road: Set `produced_at_sha` once, before the groups run, to the HEAD of the checkout the battery runs in. Resolve it with `git.py`'s `rev_parse` over the invoking repo root (the cwd), not over any bench repo, and remove the per-member `bench.head()` assignment and the all-zeros default.)
