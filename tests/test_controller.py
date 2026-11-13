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


class _ExperimentalIdentity(FakeTransport):
    def read_identity(self):
        return 2, 36


class _UnverifiedIdentity(FakeTransport):
    def read_identity(self):
        return 9, 9


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
        info = DeviceInfo(
            path="/dev/hidraw-test",
            vendor_id=0x9999,
            product_id=0x9999,
            product_name="Unknown mouse",
            bcd_device="0000",
        )
        ctl = controller.Controller(info)
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


    def test_experimental_catalog_model_is_read_only(self) -> None:
        info = DeviceInfo(
            path="/dev/hidraw-test",
            vendor_id=0x373B,
            product_id=0x1014,
            product_name="ATK F1 Pro",
            bcd_device="0112",
        )
        ctl = controller.Controller(info)
        ctl.transport = _ExperimentalIdentity()
        state = ctl.read_full()
        self.assertEqual(state.model_name, "ATK F1 Pro")
        self.assertTrue(state.experimental)
        self.assertTrue(state.read_only)
        self.assertTrue(ctl.read_only)


if __name__ == "__main__":
    unittest.main()


class _FakeV2Transport:
    def __init__(self):
        self.opened = False
        self.closed = False
        self.battery = {"percent": 64, "charging": True, "millivolts": None}
        self.config = bytearray(18)
        self.config[2] = 0
        self.config[5] = 0
        self.config[6] = 0
        self.config[7] = 0
        self.config[8] = 0
        self.config[9:11] = (120).to_bytes(2, "little")
        self.config[11] = 0
        self.dpi = bytearray(66)
        self.dpi[0] = 0
        self.dpi[1] = 4
        for index, (x, y, color) in enumerate((
            (1600, 1600, "#ff0000"), (3200, 3200, "#00ff00"),
            (6400, 6400, "#0000ff"), (12800, 12800, "#ffffff"),
        )):
            self._put_stage(index, x, y, color)
        self.sensor = 0
        self.light = bytes((2, 170, 15))
        self.buttons = bytearray(30)
        for index, action in enumerate((
            (1, 0, 0, 0), (1, 0, 1, 0), (1, 0, 2, 0),
            (1, 0, 3, 0), (1, 0, 4, 0), (10, 0, 0, 0),
        )):
            self.buttons[index * 5:index * 5 + 5] = bytes(action) + b"\0"
        self.identity = (2, 1)

    def _put_stage(self, index, x, y, color):
        offset = 2 + index * 8
        self.dpi[offset:offset + 2] = x.to_bytes(2, "little")
        self.dpi[offset + 2:offset + 4] = y.to_bytes(2, "little")
        r, g, b = bytes.fromhex(color.lstrip("#"))
        self.dpi[offset + 4:offset + 7] = bytes((b, g, r))

    def open(self):
        self.opened = True

    def close(self):
        self.closed = True

    def read_identity(self):
        return self.identity

    def read_version(self):
        return "1.03"

    def read_config(self):
        return bytes(self.config)

    def read_dpi(self):
        return bytes(self.dpi)

    def read_sensor_mode(self):
        return self.sensor

    def read_lighting(self):
        return self.light

    def read_buttons(self):
        return bytes(self.buttons)

    def read_battery(self):
        if isinstance(self.battery, Exception):
            raise self.battery
        return dict(self.battery)

    def read_online(self):
        return True

    def read_dongle_version(self):
        return "1.0.19"

    def set_rate(self, hertz):
        code = protocol.V2_RATE_TO_CODE[hertz]
        self.config[2] = code
        return hertz

    def set_dpi(self, stage, x, y, color, active):
        self._put_stage(stage, x, y, color)
        if active:
            self.dpi[0] = stage

    def set_lod(self, level):
        self.config[5] = level - 1

    def set_motion_sync(self, enabled):
        self.config[6] = int(enabled)

    def set_angle_snap(self, enabled):
        self.config[7] = int(enabled)

    def set_ripple(self, enabled):
        self.config[8] = int(enabled)

    def set_debounce(self, milliseconds):
        self.config[11] = milliseconds

    def set_sleep(self, seconds):
        self.config[9:11] = seconds.to_bytes(2, "little")

    def set_sensor_mode(self, code):
        self.sensor = code

    def set_lighting(self, mode, brightness, speed):
        self.light = bytes((mode, brightness, speed))

    def set_profile(self, index):
        self.config[0] = index - 1

    def set_button(self, index, action):
        self.buttons[index * 5:index * 5 + 5] = bytes(action) + b"\0"

    def reset(self):
        self.buttons = bytearray(30)


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

    def test_full_reads_settings(self) -> None:
        session = self._controller()
        state = session.open()
        self.assertTrue(session.transport.opened)
        self.assertFalse(state.telemetry_only)
        self.assertFalse(state.read_only)
        self.assertEqual(state.model_name, "ATK Dragonfly A9 Pro Max 2.0")
        self.assertEqual(state.sensor, "PAW3395Ultra")
        self.assertEqual(state.firmware, "1.03")
        self.assertEqual(state.dongle_firmware, "1.0.19")
        self.assertEqual(state.dpi, 1600)
        self.assertEqual(state.stage_count, 4)
        self.assertEqual(state.polling_rate, 1000)
        self.assertEqual(state.profile, 1)
        self.assertEqual(state.lod_code, 1)
        self.assertEqual(state.sleep_seconds, 120)
        self.assertEqual(len(state.buttons), 6)
        self.assertEqual(state.buttons[2].action_id, "middle")
        self.assertTrue(state.supports_button_remap)
        self.assertTrue(state.supports_lighting)
        self.assertFalse(state.supports_angle)
        self.assertFalse(state.supports_stage_count)
        self.assertGreaterEqual(state.battery, 0)

    def test_read_live_updates_battery_and_config(self) -> None:
        session = self._controller()
        session.read_full()
        session.transport.battery = {"percent": 55, "charging": False, "millivolts": None}
        session.transport.config[2] = protocol.V2_RATE_TO_CODE[8000]
        state = session.read_live()
        self.assertEqual(state.battery, 55)
        self.assertFalse(state.charging)
        self.assertEqual(state.polling_rate, 8000)

    def test_polling_write(self) -> None:
        session = self._controller()
        session.read_full()
        self.assertEqual(session.set_polling(8000), 8000)
        self.assertEqual(session.state.polling_rate, 8000)

    def test_dpi_write_and_active_stage(self) -> None:
        session = self._controller()
        session.read_full()
        self.assertEqual(session.set_stage_dpi(1, 3200, 3200), (3200, 3200))
        self.assertEqual(session.set_active_stage(1), 1)
        self.assertEqual(session.state.active_stage, 1)
        self.assertEqual(session.state.dpi, 3200)

    def test_button_remap_and_reset(self) -> None:
        session = self._controller()
        session.read_full()
        self.assertEqual(session.set_button_action(2, "back"), "Back")
        self.assertEqual(session.state.buttons[2].action_id, "back")
        session.reset_buttons()
        self.assertEqual(session.state.buttons[2].action_id, "middle")

    def test_lighting_and_profile(self) -> None:
        session = self._controller()
        session.read_full()
        self.assertEqual(session.set_led_mode(1, 2, 1)[0], 1)
        self.assertEqual(session.set_led_mode(0, 0, 0)[0], 0)
        self.assertEqual(session.set_profile(3), 3)
        self.assertEqual(session.state.profile, 3)

    def test_online_status_reports_failure(self) -> None:
        session = self._controller()
        session.transport.read_online = lambda: False
        self.assertFalse(session.online_status())
        session.transport.read_online = lambda: True
        self.assertTrue(session.online_status())

    def test_wired_link_has_no_dongle_firmware(self) -> None:
        info = DeviceInfo(
            "/dev/hidraw-cable", 0x373B, 0x1264,
            "ATK ATK A9 PRO MAX 2.0 NK", "0301", "0100",
            True, b"", "v2", True,
        )
        session = controller.V2Controller(info)
        transport = _FakeV2Transport()

        def unexpected():
            raise AssertionError("command 0x88 must not run on a wired link")

        transport.read_dongle_version = unexpected
        session.transport = transport
        state = session.read_full()
        self.assertEqual(state.dongle_firmware, "")

    def test_unknown_v2_is_read_only(self) -> None:
        session = self._controller()
        session.transport.identity = (9, 9)
        state = session.read_full()
        self.assertTrue(state.read_only)
        self.assertTrue(state.telemetry_only)
        self.assertFalse(state.supports_button_remap)

    def test_missing_identity_does_not_fall_back_to_usb_id(self) -> None:
        session = self._controller()

        def no_identity():
            raise protocol.ProtocolError("identity unavailable")

        session.transport.read_identity = no_identity
        state = session.read_full()
        self.assertTrue(state.read_only)
        self.assertTrue(state.telemetry_only)

    def test_factory_picks_v2(self) -> None:
        info = DeviceInfo("/dev/hidraw-test", 0x373B, 0x11DC, "NK dongle")
        info.protocol = "v2"
        self.assertIsInstance(controller.controller_for(info), controller.V2Controller)
        info.protocol = "v1"
        self.assertIsInstance(controller.controller_for(info), controller.Controller)


class _R1NKTransport(_FakeV2Transport):
    """VXE R1 NK: eight DPI slots, unused ones at 0, buttons as class 0."""

    def __init__(self) -> None:
        super().__init__()
        self.identity = (2, 8)
        self.dpi = bytearray(66)
        self.dpi[0] = 2
        self.dpi[1] = 8
        for index, dpi in enumerate((400, 800, 1600, 3200)):
            self._put_stage(index, dpi, dpi, "#ffffff")
        self.buttons = bytearray(30)
        self.light = b"\x00\x00\x00"

    def set_button(self, index, action):
        # The firmware stores a slot's own default as class 0.
        default = controller.V2_BUTTON_ACTIONS[controller.DEFAULT_BUTTON_ACTIONS[index]]
        record = bytes(5) if tuple(action) == default else bytes(action) + b"\0"
        self.buttons[index * 5:index * 5 + 5] = record


class R1NKControllerTests(unittest.TestCase):
    def _controller(self):
        info = DeviceInfo(
            "/dev/hidraw-nk", 0x373B, 0x1216,
            "ATK NK mouse NANO dongle", "0800", "0100",
            True, b"", "v2", True,
        )
        session = controller.V2Controller(info)
        session.transport = _R1NKTransport()
        return session

    def test_unused_dpi_slots_are_trimmed(self) -> None:
        state = self._controller().read_full()
        self.assertEqual(state.model_name, "VXE R1 NK")
        self.assertEqual(state.sensor, "PAW3395SE")
        self.assertFalse(state.read_only)
        self.assertEqual(state.stage_count, 4)
        self.assertEqual(
            state.stages, [(400, 400), (800, 800), (1600, 1600), (3200, 3200)]
        )
        self.assertEqual(state.active_stage, 2)
        self.assertEqual(state.dpi, 1600)

    def test_factory_default_buttons_are_named(self) -> None:
        state = self._controller().read_full()
        self.assertEqual(
            [button.action_id for button in state.buttons],
            ["left", "right", "middle", "back", "forward", "dpi_cycle"],
        )
        self.assertTrue(all(button.readable for button in state.buttons))

    def test_writing_a_slot_default_verifies(self) -> None:
        session = self._controller()
        session.read_full()
        self.assertEqual(session.set_button_action(2, "middle"), "Middle click")
        self.assertEqual(session.state.buttons[2].action_id, "middle")

    def test_remap_to_a_different_action_verifies(self) -> None:
        session = self._controller()
        session.read_full()
        self.assertEqual(session.set_button_action(3, "dpi_up"), "DPI up")
        self.assertEqual(session.state.buttons[3].action_id, "dpi_up")
        self.assertEqual(session.state.buttons[2].action_id, "middle")

    def test_unsupported_controls_are_reported_off(self) -> None:
        state = self._controller().read_full()
        self.assertFalse(state.supports_angle)
        self.assertFalse(state.supports_lighting)
        self.assertFalse(state.supports_stage_colors)
        self.assertFalse(state.supports_performance_mode)
        self.assertTrue(state.supports_button_remap)


class _A9UltimateIdentity(FakeTransport):
    def read_identity(self):
        return 1, 3


class A9UltimateTests(unittest.TestCase):
    def _controller(self):
        info = DeviceInfo(
            "/dev/hidraw-ultimate", 0x373B, 0x11B6,
            "Compx ATK A9 Ultimate", "0303", "0303",
            True, b"", "v1", True,
        )
        session = controller.Controller(info)
        session.transport = _A9UltimateIdentity()
        return session

    def test_identity_enables_settings(self) -> None:
        state = self._controller().read_full()
        self.assertEqual(state.model_name, "ATK A9 Ultimate")
        self.assertEqual((state.cid, state.mid), (1, 3))
        self.assertEqual(state.sensor, "PAW3950Ultra")
        self.assertFalse(state.read_only)
        self.assertTrue(state.supports_button_remap)
        self.assertTrue(state.supports_lighting)

    def test_stage_records_decode_with_the_ultra_encoding(self) -> None:
        # The report's raw stages were 0x27/0x4f/0x9f/0x3f-0x44: 400-3200 DPI
        # under the ultra encoding, not the 2000-16000 the step-50 table gives.
        transport = _A9UltimateIdentity()
        for index, dpi in enumerate((400, 800, 1600, 3200)):
            put(transport.mem, 0x000C + index * 4,
                protocol.pack_dpi_stage(dpi, dpi, "ultra"))
        session = self._controller()
        session.transport = transport
        state = session.read_full()
        self.assertEqual(state.stages, [(400, 400), (800, 800), (1600, 1600), (3200, 3200)])
        self.assertEqual(state.dpi, 1600)

    def test_cable_keeps_its_reported_polling_rate(self) -> None:
        session = self._controller()
        state = session.read_full()
        self.assertEqual(state.polling_rate, 8000)
        self.assertEqual(session.caps.link_ceiling, 8000)
        self.assertIn(4000, session.caps.polling_rates)
        self.assertEqual(session.set_polling(4000), 4000)


if __name__ == "__main__":
    unittest.main()
