# Command Sandbox Conformance

Status: **causal suite passing on a developer workstation; no production backend certified**

The repository adapter is `motor.runner.DockerSandboxRunner`, composed into the CLI by
`--sandbox <cfg.json>` (`motor.runner.compor_sandbox`, fail-closed: no usable sandbox, no run).
`tests/test_sandbox_causal.py` implements the causal suite below and executes real containers;
it is skipped unless `KORTEX_SANDBOX_IMAGE` names a locally provisioned immutable digest.

That suite passing is evidence, NOT certification. It was first run on macOS/Docker Desktop on
2026-07-28, which satisfies the preflight (`OSType == linux`, from the engine VM) while being
exactly the deployment this document says nothing may be inferred from.

Two defects were found only by executing, after both had survived the preconditions tests:
the adapter passed `--mount ...,rw`, which Docker rejects with exit 125 before starting the
container; and the graph resolved the executable allowlist against the HOST, so a path that
exists only inside the image failed `resolve(strict=True)` and every command was refused.
Both were invisible because no entrypoint composed the runner at all.

A command backend may be enabled only for the exact adapter, engine, policy and image digest
that pass this conformance suite. Unit-test fakes cannot satisfy it.

## Deployment prerequisites

- Ephemeral dedicated Linux runner with a versioned container engine.
- Production adapter composed explicitly; host subprocess execution is prohibited.
- Pre-provisioned image referenced by immutable digest.
- Versioned sandbox policy and executable allowlist.
- No implicit image pull during certification.

The preflight records engine, operating system, adapter, policy and effective image digest.
The current macOS workspace has no reachable Docker daemon or pre-provisioned digest, so no
deployment evidence may be inferred from the adapter tests.

## Required isolation

- Network namespace without external network or DNS access.
- Read-only root filesystem and exactly one writable workspace mount.
- No parent-directory, host-root or engine-socket mount.
- Environment constructed from an allowlist, without host inheritance.
- Non-root user, all capabilities dropped, `no-new-privileges` and a PID limit.
- Validated `argv` executed without an intermediate shell.

## Causal tests

The backend must prove:

- writes succeed inside the workspace and fail outside it;
- host secrets and sibling files are unreadable;
- external networking and DNS are unavailable without relying on a public service;
- combined stdout and stderr are limited to 1 MiB while streaming;
- timeout accepts only strict integers from 1 through 300 seconds;
- timeout sends TERM and then KILL to the entire process unit within two seconds;
- no descendant survives cleanup;
- the sandbox unit is removed after success, failure, overflow and timeout.

Absence of any prerequisite fails the conformance job rather than skipping it.

## Linux evidence baseline

The manual workflow `.github/workflows/h05b-linux-evidence.yml` targets a dedicated,
non-root, self-hosted Linux runner labelled `h05b-sandbox`. It requires an operator-supplied
immutable digest whose image is already provisioned, runs the local H05b causal tests, and
uploads the adapter's observed deployment identity as JSON.

A successful run records engine, OS, adapter, policy, requested/effective digest and causal probes
for isolation, output, timeout and cleanup. The interpreter path is operator-supplied via `KORTEX_SANDBOX_PYTHON` and must appear in the
sealed allowlist; absence fails the job. (`python:3.13-slim` ships it at `/usr/local/bin/python3`,
not `/usr/bin/python3`.) The report remains evidence rather than certification
and may become a human promotion-gate input only after independent review on the target deployment.
