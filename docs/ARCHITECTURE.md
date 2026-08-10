# Architecture

Kortex is an orchestration kernel for evidence-driven workflows. A typed `WorkflowSpec`
describes roles, dependencies, validators and human gates. The runtime interprets that data
with a fixed graph instead of generating new control flow for every mission.

## Layers

1. **Motor**: executes one workflow, validates outputs, reconciles failures and emits events.
2. **Domain harnesses**: encode reusable methods and evidence requirements for software,
   hardware and mechanical work.
3. **Panel and MCP surface**: project motor state and accept explicitly authorized actions.
4. **External clients**: optional consumers of the MCP contract; they are not authorities
   inside the motor.

## Execution flow

1. A `WorkflowSpec` is validated before graph construction.
2. Executors are selected by declared tier and capabilities.
3. Outputs cross validators or gates before synthesis.
4. Failed validation identifies the source node and triggers bounded reconciliation.
5. Relevant transitions are appended directly or relayed from a durable outbox to the
   schema-validated event ledger before a normal CLI/service completion.
6. The panel, curator and MCP service derive read models from persisted state.

## Trust boundaries

- Model output is data, not permission.
- Sensitive gates are always human-controlled.
- Human input is external input: a senior's finding, a pentest report or the owner's observation
  enters as a high-prior hypothesis to be tested, never as a verdict that skips the test.
- A gate asking about correctness is a missing verifier, not a source of truth. Human judgment is
  authoritative over ends — intent, taste, risk acceptance, spending — not over means.
- Curator promotion is an intent requiring a gate, never an automatic mutation.
- Commands are represented as validated `argv` and remain disabled without a certified
  sandbox backend. `CommandRunner` is a protocol: any backend that satisfies the sandbox
  conformance document may implement it, on this machine or in a cloud container.
- Provider choice is free; provider identity is not. A route carries an attestation level, and
  independence asserted in configuration is not independence observed — two route identifiers behind
  one aggregator are a single judgement until the serving upstream is verified per response.
- Monetary operations use reservations, idempotency keys and recoverable state transitions.

The normative list is in `motor/docs/INVARIANTES.md`. Architectural decisions are recorded
in `motor/docs/ADR-*.md`, and the MCP boundary is documented in
`motor/docs/ARQUITETURA-MCP.md`.

## Repository map

```text
motor/             Python package, tests, examples, panel and motor documentation
docs/              System architecture, lifecycle decision, roadmap and design tokens
dev-harness/       Reusable software-engineering methodology and templates
harness-hardware/  Hardware-domain blueprint
harness-mecanico/  Mechanical-domain blueprint
.github/workflows/ Continuous integration gates
```
