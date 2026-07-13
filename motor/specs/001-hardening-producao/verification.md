# Hardening Verification

Status: **not production certified**

## Verified scope

The H00-H13 program and the H12b extension through H12b2c1 provide causal tests for:

- strict spec, verdict, capability and reconciliation behavior;
- command identity, `argv` integrity and default-deny composition;
- schema-validated event append, recovery and read-only projections;
- curator isolation, anti-Goodhart certification and gated promotion intent;
- durable human decisions, crash recovery and idempotent outbox processing;
- monetary event schemas, SQLite reservations, replay, exclusive claims and lease/ack state.

The public test corpus is content-addressed by `reproducer-manifest.jsonl` and
`reproducer-corpus-00bbc07deca063f5.tar`. `tests/test_hardening_*.py` contains the maintained
causal tests. Loose audit copies and session reports are not part of the repository contract.

## Current gates

At revision `cb2318e`, the authoritative suite completed with `713 passed`. Ruff, mypy,
Bandit high/high, Gitleaks, compileall, source/wheel build and diff checks passed. CI repeats
lint, type checking, tests, SAST, secret scanning and package build on GitHub.

Counts are evidence for that revision only. A release must rerun every gate from a clean
checkout.

## Open production blockers

1. **Sandbox backend (H05b):** command execution remains unavailable in production until a
   concrete backend satisfies `sandbox-conformance.md`. String validation and a working
   directory are not sandboxing.
2. **Budget integration:** H12b2c1 persists claim/lease/ack state but does not publish events.
   Relay transport, graph callsite integration and real provider pricing adapters remain
   incomplete.
3. **Curator authority:** the protocol fails closed without an authoritative certification
   repository supplied by the deployment.

Default-deny contains these gaps but does not prove the missing capabilities.

## Verification rule

No production claim may be inferred from a fake runner, a dirty checkout, a skipped test or a
historical pass count. The invariant matrix and current tests take precedence over narrative
status documents.
