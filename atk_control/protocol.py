"""Low-level COMPX / ATK vendor-HID protocol.

The configuration channel is the ``0xff02:0x0002`` vendor collection.  Every
command is a 16-byte payload carried in HID report ``0x08``.  The byte sum of
the 17-byte wire report (report id + 16 payload bytes) is ``0x55``.

    host -> mouse   08 <cmd> <status> <addr_hi> <addr_lo> <len> <data...> <sum>
    mouse -> host   08 <cmd> <status> <addr_hi> <addr_lo> <len> <data...> <sum>

Reads use ``cmd=0x08`` and writes use ``cmd=0x07``.  This framing is shared by
the ATK, VXE and MAD mice built on COMPX hardware.  It was recovered from the
public ATK HUB web driver; this project is not affiliated with ATK or VXE.
"""

from __future__ import annotations

import errno
import os
import select
import time
from dataclasses import dataclass, field
from pathlib import Path

from .locking import DeviceLock, LockBusy

REPORT_ID = 0x08
PAYLOAD_SIZE = 16
WIRE_SIZE = 17
CHECKSUM_TOTAL = 0x55
MAX_EEPROM_CHUNK = 10

CMD_READ_EEPROM = 0x08
CMD_WRITE_EEPROM = 0x07
CMD_BATTERY = 0x04
CMD_VERSION = 0x12
CMD_CID_MID = 0x10
CMD_CURRENT_PROFILE = 0x0E
CMD_SET_PROFILE = 0x0F
CMD_LONG_RANGE_GET = 0x17
CMD_LONG_RANGE_SET = 0x16
CMD_RECEIVER_ONLINE = 0x03
CMD_RECEIVER_PAIR_STATUS = 0x06

# EEPROM map shared by the family.
ADDR_SYSTEM = 0x0000
ADDR_LIFT_OFF = 0x000A
ADDR_DPI_BASE = 0x000C
ADDR_STAGE_COLOR_BASE = 0x002C
ADDR_DPI_LIGHT = 0x004C
ADDR_ADVANCED = 0x00A9
ADDR_ANGLE = 0x00BD
ADDR_SENSOR_MODE = 0x00B5

SUPPORTED_VIDS = (0x373B, 0x3554)

# USB ids that are receivers rather than a mouse's own cable connection.
# The ceiling is the link's maximum report rate.
RECEIVER_CEILINGS: dict[int, int] = {
    0x1040: 8000,  # COMPX MAD 8K Dongle
    0x101B: 8000,  # ATK Mouse 8K Dongle
    0x1031: 8000,  # ATK 8K Dongle Light
    0x111A: 8000,
    0x111B: 8000,
    0x1159: 8000,
    0x115E: 8000,
    0x11A7: 8000,
    0x11C8: 8000,
    0x11CD: 8000,
    0x11CE: 8000,
    0x11D8: 8000,
    0x11D9: 8000,
    0x11F4: 8000,
    0x11FD: 8000,
    0x11FE: 8000,
    0x1278: 8000,
    0x1279: 8000,
    0x127A: 8000,
    0x127B: 8000,
    0x12CC: 8000,
    0x12E9: 8000,
    0x1303: 8000,
    0x101A: 1000,
    0x104D: 1000,
    0x1085: 1000,
    0x10C9: 1000,
    0x11A9: 4000,  # ATK / VXE 4K dongle
    0xF400: 1000,
    0xF505: 4000,
    0xF50B: 1000,
    0xF58A: 1000,
    0xF58D: 4000,
    0xF58E: 1000,
}

# Human-readable receiver names for the USB ids we have seen in the vendor
# device database.  Unknown ids fall back to the USB product string.
RECEIVER_NAMES: dict[int, str] = {
    0x1040: "MAD 8K Dongle",
    0x101A: "ATK 1K Dongle",
    0x101B: "ATK 8K Dongle",
    0x10C9: "ATK NearLink Dongle",
    0x11A9: "ATK 4K Dongle",
    0xF58A: "VXE 1K Dongle",
    0xF58D: "VXE 4K Dongle",
    0xF58E: "VXE 1K Dongle",
    0xF505: "VGN/VXE 4K Dongle",
}

POLLING_CODES: tuple[tuple[int, int], ...] = (
    (0x08, 125),
    (0x04, 250),
    (0x02, 500),
    (0x01, 1000),
    (0x10, 2000),
    (0x20, 4000),
    (0x40, 8000),
)
POLLING_FROM_CODE = dict(POLLING_CODES)
POLLING_TO_CODE = {hz: code for code, hz in POLLING_CODES}

LIFT_OFF_CODES: tuple[tuple[int, int], ...] = ((1, 7), (4, 10), (11, 17))
LIFT_OFF_MM_TO_CODE = {mm: code for code, mm in LIFT_OFF_CODES}
LIFT_OFF_LABELS = {7: "Low", 10: "Medium", 17: "High"}

SLEEP_STEP_SECONDS = 10
DEFAULT_SLEEP_OPTIONS = (30, 60, 120, 180, 300, 600, 1200, 1800)
DEFAULT_DEBOUNCE_OPTIONS = (0, 1, 2, 4, 8, 15, 20)


class ProtocolError(Exception):
    """A device answered with malformed data or did not answer."""


class DeviceNotFound(ProtocolError):
    pass


class PermissionDenied(ProtocolError):
    pass


class DeviceBusy(ProtocolError):
    pass


def checksum(payload15: bytes) -> int:
    """Checksum for a frame, including the report id in the byte sum."""
    if len(payload15) != PAYLOAD_SIZE - 1:
        raise ValueError("checksum() expects 15 payload bytes")
    return (CHECKSUM_TOTAL - ((REPORT_ID + sum(payload15)) & 0xFF)) & 0xFF


def build_frame(cmd: int, body: bytes = b"") -> bytes:
    """Build one 16-byte payload (without the report id)."""
    if not 0 <= cmd <= 0xFF:
        raise ValueError("command must be a byte")
    if len(body) > 14:
        raise ValueError("body too long for one COMPX frame")
    payload = bytearray(PAYLOAD_SIZE)
    payload[0] = cmd
    payload[1:1 + len(body)] = body
    payload[15] = checksum(bytes(payload[:15]))
    return bytes(payload)


def build_read(addr: int, length: int) -> bytes:
    if not 1 <= length <= MAX_EEPROM_CHUNK:
        raise ValueError("read length must be 1-10")
    if not 0 <= addr <= 0xFFFF:
        raise ValueError("address out of range")
    return build_frame(
        CMD_READ_EEPROM,
        bytes((0, (addr >> 8) & 0xFF, addr & 0xFF, length)),
    )


def build_write(addr: int, data: bytes) -> bytes:
    if not 1 <= len(data) <= MAX_EEPROM_CHUNK:
        raise ValueError("write length must be 1-10")
    if not 0 <= addr <= 0xFFFF:
        raise ValueError("address out of range")
    return build_frame(
        CMD_WRITE_EEPROM,
        bytes((0, (addr >> 8) & 0xFF, addr & 0xFF, len(data))) + bytes(data),
    )


def report_is_valid(report_id: int, payload: bytes) -> bool:
    return (
        report_id == REPORT_ID
        and len(payload) >= PAYLOAD_SIZE
        and checksum(bytes(payload[:15])) == payload[15]
    )


def decode_report(raw: bytes) -> bytes | None:
    """Return the 16-byte payload from a hidraw read, or None."""
    if not raw:
        return None
    if raw[0] == REPORT_ID and len(raw) >= WIRE_SIZE:
        payload = bytes(raw[1:WIRE_SIZE])
        return payload if report_is_valid(REPORT_ID, payload) else None
    # A few hidraw backends strip the numbered report id for the app.
    if len(raw) >= PAYLOAD_SIZE:
        payload = bytes(raw[:PAYLOAD_SIZE])
        return payload if report_is_valid(REPORT_ID, payload) else None
    return None


def decode_pair(value: int, check: int) -> int | None:
    if (value + check) & 0xFF != CHECKSUM_TOTAL:
        return None
    return value & 0xFF


def pack_pair(value: int) -> bytes:
    value &= 0xFF
    return bytes((value, (CHECKSUM_TOTAL - value) & 0xFF))


def decode_dpi_axis(byte: int, nibble: int, family: str = "step50") -> int:
    if family == "ultra":
        code = (((nibble >> 2) & 0x03) << 8) | (byte & 0xFF)
        base = 10050 + code * 50 if nibble & 2 else (code + 1) * 10
        return base * 2 if nibble & 1 else base
    if family == "step50":
        count = (byte & 0xFF) | (((nibble >> 2) & 0x03) << 8)
        dpi = (count + 1) * 50
        return dpi * 2 if nibble & 1 else dpi
    raise ValueError(f"unsupported DPI family {family}")


def encode_dpi_axis(dpi: int, family: str = "step50") -> tuple[int, int]:
    if family == "ultra":
        value = dpi
        doubled = 0
        if value > 30000:
            doubled = 1
            value = round(value / 2)
        if value <= 10000:
            code = value // 10 - 1
            return code & 0xFF, (((code >> 8) << 2) | doubled) & 0x0F
        code = (value - 10050) // 50
        return code & 0xFF, (((code >> 8) << 2) | 2 | doubled) & 0x0F
    if family == "step50":
        doubled = dpi > 30000
        count = round(dpi / (100 if doubled else 50)) - 1
        return count & 0xFF, ((((count >> 8) & 0x03) << 2) | (1 if doubled else 0)) & 0x0F
    raise ValueError(f"unsupported DPI family {family}")


def pack_dpi_stage(x: int, y: int, family: str = "step50") -> bytes:
    xb, xn = encode_dpi_axis(x, family)
    yb, yn = encode_dpi_axis(y, family)
    mode = ((yn & 0x0F) << 4) | (xn & 0x0F)
    total = (xb + yb + mode) & 0xFF
    return bytes((xb, yb, mode, (CHECKSUM_TOTAL - total) & 0xFF))


def unpack_dpi_stage(data: bytes, family: str = "step50") -> tuple[int, int] | None:
    if len(data) < 4 or (sum(data[:4]) & 0xFF) != CHECKSUM_TOTAL:
        return None
    try:
        return (
            decode_dpi_axis(data[0], data[2] & 0x0F, family),
            decode_dpi_axis(data[1], (data[2] >> 4) & 0x0F, family),
        )
    except ValueError:
        return None


def dpi_values(min_dpi: int, max_dpi: int, family: str) -> list[int]:
    """The vendor's selectable DPI values for a sensor."""
    values: list[int] = []
    if family == "ultra":
        values.extend(range(min_dpi, min(max_dpi, 10000) + 1, 10))
        values.extend(range(10050, min(max_dpi, 30000) + 1, 50))
        values.extend(range(30100, max_dpi + 1, 100))
    else:
        values.extend(range(min_dpi, min(max_dpi, 10000) + 1, 50))
        values.extend(range(10050, min(max_dpi, 30000) + 1, 50))
        values.extend(range(30100, max_dpi + 1, 100))
    return [v for v in values if v >= min_dpi]


def clamp_dpi(value: int, options: list[int]) -> int:
    if not options:
        return value
    return min(options, key=lambda item: abs(item - value))


def pack_rgb(color: str) -> bytes | None:
    text = color.strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        rgb = bytes(int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None
    total = sum(rgb) & 0xFF
    return rgb + bytes(((CHECKSUM_TOTAL - total) & 0xFF,))


def unpack_rgb(record: bytes) -> str | None:
    if len(record) < 4 or (sum(record[:4]) & 0xFF) != CHECKSUM_TOTAL:
        return None
    return "#" + "".join(f"{byte:02x}" for byte in record[:3])


@dataclass
class DeviceInfo:
    path: str
    vendor_id: int
    product_id: int
    product_name: str
    interface: str = ""
    bcd_device: str = ""
    accessible: bool = True

    @property
    def hidraw_name(self) -> str:
        return os.path.basename(self.path)

    @property
    def is_receiver(self) -> bool:
        return self.product_id in RECEIVER_CEILINGS or any(
            word in self.product_name.lower()
            for word in ("dongle", "receiver", "8k", "4k")
        )

    @property
    def link_ceiling(self) -> int:
        return RECEIVER_CEILINGS.get(self.product_id, 8000 if self.is_receiver else 1000)


def _read_uevent(sysdev: Path) -> dict[str, str]:
    try:
        text = (sysdev / "device" / "uevent").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    result: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _read_descriptor(sysdev: Path) -> bytes:
    try:
        return (sysdev / "device" / "report_descriptor").read_bytes()
    except OSError:
        return b""


def _is_config_descriptor(descriptor: bytes) -> bool:
    if not descriptor:
        return False
    # Usage Page (Vendor 0xff02), Usage (2), Report ID 8, 16-byte in/out.
    return (
        b"\x06\x02\xff\x09\x02" in descriptor
        and b"\x85\x08" in descriptor
        and b"\x95\x10" in descriptor
    )


def discover(vendor_ids: tuple[int, ...] = SUPPORTED_VIDS) -> list[DeviceInfo]:
    """Find COMPX configuration collections under /sys/class/hidraw."""
    found: list[DeviceInfo] = []
    base = Path("/sys/class/hidraw")
    try:
        entries = sorted(base.iterdir())
    except OSError:
        return found

    for sysdev in entries:
        uevent = _read_uevent(sysdev)
        hid_id = uevent.get("HID_ID", "").upper()
        parts = hid_id.split(":")
        if len(parts) != 3:
            continue
        try:
            vendor = int(parts[1], 16)
            product = int(parts[2], 16)
        except ValueError:
            continue
        if vendor not in vendor_ids:
            continue
        descriptor = _read_descriptor(sysdev)
        if not _is_config_descriptor(descriptor):
            continue
        bcd = ""
        # The hidraw node sits under a HID device node; the USB device with
        # bcdDevice is two levels above the interface directory.
        for candidate in (
            sysdev / "device" / "bcdDevice",
            sysdev / "device" / ".." / ".." / "bcdDevice",
        ):
            try:
                bcd = candidate.read_text(encoding="ascii").strip()
                if bcd:
                    break
            except OSError:
                continue
        path = f"/dev/{sysdev.name}"
        found.append(
            DeviceInfo(
                path=path,
                vendor_id=vendor,
                product_id=product,
                product_name=uevent.get("HID_NAME", "ATK/VXE mouse").strip(),
                interface=os.path.basename(os.path.realpath(sysdev / "device")),
                bcd_device=bcd,
                accessible=os.access(path, os.R_OK | os.W_OK),
            )
        )
    # A receiver and the directly cabled mouse can both be present; the worker
    # handles preference, but a stable order keeps the CLI predictable.
    found.sort(key=lambda item: (item.is_receiver, item.vendor_id, item.product_id, item.path))
    return found


class CompxTransport:
    """Blocking hidraw transport for one configuration collection."""

    def __init__(self, path: str, timeout: float = 0.6, debug: bool = False) -> None:
        self.path = path
        self.timeout = timeout
        self.debug = debug
        self.fd = -1
        self.last_error: str | None = None
        self._bcd = ""
        self._device_lock: DeviceLock | None = None

    def open(self) -> None:
        if self.fd >= 0:
            return
        if self._device_lock is None:
            self._device_lock = DeviceLock(self.path)
        try:
            self._device_lock.acquire()
        except LockBusy as exc:
            raise DeviceBusy(str(exc)) from exc
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as exc:
            self._device_lock.release()
            raise PermissionDenied(
                f"No permission for {self.path}. Install the ATK Control udev rule "
                "(71-atk-control.rules) and reconnect the device."
            ) from exc
        except FileNotFoundError as exc:
            self._device_lock.release()
            raise DeviceNotFound(f"{self.path} disappeared") from exc
        except OSError as exc:
            self._device_lock.release()
            raise ProtocolError(f"could not open {self.path}: {exc}") from exc

    def close(self) -> None:
        if self.fd >= 0:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = -1
        if self._device_lock is not None:
            self._device_lock.release()
            self._device_lock = None

    @property
    def is_open(self) -> bool:
        return self.fd >= 0

    def __enter__(self) -> "CompxTransport":
        self.open()
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- raw I/O -----------------------------------------------------------
    def _write(self, payload: bytes) -> None:
        if self.fd < 0:
            raise ProtocolError("device is not open")
        report = bytes((REPORT_ID,)) + bytes(payload)
        try:
            written = os.write(self.fd, report)
        except OSError as exc:
            raise ProtocolError(f"write failed: {exc}") from exc
        if written not in (len(report), len(payload)):
            raise ProtocolError(f"short HID write ({written} bytes)")
        if self.debug:
            print(">>", report.hex(" "))

    def _read_report(self, timeout: float) -> bytes | None:
        if self.fd < 0:
            return None
        ready, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        if not ready:
            return None
        try:
            data = os.read(self.fd, 65)
        except BlockingIOError:
            return None
        except OSError as exc:
            if exc.errno in (errno.ENODEV, errno.EIO):
                raise DeviceNotFound(f"device disappeared: {exc}") from exc
            raise ProtocolError(f"read failed: {exc}") from exc
        if self.debug and data:
            print("<<", data.hex(" "))
        return data

    def drain(self, settle: float = 0.025) -> None:
        deadline = time.monotonic() + settle
        while time.monotonic() < deadline:
            if self._read_report(max(0.0, deadline - time.monotonic())) is None:
                break

    def _exchange(self, payload: bytes, matcher, retries: int = 3) -> bytes:
        last: Exception | None = None
        for _attempt in range(max(1, retries)):
            self.drain(0.005)
            self._write(payload)
            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                raw = self._read_report(max(0.0, deadline - time.monotonic()))
                if raw is None:
                    break
                reply = decode_report(raw)
                if reply is None:
                    continue
                if matcher(reply):
                    return reply
            last = ProtocolError("the mouse did not answer (asleep, out of range, or another app owns it)")
        assert last is not None
        raise last

    # -- commands ----------------------------------------------------------
    def read_eeprom(self, addr: int, length: int) -> bytes:
        request = build_read(addr, length)
        hi, lo = (addr >> 8) & 0xFF, addr & 0xFF

        def matches(reply: bytes) -> bool:
            return (
                reply[0] == CMD_READ_EEPROM
                and reply[1] == 0
                and reply[2] == hi
                and reply[3] == lo
                and reply[4] >= length
            )

        reply = self._exchange(request, matches)
        return bytes(reply[5:5 + length])

    def write_eeprom(self, addr: int, data: bytes) -> None:
        """Write one register and consume the optional echo.

        Callers must read the value back when confirmation matters.
        """
        if self.fd < 0:
            raise ProtocolError("device is not open")
        self.drain(0.005)
        self._write(build_write(addr, data))
        # Some receivers echo the write frame; draining it here prevents a
        # stale echo from being mistaken for the next read.
        self.drain(0.03)

    def _simple_command(self, cmd: int, attempts: int = 3) -> bytes:
        def matches(reply: bytes) -> bool:
            return reply[0] == cmd and reply[1] == 0

        return self._exchange(build_frame(cmd), matches, retries=attempts)

    def read_battery(self) -> dict[str, int | bool | None]:
        reply = self._simple_command(CMD_BATTERY)
        length = min(reply[4], 10)
        data = reply[5:5 + length]
        percent = data[0] if len(data) >= 1 else None
        charging = bool(data[1]) if len(data) >= 2 else None
        millivolts = None
        if len(data) >= 4:
            mv = (data[2] << 8) | data[3]
            millivolts = mv if mv > 0 else None
        return {"percent": percent, "charging": charging, "millivolts": millivolts}

    def read_identity(self) -> tuple[int, int]:
        reply = self._simple_command(CMD_CID_MID)
        if reply[4] < 2:
            raise ProtocolError("short CID/MID reply")
        return reply[5], reply[6]

    def read_firmware(self, attempts: int = 1) -> str:
        reply = self._simple_command(CMD_VERSION, attempts=attempts)
        length = min(reply[4], 10)
        data = reply[5:5 + length]
        if len(data) < 2:
            return ""
        return f"{data[0]:x}.{data[1]:02x}"

    def read_profile(self) -> int | None:
        try:
            reply = self._simple_command(CMD_CURRENT_PROFILE)
        except ProtocolError:
            return None
        return reply[5] if reply[4] >= 1 and reply[5] < 4 else None

    def set_profile(self, profile: int) -> None:
        if not 0 <= profile <= 3:
            raise ValueError("profile must be 0-3")
        frame = bytearray(build_frame(CMD_SET_PROFILE))
        frame[4] = 1
        frame[5] = profile
        frame[15] = 0
        frame[15] = checksum(bytes(frame[:15]))
        self._exchange(bytes(frame), lambda reply: reply[0] == CMD_SET_PROFILE and reply[1] == 0)

    def receiver_online(self) -> dict | None:
        try:
            reply = self._simple_command(CMD_RECEIVER_ONLINE)
        except ProtocolError:
            return None
        data = reply[5:5 + max(4, reply[4])]
        if len(data) < 4:
            return None
        return {
            "online": data[0] == 1,
            "status": data[0],
            "rf_id": bytes((data[3], data[2], data[1])).hex(" ").upper(),
        }

    def read_long_range(self) -> bool | None:
        try:
            reply = self._simple_command(CMD_LONG_RANGE_GET)
        except ProtocolError:
            return None
        if reply[4] < 1 or reply[5] > 1:
            return None
        return reply[5] == 1

    def set_long_range(self, enabled: bool) -> None:
        frame = bytearray(build_frame(CMD_LONG_RANGE_SET, bytes((0, 0, 0, 10, 1 if enabled else 0))))
        frame[15] = 0
        frame[15] = checksum(bytes(frame[:15]))
        self._write(bytes(frame))
        time.sleep(0.03)
        self.drain(0.02)
        confirmed = self.read_long_range()
        if confirmed is not enabled:
            raise ProtocolError("the mouse did not retain the long-range setting")


def format_bcd(value: str) -> str:
    """Turn a sysfs bcdDevice string such as '0123' into '1.23'."""
    value = value.strip()
    if not value:
        return ""
    try:
        number = int(value, 16)
    except ValueError:
        return value
    return f"{number >> 8:x}.{number & 0xFF:02x}"


def battery_is_plausible(percent: int | None, charging: bool | None) -> bool:
    return percent is not None and 0 <= percent <= 100 and charging is not None
