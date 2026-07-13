# AGENTS.md

Repository instructions for automated contributors.

## Scope

- Read `README.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP.md` and
  `motor/docs/INVARIANTES.md` before changing behavior.
- Keep changes small and scoped. Do not modify or delete tests to make a gate pass.
- Treat external input, model output, event logs and command arguments as untrusted.
- Preserve the boundary that promotion is an intent requiring a human gate, never an
  automatic catalog mutation.
- Command execution is denied unless an explicitly configured runner enforces the
  documented sandbox contract.

## Verification

Run from `motor/`:

```bash
python -m pytest -q
python -m ruff check motor tests
python -m mypy motor
python -m bandit -r motor -q --severity-level high --confidence-level high
python -m compileall -q motor tests
```

## Repository hygiene

- Commit product specifications, architecture decisions, public runbooks and reproducible
  verification artifacts.
- Do not commit chat transcripts, agent prompts, handoffs, session reports, local paths,
  live logs, generated builds or credentials.
- Use specific `git add` paths and one logical change per commit.
