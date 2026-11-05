"""Tests for the pure window redraw signature."""

from __future__ import annotations

import unittest

from atk_control.state import MouseState
from atk_control.view_state import state_signature


class ViewStateTests(unittest.TestCase):
    def test_stage_color_change_changes_signature(self) -> None:
        first = MouseState(stage_colors=["#ff0000", "#00ff00"])
        second = MouseState(stage_colors=["#0000ff", "#00ff00"])
        self.assertNotEqual(state_signature(first), state_signature(second))

    def test_volatile_telemetry_does_not_trigger_redraw(self) -> None:
        first = MouseState(battery=80, receiver_online=True, rf_id="AA BB CC")
        second = MouseState(battery=80, receiver_online=False, rf_id="DD EE FF", voltage_mv=3999)
        self.assertEqual(state_signature(first), state_signature(second))


if __name__ == "__main__":
    unittest.main()
