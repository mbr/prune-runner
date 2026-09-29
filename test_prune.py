"""Checks selection, host guards, and service submission without deleting files."""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import prune


class PruneTests(unittest.TestCase):
    """Exercises action policy with privileged operations mocked out."""

    def test_selection_and_invalid_inputs(self):
        """Checks defaults, exclusions, whitespace, duplicates, and rejected names."""
        self.assertEqual(prune.select_groups("all", ""), list(prune.GROUPS))
        self.assertEqual(
            prune.select_groups("android\njava android\tdocker", "java"),
            ["android", "docker"],
        )
        self.assertEqual(prune.select_groups("all", "all"), [])
        self.assertEqual(prune.select_groups("", "docker"), [])
        for remove, keep in [
            ("all typo", ""),
            ("android", "typo"),
            ("android,docker", ""),
            ("; rm -rf /", ""),
        ]:
            with self.subTest(remove=remove, keep=keep):
                with self.assertRaises(ValueError):
                    prune.select_groups(remove, keep)

    def test_host_guards(self):
        """Rejects local, self-hosted, non-Ubuntu, and container environments."""
        hosted = {
            "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "Linux",
        }
        with (
            patch.dict(os.environ, hosted, clear=True),
            patch.object(prune.platform, "freedesktop_os_release", return_value={"ID": "ubuntu"}),
            patch.object(Path, "read_text", return_value="systemd\n"),
        ):
            prune.require_runner()
            for key, value in [
                ("GITHUB_ACTIONS", "false"),
                ("RUNNER_ENVIRONMENT", "self-hosted"),
                ("RUNNER_OS", "macOS"),
            ]:
                with patch.dict(os.environ, {key: value}), self.assertRaises(ValueError):
                    prune.require_runner()
            with (
                patch.object(
                    prune.platform, "freedesktop_os_release", return_value={"ID": "debian"}
                ),
                self.assertRaises(ValueError),
            ):
                prune.require_runner()
            with (
                patch.object(Path, "read_text", return_value="bash\n"),
                self.assertRaises(ValueError),
            ):
                prune.require_runner()

    def test_services_and_outputs(self):
        """Checks nonblocking fixed commands, distinct invocations, and no-op output."""
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(prune.subprocess, "run") as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            output = Path(temporary) / "output"
            prune.launch(list(prune.GROUPS), output)
            self.assertEqual(run.call_args_list[0].args[0], ["sudo", "-n", "true"])
            values = dict(line.split("=", 1) for line in output.read_text().splitlines())
            units = values["units"].split()
            self.assertEqual(values["groups"].split(), list(prune.GROUPS))
            self.assertEqual(len(set(units)), len(prune.GROUPS))
            for call, group, unit in zip(run.call_args_list[1:], prune.GROUPS, units):
                args = call.args[0]
                self.assertIn("--no-block", args)
                self.assertIn("--property=RemainAfterExit=yes", args)
                self.assertIn("--property=TimeoutStartSec=10min", args)
                self.assertIn(f"--unit={unit}", args)
                self.assertEqual(args[args.index("--") + 1 :], prune.command(group))
                self.assertTrue(call.kwargs["check"])
            second = Path(temporary) / "second"
            prune.launch(["docker"], second)
            self.assertNotIn(second.read_text().split("units=", 1)[1].strip(), units)
            run.reset_mock()
            empty = Path(temporary) / "empty"
            prune.launch([], empty)
            run.assert_not_called()
            self.assertEqual(empty.read_text(), "groups=\nunits=\n")
        self.assertEqual(
            prune.command("android"), ["/usr/bin/rm", "-rf", "--", "/usr/local/lib/android"]
        )
        self.assertEqual(prune.command("apt-cache"), ["/usr/bin/apt-get", "clean"])
        docker = prune.command("docker")
        self.assertEqual(docker[:3], ["/bin/sh", "-eu", "-c"])
        self.assertEqual(
            docker[3].splitlines(),
            [
                "/usr/bin/systemctl stop docker.socket docker.service containerd.service",
                "exec /usr/bin/rm -rf -- /var/lib/docker /var/lib/containerd",
            ],
        )

    def test_action_rejects_inputs_before_privilege_and_propagates_failures(self):
        """Ensures invalid selections launch nothing and submission errors fail the step."""
        with (
            patch.dict(os.environ, {"PRUNE_RUNNER_REMOVE": "all", "PRUNE_RUNNER_KEEP": "typo"}),
            patch.object(prune.subprocess, "run") as run,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(prune.main(), 1)
            run.assert_not_called()
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.dict(
                os.environ,
                {
                    "GITHUB_OUTPUT": str(Path(temporary) / "output"),
                    "PRUNE_RUNNER_REMOVE": "android",
                    "PRUNE_RUNNER_KEEP": "",
                },
            ),
            patch.object(prune, "require_runner"),
            patch.object(
                prune.subprocess,
                "run",
                side_effect=[None, subprocess.CalledProcessError(1, "systemd-run")],
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(prune.main(), 1)


if __name__ == "__main__":
    unittest.main()
