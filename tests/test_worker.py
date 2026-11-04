"""Worker-side operation tests using the simulated device."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from atk_control import devices
from atk_control.protocol import DeviceInfo, ProtocolError
from atk_control.state import MouseState
from atk_control.worker import DeviceWorker, DemoWorker, _prioritise_candidates


class WorkerSafetyTests(unittest.TestCase):
    def test_candidate_order_keeps_selected_first_but_keeps_others(self) -> None:
        one = DeviceInfo("/dev/hidraw1", 0x373B, 0x1040, "MAD 8K", "0215", True)
        two = DeviceInfo("/dev/hidraw2", 0x3554, 0xF505, "VXE 4K", "0109", True)
        ordered, preferred = _prioritise_candidates([two, one], one.path)
        self.assertEqual([item.path for item in ordered], [one.path, two.path])
        self.assertEqual(preferred, one.path)
        ordered, preferred = _prioritise_candidates([two, one], "/dev/missing")
        self.assertEqual(len(ordered), 2)
        self.assertEqual(preferred, "/dev/missing")

    def test_auto_switches_when_preferred_device_does_not_answer(self) -> None:
        one = DeviceInfo("/dev/hidraw1", 0x373B, 0x1040, "MAD 8K", "0215", True)
        two = DeviceInfo("/dev/hidraw2", 0x3554, 0xF505, "VXE 4K", "0109", True)
        asked = []
        states = []
        toasts = []

        class FakeController:
            def __init__(self, info):
                self.info = info
                self.path = info.path
                self.model = None
                self.receiver = None

            def open(self):
                asked.append(self.path)
                if self.path == one.path:
                    raise ProtocolError("the selected mouse is asleep")
                return MouseState(model_name="VXE R1 Pro", battery=80,
                                  receiver_name="VGN/VXE 4K Dongle", receiver_pid=0xF505)

            def close(self):
                pass

        worker = DeviceWorker(
            lambda state, changed: states.append(state),
            lambda connected, error: None,
            lambda message: toasts.append(message),
        )
        worker._preferred_path = one.path
        with patch("atk_control.worker.discover", return_value=[one, two]),              patch("atk_control.worker.Controller", FakeController):
            self.assertTrue(worker._connect())
        self.assertEqual(asked, [one.path, two.path])
        self.assertEqual(worker._preferred_path, two.path)
        self.assertEqual(states[-1].model_name, "VXE R1 Pro")
        self.assertTrue(any("Switched automatically" in message for message in toasts))

    def test_offline_paired_mouse_disconnects_after_two_polls(self) -> None:
        worker = DeviceWorker(lambda *_: None, lambda *_: None)
        controller = Mock()
        controller.path = "/dev/hidraw-test"
        controller.info.is_receiver = True
        controller.read_live.return_value = MouseState(
            model_name="VXE R1 Pro", receiver_online=False, battery=90
        )
        worker._controller = controller
        worker._last_full = time.monotonic()
        worker._disconnect = Mock()
        with patch("atk_control.worker.os.path.exists", return_value=True):
            worker._poll()
            worker._disconnect.assert_not_called()
            worker._poll()
        worker._disconnect.assert_called_once()
        self.assertIn("offline", worker._disconnect.call_args.args[0].lower())

    def test_hidden_polling_is_slower(self) -> None:
        worker = DeviceWorker(lambda *_: None, lambda *_: None)
        hidden = worker._intervals()
        worker.set_foreground(True)
        visible = worker._intervals()
        self.assertGreaterEqual(hidden[0], 30.0)
        self.assertGreaterEqual(hidden[1], 300.0)
        self.assertEqual(visible, (3.0, 30.0))


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
            worker._write_support_report(str(target), include_raw=True)
            self.assertTrue(target.exists())
            text = target.read_text()
            self.assertIn("Raw configuration registers", text)
            self.assertIn("01 54 02 53", text)
            self.assertIn("Support request:", text)

    def test_default_support_report_omits_raw_bytes(self) -> None:
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
            text = target.read_text()
            self.assertIn("Omitted by default", text)
            self.assertNotIn("01 54 02 53", text)


if __name__ == "__main__":
    unittest.main()
