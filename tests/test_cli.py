"""Headless CLI tests that do not require a physical mouse."""

from __future__ import annotations

import contextlib
import io
import unittest
from unittest.mock import patch

from atk_control import cli, devices
from atk_control.state import MouseState


class _FakeController:
    path = "/dev/null"
    state = MouseState(model_name="MAD R", cid=2, mid=54)
    caps = devices.default_capabilities()

    def read_full(self):
        return self.state

    def close(self):
        pass


class CliTests(unittest.TestCase):
    def test_version_command(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cli.main(["version"]), 0)
        self.assertTrue(out.getvalue().startswith("atkctl "))

    def test_help_exits_cleanly(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as caught:
            cli.main(["--help"])
        self.assertEqual(caught.exception.code, 0)
        self.assertIn("status", out.getvalue())

    def test_caps_uses_discovered_controller(self) -> None:
        out = io.StringIO()
        with patch("atk_control.cli._open", return_value=_FakeController()):
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["caps"]), 0)
        self.assertIn("Model:", out.getvalue())

    def test_scan_without_devices_is_a_clean_failure(self) -> None:
        out = io.StringIO()
        with patch("atk_control.cli.discover", return_value=[]):
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["scan"]), 1)
        self.assertIn("No ATK/VXE", out.getvalue())

    def test_removed_long_range_command_is_rejected(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main(["long-range", "on"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
