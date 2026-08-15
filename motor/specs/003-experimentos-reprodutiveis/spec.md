# Reproducible Experiment Specification

## Purpose

Experiments may support only the claim their metric and controls can falsify. Raw outputs are
evidence; agent summaries are not.

## Isolation

- Run each arm in a fresh temporary working directory outside the repository.
- The fact being tested must be absent from prompts, filenames, fixtures and every local file
  visible to the executor unless that arm intentionally receives it.
- Fail closed when isolation cannot be established. Record the effective working directory,
  input inventory, pinned model configuration and command used.
- Do not let repository documentation become an accidental retrieval source.

## Experimental design

For retrieval experiments, use at least three arms:

1. No retrieval context.
2. Irrelevant retrieval context.
3. Relevant retrieval context.

Pin the model and all non-treatment parameters across arms. Use at least five repetitions per
arm unless a stronger power calculation is documented. Register the success threshold before
collecting results, and treat borderline outcomes as inconclusive.

The target fact should be non-guessable and absent from common model knowledge. A stable
baseline is required before attributing a difference to retrieval.

## Metrics

- `schema_json` measures structure and exact mechanical constraints; it does not measure
  semantic correctness by itself.
- `contem` measures the presence of terms. It is acceptable only when transporting those
  terms is the intended behavior and negative controls show they are not guessable.
- Regex checks are limited to mechanical formatting constraints.
- Semantic claims require a separately defined grader and retained raw responses.

## Evidence and claims

Store arm configuration, raw outputs, deterministic scores and aggregate results separately.
Report failed and partial runs. Do not broaden a retrieval result into a claim about synthesis,
model quality or production economics.

The executable harness is documented in `motor/docs/RUNBOOK-EXPERIMENTO-RAG.md`.
