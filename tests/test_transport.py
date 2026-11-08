"""Transport tests using pipes instead of a physical hidraw node."""

from __future__ import annotations

import os
import unittest

from atk_control.protocol import REPORT_ID, CompxTransport, ProtocolError


class _NoReplyTransport(CompxTransport):
    def __init__(self) -> None:
        super().__init__("/dev/null", timeout=0.01)
        self.writes = 0

    def _write(self, payload: bytes) -> None:
        self.writes += 1

    def _read_report(self, timeout: float) -> bytes | None:
        return None


class TransportTests(unittest.TestCase):
    def test_write_prefixes_report_id(self) -> None:
        read_fd, write_fd = os.pipe()
        transport = CompxTransport("/dev/null")
        transport.fd = write_fd
        try:
            transport._write(b"\x07" + b"\x00" * 15)
            data = os.read(read_fd, 64)
            self.assertEqual(data[0], REPORT_ID)
            self.assertEqual(data[1], 0x07)
        finally:
            os.close(read_fd)
            transport.close()

    def test_read_timeout_returns_none(self) -> None:
        read_fd, write_fd = os.pipe()
        transport = CompxTransport("/dev/null")
        transport.fd = read_fd
        try:
            self.assertIsNone(transport._read_report(0.01))
        finally:
            os.close(write_fd)
            transport.close()

    def test_exchange_retries_then_raises(self) -> None:
        transport = _NoReplyTransport()
        with self.assertRaises(ProtocolError):
            transport._exchange(b"\x00" * 16, lambda _reply: True, retries=2)
        self.assertEqual(transport.writes, 2)

    def test_closed_write_raises(self) -> None:
        transport = CompxTransport("/dev/null")
        with self.assertRaises(ProtocolError):
            transport._write(b"\x00" * 16)


if __name__ == "__main__":
    unittest.main()
