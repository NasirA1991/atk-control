"""Headless CLI: atkctl."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

from . import config, devices, diagnostics, protocol
from .controller import BUTTON_ACTION_ORDER, Controller
from .protocol import DeviceNotFound, PermissionDenied, ProtocolError, discover
from .state import MouseState


def _state_dict(state: MouseState) -> dict:
    data = dataclasses.asdict(state)
    if data.get("rf_id"):
        data["rf_id"] = data["rf_id"][:2] + "••••••"
    return data


def _open(path: str | None = None) -> Controller:
    candidates = discover()
    if path:
        candidates = [c for c in candidates if c.path == path]
        if not candidates:
            raise ProtocolError(f"{path} is not an ATK/VXE configuration interface")
    errors: list[str] = []
    for info in candidates:
        controller = Controller(info)
        try:
            controller.open()
        except PermissionDenied as exc:
            errors.append(str(exc))
            continue
        except (ProtocolError, OSError) as exc:
            receiver = devices.receiver_for(info.product_id, info.product_name)
            display = receiver.name if receiver else info.product_name
            errors.append(f"{display}: {exc}")
            continue
        return controller
    if errors:
        raise ProtocolError(errors[0])
    raise DeviceNotFound("No ATK/VXE mouse or receiver found. Check the udev rule.")


def _print_scan() -> int:
    candidates = discover()
    if not candidates:
        print("No ATK/VXE configuration interface found.")
        return 1
    for info in candidates:
        access = "read/write" if info.accessible else "no permission"
        kind = "receiver" if info.is_receiver else "mouse"
        print(f"{info.path}  {info.vendor_id:04x}:{info.product_id:04x}  "
              f"{kind:8}  {info.product_name}  [{access}]")
    return 0


def _caps_text(caps: devices.Capabilities) -> str:
    lines = [
        f"Model:          {caps.name}",
        f"Brand:          {caps.brand}",
        f"Sensor:         {caps.sensor.name} ({caps.sensor.family})",
        f"DPI range:      {caps.sensor.min_dpi}-{caps.sensor.max_dpi}",
        f"Polling rates:  {', '.join(str(v) for v in caps.polling_rates)} Hz",
        f"Link ceiling:   {caps.link_ceiling} Hz",
        f"Receiver:       {caps.receiver.name if caps.receiver else 'wired/direct'}",
        f"Sensor angle:   {'yes' if caps.angle else 'no'}",
        f"DPI lighting:   {'yes' if caps.dpi_lighting else 'no'}",
        f"Stage colours:  {'yes' if caps.stage_colors else 'no'}",
        f"Performance:    {'yes' if caps.performance_mode else 'no'}",
        f"Long range:     {'yes' if caps.long_range else 'no'}",
    ]
    return "\n".join(lines)


def _status(controller: Controller, as_json: bool) -> int:
    state = controller.read_full()
    caps = controller.caps
    if as_json:
        payload = _state_dict(state)
        payload["connection"] = state.link_label
        payload["link_ceiling"] = caps.link_ceiling
        payload["supported_polling_rates"] = caps.polling_rates
        payload["dpi_min"] = caps.sensor.min_dpi
        payload["dpi_max"] = caps.sensor.max_dpi
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    display = state.model_name
    if state.brand and not display.lower().startswith(state.brand.lower()):
        display = f"{state.brand} {display}"
    print(f"{display}  ({state.vendor_id:04x}:{state.product_id:04x})")
    print(f"Link       : {state.link_label}")
    print(f"Battery    : {state.battery if state.battery is not None else '?'}%"
          + (" charging" if state.charging else ""))
    if state.voltage_mv:
        print(f"Voltage    : {state.voltage_mv} mV")
    firmware = state.firmware or (
        "not forwarded by the receiver" if state.via_receiver else "unknown"
    )
    print(f"Firmware   : {firmware}")
    print(f"DPI        : {state.dpi} x {state.dpi_y}  (stage {state.active_stage + 1}/{state.stage_count})")
    print(f"Polling    : {state.polling_rate} Hz")
    print(f"Motion sync: {_onoff(state.motion_sync)}")
    print(f"Ripple     : {_onoff(state.ripple_control)}")
    if state.sensor_mode is not None:
        print(f"Sensor mode: {_sensor_mode_label(state.sensor_mode)}")
    print(f"Lift-off   : {state.lod_mm:.1f} mm" if state.lod_mm is not None else "Lift-off   : unknown")
    print(f"Debounce   : {state.debounce_ms} ms" if state.debounce_ms is not None else "Debounce   : unknown")
    print(f"Sleep      : {state.sleep_seconds} s" if state.sleep_seconds else "Sleep      : unknown")
    return 0


def _sensor_mode_label(mode: int) -> str:
    return {
        0: "Basic",
        1: "Competitive",
        2: "Competitive MAX",
        3: "Competitive MAX 13K",
    }.get(mode, f"mode {mode}")


def _onoff(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "on" if value else "off"


def _parse_onoff(value: str) -> bool:
    text = value.lower()
    if text in ("on", "yes", "true", "1", "enable", "enabled"):
        return True
    if text in ("off", "no", "false", "0", "disable", "disabled"):
        return False
    raise argparse.ArgumentTypeError("expected on or off")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atkctl",
        description="Configure ATK/VXE gaming mice (MAD R, VXE R1 and relatives).",
    )
    parser.add_argument("--device", help="hidraw node to use, for example /dev/hidraw22")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("status", help="show device status")
    p.add_argument("--json", action="store_true")

    sub.add_parser("scan", help="list detected ATK/VXE interfaces")
    sub.add_parser("caps", help="show supported features and ranges")

    p = sub.add_parser("polling", help="set the report rate")
    p.add_argument("hz", type=int)

    p = sub.add_parser("dpi", help="set DPI for the active stage")
    p.add_argument("dpi", type=int)
    p.add_argument("--y", type=int, help="separate Y DPI")
    p.add_argument("--stage", type=int, help="1-based DPI stage (default: active)")

    p = sub.add_parser("stage", help="switch the active DPI stage")
    p.add_argument("number", type=int)

    p = sub.add_parser("motion-sync", help="toggle Motion Sync")
    p.add_argument("value", type=_parse_onoff)

    p = sub.add_parser("ripple", help="toggle ripple control")
    p.add_argument("value", type=_parse_onoff)

    p = sub.add_parser("straight-line", help="toggle straight-line correction")
    p.add_argument("value", type=_parse_onoff)

    p = sub.add_parser("performance", help="toggle competitive performance mode")
    p.add_argument("value", type=_parse_onoff)

    p = sub.add_parser("sensor-mode", help="set sensor sampling mode")
    p.add_argument("mode", choices=["basic", "competitive", "max", "max13k", "0", "1", "2", "3"])

    p = sub.add_parser("button", help="remap a physical button (1-6)")
    p.add_argument("index", type=int, help="button number from `atkctl status --json`/UI")
    p.add_argument("action", choices=list(BUTTON_ACTION_ORDER))

    sub.add_parser("buttons-reset", help="restore default mouse button assignments")

    sub.add_parser("add-stage", help="add a DPI stage (copies the last stage)")
    sub.add_parser("remove-stage", help="remove the last DPI stage")

    p = sub.add_parser("long-range", help="toggle long-range mode")
    p.add_argument("value", type=_parse_onoff)

    p = sub.add_parser("lod", help="set lift-off distance in millimetres (1 or 2)")
    p.add_argument("value")

    p = sub.add_parser("debounce", help="set button debounce in milliseconds")
    p.add_argument("ms", type=int)

    p = sub.add_parser("sleep", help="set the sleep timer in seconds")
    p.add_argument("seconds", type=int)

    p = sub.add_parser("angle", help="set sensor rotation in degrees")
    p.add_argument("degrees", type=int)
    p.add_argument("--off", action="store_true", help="disable rotation")

    p = sub.add_parser("profile", help="select an onboard profile (1-4)")
    p.add_argument("number", type=int)

    p = sub.add_parser("light", help="set the DPI indicator LED")
    p.add_argument("mode", choices=["off", "steady", "breathing"])
    p.add_argument("--brightness", choices=["low", "medium", "high"], default="medium")
    p.add_argument("--speed", choices=["slow", "medium", "fast"], default="medium")

    p = sub.add_parser("report", help="write a read-only support report")
    p.add_argument("-o", "--output", help="output path (default: stdout)")

    p = sub.add_parser("support", help="save a support report and show the issue URL")
    p.add_argument("-o", "--output", help="output path (default: current directory)")

    sub.add_parser("version", help="print the version")
    return parser


def _set_and_print(label: str, value) -> int:
    print(f"{label}: {value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(f"atkctl {config.VERSION}")
        return 0
    if args.command == "scan":
        return _print_scan()

    controller: Controller | None = None
    try:
        controller = _open(args.device)
        read_only_commands = {None, "status", "caps", "report", "support"}
        if controller.state.read_only and args.command not in read_only_commands:
            print(
                "atkctl: this mouse is recognized but not in the supported model "
                "database yet; settings are read-only. Run `atkctl report` and "
                "open a device support issue.",
                file=sys.stderr,
            )
            return 4
        if args.command in (None, "status"):
            return _status(controller, bool(getattr(args, "json", False)))
        if args.command == "caps":
            print(_caps_text(controller.caps))
            return 0
        if args.command == "polling":
            return _set_and_print("Polling", f"{controller.set_polling(args.hz)} Hz")
        if args.command == "dpi":
            stage = (args.stage - 1) if args.stage else controller.state.active_stage
            x, y = controller.set_stage_dpi(stage, args.dpi, args.y)
            return _set_and_print("DPI", f"{x} x {y}")
        if args.command == "stage":
            return _set_and_print("Active stage", controller.set_active_stage(args.number - 1) + 1)
        if args.command == "motion-sync":
            return _set_and_print("Motion Sync", _onoff(controller.set_motion_sync(args.value)))
        if args.command == "ripple":
            return _set_and_print("Ripple control", _onoff(controller.set_ripple(args.value)))
        if args.command == "straight-line":
            return _set_and_print("Straight-line correction", _onoff(controller.set_straight_line(args.value)))
        if args.command == "performance":
            return _set_and_print("Performance mode", _onoff(controller.set_performance_mode(args.value)))
        if args.command == "sensor-mode":
            values = {"basic": 0, "competitive": 1, "max": 2, "max13k": 3}
            mode = int(args.mode) if args.mode.isdigit() else values[args.mode]
            return _set_and_print("Sensor mode", _sensor_mode_label(controller.set_sensor_mode(mode)))
        if args.command == "button":
            label = controller.set_button_action(args.index - 1, args.action)
            return _set_and_print("Button", label)
        if args.command == "buttons-reset":
            controller.reset_buttons()
            return _set_and_print("Buttons", "factory mapping restored")
        if args.command == "add-stage":
            return _set_and_print("DPI stages", controller.add_stage())
        if args.command == "remove-stage":
            return _set_and_print("DPI stages", controller.remove_last_stage())
        if args.command == "long-range":
            return _set_and_print("Long range", _onoff(controller.set_long_range(args.value)))
        if args.command == "lod":
            return _set_lod(controller, args.value)
        if args.command == "debounce":
            return _set_and_print("Debounce", f"{controller.set_debounce(args.ms)} ms")
        if args.command == "sleep":
            return _set_and_print("Sleep", f"{controller.set_sleep(args.seconds)} s")
        if args.command == "angle":
            degrees, enabled = controller.set_angle(args.degrees, not args.off)
            return _set_and_print("Sensor rotation", f"{degrees} deg, {_onoff(enabled)}")
        if args.command == "profile":
            return _set_and_print("Profile", controller.set_profile(args.number))
        if args.command == "light":
            mode = {"off": 0, "steady": 1, "breathing": 2}[args.mode]
            brightness = {"low": 0, "medium": 1, "high": 2}[args.brightness]
            speed = {"slow": 0, "medium": 1, "fast": 2}[args.speed]
            result = controller.set_led_mode(mode, brightness, speed)
            return _set_and_print("DPI LED", f"mode {result[0]}, brightness {result[1]}, speed {result[2]}")
        if args.command in ("report", "support"):
            state = controller.read_full()
            raw = controller.collect_raw_registers()
            text = diagnostics.report_text(
                state, controller.path, controller.caps, raw_registers=raw
            )
            if args.command == "support" and not args.output:
                args.output = diagnostics.default_filename()
            if args.output:
                path = diagnostics.write_report(
                    args.output, state, controller.path, controller.caps,
                    raw_registers=raw,
                )
                print(f"Support report saved to {path}")
                print(f"Attach it to: {config.SUPPORT_URL}")
            else:
                print(text)
                print(f"\nSupport request: {config.SUPPORT_URL}")
            return 0
        parser.print_help()
        return 0
    except PermissionDenied as exc:
        print(f"atkctl: {exc}", file=sys.stderr)
        print("Install the udev rule from data/udev/71-atk-control.rules.", file=sys.stderr)
        return 3
    except (ProtocolError, ValueError) as exc:
        print(f"atkctl: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    finally:
        if controller is not None:
            controller.close()


def _set_lod(controller: Controller, value: str) -> int:
    text = value.lower()
    if text in ("low", "medium", "high"):
        mm = {"low": 0.7, "medium": 1.0, "high": 1.7}[text]
    else:
        try:
            mm = float(text)
        except ValueError:
            raise ProtocolError("lift-off must be low, medium, high or millimetres") from None
    choices = controller.caps.lift_off_choices
    code = min(choices, key=lambda item: abs(item[1] - mm))[0]
    controller.set_lift_off_code(code)
    return _set_and_print("Lift-off", f"{(code + 6) / 10:.1f} mm")


if __name__ == "__main__":
    raise SystemExit(main())
