"""Diagnostics report tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from compx_control import diagnostics
from compx_control.state import Button, MouseState


class DiagnosticsTests(unittest.TestCase):
    def _state(self) -> MouseState:
        return MouseState(
            vendor_id=0x373B,
            product_id=0x1040,
            usb_name="Compx MAD 8K DONGLE",
            cid=2,
            mid=49,
            model_name="MAD R",
            brand="ATK",
            sensor="PAW3395",
            firmware="1.24",
            via_receiver=True,
            receiver_name="MAD 8K Dongle",
            receiver_pid=0x1040,
            rf_id="A4 19 7C",
            battery=76,
            charging=False,
            dpi=1600,
            dpi_y=1600,
            stages=[(400, 400), (800, 800), (1600, 1600)],
            active_stage=2,
            stage_count=3,
            polling_rate=8000,
            buttons=[Button("Left", "Left click")],
        )

    def test_report_redacts_rf_id(self) -> None:
        text = diagnostics.report_text(self._state())
        self.assertIn("MAD R", text)
        self.assertNotIn("A4 19 7C", text)
        self.assertIn("A4 ••••••", text)

    def test_write_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.md"
            path = diagnostics.write_report(target, self._state())
            self.assertTrue(path.exists())
            self.assertIn("# Compx Control device report", path.read_text())

    def test_default_filename(self) -> None:
        self.assertRegex(diagnostics.default_filename(), r"^compx-control-report-\d{8}-\d{4}\.md$")


if __name__ == "__main__":
    unittest.main()
