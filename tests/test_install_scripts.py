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


def _stub_bin(base: Path, manager: str) -> Path:
    """A PATH containing only what install.sh needs before the ownership guard."""
    bin_dir = base / "bin"
    bin_dir.mkdir()
    for tool in ("dirname", "head", "cut"):
        os.symlink(f"/usr/bin/{tool}", bin_dir / tool)
    (bin_dir / "id").write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = "-u" ]; then echo 0; exit 0; fi\n'
        'exec /usr/bin/id "$@"\n',
        encoding="utf-8",
    )
    if manager == "pacman":
        (bin_dir / "pacman").write_text(
            '#!/bin/sh\n[ "$1" = "-Qqo" ] && { echo atk-control; exit 0; }\nexit 1\n',
            encoding="utf-8",
        )
    elif manager == "dpkg":
        (bin_dir / "dpkg").write_text(
            '#!/bin/sh\n[ "$1" = "-S" ] && { echo "atk-control: $2"; exit 0; }\nexit 1\n',
            encoding="utf-8",
        )
    elif manager == "rpm":
        (bin_dir / "rpm").write_text(
            '#!/bin/sh\n[ "$1" = "-qf" ] && { echo "atk-control-0.9.6-1.x86_64"; exit 0; }\nexit 1\n',
            encoding="utf-8",
        )
    else:
        raise AssertionError(manager)
    for path in bin_dir.iterdir():
        if not path.is_symlink():
            path.chmod(0o755)
    return bin_dir


class PackageOwnershipGuardTests(unittest.TestCase):
    def _run(self, script: str, manager: str, owned: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            prefix = base / "prefix"
            home.mkdir()
            if owned == "share":
                (prefix / "share" / "atk-control").mkdir(parents=True)
            else:
                (prefix / "bin").mkdir(parents=True)
                (prefix / "bin" / "atk-control").write_text("", encoding="utf-8")
            stub_bin = _stub_bin(base, manager)
            env = os.environ.copy()
            env["HOME"] = str(home)
            env["PATH"] = str(stub_bin)
            env.pop("DESTDIR", None)
            env.pop("XDG_CONFIG_HOME", None)
            return subprocess.run(
                ["/bin/bash", str(ROOT / script), "--prefix", str(prefix)],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_install_refuses_each_package_manager_owned_path(self) -> None:
        for manager in ("pacman", "dpkg", "rpm"):
            with self.subTest(manager=manager):
                result = self._run("install.sh", manager, "share")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("owned by package", result.stderr)
                self.assertIn("--force", result.stderr)

    def test_uninstall_refuses_each_package_manager_owned_path(self) -> None:
        for manager in ("pacman", "dpkg", "rpm"):
            with self.subTest(manager=manager):
                result = self._run("uninstall.sh", manager, "bin")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("owned by package", result.stderr)
                self.assertIn("--force", result.stderr)


if __name__ == "__main__":
    unittest.main()
