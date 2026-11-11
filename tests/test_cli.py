"""Headless CLI tests that do not require a physical mouse."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atk_control import cli, devices
from atk_control.protocol import DeviceInfo, DeviceNotFound
from atk_control.state import MouseState


class _FakeController:
    path = "/dev/null"
    state = MouseState(model_name="MAD R", cid=2, mid=54)
    caps = devices.default_capabilities()

    def read_full(self):
        return self.state

    def read_live(self):
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

    def test_battery_reports_level_and_voltage(self) -> None:
        ctl = _FakeController()
        ctl.state = MouseState(
            model_name="MAD R", battery=76, charging=False,
            voltage_mv=3980, polling_rate=8000,
        )
        out = io.StringIO()
        with patch("atk_control.cli._open", return_value=ctl):
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["battery"]), 0)
        self.assertIn("Battery: 76%", out.getvalue())
        self.assertIn("3980 mV", out.getvalue())

    def test_battery_json_and_watch(self) -> None:
        ctl = _FakeController()
        ctl.state = MouseState(
            model_name="MAD R", battery=76, charging=True,
            voltage_mv=3980, polling_rate=8000,
        )
        out = io.StringIO()
        with patch("atk_control.cli._open", return_value=ctl):
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["battery", "--json"]), 0)
        self.assertEqual(
            json.loads(out.getvalue()),
            {
                "model": "MAD R",
                "battery": 76,
                "charging": True,
                "voltage_mv": 3980,
                "polling_rate": 8000,
            },
        )

        out = io.StringIO()
        with patch("atk_control.cli._open", return_value=ctl), \
                patch("atk_control.cli.time.sleep") as sleep:
            with contextlib.redirect_stdout(out):
                self.assertEqual(
                    cli.main(["watch", "--count", "2", "--interval", "0.2"]), 0
                )
        lines = [line for line in out.getvalue().splitlines() if line]
        self.assertEqual(len(lines), 2)
        self.assertIn("76%+", lines[0])
        sleep.assert_called_once_with(0.2)

    def test_watch_rejects_invalid_interval(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main(["watch", "--interval", "0"])
        self.assertEqual(caught.exception.code, 2)

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
        self.assertIn("No supported ATK/VXE", out.getvalue())

    def test_removed_long_range_command_is_rejected(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                cli.main(["long-range", "on"])
        self.assertEqual(caught.exception.code, 2)


    def test_scan_all_reports_unsupported_interface(self) -> None:
        info = DeviceInfo(
            "/dev/hidraw-a9", 0x373B, 0x1216, "ATK A9 Plus 2.0",
            supported=False,
            unsupported_reason="vendor usage page 0xff05 instead of 0xff02",
        )
        out = io.StringIO()
        with patch("atk_control.cli.discover_all", return_value=[info]):
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["scan", "--all"]), 0)
        self.assertIn("unsupported", out.getvalue())
        self.assertIn("0xff05", out.getvalue())

    def test_report_falls_back_without_supported_device(self) -> None:
        out = io.StringIO()
        with patch("atk_control.cli._open", side_effect=DeviceNotFound("no device")), \
                patch("atk_control.cli.discover_all", return_value=[]):
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["report"]), 0)
        self.assertIn("# ATK Control discovery report", out.getvalue())

    def test_support_falls_back_and_writes_discovery_report(self) -> None:
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "discovery.md"
            with patch("atk_control.cli._open", side_effect=DeviceNotFound("no device")), \
                    patch("atk_control.cli.discover_all", return_value=[]):
                with contextlib.redirect_stdout(out):
                    self.assertEqual(cli.main(["support", "-o", str(target)]), 0)
            self.assertTrue(target.exists())
            self.assertIn("# ATK Control discovery report", target.read_text())
        self.assertIn("Discovery report saved", out.getvalue())


if __name__ == "__main__":
    unittest.main()
