"""High-level COMPX mouse controller built on the 0x55 EEPROM transport."""

from __future__ import annotations

import functools
import logging
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
    V2Transport,
    decode_pair,
    pack_dpi_stage,
    pack_pair,
    pack_rgb,
    unpack_dpi_stage,
    unpack_rgb,
)
from .state import Button, MouseState

logger = logging.getLogger(__name__)

BUTTON_ADDRESSES = (0x0060, 0x0068, 0x0070)
BUTTON_NAMES = ("Left", "Right", "Middle", "Back", "Forward", "Bottom")


def button_address(index: int) -> int:
    """Physical register address for a button slot, independent of read success."""
    if not 0 <= index < len(BUTTON_NAMES):
        raise ValueError("button index out of range")
    return BUTTON_ADDRESSES[index // 2] + (index % 2) * 4

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

# Button actions that are shared across the ATK/VXE mouse family.  These are
# the safe, well-understood assignments; macro/shortcut classes are read-only.
BUTTON_ACTIONS: dict[str, tuple[int, int, int, str]] = {
    "left": (0x01, 0x01, 0x00, "Left click"),
    "right": (0x01, 0x02, 0x00, "Right click"),
    "middle": (0x01, 0x04, 0x00, "Middle click"),
    "back": (0x01, 0x08, 0x00, "Back"),
    "forward": (0x01, 0x10, 0x00, "Forward"),
    "dpi_cycle": (0x02, 0x01, 0x00, "DPI cycle"),
    "dpi_up": (0x02, 0x02, 0x00, "DPI up"),
    "dpi_down": (0x02, 0x03, 0x00, "DPI down"),
    "disabled": (0x00, 0x00, 0x00, "Disabled"),
}
BUTTON_ACTION_ORDER = (
    "left", "right", "middle", "back", "forward",
    "dpi_cycle", "dpi_up", "dpi_down", "disabled",
)
DEFAULT_BUTTON_ACTIONS = (
    "left", "right", "middle", "back", "forward", "dpi_cycle",
)
LOD_MM_BY_CODE = {1: 1.0, 2: 2.0, 3: 0.7}


def button_action_key(key_class: int, value1: int, value2: int) -> str:
    for key, (cls, v1, v2, _label) in BUTTON_ACTIONS.items():
        if (cls, v1, v2) == (key_class, value1, value2):
            return key
    return ""


def decode_button_action(key_class: int, value1: int, value2: int) -> str:
    if key_class == 0x00:
        return "Disabled"
    if key_class == 0x01:
        return MOUSE_ACTION_LABELS.get(value1, f"Mouse 0x{value1:02x}")
    if key_class == 0x02:
        return DPI_ACTION_LABELS.get(value1, "DPI control")
    label = BUTTON_CLASS_LABELS.get(key_class, f"Action 0x{key_class:02x}")
    return f"{label} (0x{value1:02x}, 0x{value2:02x})"


def pack_button_record(key_class: int, value1: int, value2: int) -> bytes:
    total = (key_class + value1 + value2) & 0xFF
    return bytes((key_class & 0xFF, value1 & 0xFF, value2 & 0xFF,
                  (0x55 - total) & 0xFF))


def lod_mm(code: int | None) -> float | None:
    if code is None:
        return None
    return LOD_MM_BY_CODE.get(code)


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
        # Some receivers never answer command 0x03.  Remember consecutive
        # failures so the live poll stops paying for three timeouts each time.
        self._online_misses = 0

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
        if last is None:
            raise ProtocolError("the mouse did not answer")
        raise last

    def _identify(self) -> tuple[int | None, int | None, str]:
        cid = mid = None
        last: Exception | None = None
        # The transport retries each command three times already, and the worker
        # retries the whole connect, so one call here is enough.  Looping three
        # times on top of that cost 5.4 s on a sleeping mouse.
        try:
            cid, mid = self.transport.read_identity()
        except ProtocolError as exc:
            last = exc
        if cid is None and self.model is not None:
            # The model is already known, so this is a dropped poll, not a new
            # device.  Returning None here used to downgrade the mouse to an
            # unknown, read-only model and misread its DPI encoding.
            raise ProtocolError("The mouse stopped answering its identity command") from last
        if cid is None and self.receiver is not None:
            sleep_hint = (
                "The receiver answered, but the paired mouse did not. "
                "Turn the mouse on or move it, then retry."
            )
            raise ProtocolError(sleep_hint) from last
        firmware = ""
        # Query the firmware only after the mouse has answered the identity
        # command.  Both the 8K and 4K receivers return 0x12 once awake.
        if cid is not None:
            try:
                firmware = self.transport.read_firmware(attempts=2)
            except ProtocolError:
                pass
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

    def _read_sensor_mode(self) -> int | None:
        raw = self._read_optional(ADDR_SENSOR_MODE, 6)
        if raw is None or len(raw) < 6:
            return None
        if raw[2] != 0x06 or raw[3] != 0x4F:
            return None
        mode = decode_pair(raw[4], raw[5])
        return mode if mode in (0, 1, 2, 3) else None

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
        """Return all button slots without collapsing unreadable records.

        Button writes use the physical slot index.  Dropping a corrupt record
        would shift every later button and make a remap land on the wrong
        physical button, so invalid records become disabled placeholders.
        """
        buttons: list[Button] = []
        for group_index, address in enumerate(BUTTON_ADDRESSES):
            raw = self._read_optional(address, 8)
            for slot in range(2):
                index = group_index * 2 + slot
                if index >= len(BUTTON_NAMES):
                    continue
                if index == 5 and not include_bottom:
                    continue
                if raw is None or len(raw) < 8:
                    buttons.append(Button(
                        name=BUTTON_NAMES[index],
                        action="Unreadable",
                        readable=False,
                    ))
                    continue
                record = raw[slot * 4:(slot + 1) * 4]
                key_class, value1, value2, check = record
                valid = (key_class + value1 + value2 + check) & 0xFF == 0x55
                if not valid:
                    buttons.append(Button(
                        name=BUTTON_NAMES[index],
                        action="Unreadable",
                        raw=" ".join(f"{byte:02x}" for byte in record),
                        readable=False,
                    ))
                    continue
                buttons.append(
                    Button(
                        name=BUTTON_NAMES[index],
                        action=decode_button_action(key_class, value1, value2),
                        raw=" ".join(f"{byte:02x}" for byte in record),
                        action_id=button_action_key(key_class, value1, value2),
                    )
                )
        return buttons

    def _read_receiver(self) -> dict | None:
        if not self.info.is_receiver:
            return None
        if self._online_misses >= 3:
            # This receiver has not answered 0x03 three times in a row; the
            # link is still up, so stop spending a timeout on it every poll.
            return None
        info = self.transport.receiver_online()
        self._online_misses = 0 if info is not None else self._online_misses + 1
        return info

    def online_status(self) -> bool | None:
        """Cheap receiver-only liveness check (does not read the mouse)."""
        if not self.info.is_receiver:
            return True
        info = self._read_receiver()
        if not isinstance(info, dict) or "online" not in info:
            return None
        return bool(info["online"])

    def read_full(self) -> MouseState:
        """Read identity and all readable settings.  Missing optional rows are OK."""
        self.receiver = devices.receiver_for(self.info.product_id, self.info.product_name)
        cid, mid, firmware = self._identify()
        if cid is not None and mid is not None:
            # The mouse answered its identity, so trust only the identity
            # table.  Falling back to the USB id here would grant writes to a
            # model this app never actually identified, and shared receivers
            # make that a real risk.
            self.model = devices.MODEL_BY_CIDMID.get((cid, mid))
        else:
            self.model = devices.MODEL_BY_USB.get((self.info.vendor_id, self.info.product_id))
        self.read_only = self.model is None or self.model.experimental
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
        if self.model is not None:
            model_name = self.model.name
        elif self.info.is_receiver:
            # The USB product is the receiver, not the paired mouse.
            model_name = "Unknown ATK/VXE mouse"
        else:
            model_name = devices.fallback_name(self.info.product_name)
        state = MouseState(
            vendor_id=self.info.vendor_id,
            product_id=self.info.product_id,
            usb_name=self.info.product_name,
            cid=cid,
            mid=mid,
            model_name=model_name,
            brand=self.model.brand if self.model else ("VXE" if "vxe" in self.info.product_name.lower() else "ATK"),
            sensor=self.model.sensor if self.model else "Unknown sensor",
            firmware=firmware,
            usb_bcd=protocol.format_bcd(self.info.bcd_device),
            via_receiver=self.info.is_receiver,
            receiver_name=self.receiver.name if self.receiver else "",
            receiver_pid=self.receiver.product_id if self.receiver else None,
            wired=not self.info.is_receiver,
            read_only=self.read_only,
            experimental=bool(self.model and self.model.experimental),
            dpi=stages[active][0],
            dpi_y=stages[active][1],
            stages=stages,
            active_stage=active,
            stage_count=count,
            polling_rate=polling,
            supports_sensor_max=bool(self.model and self.model.sensor_max),
            supports_button_remap=bool(self.model and self.model.button_remap),
        )

        try:
            battery = self.transport.read_battery()
            percent = battery.get("percent")
            charging = battery.get("charging")
            voltage = battery.get("millivolts")
            if (
                isinstance(percent, int)
                and isinstance(charging, bool)
                and protocol.battery_is_plausible(percent, charging)
            ):
                state.battery = percent
                state.charging = charging
            else:
                state.battery = None
                state.charging = None
            state.voltage_mv = voltage if isinstance(voltage, int) else None
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
                state.lod_mm = lod_mm(code)

        angle, angle_enabled = self._read_angle()
        if angle is not None:
            state.angle_degrees = angle
            state.angle_enabled = angle_enabled
            state.supports_angle = True

        sensor_mode = self._read_sensor_mode()
        if sensor_mode is not None:
            state.sensor_mode = sensor_mode
            state.performance_mode = sensor_mode != 0
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
            percent = battery.get("percent")
            charging = battery.get("charging")
            voltage = battery.get("millivolts")
            if (
                isinstance(percent, int)
                and isinstance(charging, bool)
                and protocol.battery_is_plausible(percent, charging)
            ):
                state.battery = percent
                state.charging = charging
            else:
                state.battery = None
                state.charging = None
            state.voltage_mv = voltage if isinstance(voltage, int) else None
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
        if code is None:
            raise ProtocolError(f"Unknown polling rate {hertz} Hz")
        # Only the polling field belongs to this write. Sending a read-modify-
        # write of the whole system row can overwrite a stage change made by
        # the mouse or another utility in between the read and the write.
        self.transport.write_eeprom(ADDR_SYSTEM, pack_pair(code))
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
        if confirmed is None:
            raise ProtocolError("the mouse returned an invalid DPI stage")
        self._require(confirmed == (x, y), f"The mouse kept {confirmed[0]}×{confirmed[1]} DPI")
        self.state.stages[index] = confirmed
        if index == self.state.active_stage:
            self.state.dpi, self.state.dpi_y = confirmed
        return confirmed

    def set_stage_color(self, index: int, color: str) -> str:
        self._require(self.caps.stage_colors, "This mouse does not expose stage colours")
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        normalized = f"#{color.strip().lstrip('#').lower()}"
        packed = pack_rgb(normalized)
        self._require(packed is not None, "Colour must be #rrggbb")
        if packed is None:
            raise ProtocolError("Colour must be #rrggbb")
        group_address = ADDR_STAGE_COLOR_BASE + (index // 2) * 8
        group = bytearray(self.transport.read_eeprom(group_address, 8))
        group[(index % 2) * 4:(index % 2) * 4 + 4] = packed
        self.transport.write_eeprom(group_address, bytes(group))
        time.sleep(0.03)
        confirmed_raw = self.transport.read_eeprom(group_address, 8)
        confirmed = unpack_rgb(confirmed_raw[(index % 2) * 4:(index % 2) * 4 + 4])
        self._require(confirmed == normalized, f"The mouse kept {confirmed or 'an invalid colour'}")
        while len(self.state.stage_colors) < self.state.stage_count:
            self.state.stage_colors.append("#ffffff")
        self.state.stage_colors[index] = confirmed or normalized
        return confirmed or normalized

    def set_lift_off_code(self, code: int) -> int:
        allowed = [item[0] for item in self.caps.lift_off_choices]
        self._require(code in allowed, "That lift-off value is not available")
        self.transport.write_eeprom(ADDR_LIFT_OFF, pack_pair(code))
        time.sleep(0.03)
        raw = self.transport.read_eeprom(ADDR_LIFT_OFF, 2)
        actual = decode_pair(raw[0], raw[1])
        self._require(actual == code, "The mouse did not retain the lift-off setting")
        self.state.lod_code = code
        self.state.lod_mm = lod_mm(code)
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

    def set_sensor_mode(self, mode: int) -> int:
        self._require(self.state.supports_performance_mode, "Sensor sampling mode is not exposed")
        self._require(mode in (0, 1, 2), "Sensor mode must be Basic, Competitive or Competitive MAX")
        if mode >= 2:
            self._require(
                self.state.supports_sensor_max,
                "Competitive MAX has not been verified for this model; use ATK HUB for it",
            )
        row = bytearray(self.transport.read_eeprom(ADDR_SENSOR_MODE, 6))
        row[4:6] = pack_pair(mode)
        self.transport.write_eeprom(ADDR_SENSOR_MODE, bytes(row))
        time.sleep(0.04)
        confirmed = self._read_sensor_mode()
        self._require(confirmed == mode, "The mouse did not retain the sensor sampling mode")
        self.state.sensor_mode = mode
        self.state.performance_mode = mode != 0
        return mode

    def set_performance_mode(self, enabled: bool) -> bool:
        mode = self.set_sensor_mode(1 if enabled else 0)
        return mode != 0

    def set_button_action(self, index: int, action: str) -> str:
        self._require(
            self.state.supports_button_remap,
            "Button remapping has not been verified for this model",
        )
        self._require(0 <= index < len(BUTTON_NAMES), "Button index out of range")
        self._require(action in BUTTON_ACTIONS, "Unsupported button action")
        if index == 5 and self.model is not None and not self.model.bottom_button:
            raise ProtocolError("This mouse has no bottom button")
        if not self.state.buttons:
            raise ProtocolError("Button assignments are not readable on this mouse")
        if index < len(self.state.buttons) and not self.state.buttons[index].readable:
            raise ProtocolError(
                f"The {BUTTON_NAMES[index]} button record is unreadable; "
                "restore defaults before remapping it"
            )
        key_class, value1, value2, label = BUTTON_ACTIONS[action]
        address = button_address(index)
        packed = pack_button_record(key_class, value1, value2)
        self.transport.write_eeprom(address, packed)
        time.sleep(0.04)
        confirmed = self.transport.read_eeprom(address, 4)
        self._require(confirmed == packed, "The mouse did not retain the button assignment")
        updated = list(self.state.buttons)
        if index < len(updated):
            old = updated[index]
            updated[index] = Button(
                name=old.name, action=label, raw=" ".join(f"{b:02x}" for b in packed),
                action_id=action,
            )
            self.state.buttons = updated
        return label

    def reset_buttons(self) -> None:
        self._require(
            self.state.supports_button_remap,
            "Button remapping has not been verified for this model",
        )
        self._require(bool(self.state.buttons), "Button assignments are not readable on this mouse")
        indices = list(range(len(self.state.buttons)))
        snapshot = []
        for index in indices:
            address = button_address(index)
            snapshot.append((address, self.transport.read_eeprom(address, 4)))
        applied = 0
        try:
            for index, action in enumerate(DEFAULT_BUTTON_ACTIONS):
                if index not in indices:
                    continue
                key_class, value1, value2, _label = BUTTON_ACTIONS[action]
                packed = pack_button_record(key_class, value1, value2)
                address = button_address(index)
                self.transport.write_eeprom(address, packed)
                applied += 1
                time.sleep(0.03)
                if self.transport.read_eeprom(address, 4) != packed:
                    raise ProtocolError(f"The mouse did not retain the default for button {index + 1}")
        except (ProtocolError, OSError) as exc:
            restored = True
            for address, raw in snapshot:
                try:
                    self.transport.write_eeprom(address, raw)
                    time.sleep(0.02)
                    if self.transport.read_eeprom(address, 4) != raw:
                        restored = False
                except (ProtocolError, OSError):
                    restored = False
            self.state.buttons = self._read_buttons(
                self.model.bottom_button if self.model else True
            )
            suffix = (
                "original mappings restored"
                if restored else "recovery was incomplete — review the button assignments"
            )
            raise ProtocolError(
                f"Button reset stopped after {applied} change(s); {suffix}. ({exc})"
            ) from exc
        self.state.buttons = self._read_buttons(
            self.model.bottom_button if self.model else True
        )

    def add_stage(self) -> int:
        self._require(self.state.stage_count < 8, "This mouse already has eight DPI stages")
        count = self.state.stage_count
        new_index = count
        last_stage = self.state.stages[-1] if self.state.stages else (800, 800)
        family = self.caps.sensor.family
        packed = pack_dpi_stage(last_stage[0], last_stage[1], family)
        address = ADDR_DPI_BASE + new_index * 4
        color = self.state.stage_colors[-1] if self.state.stage_colors else "#ffffff"
        packed_color = pack_rgb(color) if self.caps.stage_colors else None

        # Preflight every shared read before the first write.  In particular,
        # a failed colour-group read must never be replaced by zero bytes: the
        # other four bytes belong to a neighbouring stage.
        system = bytearray(self.transport.read_eeprom(ADDR_SYSTEM, 10))
        group_address = None
        group = None
        if packed_color is not None and self.caps.stage_colors:
            group_address = ADDR_STAGE_COLOR_BASE + (new_index // 2) * 8
            group = bytearray(self.transport.read_eeprom(group_address, 8))

        self.transport.write_eeprom(address, packed)
        time.sleep(0.03)
        confirmed = unpack_dpi_stage(self.transport.read_eeprom(address, 4), family)
        self._require(confirmed == last_stage, "The mouse did not accept the new DPI stage")

        if group is not None and group_address is not None and packed_color is not None:
            slot = (new_index % 2) * 4
            group[slot:slot + 4] = packed_color
            self.transport.write_eeprom(group_address, bytes(group))
            time.sleep(0.03)
            confirmed_group = self.transport.read_eeprom(group_address, 8)
            self._require(
                confirmed_group[slot:slot + 4] == packed_color,
                "The mouse did not retain the new stage colour",
            )

        system[2:4] = pack_pair(new_index + 1)
        self.transport.write_eeprom(ADDR_SYSTEM, bytes(system[:6]))
        time.sleep(0.05)
        system_after = self.transport.read_eeprom(ADDR_SYSTEM, 10)
        self._require(
            decode_pair(system_after[2], system_after[3]) == new_index + 1,
            "The mouse did not retain the new DPI stage count",
        )
        self.state.stages.append(confirmed or last_stage)
        self.state.stage_colors.append(color)
        self.state.stage_count = new_index + 1
        return self.state.stage_count

    def remove_last_stage(self) -> int:
        self._require(self.state.stage_count > 1, "At least one DPI stage is required")
        system = bytearray(self.transport.read_eeprom(ADDR_SYSTEM, 10))
        new_count = self.state.stage_count - 1
        active = min(self.state.active_stage, new_count - 1)
        system[2:4] = pack_pair(new_count)
        system[4:6] = pack_pair(active)
        self.transport.write_eeprom(ADDR_SYSTEM, bytes(system[:6]))
        time.sleep(0.05)
        system_after = self.transport.read_eeprom(ADDR_SYSTEM, 10)
        self._require(
            decode_pair(system_after[2], system_after[3]) == new_count,
            "The mouse did not retain the new DPI stage count",
        )
        self.state.stages = self.state.stages[:new_count]
        self.state.stage_colors = self.state.stage_colors[:new_count]
        self.state.stage_count = new_count
        self.state.active_stage = active
        self.state.dpi, self.state.dpi_y = self.state.stages[active]
        return new_count

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

    def commit_settings(self) -> None:
        """Commit the active profile to the mouse's onboard storage.

        The protocol exposes profile configuration as a working copy; the
        vendor firmware only flushes it when the active profile changes.
        Switching to another profile and back preserves the active profile
        while forcing that flush.  Without this, changes survive until the
        mouse is powered off and then revert to the last saved profile.
        """
        current = self._read_profile()
        self._require(current is not None, "The mouse did not report its active profile")
        if current is None:
            raise ProtocolError("The mouse did not report its active profile")
        self._require(self.caps.profiles, "This mouse does not expose onboard profiles")
        other = 2 if current == 1 else 1
        switched = False
        try:
            self.transport.set_profile(other - 1)
            switched = True
            time.sleep(0.18)
            self.transport.set_profile(current - 1)
            switched = False
            time.sleep(0.22)
            confirmed = self._read_profile()
            self._require(confirmed == current,
                          "The mouse did not return to its profile after saving")
        except Exception:
            if switched:
                logger.exception("profile commit interrupted; restoring profile %d", current)
                try:
                    self.transport.set_profile(current - 1)
                except Exception:
                    logger.exception("could not restore profile %d after failed commit", current)
            raise
        self.state.profile = current


def _guard_read_only(method):
    """Refuse a v1 write unless the model is verified or allowed to write."""

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self.read_only:
            raise ProtocolError(
                "This model is read-only until its settings are verified"
            )
        return method(self, *args, **kwargs)

    return wrapper


# Every v1 write lands in one of these methods.  The worker and the CLI also
# check read_only before queueing work, but a direct caller must not be able to
# skip the check, so it lives here as well.
_WRITE_METHODS = (
    "set_polling",
    "set_active_stage",
    "set_stage_dpi",
    "set_stage_color",
    "set_lift_off_code",
    "set_debounce",
    "set_motion_sync",
    "set_sleep",
    "set_straight_line",
    "set_ripple",
    "set_angle",
    "set_sensor_mode",
    "set_performance_mode",
    "set_button_action",
    "reset_buttons",
    "add_stage",
    "remove_last_stage",
    "set_led_mode",
    "set_profile",
    "commit_settings",
)
for _write_name in _WRITE_METHODS:
    setattr(Controller, _write_name, _guard_read_only(getattr(Controller, _write_name)))


V2_BUTTON_ACTIONS: dict[str, tuple[int, int, int, int]] = {
    "left": (1, 0, 0, 0),
    "right": (1, 0, 1, 0),
    "middle": (1, 0, 2, 0),
    "back": (1, 0, 3, 0),
    "forward": (1, 0, 4, 0),
    "dpi_cycle": (10, 0, 0, 0),
    "dpi_up": (11, 0, 0, 0),
    "dpi_down": (12, 0, 0, 0),
    "disabled": (255, 0, 0, 0),
}
V2_BUTTON_LABELS = {
    "left": "Left click", "right": "Right click", "middle": "Middle click",
    "back": "Back", "forward": "Forward", "dpi_cycle": "DPI cycle",
    "dpi_up": "DPI up", "dpi_down": "DPI down", "disabled": "Disabled",
}
V2_BUTTON_IDS = {value: key for key, value in V2_BUTTON_ACTIONS.items()}


class V2Controller:
    """Full controller for 0xff05 (A9 Pro Max 2.0 class) mice.

    The 0xff05 protocol uses a 64-byte request/response frame with a checksum
    and a command header.  It is not compatible with the v1 EEPROM commands.
    This controller implements the documented settings surface and keeps the
    same MouseState shape used by the rest of the application.
    """

    def __init__(self, info: DeviceInfo, debug: bool = False) -> None:
        self.info = info
        self.debug = debug
        self.transport = V2Transport(info.path, wireless=info.is_receiver, debug=debug)
        self.model: devices.Model | None = None
        self.receiver = devices.receiver_for(info.product_id, info.product_name)
        self.caps = devices.capabilities_for(
            model=None, receiver=self.receiver, usb_name=info.product_name
        )
        self.state = MouseState(
            vendor_id=info.vendor_id,
            product_id=info.product_id,
            usb_name=info.product_name,
            usb_bcd=protocol.format_bcd(info.bcd_device),
            via_receiver=info.is_receiver,
            wired=not info.is_receiver,
            protocol="v2",
            read_only=True,
            telemetry_only=True,
        )
        self.read_only = True

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

    @staticmethod
    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise ProtocolError(message)

    def _identity(self) -> tuple[int | None, int | None, str]:
        cid: int | None = None
        mid: int | None = None
        firmware = ""
        try:
            cid, mid = self.transport.read_identity()
        except ProtocolError:
            logger.debug("v2 identity command failed", exc_info=True)
        try:
            firmware = self.transport.read_version()
        except ProtocolError:
            logger.debug("v2 firmware command failed", exc_info=True)
        return cid, mid, firmware

    def _set_model(self, cid: int | None, mid: int | None) -> None:
        self.model = devices.v2_model_for(
            cid, mid, self.info.vendor_id, self.info.product_id, self.info.product_name
        )
        self.receiver = devices.receiver_for(self.info.product_id, self.info.product_name)
        self.caps = devices.capabilities_for(
            model=self.model,
            receiver=self.receiver,
            sensor_name=self.model.sensor if self.model else None,
            usb_name=self.info.product_name,
        )
        # A9 Pro Max 2.0 is a direct 8 kHz device; a cable still advertises the
        # same report-rate table even though it has no receiver descriptor.
        if self.model is not None and self.receiver is None:
            self.caps.receiver = devices.Receiver(0, "USB cable", self.model.max_polling)
            self.caps.polling_rates = [hz for hz in (125, 250, 500, 1000, 2000, 4000, 8000)
                                       if hz <= self.model.max_polling]
            self.caps.link_ceiling = self.model.max_polling

    def _apply_battery(self, state: MouseState) -> None:
        try:
            battery = self.transport.read_battery()
        except ProtocolError:
            return
        percent = battery.get("percent")
        charging = battery.get("charging")
        if (
            isinstance(percent, int)
            and isinstance(charging, bool)
            and protocol.battery_is_plausible(percent, charging)
        ):
            state.battery = percent
            state.charging = charging
        voltage = battery.get("millivolts")
        state.voltage_mv = voltage if isinstance(voltage, int) else None

    def _apply_config(self, state: MouseState, config: bytes) -> None:
        if len(config) < 12:
            return
        state.profile = config[0] + 1
        state.polling_rate = protocol.V2_CODE_TO_RATE.get(config[2], 1000)
        state.lod_code = config[5] + 1
        state.lod_mm = lod_mm(state.lod_code)
        state.motion_sync = bool(config[6])
        state.angle_enabled = bool(config[7])
        state.straight_line = bool(config[7])
        state.ripple_control = bool(config[8])
        state.sleep_seconds = int.from_bytes(config[9:11], "little")
        state.debounce_ms = config[11]

    def _apply_dpi(self, state: MouseState, raw: bytes) -> None:
        if len(raw) < 2:
            return
        count = max(1, min(8, raw[1]))
        stages: list[tuple[int, int]] = []
        colors: list[str] = []
        for index in range(count):
            offset = 2 + index * 8
            if offset + 7 > len(raw):
                break
            stages.append((
                int.from_bytes(raw[offset:offset + 2], "little"),
                int.from_bytes(raw[offset + 2:offset + 4], "little"),
            ))
            colors.append(f"#{raw[offset + 6]:02x}{raw[offset + 5]:02x}{raw[offset + 4]:02x}")
        if not stages:
            return
        count = len(stages)
        active = min(raw[0], count - 1)
        # Byte 1 is the table size, not the configured stage count: the R1 NK
        # always reports eight and leaves the unused slots at 0 DPI.  Trim
        # that tail so an unusable stage cannot be selected or activated.
        while len(stages) > active + 1 and stages[-1] == (0, 0):
            stages.pop()
        count = len(stages)
        active = min(active, count - 1)
        state.stages = stages
        state.stage_colors = colors[:count]
        state.stage_count = count
        state.active_stage = active
        state.dpi, state.dpi_y = stages[active]

    def _apply_lighting(self, state: MouseState, raw: bytes) -> None:
        if len(raw) < 3:
            return
        state.led_mode = protocol.V2_CODE_TO_LIGHT_MODE.get(raw[0], 0)
        if state.led_mode == 0:
            state.led_brightness = 0
            state.led_speed = 0
            return
        state.led_brightness = min(
            range(3), key=lambda index: abs(protocol.V2_LIGHT_BRIGHTNESS[index] - raw[1])
        )
        state.led_speed = min(
            range(3), key=lambda index: abs(protocol.V2_LIGHT_SPEED[index] - raw[2])
        )

    def _apply_sensor_mode(self, state: MouseState, raw: int) -> None:
        state.sensor_mode = protocol.V2_CODE_TO_SENSOR_MODE.get(raw, 0)
        state.performance_mode = state.sensor_mode != 0

    def _read_buttons(self, state: MouseState) -> None:
        try:
            raw = self.transport.read_buttons()
        except ProtocolError:
            return
        buttons: list[Button] = []
        for index in range(6):
            offset = index * 5
            if offset + 5 > len(raw):
                break
            record = raw[offset:offset + 5]
            action = (record[0], record[1], record[2], record[3])
            raw_text = " ".join(f"{value:02x}" for value in record)
            if (
                action == (0, 0, 0, 0)
                and self.model is not None
                and self.model.normalizes_default_buttons
            ):
                # This firmware stores a factory-default assignment as class 0
                # instead of the explicit class-1 value.
                default_id = (
                    DEFAULT_BUTTON_ACTIONS[index]
                    if index < len(DEFAULT_BUTTON_ACTIONS) else ""
                )
                buttons.append(Button(
                    name=BUTTON_NAMES[index],
                    action=V2_BUTTON_LABELS.get(default_id, "Factory default"),
                    raw=raw_text,
                    action_id=default_id,
                    readable=True,
                ))
                continue
            action_id = V2_BUTTON_IDS.get(action, "")
            label = V2_BUTTON_LABELS.get(action_id, "Custom / unsupported")
            buttons.append(Button(
                name=BUTTON_NAMES[index],
                action=label,
                raw=raw_text,
                action_id=action_id,
                readable=action != (0, 0, 0, 0),
            ))
        if buttons:
            state.buttons = buttons

    def _apply_flags(self, state: MouseState) -> None:
        model = self.model
        state.read_only = model is None
        state.telemetry_only = model is None
        state.supports_angle = False
        state.supports_performance_mode = bool(model and model.performance_mode)
        state.supports_sensor_max = bool(model and model.sensor_max)
        state.supports_button_remap = bool(model and model.button_remap)
        state.supports_lighting = bool(model and model.dpi_lighting)
        state.supports_stage_colors = bool(model and model.stage_colors)
        state.supports_stage_count = False
        self.read_only = state.read_only

    def _dongle_firmware(self) -> str:
        """Version of the receiver itself; only receivers answer command 0x88."""
        if not self.info.is_receiver:
            return ""
        try:
            return self.transport.read_dongle_version()
        except ProtocolError:
            logger.debug("v2 dongle firmware read failed", exc_info=True)
            return ""

    def read_full(self) -> MouseState:
        cid, mid, firmware = self._identity()
        self._set_model(cid, mid)
        state = MouseState(
            vendor_id=self.info.vendor_id,
            product_id=self.info.product_id,
            usb_name=self.info.product_name,
            cid=cid,
            mid=mid,
            model_name=self.model.name if self.model else devices.fallback_name(self.info.product_name),
            brand=self.model.brand if self.model else "ATK",
            sensor=self.model.sensor if self.model else "Unknown sensor",
            firmware=firmware,
            dongle_firmware=self._dongle_firmware(),
            usb_bcd=protocol.format_bcd(self.info.bcd_device),
            via_receiver=self.info.is_receiver,
            receiver_name=self.receiver.name if self.receiver else "",
            receiver_pid=self.receiver.product_id if self.receiver else None,
            wired=not self.info.is_receiver,
            protocol="v2",
        )
        self._apply_flags(state)

        try:
            self._apply_config(state, self.transport.read_config())
        except ProtocolError:
            logger.debug("v2 config read failed", exc_info=True)
        try:
            self._apply_dpi(state, self.transport.read_dpi())
        except ProtocolError:
            logger.debug("v2 DPI read failed", exc_info=True)
        try:
            self._apply_sensor_mode(state, self.transport.read_sensor_mode())
        except ProtocolError:
            logger.debug("v2 sensor mode read failed", exc_info=True)
        try:
            self._apply_lighting(state, self.transport.read_lighting())
        except ProtocolError:
            logger.debug("v2 lighting read failed", exc_info=True)
        self._read_buttons(state)
        self._apply_battery(state)
        try:
            state.receiver_online = self.transport.read_online() if self.info.is_receiver else True
        except ProtocolError:
            state.receiver_online = None
        self.caps.performance_mode = self.caps.performance_mode or state.supports_performance_mode
        self.state = state
        return state

    def read_live(self) -> MouseState:
        if not self.state.model_name:
            return self.read_full()
        state = self.state
        self._apply_battery(state)
        try:
            self._apply_config(state, self.transport.read_config())
        except ProtocolError:
            pass
        # The stage button on the mouse changes the active index without
        # touching the config block, so read the one byte and reload only when
        # it moved.
        try:
            active = self.transport.read_memory(1, 1)
            if active and active[0] != state.active_stage:
                self._reload_dpi()
        except ProtocolError:
            pass
        return state

    def online_status(self) -> bool | None:
        try:
            if self.is_receiver:
                return self.transport.read_online()
            self.transport.read_battery()
            return True
        except ProtocolError:
            return None

    def set_polling(self, hertz: int) -> int:
        self._require(not self.read_only, "This 0xFF05 device is not in the verified model table")
        self._require(hertz in self.caps.polling_rates, f"{hertz} Hz is not available on this link")
        actual = self.transport.set_rate(hertz)
        self._require(actual == hertz, f"The mouse kept {actual} Hz")
        self.state.polling_rate = actual
        return actual

    def set_active_stage(self, index: int) -> int:
        self._require(not self.read_only, "DPI stages are read-only on this 0xFF05 device")
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        x, y = self.state.stages[index]
        color = self.state.stage_colors[index] if index < len(self.state.stage_colors) else "#ffffff"
        self.transport.set_dpi(index, x, y, color, True)
        self._reload_dpi()
        self._require(self.state.active_stage == index, "The mouse did not switch DPI stage")
        return index

    def _reload_dpi(self) -> None:
        self._apply_dpi(self.state, self.transport.read_dpi())

    def set_stage_dpi(self, index: int, x: int, y: int | None = None) -> tuple[int, int]:
        self._require(not self.read_only, "DPI stages are read-only on this 0xFF05 device")
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        y = x if y is None else y
        self._require(x in self.caps.dpi_options and y in self.caps.dpi_options, "Unsupported DPI value")
        color = self.state.stage_colors[index] if index < len(self.state.stage_colors) else "#ffffff"
        self.transport.set_dpi(index, x, y, color, index == self.state.active_stage)
        self._reload_dpi()
        stage = self.state.stages[index]
        self._require(stage == (x, y), "The mouse did not retain the DPI settings")
        return stage

    def set_stage_color(self, index: int, color: str) -> str:
        self._require(not self.read_only, "DPI colours are read-only on this 0xFF05 device")
        self._require(
            self.state.supports_stage_colors,
            "This mouse does not expose stage colours",
        )
        self._require(0 <= index < self.state.stage_count, "DPI stage out of range")
        if len(color) != 7 or not color.startswith("#"):
            raise ProtocolError("Colour must be #rrggbb")
        x, y = self.state.stages[index]
        self.transport.set_dpi(index, x, y, color, index == self.state.active_stage)
        self._reload_dpi()
        actual = self.state.stage_colors[index]
        self._require(actual.lower() == color.lower(), "The mouse did not retain the stage colour")
        return actual

    def set_lift_off_code(self, code: int) -> int:
        self._require(not self.read_only, "Lift-off distance is read-only on this 0xFF05 device")
        allowed = [item[0] for item in self.caps.lift_off_choices]
        self._require(code in allowed, "That lift-off value is not available")
        self.transport.set_lod(code)
        config = self.transport.read_config()
        actual = config[5] + 1
        self._require(actual == code, "The mouse did not retain the lift-off setting")
        self.state.lod_code = actual
        self.state.lod_mm = lod_mm(actual)
        return actual

    def set_debounce(self, milliseconds: int) -> int:
        self._require(not self.read_only, "Debounce is read-only on this 0xFF05 device")
        self._require(milliseconds in self.caps.debounce_options, "Unsupported debounce value")
        self.transport.set_debounce(milliseconds)
        actual = self.transport.read_config()[11]
        self._require(actual == milliseconds, "The mouse did not retain the debounce setting")
        self.state.debounce_ms = actual
        return actual

    def set_motion_sync(self, enabled: bool) -> bool:
        self._require(not self.read_only, "Motion Sync is read-only on this 0xFF05 device")
        self.transport.set_motion_sync(enabled)
        actual = bool(self.transport.read_config()[6])
        self._require(actual == enabled, "The mouse did not retain Motion Sync")
        self.state.motion_sync = actual
        return actual

    def set_sleep(self, seconds: int) -> int:
        self._require(not self.read_only, "The sleep timer is read-only on this 0xFF05 device")
        self._require(seconds in self.caps.sleep_options, "Unsupported sleep timer")
        self.transport.set_sleep(seconds)
        actual = int.from_bytes(self.transport.read_config()[9:11], "little")
        self._require(actual == seconds, "The mouse did not retain the sleep timer")
        self.state.sleep_seconds = actual
        return actual

    def set_straight_line(self, enabled: bool) -> bool:
        self._require(not self.read_only, "Angle snap is read-only on this 0xFF05 device")
        self.transport.set_angle_snap(enabled)
        actual = bool(self.transport.read_config()[7])
        self._require(actual == enabled, "The mouse did not retain angle snap")
        self.state.straight_line = actual
        self.state.angle_enabled = actual
        return actual

    def set_ripple(self, enabled: bool) -> bool:
        self._require(not self.read_only, "Ripple control is read-only on this 0xFF05 device")
        self.transport.set_ripple(enabled)
        actual = bool(self.transport.read_config()[8])
        self._require(actual == enabled, "The mouse did not retain ripple control")
        self.state.ripple_control = actual
        return actual

    def set_angle(self, degrees: int, enabled: bool) -> tuple[int, bool]:
        raise ProtocolError("Sensor rotation is not exposed by the 0xFF05 protocol")

    def set_sensor_mode(self, mode: int) -> int:
        self._require(not self.read_only, "Sensor mode is read-only on this 0xFF05 device")
        self._require(mode in (0, 1, 2), "Sensor mode must be Basic, Competitive or Competitive MAX")
        self.transport.set_sensor_mode(protocol.V2_SENSOR_MODE_TO_CODE[mode])
        actual = protocol.V2_CODE_TO_SENSOR_MODE.get(self.transport.read_sensor_mode(), 0)
        self._require(actual == mode, "The mouse did not retain the sensor mode")
        self.state.sensor_mode = actual
        self.state.performance_mode = actual != 0
        return actual

    def set_performance_mode(self, enabled: bool) -> bool:
        return self.set_sensor_mode(1 if enabled else 0) != 0

    def set_button_action(self, index: int, action: str) -> str:
        self._require(not self.read_only, "Button remapping is read-only on this 0xFF05 device")
        self._require(self.state.supports_button_remap, "Button remapping has not been verified for this model")
        self._require(0 <= index < len(BUTTON_NAMES), "Button index out of range")
        self._require(action in V2_BUTTON_ACTIONS, "Unsupported button action")
        if index == 5 and self.model is not None and not self.model.bottom_button:
            raise ProtocolError("This mouse has no bottom button")
        self.transport.set_button(index, V2_BUTTON_ACTIONS[action])
        self._read_buttons(self.state)
        actual = self.state.buttons[index].action_id if index < len(self.state.buttons) else ""
        self._require(actual == action, "The mouse did not retain the button assignment")
        return V2_BUTTON_LABELS[action]

    def reset_buttons(self) -> None:
        self._require(not self.read_only, "Button remapping is read-only on this 0xFF05 device")
        self._require(bool(self.state.buttons), "Button assignments are not readable on this mouse")
        snapshot = [button.action_id for button in self.state.buttons]
        applied = 0
        try:
            for index, action in enumerate(DEFAULT_BUTTON_ACTIONS):
                if index >= len(self.state.buttons):
                    continue
                self.transport.set_button(index, V2_BUTTON_ACTIONS[action])
                applied += 1
            self._read_buttons(self.state)
            for index, action in enumerate(DEFAULT_BUTTON_ACTIONS):
                if index < len(self.state.buttons):
                    self._require(
                        self.state.buttons[index].action_id == action,
                        f"The mouse did not retain the default for button {index + 1}",
                    )
        except ProtocolError as exc:
            for button_index, action_id in enumerate(snapshot):
                if action_id in V2_BUTTON_ACTIONS:
                    try:
                        self.transport.set_button(button_index, V2_BUTTON_ACTIONS[action_id])
                    except ProtocolError:
                        break
            self._read_buttons(self.state)
            raise ProtocolError(
                f"Button reset stopped after {applied} change(s); review the assignments. ({exc})"
            ) from exc

    def add_stage(self) -> int:
        raise ProtocolError("This 0xFF05 firmware does not expose a DPI stage-count command")

    def remove_last_stage(self) -> int:
        raise ProtocolError("This 0xFF05 firmware does not expose a DPI stage-count command")

    def set_led_mode(self, mode: int, brightness: int, speed: int) -> tuple[int, int, int]:
        self._require(not self.read_only, "Lighting is read-only on this 0xFF05 device")
        self._require(mode in (0, 1, 2), "LED mode must be off, steady or breathing")
        self._require(brightness in (0, 1, 2), "Invalid brightness")
        self._require(speed in (0, 1, 2), "Invalid LED speed")
        raw_mode = protocol.V2_LIGHT_MODE_TO_CODE[mode]
        raw_brightness = 0 if mode == 0 else protocol.V2_LIGHT_BRIGHTNESS[brightness]
        raw_speed = 0 if mode == 0 else protocol.V2_LIGHT_SPEED[speed]
        self.transport.set_lighting(raw_mode, raw_brightness, raw_speed)
        raw = self.transport.read_lighting()
        actual_mode = protocol.V2_CODE_TO_LIGHT_MODE.get(raw[0], 0)
        self._require(actual_mode == mode, "The mouse did not retain the lighting mode")
        self._apply_lighting(self.state, raw)
        return self.state.led_mode or 0, self.state.led_brightness or 0, self.state.led_speed or 0

    def set_profile(self, profile: int) -> int:
        self._require(not self.read_only, "Profiles are read-only on this 0xFF05 device")
        self._require(1 <= profile <= 4, "Profile must be between 1 and 4")
        self.transport.set_profile(profile)
        actual = self.transport.read_config()[0] + 1
        self._require(actual == profile, f"The mouse kept profile {actual}")
        self.state.profile = actual
        return actual

    def commit_settings(self) -> None:
        # The 0xff05 protocol writes the active profile directly; no v1 profile
        # bounce is needed.
        return

    # Memory blocks that describe the settings surface, at the addresses the
    # firmware itself documents (see docs/PROTOCOL.md).
    RAW_BLOCKS: tuple[tuple[int, int], ...] = (
        (0x0001, 66),  # DPI table: active index, count, eight stages
        (0x004A, 1),   # sensor sampling mode
        (0x004C, 3),   # LED mode, brightness, speed
        (0x0052, 30),  # six button records
    )

    def collect_raw_registers(self, start: int = 0, end: int = 0,
                              include_disabled: bool = True) -> dict[int, bytes | None]:
        """Read the 0xFF05 memory blocks for a support report (read-only).

        Without this a --raw report from a 0xFF05 mouse carried no device
        bytes at all, which is exactly the data the next model needs.
        """
        result: dict[int, bytes | None] = {}
        for address, length in self.RAW_BLOCKS:
            try:
                result[address] = self.transport.read_memory(address, length)
            except ProtocolError:
                result[address] = None
        return result


def controller_for(info: DeviceInfo, debug: bool = False) -> Controller | V2Controller:
    """Open the right controller for the discovered protocol generation."""
    if info.protocol == "v2":
        return V2Controller(info, debug=debug)
    return Controller(info, debug=debug)
