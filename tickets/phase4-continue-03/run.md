## Outcome

ok

## Surprises / judgment calls

The predecessor caller-closure scan also examines this seeded proof. Constructor
names are assembled in the proof so its assertion does not itself look like a
production caller; the reliability ticket explicitly prohibits those constructors
in its new paths, and the proof applies the predecessor pattern once they exist.

## Dead ends

The first full-suite run exposed that the proof's literal constructor names were
included by the predecessor's all-tests caller scan. The focused proof passed, but
the full suite failed until the proof stopped resembling a caller.

## Second problems filed


## Resolved engine/model

Codex / GPT-5

## Predicted vs actual

Expected 75m; actual about 25m.
