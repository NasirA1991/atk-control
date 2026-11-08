"""Per-device advisory lock tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atk_control.locking import DeviceLock, LockBusy


class LockTests(unittest.TestCase):
    def test_second_owner_is_rejected_and_lock_is_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = DeviceLock("/dev/hidraw-test", directory=base)
            second = DeviceLock("/dev/hidraw-test", directory=base)
            first.acquire()
            try:
                with self.assertRaises(LockBusy):
                    second.acquire()
            finally:
                first.release()
            third = DeviceLock("/dev/hidraw-test", directory=base)
            third.acquire()
            third.release()

    def test_unsafe_lock_directories_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            base.chmod(0o755)
            with self.assertRaises(LockBusy):
                DeviceLock("/dev/hidraw-test", directory=base).acquire()

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "target"
            target.mkdir(mode=0o700)
            link = base / "lock-dir"
            link.symlink_to(target, target_is_directory=True)
            with self.assertRaises(LockBusy):
                DeviceLock("/dev/hidraw-test", directory=link).acquire()

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            target = base / "target"
            target.write_text("not a lock", encoding="utf-8")
            (base / "hidraw-test.lock").symlink_to(target)
            with self.assertRaises(LockBusy):
                DeviceLock("/dev/hidraw-test", directory=base).acquire()

    def test_different_devices_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first = DeviceLock("/dev/hidraw-one", directory=base)
            second = DeviceLock("/dev/hidraw-two", directory=base)
            first.acquire()
            second.acquire()
            second.release()
            first.release()


if __name__ == "__main__":
    unittest.main()
