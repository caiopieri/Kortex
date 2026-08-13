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
  documented sandbox contract. `CommandRunner` is the extension point; a new backend is
  certified against `motor/specs/001-hardening-producao/sandbox-conformance.md`, never by
  self-report.
- Provider identity is evidence, not configuration. Do not treat distinct route identifiers
  behind a single aggregator as independent executor and verifier, and do not introduce lossy
  prompt compression on any path feeding the reproducer corpus or the curator.
- Do not build clients for additional inference providers. The OpenAI-compatible plug already
  exists; aggregation of inference is a configuration concern, execution of commands is not.

- Architecture is evidence identity, not a build flag. An image rebuilt for another
  architecture has a different digest and does not inherit the previous one's conformance
  evidence. Add a config; never repoint an existing one whose filename then lies.
- Cost containment is currency-specific. A route without a declared price fails closed by
  design; registering it at zero silences the only monetary containment the engine has.
  Free routes are scarce in quota and availability, not money — they need their own
  containment, not an entry in the price table.
- A process gate proves what its own suite asserts. When the same run writes both the code
  and its tests, green means self-consistency, not conformance to the mission. Contracts
  must assert canonical calls and negatives derived from the brief, checked by a validator
  the generated suite does not author.

## Verification

Run the full suite **one at a time per checkout**. `motor/__main__.py` opens the
repository-root `log.jsonl` under an exclusive `flock`, so two concurrent suites — or two
agents on the same repository — contaminate each other and produce different failure sets.
Concurrent measurement is not evidence. Coordinate before running.

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
