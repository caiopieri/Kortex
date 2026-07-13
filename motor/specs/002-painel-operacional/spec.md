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

## Verification

- `motor/tests/test_painel.py` covers deterministic read projections and HTTP endpoints.
- `motor/tests/test_painel_despacho.py` covers dispatch guards, concurrency and process
  construction.
- `motor/tests/test_hardening_h12b0.py` covers monetary event projection.
- `npm run build` in `motor/motor_painel/app/` verifies the production client bundle.
