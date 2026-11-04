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
