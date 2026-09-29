# Deterministic fixture host

Copy this directory into a fresh host repository and commit the base through
the engine Git seam. Use the Squatch virtual environment (with Squatch installed)
and configure the local Git author identity before running scripted work.
Render the managed conduct block with `squatch core` during host setup.

Launch `python bin/fixture-serve` from that environment. It puts this host's
`bin` first on PATH, strips provider keys, and execs `squatch serve` against the
host-root profile. Direct adapter callers must likewise put `hosts/fixture/bin`
first on PATH; `codex` here is an executable Python script, never a model client.
It reads the surface from the prompt header and requires exactly one closed
`fixture-scenario: <name>` marker. Author and Review emit the engine's JSON
contracts; Implement applies and commits the canned change and leaves its run
record uncommitted in the ticket outbox.

`scenarios.json` is the closed scenario list, with three distinct ticket stems:

- `deterministic-app` adds a receipt without changing classification.
- `report-to-regression` fixes the planted Squatch classification defect and
  adds `scenario-output/regression_check.py`. The bug ticket carries only that
  new test: running it over the base app fails; running it over the fix passes.
- `machine-introduced-escape` changes containment only in its canned Implement
  diff. The base is correct. The smoke check deliberately misses containment,
  allowing a later report to expose an escape from the machine merge.

`python bin/fixture-replay` runs the smoke scenario. Explicit `--scenario`
runs compare the real app output with the recorded expectation and exit 1 on
a reproduced defect, 0 on a match. Thus the regression is red before its fix,
and the escape is red only after its introducing ticket.

Reports and their replay files are bounded version-1 fixtures, not engine
receipts. `app_commit` values are symbolic fixture identities: the later
host-loop runner must substitute the actual base or machine squash SHA when
publishing a report, preserve its evidence, and derive attribution from real
squash trailers. This scaffold does not invent merge provenance or run the
later inbox, escape-column, or supervised-confirm machinery.
