# AGENTS.md

Repository instructions for automated contributors.

## Start here — this project already has an architecture

Kortex is not a blank repository. The architecture, the founding vision and the decisions
that must not be relitigated are **already written down**. Before proposing anything, know
what exists.

**Read `docs/ESTADO.md` first.** It is the living document: it says where the build currently
stands, which fronts are done, which are open, and what to read next for the front you are
about to touch. It carries partially ticked checklists and the measured facts behind them.

`docs/ESTADO.md` names the reading order. The short version:

1. this file — invariants and contribution rules
2. `docs/ESTADO.md` — where we stopped
3. `docs/PARECER-ARQUITETO-visao-vs-sistema.md` — the founding vision, recorded faithfully
4. `docs/DECISAO-ciclo-de-vida-workflow.md` — canonical on workflows; wins over any other
   document on that topic
5. `motor/docs/INVARIANTES.md` — what the engine promises and may not break

**Do not record progress in this file.** `AGENTS.md` holds invariants that rarely change and
only points at what is updatable. State goes in `docs/ESTADO.md`; priorities go in
`docs/ROADMAP.md`. When you finish something real — something backed by evidence, not by
prose — update `docs/ESTADO.md`, not this file.

Older documents may be stale. `docs/ESTADO.md` §2 flags the ones known to lie and in what.
When you find a new one, flag it there too; do not silently rewrite the old document.

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

Run the full suite **one at a time per checkout**. Each CLI run now owns
`<workspace>/<run_id>/log.jsonl` under an exclusive `flock`; the repository-root
`log.jsonl` is legacy read-only. The persistent SQLite/checkpointer and other shared
fixtures may still contend when two suites or agents use the same checkout, so concurrent
measurement is not evidence. Coordinate before running.

Run from `motor/`:

```bash
python -m pytest -q
python -m ruff check motor tests
python -m mypy motor
python -m bandit -r motor -q --severity-level high --confidence-level high
python -m compileall -q motor tests
```

### When you change what a field means, follow it to its consumers

A field that changes shape — new value, new `null`, new absence — is not done until you
have looked at every place that reads it. Grep the name across both languages. This is not
about crashes; it is about **a consumer silently converting your honesty back into a claim**.

Real case, 2026-08-22 (issue #29): the backend correctly stopped reporting `estado: "ativa"`
for a run it could not describe, and returned `null` instead. A board column did
`if (estado === 'ativa') return 'prod'; return 'plan';` — so the run went from lying
*"running"* to lying *"planned"*. The Python diff was right and the system got no more
honest. The second lie is harder to spot, because "plan" looks harmless.

A default branch that swallows `null` is where this hides. Make the unknown case explicit,
and prefer declaring it over hiding the row: **disappearing from the screen is another way
of not declaring.**

## Repository hygiene

- Commit product specifications, architecture decisions, public runbooks and reproducible
  verification artifacts.
- Do not commit chat transcripts, agent prompts, handoffs, session reports, local paths,
  live logs, generated builds or credentials.
- Use specific `git add` paths and one logical change per commit.
