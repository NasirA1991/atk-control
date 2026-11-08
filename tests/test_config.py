"""Preference loading, validation and atomic persistence."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from atk_control import config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"XDG_CONFIG_HOME": self.temp.name})
        self.env.start()

    def tearDown(self) -> None:
        self.env.stop()
        self.temp.cleanup()

    def write(self, payload: object) -> None:
        path = config.config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    def test_bad_types_fall_back_and_do_not_crash(self) -> None:
        self.write({
            "live_refresh_seconds": "fast",
            "full_refresh_seconds": None,
            "start_hidden": "yes",
            "tray_icon_style": "not-a-style",
            "unknown": [1, 2, 3],
        })
        data = config.load()
        self.assertEqual(data["live_refresh_seconds"], config.DEFAULTS["live_refresh_seconds"])
        self.assertEqual(data["full_refresh_seconds"], config.DEFAULTS["full_refresh_seconds"])
        self.assertFalse(data["start_hidden"])
        self.assertEqual(data["tray_icon_style"], config.DEFAULT_TRAY_STYLE)

    def test_numbers_are_clamped_and_unknown_keys_are_dropped(self) -> None:
        self.write({"live_refresh_seconds": 999, "full_refresh_seconds": 1, "start_hidden": True, "x": 1})
        data = config.load()
        self.assertEqual(data["live_refresh_seconds"], 120.0)
        self.assertGreaterEqual(data["full_refresh_seconds"], data["live_refresh_seconds"])
        self.assertTrue(data["start_hidden"])
        self.assertNotIn("x", data)

    def test_atomic_save_uses_safe_permissions(self) -> None:
        self.assertTrue(config.save({"tray_icon_style": "hex", "live_refresh_seconds": 4}))
        mode = config.config_path().stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)
        self.assertEqual(config.load()["live_refresh_seconds"], 4.0)
        self.assertFalse(any(p.name.startswith(".config-") for p in config.config_dir().iterdir()))


if __name__ == "__main__":
    unittest.main()
