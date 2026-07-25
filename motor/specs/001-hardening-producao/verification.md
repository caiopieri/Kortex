# Hardening Verification

Status: **not production certified**

## Verified scope

The H00-H13 program and the H12b extension through H12b4f provide causal tests for:

- strict spec, verdict, capability and reconciliation behavior;
- command identity, `argv` integrity and default-deny composition;
- schema-validated event append, recovery and read-only projections;
- curator isolation, anti-Goodhart certification and gated promotion intent;
- durable human decisions, crash recovery and idempotent outbox processing;
- monetary event schemas, SQLite reservations, replay, exclusive claims and lease/ack state;
- at-least-once budget relay delivery with stable `event_id`, defensive payload copying and
  ACK only after successful publication;
- durable consumer deduplication in the real JSONL event ledger across reopen/redelivery,
  with divergent deliveries rejected before ACK.
- conservative pre-call reservation at planner, executor, verifier, evaluator, reconciliation
  and synthesizer callsites, with distinct retry/failover identities and `UNKNOWN_COST` fail-closed;
- sealed, fresh pricing/FX composition for the costed OpenAI adapter and fail-closed production
  entrypoints when durable budget dependencies are absent.
- certified route topology preflight requiring independent executor/verifier provider identities
  before active CLI/service paths, with same-provider aliases rejected;
- a mandatory governed bootstrap ceiling propagated through CLI, service and planner, without
  weakening conservative reservation;
- a 64 KiB UTF-8 cap on serialized MCP tool responses and bounded error messages.

The public test corpus is content-addressed by `reproducer-manifest.jsonl` and
`reproducer-corpus-0bdbb677dd281edc.tar`. `tests/test_hardening_*.py` contains the maintained
causal tests. Loose audit copies and session reports are not part of the repository contract.

## Current gates

At revision `cb2318e`, the authoritative suite completed with `713 passed`. Ruff, mypy,
Bandit high/high, Gitleaks, compileall, source/wheel build and diff checks passed. CI repeats
lint, type checking, tests, SAST, secret scanning and package build on GitHub.

For the H12b2c2 integration of source commit `3562a6c` over base `901ce2c`, the focused
H12b0-H12b2c2 chain completed with `100 passed` and the full suite with `726 passed`. Ruff,
mypy, Bandit high/high, compileall and diff checks passed.

For the H12b3 integration over base `df1a3f4`, the focused H12b0-H12b3 chain completed with
`104 passed` and the full suite with `730 passed`. Ruff, mypy, Bandit high/high, compileall,
Gitleaks and diff checks passed. Packaging was unchanged, so no build claim is added.

For the H12b4 chain through `7176ac2`, independent callsite review was GREEN. Follow-up H13
corrections `7f804fc` and `fda5b47` bounded MCP input, exposed gate identity and relayed the CLI
monetary outbox before success. The full suite completed with `790 passed`; Ruff, mypy, Bandit
high/high, compileall, Gitleaks and diff checks passed. These gates establish fail-closed integration,
not real-provider operability or production certification.

The H13 integration audit closed at `e2f9daa`. The clean source checkout at `4d612f3` and the rebuilt
sdist incorporating `e2f9daa` each completed with `790 passed`; Ruff, mypy, Bandit high/high,
compileall, Gitleaks and diff checks passed. The wheel installed in a temporary environment, imported the motor,
MCP, service and panel modules, contained both runtime HTML fallbacks, and excluded tests, test
helpers, scripts and examples. The sdist retained the examples, scripts, corpus and test helpers
required to reproduce its suite.

The follow-up H12b/H13 integration through `bdd883d` added certified topology preflight, governed
bootstrap wiring and bounded MCP responses. The full suite completed with `826 passed`; Ruff, mypy,
Bandit high/high, compileall, manifest validation, Gitleaks, diff checks and source/wheel build passed.
The recurrent H11 scheduling test missed its five-second polling window once by about 10 ms, then
passed isolated and in the final full run without test relaxation.

H05b follow-up is intentionally not certified: `DockerSandboxRunner`, its local causal tests and a
manual `h05b-linux-evidence.yml` workflow now exist. The workflow fails closed without a dedicated
non-root Linux runner and preprovisioned image digest, then records actual isolation, output,
timeout and cleanup probes as reviewable evidence. No such artifact has been reviewed from this
macOS checkout, so C2/C3 remain blocked; the runner's selector-based output limit is not treated as
deployment proof.

Counts are evidence for that revision only. A release must rerun every gate from a clean
checkout.

## Open production blockers

1. **Sandbox backend (H05b):** command execution remains unavailable in production until a
   concrete backend satisfies `sandbox-conformance.md`. String validation and a working
   directory are not sandboxing.
2. **Budget operation:** callsite/run-identity integration and a costed OpenAI adapter are present,
   but one OpenAI route cannot satisfy executor-verifier provider independence. The deployment must
   supply two certified provider routes and size mandatory `teto_bootstrap_brl` for conservative
   reservation. Studio and real experiments remain unavailable until durable costed composition is
   supplied. Relay recovery requires polling in the service or explicit reuse of the same CLI
   `run_id`.
3. **Curator authority:** the protocol fails closed without an authoritative certification
   repository supplied by the deployment.

Default-deny contains these gaps but does not prove the missing capabilities.

## Verification rule

No production claim may be inferred from a fake runner, a dirty checkout, a skipped test or a
historical pass count. The invariant matrix and current tests take precedence over narrative
status documents.
