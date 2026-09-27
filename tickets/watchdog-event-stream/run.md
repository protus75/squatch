## Outcome

ok

## Surprises / judgment calls

Kept the prior chunked stdout reader so JSONL records over 64 KiB preserve capture semantics, and routed callback failures through the existing group kill-and-wait path. Expanded the provider proof across all three Codex tool shapes, Claude positive and negative shapes, non-JSON chatter, redaction, prompt spool capture, terminal parsing, and cost preservation.

## Dead ends

None.

## Second problems filed

None.

## Resolved engine/model

OpenAI Codex, GPT-5.

## Predicted vs actual

Expected: 75m. Actual: about 20m.
