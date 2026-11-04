"""Per-device advisory lock shared by the GUI and CLI.

The lock is an flock() on a small file named after the hidraw node.  It is
released automatically when the process exits, so a crash cannot leave the
device permanently locked.
"""

from __future__ import annotations

import fcntl
import os
import tempfile
from pathlib import Path


class LockBusy(Exception):
    """Another process owns the same device."""


def lock_directory() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    return Path(base) / f"atk-control-{os.getuid()}"


class DeviceLock:
    def __init__(self, device_path: str, directory: Path | None = None) -> None:
        self.device_path = device_path
        self.directory = directory or lock_directory()
        self.path = self.directory / f"{Path(device_path).name}.lock"
        self.fd = -1

    def acquire(self) -> None:
        if self.fd >= 0:
            return
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        except OSError as exc:
            raise LockBusy(f"could not create the device lock: {exc}") from exc
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            owner = "another process"
            try:
                raw = os.read(fd, 128).decode("utf-8", "replace").strip()
                if raw:
                    owner = raw
            except OSError:
                pass
            os.close(fd)
            raise LockBusy(
                f"{self.device_path} is already controlled by {owner}. "
                "Close the other ATK Control window or CLI and retry."
            ) from exc
        except OSError as exc:
            os.close(fd)
            raise LockBusy(f"could not lock {self.device_path}: {exc}") from exc
        try:
            os.ftruncate(fd, 0)
            os.write(fd, f"PID {os.getpid()} ({Path(os.path.realpath('/proc/self/exe')).name})\n".encode())
            os.fsync(fd)
        except OSError:
            pass
        self.fd = fd

    def release(self) -> None:
        if self.fd < 0:
            return
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(self.fd)
        except OSError:
            pass
        self.fd = -1
