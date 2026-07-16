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

The public test corpus is content-addressed by `reproducer-manifest.jsonl` and
`reproducer-corpus-1655f6059e06c318.tar`. `tests/test_hardening_*.py` contains the maintained
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

H05b follow-up is intentionally not certified: `DockerSandboxRunner` and 14 causal preflight/policy
tests now exist in the source tree, but the Docker daemon is unreachable on this macOS host and no
Linux runner, preloaded image digest or conformance job is available. C2/C3 remain blocked; the
adapter's post-capture truncation is not claimed as streaming output control.

Counts are evidence for that revision only. A release must rerun every gate from a clean
checkout.

## Open production blockers

1. **Sandbox backend (H05b):** command execution remains unavailable in production until a
   concrete backend satisfies `sandbox-conformance.md`. String validation and a working
   directory are not sandboxing.
2. **Budget operation:** callsite/run-identity integration and a costed OpenAI adapter are present,
   but one OpenAI route cannot satisfy executor-verifier provider independence and conservative
   pricing exceeds the current R$ 2 bootstrap before transport. Studio and real experiments remain
   unavailable until durable costed composition is supplied. Relay recovery requires polling in the
   service or explicit reuse of the same CLI `run_id`.
3. **Curator authority:** the protocol fails closed without an authoritative certification
   repository supplied by the deployment.

Default-deny contains these gaps but does not prove the missing capabilities.

## Verification rule

No production claim may be inferred from a fake runner, a dirty checkout, a skipped test or a
historical pass count. The invariant matrix and current tests take precedence over narrative
status documents.
