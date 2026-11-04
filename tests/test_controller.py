"""Controller tests against an in-memory COMPX register file."""

from __future__ import annotations

import unittest

from compx_control import controller, devices, protocol
from compx_control.protocol import DeviceInfo, pack_pair, pack_rgb
from compx_control.state import MouseState


def put(mem: bytearray, addr: int, data: bytes) -> None:
    mem[addr:addr + len(data)] = data


class FakeTransport:
    def __init__(self) -> None:
        self.mem = bytearray(0x2000)
        self.writes: list[tuple[int, bytes]] = []
        self.profile = 1
        self.closed = False
        self._fill()

    def _fill(self) -> None:
        put(self.mem, 0x0000, pack_pair(0x40) + pack_pair(4) + pack_pair(2) + b"\x00\x00\x00\x00")
        for index, dpi in enumerate((400, 800, 1600, 3200)):
            put(self.mem, 0x000C + index * 4, protocol.pack_dpi_stage(dpi, dpi, "step50"))
        colours = ("#4cd7d0", "#8ee36b", "#ff8a4c", "#ffd166")
        for index, colour in enumerate(colours):
            group = 0x002C + (index // 2) * 8
            if not self.mem[group:group + 4]:
                put(self.mem, group, b"\x00\x00\x00\x00" * 2)
            record = pack_rgb(colour)
            assert record
            put(self.mem, group + (index % 2) * 4, record)
        put(self.mem, 0x004C, pack_pair(1) + pack_pair(0x80) + pack_pair(3) + pack_pair(1))
        put(self.mem, 0x00A9, pack_pair(2) + pack_pair(1) + pack_pair(30) + pack_pair(0) + pack_pair(1))
        put(self.mem, 0x00BD, pack_pair(0) + pack_pair(0))
        put(self.mem, 0x00B5, bytes((1, 0x54, 6, 0x4F, 1, 0x54)))
        put(self.mem, 0x000A, pack_pair(4))
        buttons = (
            (1, 1, 0), (1, 2, 0),
            (1, 4, 0), (1, 8, 0),
            (1, 16, 0), (2, 1, 0),
        )
        for index, (key_class, value1, value2) in enumerate(buttons):
            check = (0x55 - key_class - value1 - value2) & 0xFF
            put(self.mem, 0x0060 + index * 4, bytes((key_class, value1, value2, check)))

    def close(self) -> None:
        self.closed = True

    def read_eeprom(self, addr: int, length: int) -> bytes:
        return bytes(self.mem[addr:addr + length])

    def write_eeprom(self, addr: int, data: bytes) -> None:
        self.writes.append((addr, bytes(data)))
        self.mem[addr:addr + len(data)] = data

    def read_battery(self):
        return {"percent": 76, "charging": False, "millivolts": 3980}

    def read_identity(self):
        return 2, 49

    def read_firmware(self):
        return "1.24"

    def read_profile(self):
        return self.profile

    def set_profile(self, profile: int):
        self.profile = profile

    def receiver_online(self):
        return {"online": True, "status": 1, "rf_id": "A4 19 7C"}


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        info = DeviceInfo(
            path="/dev/hidraw-test",
            vendor_id=0x373B,
            product_id=0x1040,
            product_name="Compx MAD 8K DONGLE",
            bcd_device="0112",
        )
        self.ctl = controller.Controller(info)
        self.fake = FakeTransport()
        self.ctl.transport = self.fake
        self.state = self.ctl.read_full()

    def test_full_read(self) -> None:
        state = self.state
        self.assertEqual(state.model_name, "MAD R")
        self.assertEqual(state.sensor, "PAW3395")
        self.assertEqual(state.firmware, "")
        self.assertEqual(state.identity, "2, 49")
        self.assertTrue(state.via_receiver)
        self.assertEqual(state.receiver_name, "MAD 8K Dongle")
        self.assertEqual(state.battery, 76)
        self.assertFalse(state.charging)
        self.assertEqual(state.voltage_mv, 3980)
        self.assertEqual(state.polling_rate, 8000)
        self.assertEqual(state.dpi, 1600)
        self.assertEqual(state.stage_count, 4)
        self.assertEqual(state.active_stage, 2)
        self.assertEqual(state.stage_colors, ["#4cd7d0", "#8ee36b", "#ff8a4c", "#ffd166"])
        self.assertEqual(state.lod_mm, 1.0)
        self.assertEqual(state.debounce_ms, 2)
        self.assertTrue(state.motion_sync)
        self.assertEqual(state.sleep_seconds, 300)
        self.assertTrue(state.ripple_control)
        self.assertFalse(state.straight_line)
        self.assertTrue(state.supports_angle)
        self.assertTrue(state.supports_lighting)
        self.assertTrue(state.supports_performance_mode)
        self.assertEqual(state.profile, 2)
        self.assertEqual(len(state.buttons), 5)
        self.assertEqual(state.buttons[0].action, "Left click")

    def test_polling_and_dpi_writes(self) -> None:
        self.assertEqual(self.ctl.set_polling(4000), 4000)
        self.assertEqual(self.ctl.state.polling_rate, 4000)
        x, y = self.ctl.set_stage_dpi(2, 800, 800)
        self.assertEqual((x, y), (800, 800))
        self.assertEqual(self.ctl.state.stages[2], (800, 800))
        self.assertEqual(self.ctl.set_active_stage(1), 1)
        self.assertEqual(self.ctl.state.dpi, 800)

    def test_sensor_settings(self) -> None:
        self.assertEqual(self.ctl.set_lift_off_code(4), 4)
        self.assertEqual(self.ctl.set_debounce(4), 4)
        self.assertFalse(self.ctl.set_motion_sync(False))
        self.assertEqual(self.ctl.set_sleep(120), 120)
        self.assertTrue(self.ctl.set_straight_line(True))
        self.assertFalse(self.ctl.set_ripple(False))
        self.assertEqual(self.ctl.set_angle(-15, True), (-15, True))

    def test_lighting_and_profile(self) -> None:
        mode, brightness, speed = self.ctl.set_led_mode(2, 2, 2)
        self.assertEqual((mode, brightness, speed), (2, 2, 2))
        self.assertEqual(self.ctl.set_performance_mode(False), False)
        self.assertEqual(self.ctl.set_stage_color(1, "#112233"), "#112233")
        self.assertEqual(self.ctl.set_profile(3), 3)

    def test_read_live(self) -> None:
        live = self.ctl.read_live()
        self.assertIsInstance(live, MouseState)
        self.assertEqual(live.battery, 76)
        self.assertEqual(live.polling_rate, 8000)

    def test_bad_dpi_value_is_rejected(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            self.ctl.set_stage_dpi(0, 12345, 12345)


if __name__ == "__main__":
    unittest.main()
