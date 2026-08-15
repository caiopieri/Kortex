# Security Policy

## Supported version

Security fixes target the latest revision of `main`. The project is under production
hardening and is not yet certified for untrusted production command execution.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting or open a private security advisory for this
repository. Do not publish exploit details in a public issue before a fix is available.

Include the affected revision, impact, reproduction steps and any proposed mitigation.
Reports involving command execution, event integrity, budget enforcement, human gates or
curator promotion are treated as high priority.

## Security boundaries

- External input and model output are untrusted.
- Command execution is default-deny without an explicitly composed sandbox runner.
- A curator recommendation cannot apply itself; promotion remains gated human intent.
- Event and monetary ledgers require durable, idempotent state transitions.
- Credentials must be provided through the environment and must never enter logs or Git.

The engineering checklist is maintained in `motor/docs/security-DoD.md`.
