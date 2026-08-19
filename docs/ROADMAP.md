# Roadmap

Kortex evolves in small, verifiable slices. Dates are intentionally omitted; priority is
expressed as Now, Next and Later.

## Current state

The living answer to "where are we" is **`ESTADO.md`** — it carries the per-front checklists,
the measured facts behind each tick, and the reading order for whichever front you are about
to touch. It is updated on every real advance; this file is not.

This document keeps only the **priorities** (Now / Next / Later). When the two disagree about
what is already built, `ESTADO.md` wins, because it is the one that gets updated.

## Now

Sequencing note (revised): item 3 **was** the unblocker and is now done — the motor runs what
it writes, and the process gate is certified on a dedicated Linux runner. The bottleneck moved
up a layer: the engine executes one mission well, and nothing composes missions into stages.
`ESTADO.md` §G tracks that layer, and §4 states the order the current state suggests — parallel
missions (blocked on a founder decision) and a typed artifact contract carrying provenance
across runs, which is what any composition depends on. Item 2 is independent; item 4 is
continuous.

1. ~~Provide at least two independently identified costed provider routes and a
   budget/configuration that can satisfy conservative pre-call reservations in a real run.~~
   **Done** — see `ESTADO.md` §5 for the routes verified in a real run.
2. Restore Studio and real experiment entrypoints only after they receive durable run identity,
   budget ledger, monetary sink and certified costed factories.
3. **Done** — a Docker backend is implemented and certified on a dedicated Linux runner
   (34 conformance tests; see `ESTADO.md` §B and §5). The note below is kept because its
   reasoning about egress, output limits and process-tree cleanup still governs any *new*
   backend. Original item: implement and certify a sandbox backend against
   `../motor/specs/001-hardening-producao/sandbox-conformance.md`. `CommandRunner` is already a
   `Protocol`, so the shortest path may not be a dedicated Linux runner: a cloud backend with
   isolated containers, digest-pinned images and per-second billing is a candidate implementation,
   and the same primitive later serves GPU work such as fine-tuning. Read the conformance document
   against the provider's documentation *before* writing code — controllable egress, streaming
   output limits and deterministic process-tree cleanup decide feasibility. See
   `DECISAO-provedores-e-computacao.md`.
4. Keep the panel operationally honest and event-sourced according to
   `../motor/specs/002-painel-operacional/spec.md`.
5. Serve the live projection incrementally over the ledger `seq` instead of polling whole state, with
   gap detection that rebuilds the fold and renders a suspect projection as suspect. This improves the
   panel that already exists and is a precondition for any canvas surface.
6. Carry a station coordinate on failure events, or an explicit declaration that the failure has none.
   Localized failures resolve to floor/run/node; systemic ones (composition, stale pricing or FX,
   missing credential, uncovered capability, denied runner) resolve to a fixed pre-flight station. The
   surface must never invent a location. See `DECISAO-canvas-e-operacao.md`.

## Next

1. Add an authoritative certification repository for curator promotion intent.
2. Version workflow templates with evidence and reversible human approval.
3. Expand deterministic validators and non-functional requirements in `WorkflowSpec`.
4. Build a small provenance-aware knowledge catalog guided by measured retrieval gaps. Ordering is
   fixed by `DECISAO-conhecimento-e-julgamento.md`: execute/typecheck, then read what the project has
   installed, then fetch live at task time, and only then cache — keyed by package version pin, never
   by guessed TTL. Measure the repeat rate of research queries before building the cache.
5. Exercise the software harness on an external project and feed failures back into public
   templates and tests.
6. Add certification revocation to the curator. Promotion exists; expiry, re-certification and
   demotion do not, so a certified workflow stays certified indefinitely. The form is undecided —
   fixed term, sampled re-certification and automatic demotion on approval-rate decay have different
   failure modes and none has been measured.
7. Type human gates by the question they ask, not only by risk. The policy layer already separates
   sensitive from non-sensitive and already escalates coverage to an independent judge instead of the
   human; what is missing is naming the epistemic class (authority / intent / taste / correctness) in
   the gate itself, so that a correctness question reaching a human is visible as a missing verifier.
8. Extend capabilities from model skill to route capability. Today `capacidades_requeridas` speaks
   `redacao`/`codigo`/`analise`; it should also speak `gpu`/`container`/`armazenamento`, so a node can
   require compute and the router picks a backend that provides it — keeping the strict requirement
   and fail-closed behaviour of S3. Guard: if the router needs live availability lookups (quota,
   region, cold start), that belongs to the house layer, not the kernel.
9. Give routes an attestation level. A verifiable identity (direct vendor, own credential) may act as
   verifier, feed the curator and support promotion; a merely declared identity (opaque aggregator)
   may execute in volume with evidence stamped weaker. Stamp rather than block, in the spirit of
   `cobertura_de_evidencia` — but the stamp must carry consequence: a declared-only route never
   promotes and never enters the curator corpus.
10. Do not build an inference gateway. Multi-provider inference has a de facto standard and the plug
   already exists (`ClienteOpenAICompat`, `base_url`); an external aggregator enters as one low-tier
   connection among many, never as the single entrypoint.
11. Build the operation surface as an infinite canvas organized in floors, starting as a view only.
   Bulk rendering off the DOM with level-of-detail, interactive detail in an overlaid focus layer, one
   source of coordinates, behind a thin interface so the renderer choice stays reversible. Keep
   ReactFlow for a single run graph, where it is a good fit.
12. Add a draft zone with no authority — free-form notes, sketches and loose links where the operator
   generates hypotheses while the factory works. Promotion from draft to score is explicit and
   one-directional; a draft that produced a score is attached as provenance, never as evidence, and
   never enters the curator corpus.
13. Let the canvas author workflows, emitting `WorkflowSpec` and offering only the valid grammar. A
   new topological pattern still requires a certified spec version.
14. Wrap the surface in a desktop shell once the andon exists, justified by native notification of a
   raised signal or an open gate. The browser stays a first-class path.
15. Calibrate the human gate: treat each approval as a prediction and score it against later outcomes.
   If the failure rate of approved items matches that of unreviewed ones, the gate carries no
   information. Also record time-to-decision and the list of instantly stamped questions — that list
   is the priority-ordered map of where to build the next verifier. Diagnose the gate, never grade
   the operator.

## Later

- Maintenance and custody. After delivery, a product needs a **dossier** — durable, versioned context
  about a subject, where every entry carries the same evidence stamp as everything else, so it cannot
  become a place where unverified claims accumulate authority. Maintenance inverts the trigger: a
  world event composes the mission instead of a human objective. Incident response is a ladder of three
  stages with different owners and autonomy — **mitigate** (reversible by construction, therefore
  automatic, and degradation must be declared honestly rather than simulated as health), **fix** (new
  code in production, always gated), **root cause** (becomes a rule in the catalog, otherwise cost per
  product never falls). Severity classification is an authority decision and lives with the house.
  Security is the cheapest grader the system will ever have — an exploit either lands or it does not —
  which makes hardening the first domain of the certified catalog rather than the last. Guard against
  monoculture: a fleet built from one consolidated pattern shares its blind spots, so the red team must
  generate novel attacks and external audit must anchor periodically. Method belongs in `dev-harness/`;
  the motor never learns what severity means. See `DECISAO-manutencao-e-custodia.md`.

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
- An incremental client projection that misses an event without noticing displays a state that never
  existed. Gap detection over `seq` is the difference between a live view and a confident lie.
- A canvas is the most enjoyable thing in the project to build and moves none of the three production
  blockers. A fluid surface over a stopped factory renders a stopped factory more fluidly.
- If most real failures turn out to be pre-flight rather than in-graph, the fixed systemic station
  becomes the main screen and the factory map becomes decoration — an honest finding about the system,
  but one that changes what is worth building.
- Two zones on one surface invite exactly the confusion they exist to prevent: if draft and score are
  not unmistakable at a glance, someone reads a sketch as the system.
- A dossier aggregating every client's architecture, dependencies and known attack surface is a more
  valuable target than the code itself; it must be segmented per client and never assembled into one
  queryable index.
- Mitigation that restores service can close an incident that was never fixed. Mitigating must open a
  fix item with a deadline, not resolve the incident.
- Rollback is only reversible when no schema migration or data write happened between deploy and
  failure; the autonomy table assumes a clean rollback and that assumption is per-product, not general.
- A weak red team produces false confidence measured precisely. The grader is cheap; building a
  competent attacker is not.
- CLI recovery of an abandoned monetary outbox requires explicitly reusing the same `run_id`.
- Conservative full-context reservation can make a safe route operationally unusable.
- MCP output is capped only after service materialization, and oversized event batches do not yet
  paginate by count.
- A human asked an unanswerable question does not return silence; it returns noise carrying an
  approval stamp. A legitimate rejection rubber-stamped as approved enters the catalog as a process
  that works, contaminating the one asset that compounds.
- The human gate saturates. At a hundred intents per day the operator stamps without reading, and
  authority migrates to the machine in fact without migrating by right. No test detects this.
- Certification without expiry fossilizes: practices that worked for the wrong reason, and rules
  whose original context has evaporated, keep their seal.
- Executor/verifier independence can be declared in configuration and false in practice when both
  roles traverse the same aggregator. Silent re-routing is the aggregator's headline feature, not an
  edge case, and nothing currently observes which upstream actually served.
- An attestation tier that only stamps, without denying promotion and curator ingestion, becomes
  decorative: every route drifts to the cheapest unattested option and the evidence weakens
  everywhere at once.
- Structural dependency on promotional compute credit is a mortgage; the abstraction has to survive
  the provider leaving.
- A third-party cloud sandbox moves generated code onto someone else's infrastructure with
  credentials in the environment — acceptable for the owner's own code, a compliance decision the
  day it runs a client's.
- Test fixtures that pin a dated pricing/FX snapshot become time bombs — they pass when captured and
  fail on their own once the freshness window closes, which reads as a regression rather than as the
  fail-closed contract working.
