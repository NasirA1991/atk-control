from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UninstallScriptTests(unittest.TestCase):
    def test_destdir_uninstall_leaves_autostart_alone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            destdir = base / "staging"
            autostart = home / ".config" / "autostart" / "atk-control.desktop"
            autostart.parent.mkdir(parents=True)
            autostart.write_text("[Desktop Entry]\n", encoding="utf-8")

            env = os.environ.copy()
            env["HOME"] = str(home)
            env["DESTDIR"] = str(destdir)
            env.pop("XDG_CONFIG_HOME", None)

            result = subprocess.run(
                ["bash", str(ROOT / "uninstall.sh")],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=True,
            )

            self.assertTrue(autostart.is_file())
            self.assertIn("Autostart was not touched", result.stdout)


if __name__ == "__main__":
    unittest.main()
