# Operational Panel Specification

## Purpose

The panel is a projection and control surface for real motor state. It must make unavailable
information explicit and must never simulate progress, cost, health or successful actions.

## Data contract

- `painel.py` exposes stable `/dados/*` JSON endpoints derived from the event ledger and
  persisted motor state.
- Projections are deterministic folds over persisted input. Rendering code does not infer
  authority or fabricate missing state.
- React pages are thin views over that API. Shared routing, status, theme and API behavior
  live in shared components rather than per-page copies.
- A number or status shown as real must come from an API field or a declared event. Missing
  information is rendered as unavailable, not estimated or replaced by sample data.

## Operational honesty

- A control either performs the documented action or is visibly disabled/static.
- Demo, placeholder and synthetic data must be explicitly labeled and cannot appear in a
  live projection.
- Success, PID, log path and error messages shown after dispatch come from the server result.
- Theme and density preferences affect presentation only; they never alter projected state.

## Mission dispatch

Dispatch can incur external cost and therefore requires all of the following:

1. Explicit operator opt-in on the server and explicit consent in the UI.
2. Same-origin validation for browser requests.
3. A bounded JSON body with validated fields and objective length.
4. At most one active mission per panel process.
5. Process creation through a fixed executable and validated `argv`, never a shell command.
6. Failure responses that preserve evidence without claiming the mission started.

## Canvas and operation surface

The panel evolves into an infinite-canvas operation surface organized in floors. The full decision is
`docs/DECISAO-canvas-e-operacao.md`; the clauses that bind this spec are:

- Nothing exists because it is on the canvas. It exists because it is in the ledger or in a spec. The
  canvas is a projection and a spec editor, never a second source of truth.
- The surface has two visually unmistakable zones. **Draft** is free-form, carries no authority, and
  never feeds the curator. **Score** accepts only valid grammar and emits a `WorkflowSpec`. Promotion
  from draft to score is explicit and one-directional; a draft that produced a good score is attached
  to the spec version as provenance, never as evidence.
- Floors are houses. A link between floors is a typed artifact with provenance, chained by the
  orchestrator — never a free-hand line.
- Failure indicators must resolve to a station. A localized failure points at floor, run and node; a
  systemic failure (composition, stale pricing/FX, missing credential, uncovered capability, denied
  runner) points at a fixed pre-flight station. The surface never invents a location, and says so when
  a failure has none — the same three-state honesty already used for connection credentials.
- Live projection is served incrementally over the ledger `seq`. The client tracks the last `seq`,
  detects discontinuity and rebuilds the fold; while a projection is suspect it is rendered as
  suspect. A gap is never resolved by displaying a state that never existed.
- A desktop shell is justified only by capabilities the browser lacks — native notification of an open
  gate or a raised andon, operation state in the menu bar, click-through to the station. The browser
  remains a first-class path; the shell wraps the same surface rather than forking a second product.

## Verification

- `motor/tests/test_painel.py` covers deterministic read projections and HTTP endpoints.
- `motor/tests/test_painel_despacho.py` covers dispatch guards, concurrency and process
  construction.
- `motor/tests/test_hardening_h12b0.py` covers monetary event projection.
- `npm run build` in `motor/motor_painel/app/` verifies the production client bundle.
