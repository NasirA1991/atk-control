"""Worker-side operation tests using the simulated device."""

from __future__ import annotations

import unittest

from compx_control.worker import DemoWorker


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


if __name__ == "__main__":
    unittest.main()
