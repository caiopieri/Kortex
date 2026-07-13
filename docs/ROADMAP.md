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
- Command execution is default-deny because no production sandbox backend is certified.
- The complete status is maintained in
  `../motor/specs/001-hardening-producao/verification.md`.

## Now

1. Complete the budget relay after H12b2c1, preserving `event_id` through publication and
   consumer deduplication.
2. Integrate budget reservations into every model callsite, retry and fallback.
3. Provide real pricing/usage adapters without accepting model-reported cost as authority.
4. Implement and certify a sandbox backend against
   `../motor/specs/001-hardening-producao/sandbox-conformance.md`.
5. Keep the panel operationally honest and event-sourced according to
   `../motor/specs/002-painel-operacional/spec.md`.

## Next

1. Add an authoritative certification repository for curator promotion intent.
2. Version workflow templates with evidence and reversible human approval.
3. Expand deterministic validators and non-functional requirements in `WorkflowSpec`.
4. Build a small provenance-aware knowledge catalog guided by measured retrieval gaps.
5. Exercise the software harness on an external project and feed failures back into public
   templates and tests.

## Later

- Provider adapters with reconciled billing and versioned exchange rates.
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
- At-least-once delivery without durable deduplication can repeat external effects.
- Cost measured after a call cannot enforce a pre-call budget ceiling.
