# Motor contributor notes

These instructions extend the repository-level `AGENTS.md` for changes under `motor/`.

- Keep workflow dynamics in `WorkflowSpec`; do not add feature-specific graph topology.
- Nodes call capabilities through the client abstraction. Do not grant model output authority.
- Preserve event schema validation and append-only behavior.
- Add causal tests for success, boundary and hostile cases.
- Use the fake runner only in tests; it is not evidence of production sandboxing.
- Update `docs/INVARIANTES.md` when a behavioral contract changes.

Run the complete gate from this directory before submitting changes:

```bash
python -m pytest -q
python -m ruff check motor tests
python -m mypy motor
python -m bandit -r motor -q --severity-level high --confidence-level high
python -m compileall -q motor tests
```
