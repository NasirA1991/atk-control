"""Worker-side operation tests using the simulated device."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atk_control import devices
from atk_control.state import MouseState
from atk_control.worker import DeviceWorker, DemoWorker


class DemoWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.states = []
        self.links = []
        self.worker = DemoWorker(
            lambda state, changed: self.states.append(state),
            lambda connected, error: self.links.append((connected, error)),
        )
        self.worker.start()

    def test_starts_connected(self) -> None:
        self.assertTrue(self.links[0][0])
        self.assertEqual(self.states[0].model_name, "MAD R")
        self.assertEqual(self.states[0].polling_rate, 8000)

    def test_set_polling(self) -> None:
        self.worker.submit("polling", 4000)
        self.assertEqual(self.worker.state.polling_rate, 4000)

    def test_stage_and_color(self) -> None:
        self.worker.submit("active_stage", 1)
        self.assertEqual(self.worker.state.active_stage, 1)
        self.assertEqual(self.worker.state.dpi, 800)
        self.worker.submit("stage_dpi", 1, 1200, 1200)
        self.assertEqual(self.worker.state.stages[1], (1200, 1200))
        self.worker.submit("stage_color", 1, "#112233")
        self.assertEqual(self.worker.state.stage_colors[1], "#112233")

    def test_toggles(self) -> None:
        self.worker.submit("motion_sync", False)
        self.worker.submit("ripple", False)
        self.worker.submit("straight_line", True)
        self.assertFalse(self.worker.state.motion_sync)
        self.assertFalse(self.worker.state.ripple_control)
        self.assertTrue(self.worker.state.straight_line)

    def test_profile(self) -> None:
        self.worker.submit("profile", 3)
        self.assertEqual(self.worker.state.profile, 3)

    def test_demo_device_picker(self) -> None:
        devices = self.worker.available_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(self.worker.device_path, "/dev/hidraw-demo")
        self.worker.select_device("/dev/hidraw-demo")

    def test_support_report(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.md"
            self.worker.save_support_report(str(target))
            self.assertTrue(target.exists())
            text = target.read_text()
            self.assertIn("ATK Control device report", text)
            self.assertIn("MAD R", text)


class SupportReportPathTest(unittest.TestCase):
    def test_device_worker_writes_raw_report(self) -> None:
        mouse_state = MouseState(model_name="MAD R +", brand="ATK", sensor="PAW3395")
        capabilities = devices.default_capabilities()

        class FakeController:
            path = "/dev/hidraw-test"
            state = mouse_state
            caps = capabilities

            def read_full(self):
                return mouse_state

            def collect_raw_registers(self):
                return {0x0000: bytes.fromhex("01 54 02 53 01 54 00 55 00 55")}

        worker = DeviceWorker(lambda *_: None, lambda *_: None)
        worker._controller = FakeController()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "report.md"
            worker._write_support_report(str(target))
            self.assertTrue(target.exists())
            text = target.read_text()
            self.assertIn("Raw configuration registers", text)
            self.assertIn("01 54 02 53", text)
            self.assertIn("Support request:", text)


if __name__ == "__main__":
    unittest.main()
