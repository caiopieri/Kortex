# Contributing

## Development setup

Kortex requires Python 3.10 or newer.

```bash
cd motor
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

The optional React panel is in `motor/motor_painel/app/`:

```bash
cd motor/motor_painel/app
npm ci
npm run build
```

## Before opening a pull request

```bash
cd motor
python -m pytest -q
python -m ruff check motor tests
python -m mypy motor
python -m bandit -r motor -q --severity-level high --confidence-level high
python -m compileall -q motor tests
```

Keep pull requests focused. Include tests for behavior changes and document any affected
invariant or public contract. Never include credentials, provider responses, runtime logs,
agent transcripts or generated build directories.

## Design constraints

- `WorkflowSpec` carries workflow dynamics; the graph runtime remains fixed.
- Events are schema-validated and append-only.
- Sensitive gates require a human decision.
- Curator promotion produces gated intent only.
- Command execution fails closed without a certified sandbox runner.

See `docs/ARCHITECTURE.md` and `motor/docs/INVARIANTES.md` for the complete contracts.
