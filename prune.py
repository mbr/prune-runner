#!/usr/bin/python3
"""Queues independent background cleanup services on disposable Ubuntu runners."""

import os
import platform
import subprocess
import uuid
from pathlib import Path

PATHS = {
    "android": ("/usr/local/lib/android",),
    "dotnet": ("/usr/share/dotnet",),
    "haskell": ("/usr/local/.ghcup", "/opt/ghc"),
    "swift": ("/usr/local/swift", "/usr/share/swift"),
    "java": ("/usr/lib/jvm",),
    "powershell": ("/usr/local/share/powershell",),
    "browsers": ("/opt/google/chrome", "/opt/microsoft/msedge"),
    "toolcache": ("/opt/hostedtoolcache",),
}
GROUPS = (*PATHS, "docker", "apt-cache")


def parse_groups(value):
    """Validates group names before resolving the all shorthand."""
    names = set(value.split())
    unknown = names - set(GROUPS) - {"all"}
    if unknown:
        raise ValueError("unknown cleanup groups: " + ", ".join(sorted(unknown)))
    return set(GROUPS) if "all" in names else names


def select_groups(remove, keep):
    """Applies exclusions and returns selected groups in a stable order."""
    selected = parse_groups(remove) - parse_groups(keep)
    return [group for group in GROUPS if group in selected]


def require_runner():
    """Rejects unsupported hosts before invoking privileged commands."""
    required = {
        "GITHUB_ACTIONS": "true",
        "RUNNER_ENVIRONMENT": "github-hosted",
        "RUNNER_OS": "Linux",
    }
    if any(os.environ.get(key) != value for key, value in required.items()):
        raise ValueError("requires a disposable GitHub-hosted Linux runner")
    if platform.freedesktop_os_release().get("ID") != "ubuntu":
        raise ValueError("requires Ubuntu")
    if Path("/proc/1/comm").read_text().strip() != "systemd":
        raise ValueError("requires a systemd host; container jobs are not supported")


def command(group):
    """Builds fixed commands without incorporating caller-provided shell text."""
    if group == "docker":
        return [
            "/bin/sh",
            "-eu",
            "-c",
            "/usr/bin/systemctl stop docker.socket docker.service containerd.service\n"
            "exec /usr/bin/rm -rf -- /var/lib/docker /var/lib/containerd",
        ]
    if group == "apt-cache":
        return ["/usr/bin/apt-get", "clean"]
    return ["/usr/bin/rm", "-rf", "--", *PATHS[group]]


def launch(groups, output):
    """Publishes unit names and submits cleanup without waiting for completion."""
    prefix = "prune-runner-" + uuid.uuid4().hex
    units = [f"{prefix}-{group}.service" for group in groups]
    with output.open("a") as stream:
        stream.write("groups=" + " ".join(groups) + "\n")
        stream.write("units=" + " ".join(units) + "\n")
    if not groups:
        print("No cleanup groups selected.", flush=True)
        return
    subprocess.run(["sudo", "-n", "true"], check=True)
    for group, unit in zip(groups, units):
        subprocess.run(
            [
                "sudo",
                "-n",
                "systemd-run",
                "--system",
                "--quiet",
                "--no-block",
                f"--unit={unit}",
                "--property=Type=oneshot",
                "--property=RemainAfterExit=yes",
                "--property=TimeoutStartSec=10min",
                "--property=TimeoutStopSec=30s",
                "--property=StandardOutput=journal",
                "--property=StandardError=journal",
                "--setenv=PATH=/usr/sbin:/usr/bin:/sbin:/bin",
                "--",
                *command(group),
            ],
            check=True,
        )
        print(f"Queued {group}: {unit}", flush=True)


def main():
    """Validates action inputs and reports submission failures to GitHub Actions."""
    try:
        groups = select_groups(
            os.environ.get("PRUNE_RUNNER_REMOVE", "all"),
            os.environ.get("PRUNE_RUNNER_KEEP", ""),
        )
        require_runner()
        launch(groups, Path(os.environ["GITHUB_OUTPUT"]))
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        message = str(error).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error::prune-runner: {message}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
