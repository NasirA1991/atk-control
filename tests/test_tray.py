"""Tray icon rendering tests (no session bus required)."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import dbus

from atk_control.state import MouseState
from atk_control.tray import ICON_SIZE, ID_DPI_BASE, Tray, render_tray_icon


class TrayIconTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = MouseState(battery=64, charging=False, model_name="MAD R")

    def test_all_styles_return_argb_pixmap(self) -> None:
        for style in ("hex", "bars", "reticle"):
            pixmap = render_tray_icon(self.state, True, style)
            self.assertEqual(len(pixmap), 1)
            width, height, data = pixmap[0]
            self.assertEqual((width, height), (ICON_SIZE, ICON_SIZE))
            self.assertEqual(len(data), ICON_SIZE * ICON_SIZE * 4)
            self.assertGreater(sum(data[3::4]), 0)

    def test_styles_are_distinct(self) -> None:
        icons = [
            render_tray_icon(self.state, True, style)[0][2]
            for style in ("hex", "bars", "reticle")
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

    def test_tray_dpi_menu_includes_current_and_range(self) -> None:
        tray = object.__new__(Tray)
        tray.state = SimpleNamespace(dpi=260)
        options = [10, 50, 100, 200, 260, 400, 800, 1600, 3200, 6400, 30000, 42000]
        tray.caps = SimpleNamespace(
            sensor=SimpleNamespace(min_dpi=10, max_dpi=42000),
            dpi_options=options,
        )
        values = Tray._dpi_menu_values(tray)
        self.assertIn(10, values)
        self.assertIn(260, values)
        self.assertIn(42000, values)
        self.assertEqual(values, sorted(set(values)))

    def test_tray_dpi_event_uses_current_value_map(self) -> None:
        tray = object.__new__(Tray)
        tray._dpi_values = [260, 800]
        tray.polling_rates = []
        calls = []
        tray.on_dpi = calls.append
        Tray.Event(tray, ID_DPI_BASE + 1, "clicked", "", 0)
        self.assertEqual(calls, [800])

    def test_generated_tray_bus_names_are_valid(self) -> None:
        tray = object.__new__(Tray)
        tray._sni_generation = 0
        tray._flatpak_id = None
        for _ in range(3):
            name = Tray._next_sni_name(tray)
            dbus.validate_bus_name(name, allow_well_known=True, allow_unique=False)
        tray._flatpak_id = "io.github.atkcontrol.AtkControl"
        for _ in range(3):
            name = Tray._next_sni_name(tray)
            dbus.validate_bus_name(name, allow_well_known=True, allow_unique=False)

    def test_dbusmenu_children_are_variants(self) -> None:
        tray = object.__new__(Tray)
        tray._revision = 7
        node = Tray._layout_struct(
            tray,
            {"id": 0, "children": [{"id": 1, "label": "One"}]},
            7,
        )
        children = node[2]
        self.assertIsInstance(children, dbus.Array)
        self.assertEqual(children.signature, "v")
        child = children[0]
        self.assertIsInstance(child, dbus.Struct)
        self.assertEqual(child.variant_level, 1)
        self.assertEqual(int(child[0]), 1)
        self.assertEqual(str(child[1]["label"]), "One")

    def test_dbusmenu_get_layout_includes_revision_and_layout(self) -> None:
        tray = object.__new__(Tray)
        tray._revision = 12
        tray._items = lambda: [{"id": 1, "label": "One"}]
        tray._by_id = lambda item_id: None
        revision, layout = Tray.GetLayout(tray, 0, -1, [])
        self.assertEqual(int(revision), 12)
        self.assertEqual(int(layout[0]), 0)
        self.assertIsInstance(layout[2], dbus.Array)
        self.assertEqual(layout[2].signature, "v")

    def test_tray_style_items_are_a_radio_group(self) -> None:
        tray = object.__new__(Tray)
        tray.connected = False
        tray.state = None
        tray._message = "Waiting"
        tray.polling_rates = [1000]
        tray.style = "bars"
        tray.caps = None
        items = Tray._items(tray)
        style = next(item for item in items if item["id"] == 11)
        states = {child["label"]: child for child in style["children"]}
        self.assertTrue(all(child["toggle-type"] == "radio" for child in states.values()))
        self.assertEqual(states["Signal bars"]["toggle-state"], 1)
        self.assertEqual(states["Hex gauge"]["toggle-state"], 0)
        self.assertEqual(states["Reticle"]["toggle-state"], 0)

    def test_bars_and_reticle_have_transparent_background(self) -> None:
        for style in ("bars", "reticle"):
            data = render_tray_icon(self.state, True, style)[0][2]
            # Corner alpha is zero: both styles are transparent panel icons.
            self.assertEqual(data[3], 0, style)
            self.assertEqual(data[(63 * 64 + 63) * 4 + 3], 0, style)


if __name__ == "__main__":
    unittest.main()
