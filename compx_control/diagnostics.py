"""Read-only diagnostics report for support requests."""

from __future__ import annotations

import datetime as dt
import platform
import socket
from pathlib import Path

from . import config, protocol
from .state import MouseState


def _safe(value) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def report_text(state: MouseState, device_path: str | None = None,
                caps=None) -> str:
    """Build a Markdown report. RF identifiers and serials are redacted."""
    lines: list[str] = []
    lines.append("# Compx Control device report")
    lines.append("")
    lines.append(f"Generated: {dt.datetime.now().astimezone().isoformat(timespec='seconds')}")
    lines.append(f"Compx Control: {config.VERSION}")
    lines.append("")
    lines.append("## System")
    lines.append("")
    lines.append(f"- OS: {platform.platform()}")
    lines.append(f"- Kernel: {platform.release()}")
    lines.append(f"- Session: {platform.freedesktop_os_release().get('PRETTY_NAME', 'unknown')}")
    lines.append(f"- Hostname: {socket.gethostname()}")
    lines.append("")
    lines.append("## Device")
    lines.append("")
    lines.append(f"- Model: {state.model_name or state.usb_name}")
    lines.append(f"- Brand: {state.brand}")
    lines.append(f"- Sensor: {state.sensor}")
    lines.append(f"- USB ID: {state.vendor_id:04x}:{state.product_id:04x}")
    lines.append(f"- USB device revision: {state.usb_bcd or 'unknown'}")
    lines.append(f"- Firmware: {state.firmware or 'unknown'}")
    lines.append(f"- CID/MID: {state.identity}")
    lines.append(f"- Connection: {state.link_label}")
    if state.via_receiver:
        receiver = (
            f"{state.receiver_name} (0x{state.receiver_pid:04x})"
            if state.receiver_pid else "unknown"
        )
        rf_prefix = state.rf_id.split()[0] if state.rf_id else ""
        lines.append(f"- Receiver: {receiver}")
        lines.append(f"- Receiver RF id: {rf_prefix + ' ••••••' if rf_prefix else 'unknown'}")
        lines.append(f"- Receiver online: {_safe(state.receiver_online)}")
    if device_path:
        lines.append(f"- Node: {Path(device_path).name}")
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
    lines.append("")
    lines.append("## Settings")
    lines.append("")
    rows = [
        ("Lift-off code", state.lod_code),
        ("Lift-off distance", f"{state.lod_mm:.1f} mm" if state.lod_mm else None),
        ("Debounce", f"{state.debounce_ms} ms" if state.debounce_ms is not None else None),
        ("Motion Sync", state.motion_sync),
        ("Ripple control", state.ripple_control),
        ("Straight-line correction", state.straight_line),
        ("Sleep timer", f"{state.sleep_seconds} s" if state.sleep_seconds else None),
        ("Sensor rotation", f"{state.angle_degrees} deg, {'on' if state.angle_enabled else 'off'}" if state.angle_degrees is not None else None),
        ("Performance mode", state.performance_mode),
        ("Long range", state.long_range),
        ("LED mode", state.led_mode),
        ("LED brightness", state.led_brightness),
        ("LED speed", state.led_speed),
        ("Profile", state.profile),
    ]
    for label, value in rows:
        lines.append(f"- {label}: {_safe(value)}")
    lines.append("")
    if state.buttons:
        lines.append("## Buttons (read-only)")
        lines.append("")
        for button in state.buttons:
            lines.append(f"- {button.name}: {button.action}")
        lines.append("")
    lines.append("## Privacy")
    lines.append("")
    lines.append("This report is generated locally. It does not include the full RF")
    lines.append("identifier, USB serial number or any file paths outside the app.")
    lines.append("Review it before attaching it to a public issue.")
    lines.append("")
    return "\n".join(lines)


def default_filename() -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M")
    return f"compx-control-report-{stamp}.md"


def write_report(path: str | Path, state: MouseState,
                 device_path: str | None = None, caps=None) -> Path:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report_text(state, device_path, caps), encoding="utf-8")
    return target


def diagnostics_available() -> bool:
    return bool(protocol.SUPPORTED_VIDS)
