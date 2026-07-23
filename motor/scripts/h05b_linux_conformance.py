"""Causal H05b probes for a dedicated Linux Docker deployment.

This harness intentionally fails when its deployment prerequisites are absent. A green
report is evidence for human review, not automatic production certification.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4

from motor.runner import (
    MAX_COMBINED_OUTPUT_BYTES,
    CommandRequest,
    CommandResult,
    DockerSandboxRunner,
)


PYTHON = "/usr/bin/python3"


def _containers(docker_bin: str) -> set[str]:
    result = subprocess.run(
        [docker_bin, "ps", "-aq", "--filter", "name=^/motor-sandbox-"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return set(result.stdout.split())


def _run_ok(
    runner: DockerSandboxRunner, workspace: Path, source: str, *args: str, timeout: int = 10,
) -> CommandResult:
    result = runner.run(CommandRequest((PYTHON, "-c", source, *args), workspace, timeout))
    if result.erro or result.returncode != 0:
        raise RuntimeError(
            f"probe failed: erro={result.erro!r} rc={result.returncode!r} "
            f"motivo={result.motivo!r} stderr={result.stderr!r}"
        )
    return result


def collect(image_digest: str, docker_bin: str = "docker") -> dict[str, object]:
    if os.getuid() == 0:
        raise RuntimeError("H05b requires a dedicated non-root host")
    runner = DockerSandboxRunner(image_digest, (PYTHON,), docker_bin)
    baseline = _containers(docker_bin)
    # A fresh name prevents a trusted image's static ENV from masking host leakage.
    host_secret = f"H05B_HOST_SECRET_{uuid4().hex}"
    previous_secret = os.environ.get(host_secret)
    os.environ[host_secret] = "must-not-cross-boundary"

    with tempfile.TemporaryDirectory(prefix="h05b-workspace-") as workspace_raw:
        workspace = Path(workspace_raw)
        sibling = workspace.parent / f"{workspace.name}-sibling-secret"
        sibling.write_text("must-not-be-readable")
        try:
            probe_source = r'''
import json, os, pathlib
workspace = pathlib.Path("/workspace")
outside_write_blocked = False
try:
    pathlib.Path("/h05b-root-write").write_text("bad")
except OSError:
    outside_write_blocked = True
workspace.joinpath("inside-write").write_text("ok")
routes = pathlib.Path("/proc/net/route").read_text().splitlines()[1:]
non_loopback_routes = [line for line in routes if line.split()[0] != "lo"]
status = pathlib.Path("/proc/self/status").read_text().splitlines()
fields = {line.split(":", 1)[0]: line.split(":", 1)[1].strip() for line in status if ":" in line}
print(json.dumps({
    "argv_exact": os.sys.argv[1],
    "cap_eff": fields.get("CapEff"),
    "host_secret_absent": os.getenv(os.sys.argv[2]) is None,
    "network_routes_absent": not non_loopback_routes,
    "no_new_privileges": fields.get("NoNewPrivs") == "1",
    "non_root": os.getuid() != 0,
    "outside_write_blocked": outside_write_blocked,
    "sibling_unreadable": not pathlib.Path(os.sys.argv[3]).exists(),
    "workspace_write": workspace.joinpath("inside-write").read_text() == "ok",
}))
'''
            hostile = "$(touch /tmp/pwned); spaces\n--flag"
            probe = _run_ok(runner, workspace, probe_source, hostile, host_secret, str(sibling))
            isolation = json.loads(probe.stdout)
            required = {
                "argv_exact": hostile,
                "cap_eff": "0000000000000000",
                "host_secret_absent": True,
                "network_routes_absent": True,
                "no_new_privileges": True,
                "non_root": True,
                "outside_write_blocked": True,
                "sibling_unreadable": True,
                "workspace_write": True,
            }
            if isolation != required:
                raise RuntimeError(f"isolation probe diverged: {isolation!r}")

            exact = _run_ok(
                runner,
                workspace,
                "import os; os.write(1,b'a'*524288); os.write(2,b'b'*524288)",
            )
            exact_bytes = len(exact.stdout.encode()) + len(exact.stderr.encode())
            if exact_bytes != MAX_COMBINED_OUTPUT_BYTES:
                raise RuntimeError("exact combined output boundary diverged")
            overflow = runner.run(CommandRequest(
                (PYTHON, "-c", "import os; os.write(1,b'x'*1048577)"), workspace, 10,
            ))
            if overflow.erro != "output_overflow" or not overflow.truncated:
                raise RuntimeError(f"output limit not enforced: {overflow!r}")

            started = time.monotonic()
            timeout = runner.run(CommandRequest(
                (PYTHON, "-c", "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); time.sleep(60)"),
                workspace,
                1,
            ))
            elapsed = time.monotonic() - started
            if timeout.erro != "timeout" or not timeout.timed_out or elapsed > 5:
                raise RuntimeError(f"timeout/termination diverged: {timeout!r}, elapsed={elapsed:.3f}")

            failure = runner.run(CommandRequest((PYTHON, "-c", "raise SystemExit(7)"), workspace, 10))
            if failure.erro or failure.returncode != 7:
                raise RuntimeError(f"failure propagation diverged: {failure!r}")
        finally:
            sibling.unlink(missing_ok=True)
            if previous_secret is None:
                os.environ.pop(host_secret, None)
            else:
                os.environ[host_secret] = previous_secret

    residual = _containers(docker_bin) - baseline
    if residual:
        raise RuntimeError(f"sandbox containers survived cleanup: {sorted(residual)!r}")
    return {
        "status": "observed-not-certified",
        "deployment": asdict(runner.deployment_evidence()),
        "isolation": isolation,
        "output_limit_bytes": MAX_COMBINED_OUTPUT_BYTES,
        "timeout_elapsed_seconds": round(elapsed, 3),
        "cleanup_residual_container_ids": [],
    }


def main() -> None:
    digest = os.environ.get("H05B_IMAGE_DIGEST", "")
    if not digest:
        raise SystemExit("H05B_IMAGE_DIGEST is required")
    report = collect(digest, os.environ.get("H05B_DOCKER_BIN", "docker"))
    output = Path(os.environ.get("H05B_EVIDENCE_PATH", "h05b-linux-conformance.json"))
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(output.read_text(), end="")


if __name__ == "__main__":
    main()
