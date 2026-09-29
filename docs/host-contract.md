# Squatch host contract

This contract is the bounded interface for a host repository. Squatch owns its
engine plane; the host owns its application, its project-owned files, and its
decisions about which checks and providers to configure.

## Configuration

Put `config.yaml` at the host checkout root. The following is a copyable
version-1 configuration. Comments describe the `review` and `merge` fields
that a host normally customizes; the example itself is valid schema input.

<!-- host-config-example:start -->
```yaml
schema_version: 1
state_dir: .squatch/state
providers:
  - name: agent-cli
    kind: cli
    models_by_tier:
      low: agent-low
      medium: agent-medium
      high: agent-high
      max: agent-max
    limits:
      concurrency: 1
routing:
  - tier: medium
    surface: review
    candidates:
      - provider: agent-cli

# `review.mechanical` is the host's argv-only mechanical check inventory.
# `trigger: always` runs this check for every review; `hard` makes failure a gate.
review:
  mechanical:
    - code: test
      argv: [uv, run, pytest, -q]
      trigger: always
      severity: hard

# `merge.safety_checks` names passed mechanical check codes required at merge.
# `merge.strategies` declares only explicit regenerate/union conflict strategies.
merge:
  safety_checks: [test]
  strategies: []

# Optional durable landing directory for version-1 host reports.
report_inbox: .squatch/report-inbox
```
<!-- host-config-example:end -->

`schema_version: 0` is the only supported predecessor. Run
`squatch migrate-config`: it validates the complete version-1 candidate,
changes only the top-level version scalar, writes a recoverable adjacent
`config.yaml.bak`, and atomically replaces the original. A current version-1
file is unchanged. Missing, malformed, newer, or otherwise invalid configs
are refused without a write.

## Engine seams

Hosts configure behavior but do not bypass engine seams. Squatch injects its
clock as a zero-argument aware-datetime callable; waits use its injected sleep
callable. Process execution goes through `ProcessExec.run(argv, cwd, env,
timeout)`, never a shell. Filesystem work goes through `Filesystem`, whose
write/replace operations are atomic and whose `publish` operation refuses to
overwrite an existing path. Notifications use `Notifications.notify(argv)`;
the notification worker is separate from active-work execution.

The host supplies argv values and paths in configuration. It must not supply a
literal provider secret: provider authentication is an environment-variable
name, and only a process that needs that secret receives it.

## Report inbox

`report_inbox`, when configured, is a host-controlled drop location for
version-1 report files. A later Squatch inbox consumer reads each report
metadata first, accepts at most a 1 MiB replay file and a 64 KiB log excerpt,
and copies the bounded evidence into durable Suggestion Box custody before it
records a message. Reports become candidate `bug` work only through that
consumer's sequential triage; their evidence and `## Regression` contract
remain with the resulting ticket. Do not make the inbox a general-purpose
state directory or rely on an unbounded report payload.

## Managed conduct files

Squatch may own only its managed block in a routed conduct file (currently
the provider-resolved `CLAUDE.md` or `AGENTS.md`). It preserves every
project-owned byte outside that block. On first adoption, no marker-like text
means Squatch inserts its generated block; malformed, partial, duplicate, or
stray marker-like text is refused rather than rewritten.

The block begins with the generated, attributed form
`<!-- squatch:core begin version=<N> sha256=<64 hex> -->` and ends with
`<!-- squatch:core end -->`. Squatch renders the begin marker and its digest;
a host must never hand-write the marker. Re-rendering the same block is
byte-idempotent. A drifted block is repaired from the current branch template,
while the project-owned remainder stays unchanged.

## Cutover boundary

Before cutover, Squatch self-build uses its bounded bootstrap drain. After an
operator has recorded a GO baseline and starts `squatch serve` for a host,
the daemon-era supervision and host gates apply to that host work. This
contract does not authorize foreign process-state adoption: Squatch never
adopts, reconstructs, or mutates another orchestrator's running process
state. A host starts from its own configuration, files, journal, and explicit
control requests.
