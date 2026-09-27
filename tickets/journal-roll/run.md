## Outcome
ok

## Surprises / judgment calls
The preservation suite constructs schema-invalid first records and expects corruption on read, so startup fails closed for malformed or blank JSON while retaining that read-time envelope validation behavior.

## Dead ends
The first focused test used an over-escaped assertion regex; corrected before verification.

## Second problems filed

## Resolved engine/model
Codex / GPT-5

## Predicted vs actual
Expected 75m; actual about 15m.
