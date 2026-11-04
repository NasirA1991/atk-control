"""Read-only, sanitized diagnostics for adding ATK/VXE mouse support."""

from __future__ import annotations

import datetime as dt
import platform
from pathlib import Path

from . import config
from .state import MouseState


def _safe(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _node_name(path: str | None) -> str:
    return Path(path).name if path else "unknown"


def _interface_lines() -> list[str]:
    """List configuration interfaces without exposing serials or USB paths."""
    from .protocol import discover

    try:
        devices = discover()
    except Exception:
        return ["- none detected"]
    if not devices:
        return ["- none detected"]
    lines = []
    for info in devices:
        kind = "receiver" if info.is_receiver else "mouse"
        access = "read/write" if info.accessible else "no permission"
        rev = f" rev {info.bcd_device}" if info.bcd_device else ""
        lines.append(
            f"- `{_node_name(info.path)}` — {info.vendor_id:04x}:{info.product_id:04x}"
            f" — {info.product_name}{rev} — {kind} — {access}"
        )
    return lines


def _raw_lines(raw_registers: dict[int, bytes | None]) -> list[str]:
    lines = []
    for address in sorted(raw_registers):
        data = raw_registers[address]
        if data:
            lines.append(f"`0x{address:04x}`  {data.hex(' ')}")
        else:
            lines.append(f"`0x{address:04x}`  <read failed>")
    return lines


def report_text(state: MouseState, device_path: str | None = None,
                caps=None, raw_registers: dict[int, bytes | None] | None = None) -> str:
    """Build a Markdown report suitable for a public issue.

    The full RF identifier is replaced by a short prefix, the host name is not
    included, and only the selected hidraw node name is recorded.
    """
    lines: list[str] = []
    lines.append("# ATK Control device report")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}")
    lines.append(f"ATK Control: {config.VERSION}")
    lines.append("")
    lines.append("## System")
    lines.append("")
    lines.append(f"- OS: {platform.platform()}")
    lines.append(f"- Kernel: {platform.release()}")
    lines.append(f"- Distribution: {platform.freedesktop_os_release().get('PRETTY_NAME', 'unknown')}")
    lines.append("")
    lines.append("## Configuration interfaces")
    lines.append("")
    lines.extend(_interface_lines())
    lines.append("")
    if device_path:
        lines.append(f"- Selected node: `{_node_name(device_path)}`")
        lines.append("")
    lines.append("## Device")
    lines.append("")
    lines.append(f"- Model: {state.model_name or state.usb_name}")
    lines.append(f"- Brand: {state.brand}")
    lines.append(f"- Sensor: {state.sensor}")
    lines.append(f"- USB ID: {state.vendor_id:04x}:{state.product_id:04x}")
    lines.append(f"- USB device revision: {state.usb_bcd or 'unknown'}")
    lines.append(f"- Firmware: {state.firmware or 'not reported'}")
    lines.append(f"- CID/MID: {state.identity}")
    lines.append(f"- Connection: {state.link_label}")
    lines.append(f"- Read-only mode: {_safe(state.read_only)}")
    if state.via_receiver:
        receiver = (
            f"{state.receiver_name} (0x{state.receiver_pid:04x})"
            if state.receiver_pid else "unknown"
        )
        rf_prefix = state.rf_id.split()[0] if state.rf_id else ""
        lines.append(f"- Receiver: {receiver}")
        lines.append(f"- Receiver RF id: {rf_prefix + ' ••••••' if rf_prefix else 'unknown'}")
        lines.append(f"- Receiver online: {_safe(state.receiver_online)}")
    lines.append("")
    lines.append("## Telemetry")
    lines.append("")
    lines.append(f"- Battery: {_safe(state.battery)}%")
    lines.append(f"- Charging: {_safe(state.charging)}")
    lines.append(f"- Voltage: {state.voltage_mv} mV" if state.voltage_mv else "- Voltage: unknown")
    lines.append(f"- Active DPI: {state.dpi} x {state.dpi_y}")
    lines.append(f"- DPI stages: {', '.join(f'{x}x{y}' for x, y in state.stages)}")
    lines.append(f"- Active stage: {state.active_stage + 1} of {state.stage_count}")
    lines.append(f"- Polling: {state.polling_rate} Hz")
    if caps is not None:
        lines.append(f"- Link ceiling: {caps.link_ceiling} Hz")
        lines.append(f"- DPI range: {caps.sensor.min_dpi}-{caps.sensor.max_dpi} ({caps.sensor.name})")
        lines.append(f"- Polling choices: {', '.join(str(v) for v in caps.polling_rates)} Hz")
    lines.append("")
    lines.append("## Settings read from the mouse")
    lines.append("")
    rows = [
        ("Lift-off code", state.lod_code),
        ("Lift-off distance", f"{state.lod_mm:.1f} mm" if state.lod_mm else None),
        ("Debounce", f"{state.debounce_ms} ms" if state.debounce_ms is not None else None),
        ("Motion Sync", state.motion_sync),
        ("Ripple control", state.ripple_control),
        ("Straight-line correction", state.straight_line),
        ("Sleep timer", f"{state.sleep_seconds} s" if state.sleep_seconds else None),
        (
            "Sensor rotation",
            f"{state.angle_degrees} deg, {'on' if state.angle_enabled else 'off'}"
            if state.angle_degrees is not None else None,
        ),
        ("Performance mode", state.performance_mode),
        ("Long range", state.long_range),
        ("LED mode", state.led_mode),
        ("LED brightness", state.led_brightness),
        ("LED speed", state.led_speed),
        ("Profile", state.profile),
        ("Supports angle", state.supports_angle),
        ("Supports lighting", state.supports_lighting),
        ("Supports stage colours", state.supports_stage_colors),
    ]
    for label, value in rows:
        lines.append(f"- {label}: {_safe(value)}")
    lines.append("")
    if state.buttons:
        lines.append("## Buttons (read-only)")
        lines.append("")
        for button in state.buttons:
            lines.append(f"- {button.name}: {button.action}  (`{button.raw}`)")
        lines.append("")
    lines.append("## Raw configuration registers")
    lines.append("")
    if raw_registers is None:
        lines.append(
            "Omitted by default. Enable **Include raw registers** before saving, "
            "or pass `--raw`, if the maintainers ask for raw bytes. Raw bytes are "
            "undocumented device data and should be reviewed before sharing."
        )
    else:
        lines.append("Read-only dump of the vendor register window used by the app.")
        lines.append(
            "These are undocumented device bytes; review them before attaching "
            "the report to a public issue."
        )
        lines.append("")
        lines.extend(_raw_lines(raw_registers))
    lines.append("")
    lines.append("## Privacy")
    lines.append("")
    lines.append("This report is generated locally. The full RF identifier, host name,")
    lines.append("USB serial number and user file paths are not included. Raw registers")
    lines.append("are opt-in and are omitted from the default report. Review the report")
    lines.append("before attaching it to a public issue.")
    lines.append("")
    lines.append(f"Support request: {config.SUPPORT_URL}")
    lines.append("")
    return "\n".join(lines)


def default_filename() -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    return f"atk-control-report-{stamp}.md"


def write_report(path: str | Path, state: MouseState,
                 device_path: str | None = None, caps=None,
                 raw_registers: dict[int, bytes | None] | None = None) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        report_text(state, device_path, caps, raw_registers),
        encoding="utf-8",
    )
    return target
