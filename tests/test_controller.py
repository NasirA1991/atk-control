"""Controller tests against an in-memory COMPX register file."""

from __future__ import annotations

import unittest

from atk_control import controller, protocol
from atk_control.protocol import DeviceInfo, pack_pair, pack_rgb
from atk_control.state import MouseState


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
        put(self.mem, 0x000A, pack_pair(1))
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
        return 2, 54

    def read_firmware(self, attempts=1):
        return "1.24"

    def read_profile(self):
        return self.profile

    def set_profile(self, profile: int):
        self.profile = profile

    def receiver_online(self):
        return {"online": True, "status": 1, "rf_id": "A4 19 7C"}


class _ProfileCommitFailure(FakeTransport):
    def __init__(self) -> None:
        super().__init__()
        self.profile_calls: list[int] = []

    def set_profile(self, profile: int):
        self.profile_calls.append(profile)
        if len(self.profile_calls) == 2:
            raise protocol.ProtocolError("link dropped during commit")
        self.profile = profile


class _UnverifiedIdentity(FakeTransport):
    def read_identity(self):
        return 2, 49


class _ButtonFailure(FakeTransport):
    fail_writes = False

    def write_eeprom(self, addr: int, data: bytes) -> None:
        if self.fail_writes and addr >= 0x0060 and addr < 0x0078:
            self.fail_writes = False
            raise protocol.ProtocolError("simulated button write failure")
        super().write_eeprom(addr, data)


class _ColorReadFailure(FakeTransport):
    def read_eeprom(self, addr: int, length: int) -> bytes:
        if addr == 0x003C:
            raise protocol.ProtocolError("colour group unavailable")
        return super().read_eeprom(addr, length)


class _BadBattery(FakeTransport):
    def read_battery(self):
        return {"percent": 255, "charging": False, "millivolts": 3980}


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
        self.assertEqual(state.model_name, "MAD R +")
        self.assertEqual(state.sensor, "PAW3395")
        self.assertEqual(state.firmware, "1.24")
        self.assertEqual(state.identity, "2, 54")
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
        self.assertEqual(state.sensor_mode, 1)
        self.assertEqual(state.profile, 2)
        self.assertEqual(len(state.buttons), 5)
        self.assertEqual(state.buttons[0].action, "Left click")

    def test_corrupt_button_record_preserves_slots_and_addresses(self) -> None:
        # Middle is slot 2.  Its bad checksum must not hide Back/Forward or
        # shift their write addresses.
        put(self.fake.mem, 0x0068, b"\x01\x20\x00\x00")
        state = self.ctl.read_full()
        self.assertEqual(len(state.buttons), 5)
        self.assertFalse(state.buttons[2].readable)
        self.assertEqual(state.buttons[2].action, "Unreadable")
        self.assertEqual(state.buttons[3].action_id, "back")
        with self.assertRaises(protocol.ProtocolError):
            self.ctl.set_button_action(2, "back")
        self.assertEqual(self.ctl.set_button_action(3, "forward"), "Forward")
        self.assertIn((0x006C, controller.pack_button_record(1, 16, 0)), self.fake.writes)
        self.assertNotIn((0x0068, controller.pack_button_record(1, 16, 0)), self.fake.writes)

    def test_invalid_battery_reading_is_discarded(self) -> None:
        bad = _BadBattery()
        ctl = controller.Controller(self.ctl.info)
        ctl.transport = bad
        state = ctl.read_full()
        self.assertIsNone(state.battery)
        self.assertIsNone(state.charging)
        self.assertEqual(state.voltage_mv, 3980)

    def test_polling_and_dpi_writes(self) -> None:
        self.assertEqual(self.ctl.set_polling(4000), 4000)
        self.assertEqual(self.ctl.state.polling_rate, 4000)
        self.assertEqual(self.fake.writes[-1], (0x0000, pack_pair(0x20)))
        x, y = self.ctl.set_stage_dpi(2, 800, 800)
        self.assertEqual((x, y), (800, 800))
        self.assertEqual(self.ctl.state.stages[2], (800, 800))
        self.assertEqual(self.ctl.set_active_stage(1), 1)
        self.assertEqual(self.ctl.state.dpi, 800)

    def test_sensor_settings(self) -> None:
        self.assertEqual(self.ctl.set_lift_off_code(2), 2)
        self.assertEqual(self.ctl.state.lod_mm, 2.0)
        self.assertEqual(self.ctl.set_debounce(4), 4)
        self.assertFalse(self.ctl.set_motion_sync(False))
        self.assertEqual(self.ctl.set_sleep(120), 120)
        self.assertTrue(self.ctl.set_straight_line(True))
        self.assertFalse(self.ctl.set_ripple(False))
        self.assertEqual(self.ctl.set_angle(-15, True), (-15, True))

    def test_unverified_model_rejects_button_and_max_writes(self) -> None:
        ctl = controller.Controller(self.ctl.info)
        ctl.transport = _UnverifiedIdentity()
        ctl.read_full()
        self.assertFalse(ctl.state.supports_button_remap)
        self.assertFalse(ctl.state.supports_sensor_max)
        with self.assertRaises(protocol.ProtocolError):
            ctl.set_button_action(4, "back")
        with self.assertRaises(protocol.ProtocolError):
            ctl.set_sensor_mode(2)
        self.assertEqual(ctl.set_sensor_mode(1), 1)

    def test_button_reset_restores_original_on_partial_failure(self) -> None:
        fake = _ButtonFailure()
        self.ctl.transport = fake
        original = [fake.read_eeprom(0x0060 + i * 4, 4) for i in range(5)]
        fake.fail_writes = True
        with self.assertRaises(protocol.ProtocolError):
            self.ctl.reset_buttons()
        self.assertEqual(
            [fake.read_eeprom(0x0060 + i * 4, 4) for i in range(5)], original
        )
        self.assertEqual(self.ctl.state.buttons[0].action_id, "left")

    def test_sensor_mode_and_buttons(self) -> None:
        self.assertEqual(self.ctl.set_sensor_mode(2), 2)
        self.assertEqual(self.ctl.state.sensor_mode, 2)
        self.assertTrue(self.ctl.state.performance_mode)
        self.assertEqual(self.ctl.set_button_action(4, "back"), "Back")
        self.assertEqual(self.ctl.state.buttons[4].action_id, "back")
        self.ctl.reset_buttons()
        self.assertEqual(self.ctl.state.buttons[4].action_id, "forward")

    def test_stage_count_aborts_before_writes_when_colour_group_is_unreadable(self) -> None:
        self.ctl.transport = _ColorReadFailure()
        before = bytes(self.ctl.transport.mem)
        with self.assertRaises(protocol.ProtocolError):
            self.ctl.add_stage()
        self.assertEqual(self.ctl.transport.writes, [])
        self.assertEqual(bytes(self.ctl.transport.mem), before)

    def test_stage_count(self) -> None:
        group = 0x002C + (4 // 2) * 8
        put(self.fake.mem, group + 4, b"\x11\x22\x33\x00")
        self.assertEqual(self.ctl.add_stage(), 5)
        self.assertEqual(self.ctl.state.stage_count, 5)
        self.assertEqual(self.ctl.state.stages[-1], (3200, 3200))
        self.assertEqual(self.fake.read_eeprom(group + 4, 4), b"\x11\x22\x33\x00")
        self.assertEqual(self.ctl.remove_last_stage(), 4)
        self.assertEqual(self.ctl.state.stage_count, 4)

    def test_commit_settings_round_trips_profile(self) -> None:
        self.ctl.state.profile = 1
        self.ctl.commit_settings()
        self.assertEqual(self.ctl.state.profile, 1)
        self.assertEqual(self.ctl.transport.profile, 0)

    def test_commit_settings_attempts_profile_restore_after_failure(self) -> None:
        fake = _ProfileCommitFailure()
        self.ctl.transport = fake
        self.ctl.state.profile = 1
        with self.assertRaises(protocol.ProtocolError):
            self.ctl.commit_settings()
        self.assertEqual(fake.profile_calls, [1, 0, 0])

    def test_lighting_and_profile(self) -> None:
        mode, brightness, speed = self.ctl.set_led_mode(2, 2, 2)
        self.assertEqual((mode, brightness, speed), (2, 2, 2))
        self.assertEqual(self.ctl.set_performance_mode(False), False)
        self.assertEqual(self.ctl.set_stage_color(1, "#112233"), "#112233")
        self.assertEqual(self.ctl.set_stage_color(1, "112233"), "#112233")
        self.assertEqual(self.ctl.set_stage_color(1, "AABBCC"), "#aabbcc")
        self.assertEqual(self.ctl.set_profile(3), 3)

    def test_read_live(self) -> None:
        live = self.ctl.read_live()
        self.assertIsInstance(live, MouseState)
        self.assertEqual(live.battery, 76)
        self.assertEqual(live.polling_rate, 8000)

    def test_raw_register_dump(self) -> None:
        raw = self.ctl.collect_raw_registers(0x0000, 0x0020)
        self.assertIn(0x0000, raw)
        self.assertIsNotNone(raw[0x0000])
        assert raw[0x0000] is not None
        self.assertEqual(len(raw[0x0000]), 10)

    def test_bad_dpi_value_is_rejected(self) -> None:
        with self.assertRaises(protocol.ProtocolError):
            self.ctl.set_stage_dpi(0, 12345, 12345)


if __name__ == "__main__":
    unittest.main()


class _FakeV2Transport:
    def __init__(self, battery=None):
        self.battery = battery or {"percent": 64, "charging": True, "millivolts": 4020}
        self.opened = False
        self.closed = False

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def read_battery(self):
        if isinstance(self.battery, Exception):
            raise self.battery
        return dict(self.battery)


class V2ControllerTests(unittest.TestCase):
    def _controller(self):
        info = DeviceInfo(
            "/dev/hidraw-test", 0x373B, 0x11DC,
            "MADLIONS NK mouse 8K NANO dongle", "0003", "0201",
            True, b"", "v2", True,
        )
        session = controller.V2Controller(info)
        session.transport = _FakeV2Transport()
        return session

    def test_read_full_is_battery_only(self) -> None:
        session = self._controller()
        state = session.open()
        self.assertTrue(session.transport.opened)
        self.assertTrue(state.telemetry_only)
        self.assertTrue(state.read_only)
        self.assertEqual(state.battery, 64)
        self.assertTrue(state.charging)
        self.assertEqual(state.model_name, "ATK Dragonfly A9 Pro Max 2.0")
        self.assertEqual(state.polling_rate, 0)
        self.assertFalse(state.supports_button_remap)
        self.assertFalse(state.supports_lighting)

    def test_read_live_updates_battery(self) -> None:
        session = self._controller()
        session.read_full()
        session.transport.battery = {"percent": 55, "charging": False, "millivolts": 3900}
        state = session.read_live()
        self.assertEqual(state.battery, 55)
        self.assertFalse(state.charging)
        self.assertEqual(state.voltage_mv, 3900)

    def test_online_status_reports_failure(self) -> None:
        session = self._controller()
        self.assertTrue(session.online_status())
        session.transport.battery = protocol.ProtocolError("asleep")
        self.assertIsNone(session.online_status())

    def test_factory_picks_v2(self) -> None:
        info = DeviceInfo("/dev/hidraw-test", 0x373B, 0x11DC, "NK dongle")
        info.protocol = "v2"
        self.assertIsInstance(controller.controller_for(info), controller.V2Controller)
        info.protocol = "v1"
        self.assertIsInstance(controller.controller_for(info), controller.Controller)
