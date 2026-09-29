#!/usr/bin/python3
"""Checks real service completion and directory selection on disposable CI runners."""

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from prune import PATHS, require_runner


def snapshot(directory):
    """Records directory presence without traversing or warming their contents."""
    paths = {**PATHS, "docker": ("/var/lib/docker", "/var/lib/containerd")}
    before = {
        "paths": {
            group: {path: Path(path).exists() for path in roots} for group, roots in paths.items()
        },
        "free_bytes": shutil.disk_usage("/").free,
        "started": time.monotonic(),
    }
    (directory / "before.json").write_text(json.dumps(before))


def inspect(units):
    """Reads service state and retained exit results for every submitted unit."""
    if not units:
        return []
    result = subprocess.run(
        ["systemctl", "show", "--property=Id,SubState,Result,ExecMainStatus", *units],
        check=True,
        capture_output=True,
        text=True,
    )
    return [
        dict(line.split("=", 1) for line in block.splitlines() if "=" in line)
        for block in result.stdout.strip().split("\n\n")
    ]


def verify(directory):
    """Waits for cleanup, validates kept paths, and retains journals and timing."""
    before = json.loads((directory / "before.json").read_text())
    groups = os.environ["ACTUAL_GROUPS"].split()
    units = os.environ["PRUNE_UNITS"].split()
    assert groups == os.environ["EXPECTED_GROUPS"].split()
    assert len(units) == len(set(units)) == len(groups)
    report = {"foreground_delay_seconds": time.monotonic() - before["started"]}
    deadline = time.monotonic() + 660
    while True:
        states = inspect(units)
        if all(state["SubState"] in {"exited", "failed", "dead"} for state in states):
            break
        if time.monotonic() >= deadline:
            raise TimeoutError("cleanup did not finish")
        time.sleep(1)
    report["states"] = states
    report["seconds"] = time.monotonic() - before["started"]
    report["freed_bytes"] = shutil.disk_usage("/").free - before["free_bytes"]
    (directory / "result.json").write_text(json.dumps(report, indent=2))
    if units:
        journal = subprocess.run(
            ["sudo", "-n", "journalctl", "--no-pager", *[f"--unit={unit}" for unit in units]],
            check=True,
            capture_output=True,
            text=True,
        )
        (directory / "journal.txt").write_text(journal.stdout)
    assert len(states) == len(units)
    assert all(
        state["SubState"] == "exited"
        and state["Result"] == "success"
        and state["ExecMainStatus"] == "0"
        for state in states
    )
    for group, paths in before["paths"].items():
        for path, existed in paths.items():
            assert Path(path).exists() == (existed and group not in groups), path
    print(json.dumps(report, indent=2))


def main():
    """Runs one phase of the hosted-runner integration test."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["before", "after"])
    args = parser.parse_args()
    require_runner()
    directory = Path(os.environ["RUNNER_TEMP"]) / "prune-runner-smoke"
    directory.mkdir(parents=True, exist_ok=True)
    {"before": snapshot, "after": verify}[args.phase](directory)


if __name__ == "__main__":
    main()
