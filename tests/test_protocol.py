"""Protocol codec tests against frames captured from the vendor driver."""

from __future__ import annotations

import unittest

from compx_control import protocol


class ChecksumTests(unittest.TestCase):
    def test_battery_query_from_capture(self) -> None:
        wire = bytes.fromhex("08 04 00 00 00 00 00 00 00 00 00 00 00 00 00 00 49")
        self.assertEqual(bytes([protocol.REPORT_ID]) + protocol.build_frame(protocol.CMD_BATTERY), wire)

    def test_read_eeprom_request_from_capture(self) -> None:
        wire = bytes.fromhex("08 08 00 00 0c 04 00 00 00 00 00 00 00 00 00 00 35")
        self.assertEqual(
            bytes([protocol.REPORT_ID]) + protocol.build_read(0x000C, 4),
            wire,
        )

    def test_identity_reply_from_capture(self) -> None:
        wire = bytes.fromhex("08 10 00 00 00 02 02 53 00 00 00 00 00 00 00 00 e6")
        payload = protocol.decode_report(wire)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload[0], protocol.CMD_CID_MID)
        self.assertEqual(payload[4], 2)
        self.assertEqual((payload[5], payload[6]), (2, 83))

    def test_bad_checksum_is_rejected(self) -> None:
        wire = bytearray.fromhex("08 10 00 00 00 02 02 53 00 00 00 00 00 00 00 00 e6")
        wire[-1] ^= 0xFF
        self.assertIsNone(protocol.decode_report(bytes(wire)))

    def test_write_with_ten_data_bytes(self) -> None:
        frame = protocol.build_write(0x00A9, bytes(range(10)))
        self.assertEqual(len(frame), protocol.PAYLOAD_SIZE)
        self.assertEqual(protocol.checksum(frame[:15]), frame[15])


class DpiTests(unittest.TestCase):
    def test_step50_roundtrip(self) -> None:
        for dpi in (100, 400, 800, 1200, 3200, 1600, 30000):
            packed = protocol.pack_dpi_stage(dpi, dpi, "step50")
            self.assertEqual(protocol.unpack_dpi_stage(packed, "step50"), (dpi, dpi))

    def test_known_800_stage(self) -> None:
        self.assertEqual(
            protocol.pack_dpi_stage(800, 800, "step50").hex(" "),
            "0f 0f 00 37",
        )

    def test_ultra_roundtrip(self) -> None:
        for dpi in (10, 400, 9990, 10000, 10050, 16000, 30000, 30100, 42000):
            packed = protocol.pack_dpi_stage(dpi, dpi, "ultra")
            decoded = protocol.unpack_dpi_stage(packed, "ultra")
            self.assertIsNotNone(decoded, dpi)
            assert decoded is not None
            self.assertEqual(decoded[0], dpi)

    def test_options_follow_vendor_grid(self) -> None:
        options = protocol.dpi_values(100, 30000, "step50")
        self.assertIn(100, options)
        self.assertIn(30000, options)
        self.assertNotIn(105, options)
        self.assertIn(10050, options)


class ColourTests(unittest.TestCase):
    def test_rgb_roundtrip(self) -> None:
        packed = protocol.pack_rgb("#ff6b3d")
        self.assertIsNotNone(packed)
        assert packed is not None
        self.assertEqual(protocol.unpack_rgb(packed), "#ff6b3d")

    def test_invalid_colour(self) -> None:
        self.assertIsNone(protocol.pack_rgb("orange"))


class BcdTests(unittest.TestCase):
    def test_bcd(self) -> None:
        self.assertEqual(protocol.format_bcd("0112"), "1.12")
        self.assertEqual(protocol.format_bcd(""), "")

    def test_pairs(self) -> None:
        pair = protocol.pack_pair(0x1B)
        self.assertEqual(protocol.decode_pair(pair[0], pair[1]), 0x1B)
        self.assertIsNone(protocol.decode_pair(1, 2))


if __name__ == "__main__":
    unittest.main()
