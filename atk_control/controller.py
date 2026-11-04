"""High-level COMPX mouse controller built on the 0x55 EEPROM transport."""

from __future__ import annotations

import time
from . import devices, protocol
from .protocol import (
    ADDR_ADVANCED,
    ADDR_ANGLE,
    ADDR_DPI_BASE,
    ADDR_DPI_LIGHT,
    ADDR_LIFT_OFF,
    ADDR_SENSOR_MODE,
    ADDR_STAGE_COLOR_BASE,
    ADDR_SYSTEM,
    CompxTransport,
    DeviceInfo,
    DeviceNotFound,
    ProtocolError,
    decode_pair,
    pack_dpi_stage,
    pack_pair,
    pack_rgb,
    unpack_dpi_stage,
    unpack_rgb,
)
from .state import Button, MouseState

BUTTON_ADDRESSES = (0x0060, 0x0068, 0x0070)
BUTTON_NAMES = ("Left", "Right", "Middle", "Back", "Forward", "Bottom")

BUTTON_CLASS_LABELS = {
    0x00: "Disabled",
    0x01: "Mouse button",
    0x02: "DPI control",
    0x03: "Horizontal scroll",
    0x04: "Fire key",
    0x05: "Shortcut",
    0x06: "Macro",
    0x07: "Polling rate",
    0x08: "Lighting",
    0x09: "Profile",
    0x0A: "DPI lock",
    0x0B: "Wheel",
}
MOUSE_ACTION_LABELS = {
    0x00: "Disabled",
    0x01: "Left click",
    0x02: "Right click",
    0x04: "Middle click",
    0x08: "Back",
    0x10: "Forward",
}
DPI_ACTION_LABELS = {0x01: "DPI cycle", 0x02: "DPI up", 0x03: "DPI down"}


def decode_button_action(key_class: int, value1: int, value2: int) -> str:
    if key_class == 0x00:
        return "Disabled"
    if key_class == 0x01:
        return MOUSE_ACTION_LABELS.get(value1, f"Mouse 0x{value1:02x}")
    if key_class == 0x02:
        return DPI_ACTION_LABELS.get(value1, "DPI control")
    label = BUTTON_CLASS_LABELS.get(key_class, f"Action 0x{key_class:02x}")
    return f"{label} (0x{value1:02x}, 0x{value2:02x})"


class Controller:
    """One open configuration session.

    A controller is intentionally not thread-safe: a worker thread owns it.
    """

    def __init__(self, info: DeviceInfo, debug: bool = False) -> None:
        self.info = info
        self.transport = CompxTransport(info.path, debug=debug)
        self.state = MouseState(
            vendor_id=info.vendor_id,
            product_id=info.product_id,
            usb_name=info.product_name,
            usb_bcd=protocol.format_bcd(info.bcd_device),
        )
        self.model: devices.Model | None = None
        self.receiver: devices.Receiver | None = None
        self.caps: devices.Capabilities = devices.default_capabilities()
        self.read_only = True

    # -- lifecycle ---------------------------------------------------------
    def open(self) -> MouseState:
        self.transport.open()
        try:
            return self.read_full()
        except Exception:
            self.transport.close()
            raise

    def close(self) -> None:
        self.transport.close()

    @property
    def path(self) -> str:
        return self.info.path

    @property
    def is_receiver(self) -> bool:
        return self.info.is_receiver

    # -- reads -------------------------------------------------------------
    def _read_optional(self, addr: int, length: int, attempts: int = 1) -> bytes | None:
        try:
            return self._read_with_retries(addr, length, attempts)
        except ProtocolError:
            return None

    def _read_with_retries(self, addr: int, length: int, attempts: int = 2) -> bytes:
        last: Exception | None = None
        for _ in range(max(1, attempts)):
            try:
                return self.transport.read_eeprom(addr, length)
            except DeviceNotFound:
                raise
            except ProtocolError as exc:
                last = exc
                time.sleep(0.03)
        assert last is not None
        raise last

    def _identify(self) -> tuple[int | None, int | None, str]:
        firmware = ""
        # The 8K receiver does not forward command 0x12; do not spend a long
        # timeout on it before identifying the mouse.
        if not self.info.is_receiver:
            try:
                firmware = self.transport.read_firmware(attempts=1)
            except ProtocolError:
                pass
        cid = mid = None
        last: Exception | None = None
        for _ in range(3):
            try:
                cid, mid = self.transport.read_identity()
                break
            except ProtocolError as exc:
                last = exc
                time.sleep(0.12)
        if cid is None and self.model is None and self.receiver is not None:
            sleep_hint = (
                "The receiver answered, but the paired mouse did not. "
                "Turn the mouse on or move it, then retry."
            )
            raise ProtocolError(sleep_hint) from last
        return cid, mid, firmware

    def _decode_system(self, system: bytes) -> tuple[int, int, int]:
        rate_code = system[0] if system else 0
        polling = protocol.POLLING_FROM_CODE.get(rate_code, self.state.polling_rate)
        stage_count = 1
        active = 0
        if len(system) >= 4:
            count = decode_pair(system[2], system[3])
            if count is not None:
                stage_count = max(1, min(8, count))
        if len(system) >= 6:
            active_value = decode_pair(system[4], system[5])
            if active_value is not None:
                active = max(0, min(stage_count - 1, active_value))
        return polling, stage_count, active

    def _read_stages(self, count: int) -> list[tuple[int, int]]:
        family = self.caps.sensor.family
        stages: list[tuple[int, int]] = []
        for index in range(max(1, min(count, 8))):
            raw = self._read_with_retries(ADDR_DPI_BASE + index * 4, 4)
            stage = unpack_dpi_stage(raw, family)
            if stage is None:
                raise ProtocolError(f"DPI stage {index + 1} failed its checksum")
            stages.append(stage)
        return stages

    def _read_colors(self, count: int) -> list[str]:
        colors: list[str] = []
        for index in range(max(1, min(count, 8))):
            group_address = ADDR_STAGE_COLOR_BASE + (index // 2) * 8
            raw = self._read_optional(group_address, 8)
            if raw is None:
                return []
            color = unpack_rgb(raw[(index % 2) * 4:(index % 2) * 4 + 4])
            if color is None:
                return []
            colors.append(color)
        return colors

    def _read_advanced(self) -> dict[str, int | bool | None]:
        raw = self._read_optional(ADDR_ADVANCED, 10)
        result: dict[str, int | bool | None] = {
            "debounce": None,
            "motion_sync": None,
            "sleep_seconds": None,
            "straight_line": None,
            "ripple": None,
        }
        if raw is None or len(raw) < 10:
            return result
        debounce = decode_pair(raw[0], raw[1])
        if debounce is not None:
            result["debounce"] = debounce
        motion = decode_pair(raw[2], raw[3])
        if motion is not None and motion in (0, 1):
            result["motion_sync"] = bool(motion)
        sleep_units = decode_pair(raw[4], raw[5])
        if sleep_units is not None and sleep_units > 0:
            result["sleep_seconds"] = sleep_units * protocol.SLEEP_STEP_SECONDS
        straight = decode_pair(raw[6], raw[7])
        if straight is not None and straight in (0, 1):
            result["straight_line"] = bool(straight)
        ripple = decode_pair(raw[8], raw[9])
        if ripple is not None and ripple in (0, 1):
            result["ripple"] = bool(ripple)
        return result

    def _read_angle(self) -> tuple[int | None, bool | None]:
        raw = self._read_optional(ADDR_ANGLE, 4)
        if raw is None or len(raw) < 4:
            return None, None
        angle = decode_pair(raw[0], raw[1])
        enabled = decode_pair(raw[2], raw[3])
        if angle is None or enabled is None or enabled not in (0, 1):
            return None, None
        signed = angle - 0x100 if angle > 0x7F else angle
        if not -30 <= signed <= 30:
            return None, None
        return signed, bool(enabled)

    def _read_sensor_mode(self) -> bool | None:
        raw = self._read_optional(ADDR_SENSOR_MODE, 6)
        if raw is None or len(raw) < 6:
            return None
        if raw[2] != 0x06 or raw[3] != 0x4F:
            return None
        mode = decode_pair(raw[4], raw[5])
        return bool(mode) if mode in (0, 1) else None

    def _read_lighting(self) -> tuple[int | None, int | None, int | None]:
        raw = self._read_optional(ADDR_DPI_LIGHT, 8)
        if raw is None or len(raw) < 8:
            return None, None, None
        effect = 0 if raw[0:2] == b"\x00\x00" else decode_pair(raw[0], raw[1])
        brightness_raw = 0 if raw[2:4] == b"\x00\x00" else decode_pair(raw[2], raw[3])
        speed = decode_pair(raw[4], raw[5])
        enabled = 0 if raw[6:8] == b"\x00\x00" else decode_pair(raw[6], raw[7])
        if effect is None or brightness_raw is None or speed is None or enabled is None:
            return None, None, None
        if effect not in (0, 1, 2) or enabled not in (0, 1):
            return None, None, None
        mode = 0 if effect == 0 or enabled == 0 else (2 if effect == 2 else 1)
        brightness = 0 if brightness_raw <= 0x10 else (1 if brightness_raw <= 0x80 else 2)
        speed_index = 0
        if speed >= 5:
            speed_index = 2
        elif speed >= 3:
            speed_index = 1
        return mode, brightness, speed_index

    def _read_profile(self) -> int | None:
        profile = self.transport.read_profile()
        if profile is None:
            return None
        return profile + 1

    def _read_buttons(self, include_bottom: bool = True) -> list[Button]:
        buttons: list[Button] = []
        for group_index, address in enumerate(BUTTON_ADDRESSES):
            raw = self._read_optional(address, 8)
            if raw is None or len(raw) < 8:
                return []
            for slot in range(2):
                record = raw[slot * 4:(slot + 1) * 4]
                if len(record) < 4:
                    return []
                key_class, value1, value2, check = record
                valid = (key_class + value1 + value2 + check) & 0xFF == 0x55
                index = group_index * 2 + slot
                if index >= len(BUTTON_NAMES):
                    continue
                if index == 5 and not include_bottom:
                    continue
                if not valid:
                    continue
                buttons.append(
                    Button(
                        name=BUTTON_NAMES[index],
                        action=decode_button_action(key_class, value1, value2),
                        raw=" ".join(f"{byte:02x}" for byte in record),
                    )
                )
        return buttons

    def _read_receiver(self) -> dict | None:
        if not self.info.is_receiver:
            return None
        return self.transport.receiver_online()

    def read_full(self) -> MouseState:
        """Read identity and all readable settings.  Missing optional rows are OK."""
        self.receiver = devices.receiver_for(self.info.product_id, self.info.product_name)
        cid, mid, firmware = self._identify()
        self.model = devices.model_for(
            cid, mid, self.info.vendor_id, self.info.product_id, self.info.product_name
        )
        self.read_only = self.model is None
        # Use the identified sensor's DPI family while decoding stages.  The
        # conservative default would decode a PAW3950 Ultra stage incorrectly.
        self.caps = devices.capabilities_for(
            model=self.model,
            receiver=self.receiver,
            sensor_name=self.model.sensor if self.model else None,
            usb_name=self.info.product_name,
        )

        system = self._read_with_retries(ADDR_SYSTEM, 10)
        polling, count, active = self._decode_system(system)
        stages = self._read_stages(count)
        state = MouseState(
            vendor_id=self.info.vendor_id,
            product_id=self.info.product_id,
            usb_name=self.info.product_name,
            cid=cid,
            mid=mid,
            model_name=self.model.name if self.model else devices.fallback_name(self.info.product_name),
            brand=self.model.brand if self.model else ("VXE" if "vxe" in self.info.product_name.lower() else "ATK"),
            sensor=self.model.sensor if self.model else "Unknown sensor",
            firmware=firmware,
            usb_bcd=protocol.format_bcd(self.info.bcd_device),
            via_receiver=self.info.is_receiver,
            receiver_name=self.receiver.name if self.receiver else "",
            receiver_pid=self.receiver.product_id if self.receiver else None,
            wired=not self.info.is_receiver,
            read_only=self.model is None,
            dpi=stages[active][0],
            dpi_y=stages[active][1],
            stages=stages,
            active_stage=active,
            stage_count=count,
            polling_rate=polling,
        )

        try:
            battery = self.transport.read_battery()
            state.battery = battery.get("percent")
            state.charging = battery.get("charging")
            state.voltage_mv = battery.get("millivolts")
        except ProtocolError:
            pass

        advanced = self._read_advanced()
        state.debounce_ms = advanced["debounce"] if isinstance(advanced["debounce"], int) else None
        state.motion_sync = advanced["motion_sync"] if isinstance(advanced["motion_sync"], bool) else None
        state.sleep_seconds = advanced["sleep_seconds"] if isinstance(advanced["sleep_seconds"], int) else None
        state.straight_line = advanced["straight_line"] if isinstance(advanced["straight_line"], bool) else None
        state.ripple_control = advanced["ripple"] if isinstance(advanced["ripple"], bool) else None

        lift = self._read_optional(ADDR_LIFT_OFF, 2)
        if lift is not None and len(lift) >= 2:
            code = decode_pair(lift[0], lift[1])
            if code is not None:
                state.lod_code = code
                state.lod_mm = (code + 6) / 10

        angle, angle_enabled = self._read_angle()
        if angle is not None:
            state.angle_degrees = angle
            state.angle_enabled = angle_enabled
            state.supports_angle = True

        performance = self._read_sensor_mode()
        if performance is not None:
            state.performance_mode = performance
            state.supports_performance_mode = True

        led_mode, led_brightness, led_speed = self._read_lighting()
        if led_mode is not None:
            state.led_mode = led_mode
            state.led_brightness = led_brightness
            state.led_speed = led_speed
            state.supports_lighting = True

        colors = self._read_colors(count)
        if colors:
            state.stage_colors = colors
            state.supports_stage_colors = True

        try:
            state.profile = self._read_profile()
        except ProtocolError:
            state.profile = None

        state.buttons = self._read_buttons(self.model.bottom_button if self.model else True)

        receiver_info = self._read_receiver()
        if receiver_info is not None:
            state.receiver_online = bool(receiver_info["online"])
            state.rf_id = receiver_info["rf_id"]

        if state.via_receiver and state.receiver_online is None:
            # Older receivers do not implement command 0x03; the fact that the
            # mouse answered means the link is up.
            state.receiver_online = True

        self.state = state
        self.caps = devices.capabilities_for(
            model=self.model,
            receiver=self.receiver,
            sensor_name=state.sensor,
            active_polling=state.polling_rate,
            debounce=state.debounce_ms,
            sleep=state.sleep_seconds,
            usb_name=state.usb_name,
        )
        # Discovered rows take precedence over the conservative model table.
        self.caps.performance_mode = self.caps.performance_mode or state.supports_performance_mode
        self.caps.long_range = self.caps.long_range or state.supports_long_range
        self.caps.dpi_lighting = self.caps.dpi_lighting and state.supports_lighting
        self.caps.stage_colors = self.caps.stage_colors and state.supports_stage_colors
        return state

    def read_live(self) -> MouseState:
        """Cheap poll used between full refreshes."""
        if not self.state.model_name:
            return self.read_full()
        state = self.state
        try:
            battery = self.transport.read_battery()
            state.battery = battery.get("percent")
            state.charging = battery.get("charging")
            state.voltage_mv = battery.get("millivolts")
        except ProtocolError:
            pass
        system = self._read_optional(ADDR_SYSTEM, 10)
        if system is not None:
            polling, count, active = self._decode_system(system)
            state.polling_rate = polling
            if count != state.stage_count or active != state.active_stage:
                try:
                    stages = self._read_stages(count)
                    state.stages = stages
                    state.stage_count = count
                    state.active_stage = active
                    state.dpi, state.dpi_y = stages[active]
                except ProtocolError:
                    pass
        receiver_info = self._read_receiver()
        if receiver_info is not None:
            state.receiver_online = bool(receiver_info["online"])
            state.rf_id = receiver_info["rf_id"]
        return state

    def collect_raw_registers(self, start: int = 0x0000, end: int = 0x00C0,
                              chunk: int = 10) -> dict[int, bytes | None]:
        """Read the vendor register window for a sanitized support report.

        This is read-only and only used when the user explicitly asks for a
        report.  Failures are recorded per chunk rather than aborting.
        """
        result: dict[int, bytes | None] = {}
        for address in range(start, end + 1, chunk):
            length = min(chunk, end - address + 1)
            try:
                result[address] = self.transport.read_eeprom(address, length)
            except ProtocolError:
                result[address] = None
        return result

    # -- writes ------------------------------------------------------------
    def _require(self, condition: bool, message: str) -> None:
        if not condition:
            raise ProtocolError(message)

    def _write_and_read(self, addr: int, data: bytes, length: int | None = None) -> bytes:
        self.transport.write_eeprom(addr, data)
        time.sleep(0.02)
        return self.transport.read_eeprom(addr, length or len(data))

    def set_polling(self, hertz: int) -> int:
        if hertz not in self.caps.polling_rates:
            raise ProtocolError(f"{hertz} Hz is not available on this link")
        code = protocol.POLLING_TO_CODE.get(hertz)
        self._require(code is not None, f"Unknown polling rate {hertz} Hz")
        system = self.transport.read_eeprom(ADDR_SYSTEM, 10)
        system = bytearray(system)
        system[0:2] = pack_pair(code)
        # The full six-byte system row preserves stage count and active stage.
        self.transport.write_eeprom(ADDR_SYSTEM, bytes(system[:6]))
        time.sleep(0.12)
        confirmed = self.transport.read_eeprom(ADDR_SYSTEM, 10)
        actual = protocol.POLLING_FROM_CODE.get(confirmed[0])
        self._require(actual == hertz, f"The mouse kept {actual or 'an unknown'} Hz")
        self.state.polling_rate = hertz
        return hertz

    def set_active_stage(self, index: int) -> int:
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        self.transport.write_eeprom(ADDR_SYSTEM + 4, pack_pair(index))
        time.sleep(0.05)
        system = self.transport.read_eeprom(ADDR_SYSTEM, 10)
        actual = decode_pair(system[4], system[5])
        self._require(actual == index, f"The mouse kept DPI stage {(actual or 0) + 1}")
        self.state.active_stage = index
        self.state.dpi, self.state.dpi_y = self.state.stages[index]
        return index

    def set_stage_dpi(self, index: int, x: int, y: int | None = None) -> tuple[int, int]:
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        y = x if y is None else y
        family = self.caps.sensor.family
        if x not in self.caps.dpi_options or y not in self.caps.dpi_options:
            raise ProtocolError(f"{x}×{y} DPI is not supported by {self.caps.sensor.name}")
        packed = pack_dpi_stage(x, y, family)
        address = ADDR_DPI_BASE + index * 4
        self.transport.write_eeprom(address, packed)
        time.sleep(0.03)
        confirmed = unpack_dpi_stage(self.transport.read_eeprom(address, 4), family)
        self._require(confirmed is not None, "The mouse returned an invalid DPI stage")
        assert confirmed is not None
        self._require(confirmed == (x, y), f"The mouse kept {confirmed[0]}×{confirmed[1]} DPI")
        self.state.stages[index] = confirmed
        if index == self.state.active_stage:
            self.state.dpi, self.state.dpi_y = confirmed
        return confirmed

    def set_stage_color(self, index: int, color: str) -> str:
        self._require(self.caps.stage_colors, "This mouse does not expose stage colours")
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        packed = pack_rgb(color)
        self._require(packed is not None, "Colour must be #rrggbb")
        assert packed is not None
        group_address = ADDR_STAGE_COLOR_BASE + (index // 2) * 8
        group = bytearray(self.transport.read_eeprom(group_address, 8))
        group[(index % 2) * 4:(index % 2) * 4 + 4] = packed
        self.transport.write_eeprom(group_address, bytes(group))
        time.sleep(0.03)
        confirmed_raw = self.transport.read_eeprom(group_address, 8)
        confirmed = unpack_rgb(confirmed_raw[(index % 2) * 4:(index % 2) * 4 + 4])
        self._require(confirmed == color.lower(), f"The mouse kept {confirmed or 'an invalid colour'}")
        while len(self.state.stage_colors) < self.state.stage_count:
            self.state.stage_colors.append("#ffffff")
        self.state.stage_colors[index] = confirmed or color.lower()
        return confirmed or color.lower()

    def set_lift_off_code(self, code: int) -> int:
        allowed = [item[0] for item in self.caps.lift_off_choices]
        self._require(code in allowed, "That lift-off value is not available")
        self.transport.write_eeprom(ADDR_LIFT_OFF, pack_pair(code))
        time.sleep(0.03)
        raw = self.transport.read_eeprom(ADDR_LIFT_OFF, 2)
        actual = decode_pair(raw[0], raw[1])
        self._require(actual == code, "The mouse did not retain the lift-off setting")
        self.state.lod_code = code
        self.state.lod_mm = (code + 6) / 10
        return code

    def _write_advanced_pair(self, offset: int, value: int, label: str) -> int:
        block = bytearray(self.transport.read_eeprom(ADDR_ADVANCED, 10))
        block[offset:offset + 2] = pack_pair(value)
        self.transport.write_eeprom(ADDR_ADVANCED, bytes(block))
        time.sleep(0.04)
        confirmed = self.transport.read_eeprom(ADDR_ADVANCED, 10)
        actual = decode_pair(confirmed[offset], confirmed[offset + 1])
        self._require(actual == value, f"The mouse did not retain {label}")
        return value

    def set_debounce(self, milliseconds: int) -> int:
        self._require(milliseconds in self.caps.debounce_options, "Unsupported debounce value")
        self._write_advanced_pair(0, milliseconds, "the debounce setting")
        self.state.debounce_ms = milliseconds
        return milliseconds

    def set_motion_sync(self, enabled: bool) -> bool:
        self._write_advanced_pair(2, 1 if enabled else 0, "Motion Sync")
        self.state.motion_sync = enabled
        return enabled

    def set_sleep(self, seconds: int) -> int:
        self._require(seconds in self.caps.sleep_options, "Unsupported sleep timer")
        units = round(seconds / protocol.SLEEP_STEP_SECONDS)
        self._write_advanced_pair(4, units, "the sleep timer")
        self.state.sleep_seconds = seconds
        return seconds

    def set_straight_line(self, enabled: bool) -> bool:
        self._write_advanced_pair(6, 1 if enabled else 0, "straight-line correction")
        self.state.straight_line = enabled
        return enabled

    def set_ripple(self, enabled: bool) -> bool:
        self._write_advanced_pair(8, 1 if enabled else 0, "ripple control")
        self.state.ripple_control = enabled
        return enabled

    def set_angle(self, degrees: int, enabled: bool) -> tuple[int, bool]:
        self._require(self.state.supports_angle, "This mouse does not expose sensor rotation")
        self._require(-30 <= degrees <= 30, "Sensor angle must be between -30 and 30")
        angle = degrees & 0xFF
        switch = 1 if enabled else 0
        payload = pack_pair(angle) + pack_pair(switch)
        self.transport.write_eeprom(ADDR_ANGLE, payload)
        time.sleep(0.03)
        confirmed, confirmed_enabled = self._read_angle()
        self._require(
            confirmed == degrees and confirmed_enabled == enabled,
            "The mouse did not retain the sensor rotation",
        )
        self.state.angle_degrees = degrees
        self.state.angle_enabled = enabled
        return degrees, enabled

    def set_performance_mode(self, enabled: bool) -> bool:
        self._require(self.state.supports_performance_mode, "Performance mode is not exposed")
        row = bytearray(self.transport.read_eeprom(ADDR_SENSOR_MODE, 6))
        row[4:6] = pack_pair(1 if enabled else 0)
        self.transport.write_eeprom(ADDR_SENSOR_MODE, bytes(row))
        time.sleep(0.04)
        confirmed = self._read_sensor_mode()
        self._require(confirmed == enabled, "The mouse did not retain the performance mode")
        self.state.performance_mode = enabled
        return enabled

    def set_led_mode(self, mode: int, brightness: int, speed: int) -> tuple[int, int, int]:
        self._require(self.state.supports_lighting, "This mouse does not expose DPI lighting")
        self._require(mode in (0, 1, 2), "LED mode must be off, steady or breathing")
        self._require(brightness in (0, 1, 2), "Invalid brightness")
        self._require(speed in (0, 1, 2), "Invalid LED speed")
        block = bytearray(self.transport.read_eeprom(ADDR_DPI_LIGHT, 8))
        effect = 0 if mode == 0 else (2 if mode == 2 else 1)
        block[0:2] = pack_pair(effect)
        block[2:4] = pack_pair(0 if mode == 0 else (0x10, 0x80, 0xFF)[brightness])
        block[4:6] = pack_pair((1, 3, 5)[speed])
        block[6:8] = pack_pair(0 if mode == 0 else 1)
        self.transport.write_eeprom(ADDR_DPI_LIGHT, bytes(block))
        time.sleep(0.04)
        confirmed_mode, confirmed_brightness, confirmed_speed = self._read_lighting()
        self._require(
            confirmed_mode == mode and confirmed_speed == speed,
            "The mouse did not retain the lighting settings",
        )
        self.state.led_mode = mode
        self.state.led_brightness = confirmed_brightness if confirmed_brightness is not None else brightness
        self.state.led_speed = confirmed_speed
        return mode, self.state.led_brightness, speed

    def set_profile(self, profile: int) -> int:
        self._require(1 <= profile <= 4, "Profile must be between 1 and 4")
        self.transport.set_profile(profile - 1)
        time.sleep(0.08)
        confirmed = self._read_profile()
        self._require(confirmed == profile, f"The mouse kept profile {confirmed or '?'}")
        self.state.profile = profile
        return profile

    def set_long_range(self, enabled: bool) -> bool:
        self._require(self.caps.long_range, "Long-range mode is not supported")
        self.transport.set_long_range(enabled)
        confirmed = self.transport.read_long_range()
        self._require(confirmed == enabled, "The mouse did not retain long-range mode")
        self.state.long_range = enabled
        return enabled
