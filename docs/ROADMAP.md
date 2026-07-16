# Roadmap

Kortex evolves in small, verifiable slices. Dates are intentionally omitted; priority is
expressed as Now, Next and Later.

## Current state

- The fixed graph interprets validated `WorkflowSpec` data and supports dependency graphs,
  adversarial verification and bounded reconciliation.
- The event ledger has a closed schema, durable append/recovery and read-only projections.
- The curator runs in shadow mode, recomputes anti-Goodhart evidence and emits gated
  promotion intent only.
- Human decisions and monetary reservations have durable SQLite state, crash recovery and
  idempotency controls.
- Every reachable graph model effect reserves a conservative amount before transport; unknown
  cost, stale pricing/FX or missing durable dependencies fail closed.
- Budget events are relayed to the JSONL ledger with stable `event_id`, ACK-after-append and
  deduplication across reopen/redelivery in the CLI and `GerenciadorJobs` paths.
- Command execution is default-deny because no production sandbox backend is certified.
- The complete status is maintained in
  `../motor/specs/001-hardening-producao/verification.md`.

## Now

1. Provide at least two independently identified costed provider routes and a budget/configuration
   that can satisfy conservative pre-call reservations in a real run.
2. Restore Studio and real experiment entrypoints only after they receive durable run identity,
   budget ledger, monetary sink and certified costed factories.
3. Implement and certify a sandbox backend against
   `../motor/specs/001-hardening-producao/sandbox-conformance.md`.
4. Keep the panel operationally honest and event-sourced according to
   `../motor/specs/002-painel-operacional/spec.md`.

## Next

1. Add an authoritative certification repository for curator promotion intent.
2. Version workflow templates with evidence and reversible human approval.
3. Expand deterministic validators and non-functional requirements in `WorkflowSpec`.
4. Build a small provenance-aware knowledge catalog guided by measured retrieval gaps.
5. Exercise the software harness on an external project and feed failures back into public
   templates and tests.

## Later

- Provider adapters with authoritative post-run billing reconciliation.
- A single end-to-end specialist training experiment with a reliable held-out grader.
- Additional domain harnesses after the software workflow is production-certified.
- Federated knowledge sources with provenance, confidence and license metadata.
- Physical-domain and sim-to-real integrations.

## Sequencing principles

1. Prove depth in one vertical before adding breadth.
2. Gates and graders precede optimization and training.
3. Collect evidence now; train only when volume and evaluation justify it.
4. New complexity must pay for itself in quality, cost or safety.
5. Default-deny contains missing capabilities but never counts as proof they exist.

## Where this can fail

- A slow or flaky gate becomes ceremonial and gets bypassed.
- Self-generated output used as training truth can create silent model collapse.
- A UI can imply authority or progress that the motor never persisted.
- A polling-only relay can leave monetary events pending until status is requested after a crash.
- CLI recovery of an abandoned monetary outbox requires explicitly reusing the same `run_id`.
- Conservative full-context reservation can make a safe route operationally unusable.
- Full model text returned by MCP has no explicit response-size cap yet.
