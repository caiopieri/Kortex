# Command Sandbox Conformance

Status: **adapter present; no production backend certified**

The repository adapter is `motor.runner.DockerSandboxRunner`. Its local tests prove only
fail-closed preflight and policy construction; they do not satisfy this conformance suite.

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
for isolation, output, timeout and cleanup. The pre-provisioned image must expose
`/usr/bin/python3`; absence fails the job. The report remains evidence rather than certification
and may become a human promotion-gate input only after independent review on the target deployment.
