"""Tray icon rendering tests (no session bus required)."""

from __future__ import annotations

import unittest

from compx_control.state import MouseState
from compx_control.tray import ICON_SIZE, render_tray_icon


class TrayIconTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MouseState(battery=64, charging=False, model_name="MAD R")

    def test_all_styles_return_argb_pixmap(self) -> None:
        for style in ("hex", "bars", "bolt"):
            pixmap = render_tray_icon(self.state, True, style)
            self.assertEqual(len(pixmap), 1)
            width, height, data = pixmap[0]
            self.assertEqual((width, height), (ICON_SIZE, ICON_SIZE))
            self.assertEqual(len(data), ICON_SIZE * ICON_SIZE * 4)
            self.assertGreater(sum(data[3::4]), 0)

    def test_styles_are_distinct(self) -> None:
        icons = [
            render_tray_icon(self.state, True, style)[0][2]
            for style in ("hex", "bars", "bolt")
        ]
        self.assertEqual(len(set(icons)), 3)

    def test_disconnected_icon_is_dim(self) -> None:
        connected = render_tray_icon(self.state, True, "hex")[0][2]
        disconnected = render_tray_icon(None, False, "hex")[0][2]
        self.assertNotEqual(connected, disconnected)

    def test_charging_icon_differs(self) -> None:
        self.state.charging = True
        charging = render_tray_icon(self.state, True, "hex")[0][2]
        self.state.charging = False
        idle = render_tray_icon(self.state, True, "hex")[0][2]
        self.assertNotEqual(charging, idle)


if __name__ == "__main__":
    unittest.main()
