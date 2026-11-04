"""Background device worker and in-memory demo device."""

from __future__ import annotations

import copy
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Callable

from . import devices, diagnostics, protocol
from .controller import Controller
from .protocol import DeviceInfo, DeviceNotFound, PermissionDenied, ProtocolError, discover
from .state import Button, MouseState

StateCallback = Callable[[MouseState, set[str]], None]
LinkCallback = Callable[[bool, str | None], None]
ToastCallback = Callable[[str], None]


class DeviceWorker:
    """Owns the hidraw session on a background thread."""

    def __init__(
        self,
        on_state: StateCallback,
        on_link: LinkCallback,
        on_toast: ToastCallback | None = None,
        live_seconds: float = 3.0,
        full_seconds: float = 30.0,
    ) -> None:
        self.on_state = on_state
        self.on_link = on_link
        self.on_toast = on_toast
        self.live_seconds = max(1.0, live_seconds)
        self.full_seconds = max(10.0, full_seconds)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._pending: OrderedDict[str, tuple] = OrderedDict()
        self._force_full = False
        self._retry_now = False
        self._preferred_path: str | None = None
        self._available: list[DeviceInfo] = []
        self._report_path: str | None = None
        self._state = MouseState()
        self._controller: Controller | None = None
        self._connected = False
        self._last_link_error: str | None = None
        self._last_link_key: tuple[bool, str | None] | None = None
        self._last_emit = 0.0
        self._last_full = 0.0
        self._query_misses = 0
        self._warned_permission = False

    # -- public API -------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="atk-hid", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.5) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout)

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def state(self) -> MouseState:
        with self._lock:
            return copy.deepcopy(self._state)

    @property
    def device_path(self) -> str | None:
        return self._controller.path if self._controller else None

    @property
    def capabilities(self):
        return devices.capabilities_for(
            model=self._controller.model if self._controller else None,
            receiver=self._controller.receiver if self._controller else None,
            sensor_name=self.state.sensor or None,
            active_polling=self.state.polling_rate,
            debounce=self.state.debounce_ms,
            sleep=self.state.sleep_seconds,
        )

    def submit(self, method: str, *args, key: str | None = None) -> None:
        """Queue one verified device operation. Last value for a key wins."""
        with self._lock:
            self._pending[key or method] = (method, args)

    def refresh(self, full: bool = True) -> None:
        with self._lock:
            self._force_full = True

    def retry(self) -> None:
        """Ask the worker to re-scan immediately."""
        with self._lock:
            self._retry_now = True

    def available_devices(self) -> list[DeviceInfo]:
        """Configuration interfaces currently present (for a device picker)."""
        try:
            return discover()
        except Exception:
            return []

    def select_device(self, path: str) -> None:
        """Switch to another receiver or cable when more than one is present."""
        with self._lock:
            self._preferred_path = path
            self._retry_now = True

    def save_support_report(self, path: str) -> None:
        """Queue a complete, read-only support report on the worker thread."""
        with self._lock:
            self._report_path = path

    # -- callbacks --------------------------------------------------------
    def _emit_state(self, state: MouseState, changed: set[str] | None = None) -> None:
        try:
            self.on_state(copy.deepcopy(state), changed or set())
        except Exception:
            pass

    def _emit_link(self, connected: bool, error: str | None = None) -> None:
        key = (connected, error)
        self._connected = connected
        self._last_link_error = error
        if key == self._last_link_key:
            # Avoid repainting the same connection state twice a second.
            return
        self._last_link_key = key
        try:
            self.on_link(connected, error)
        except Exception:
            pass

    def _toast(self, message: str) -> None:
        if self.on_toast is not None:
            try:
                self.on_toast(message)
            except Exception:
                pass

    # -- connection -------------------------------------------------------
    def _connect(self) -> bool:
        candidates = discover()
        self._available = candidates
        if not candidates:
            self._emit_link(False, "No ATK/VXE mouse or receiver found.")
            return False
        with self._lock:
            preferred = self._preferred_path
        if preferred:
            matching = [item for item in candidates if item.path == preferred]
            if matching:
                candidates = matching
            else:
                with self._lock:
                    self._preferred_path = None

        errors: list[str] = []
        for info in candidates:
            controller = Controller(info)
            try:
                state = controller.open()
            except PermissionDenied:
                errors.append(
                    f"{info.hidraw_name}: permission denied. Install the udev rule "
                    "(71-atk-control.rules) and reconnect the mouse."
                )
                continue
            except (ProtocolError, OSError) as exc:
                receiver = devices.receiver_for(info.product_id, info.product_name)
                display = receiver.name if receiver else info.product_name
                errors.append(f"{display}: {exc}")
                continue
            self._controller = controller
            self._query_misses = 0
            self._warned_permission = False
            self._last_full = time.monotonic()
            with self._lock:
                self._state = copy.deepcopy(state)
            self._emit_link(True, None)
            self._emit_state(state, set())
            return True

        self._emit_link(False, errors[0] if errors else "The mouse did not answer.")
        return False

    def _disconnect(self, reason: str | None = None) -> None:
        controller = self._controller
        self._controller = None
        if controller is not None:
            controller.close()
        with self._lock:
            self._state = MouseState()
            self._pending.clear()
        self._query_misses = 0
        self._emit_link(False, reason)

    # -- operations -------------------------------------------------------
    def _apply_pending(self) -> None:
        controller = self._controller
        if controller is None:
            return
        if getattr(controller, "read_only", False):
            with self._lock:
                pending = bool(self._pending)
                self._pending.clear()
            if pending:
                self._toast("This model is not in the supported database yet; settings are read-only.")
            return
        with self._lock:
            pending = list(self._pending.values())
            self._pending.clear()
        for method, args in pending:
            operation = OPERATIONS.get(method)
            if operation is None:
                continue
            try:
                operation(controller, *args)
                # A profile switch changes the whole stored configuration.
                state = controller.read_full() if method == "profile" else controller.state
                if method == "profile":
                    self._last_full = time.monotonic()
                with self._lock:
                    self._state = copy.deepcopy(state)
                self._emit_state(state, set())
            except (ProtocolError, ValueError) as exc:
                self._toast(str(exc))
            except Exception as exc:  # keep the HID loop alive
                self._toast(f"Could not apply setting: {exc}")

    def _write_support_report(self, path: str) -> None:
        controller = self._controller
        if controller is None:
            self._toast("Connect a mouse before saving a support report.")
            return
        try:
            try:
                state = controller.read_full()
            except ProtocolError:
                state = controller.state
            raw = controller.collect_raw_registers()
            target = Path(path).expanduser()
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                diagnostics.report_text(state, controller.path, controller.caps, raw),
                encoding="utf-8",
            )
            self._toast(f"Support report saved: {target.name}")
        except OSError as exc:
            self._toast(f"Could not write report: {exc}")
        except Exception as exc:
            self._toast(f"Could not create support report: {exc}")

    def _poll(self, force_full: bool = False) -> None:
        controller = self._controller
        if controller is None:
            return
        if not os.path.exists(controller.path):
            self._disconnect("Mouse disconnected.")
            return
        now = time.monotonic()
        try:
            if force_full or now - self._last_full >= self.full_seconds:
                state = controller.read_full()
                self._last_full = now
            else:
                state = controller.read_live()
            self._query_misses = 0
            with self._lock:
                self._state = copy.deepcopy(state)
            self._emit_state(state, set())
            self._last_emit = now
        except DeviceNotFound:
            self._disconnect("Mouse disconnected.")
        except PermissionDenied as exc:
            self._disconnect(str(exc))
        except ProtocolError as exc:
            self._query_misses += 1
            message = str(exc)
            if self._query_misses >= 4:
                self._disconnect(message)
        except OSError as exc:
            self._disconnect(f"Device error: {exc}")

    def _run(self) -> None:
        backoff = 0.8
        while not self._stop.is_set():
            with self._lock:
                retry = self._retry_now
                self._retry_now = False
            with self._lock:
                preferred = self._preferred_path
            if (
                retry
                and self._controller is not None
                and preferred
                and self._controller.path != preferred
            ):
                self._disconnect(None)
            if self._controller is None:
                self._emit_link(False, self._last_link_error)
                if self._connect():
                    backoff = 0.8
                    continue
                self._stop.wait(0.15 if retry else backoff)
                backoff = min(backoff * 1.5, 4.0)
                continue
            with self._lock:
                report_path = self._report_path
                self._report_path = None
            if report_path:
                self._write_support_report(report_path)
            with self._lock:
                force = self._force_full
                self._force_full = False
                has_pending = bool(self._pending)
            if has_pending:
                self._apply_pending()
            elif force or time.monotonic() - self._last_emit >= self.live_seconds:
                self._poll(force_full=force)
            self._stop.wait(0.04)
        self._disconnect(None)


def _set_stage_dpi(controller: Controller, index: int, x: int, y: int) -> None:
    controller.set_stage_dpi(int(index), int(x), int(y))


def _set_angle(controller: Controller, degrees: int, enabled: bool) -> None:
    controller.set_angle(int(degrees), bool(enabled))


def _set_led(controller: Controller, mode: int, brightness: int, speed: int) -> None:
    controller.set_led_mode(int(mode), int(brightness), int(speed))


OPERATIONS = {
    "polling": lambda c, hz: c.set_polling(int(hz)),
    "active_stage": lambda c, index: c.set_active_stage(int(index)),
    "stage_dpi": _set_stage_dpi,
    "stage_color": lambda c, index, color: c.set_stage_color(int(index), str(color)),
    "lift_off": lambda c, code: c.set_lift_off_code(int(code)),
    "debounce": lambda c, ms: c.set_debounce(int(ms)),
    "motion_sync": lambda c, enabled: c.set_motion_sync(bool(enabled)),
    "sleep": lambda c, seconds: c.set_sleep(int(seconds)),
    "ripple": lambda c, enabled: c.set_ripple(bool(enabled)),
    "straight_line": lambda c, enabled: c.set_straight_line(bool(enabled)),
    "angle": _set_angle,
    "performance": lambda c, enabled: c.set_performance_mode(bool(enabled)),
    "long_range": lambda c, enabled: c.set_long_range(bool(enabled)),
    "led": _set_led,
    "profile": lambda c, profile: c.set_profile(int(profile)),
}


class DemoWorker:
    """Interactive fake MAD R used by --demo, docs and screenshot jobs."""

    def __init__(self, on_state: StateCallback, on_link: LinkCallback,
                 on_toast: ToastCallback | None = None,
                 live_seconds: float = 3.0, full_seconds: float = 30.0) -> None:
        self.on_state = on_state
        self.on_link = on_link
        self.on_toast = on_toast
        self._state = self._demo_state()
        self._stop = threading.Event()

    @staticmethod
    def _demo_state() -> MouseState:
        return MouseState(
            vendor_id=0x373B,
            product_id=0x1040,
            usb_name="Compx MAD 8K DONGLE",
            cid=2,
            mid=49,
            model_name="MAD R",
            brand="ATK",
            sensor="PAW3395",
            firmware="1.24",
            usb_bcd="1.12",
            via_receiver=True,
            receiver_name="MAD 8K Dongle",
            receiver_pid=0x1040,
            rf_id="A4 19 7C",
            receiver_online=True,
            wired=False,
            battery=76,
            charging=False,
            voltage_mv=3980,
            dpi=1600,
            dpi_y=1600,
            stages=[(400, 400), (800, 800), (1600, 1600), (3200, 3200)],
            active_stage=2,
            stage_count=4,
            stage_colors=["#4cd7d0", "#8ee36b", "#ff8a4c", "#ffd166"],
            polling_rate=8000,
            lod_code=4,
            lod_mm=1.0,
            debounce_ms=2,
            motion_sync=True,
            sleep_seconds=300,
            ripple_control=True,
            straight_line=False,
            angle_enabled=False,
            angle_degrees=0,
            performance_mode=True,
            long_range=False,
            led_mode=1,
            led_brightness=1,
            led_speed=1,
            profile=2,
            profile_count=4,
            buttons=[
                Button("Left", "Left click"),
                Button("Right", "Right click"),
                Button("Middle", "Middle click"),
                Button("Back", "Back"),
                Button("Forward", "Forward"),
            ],
            supports_angle=True,
            supports_performance_mode=True,
            supports_lighting=True,
            supports_stage_colors=True,
        )

    @property
    def connected(self) -> bool:
        return True

    @property
    def state(self) -> MouseState:
        return copy.deepcopy(self._state)

    @property
    def device_path(self) -> str | None:
        return "/dev/hidraw-demo"

    @property
    def capabilities(self):
        return devices.capabilities_for(
            model=devices.MODEL_BY_CIDMID.get((2, 49)),
            receiver=devices.receiver_for(0x1040),
            sensor_name=self._state.sensor,
            active_polling=self._state.polling_rate,
            debounce=self._state.debounce_ms,
            sleep=self._state.sleep_seconds,
            usb_name=self._state.usb_name,
        )

    def start(self) -> None:
        self.on_link(True, None)
        self.on_state(copy.deepcopy(self._state), set())

    def stop(self, timeout: float = 2.5) -> None:
        self._stop.set()

    def refresh(self, full: bool = True) -> None:
        self.on_state(copy.deepcopy(self._state), set())

    def available_devices(self) -> list[DeviceInfo]:
        return [DeviceInfo(
            path="/dev/hidraw-demo",
            vendor_id=0x373B,
            product_id=0x1040,
            product_name="Compx MAD 8K DONGLE",
            bcd_device="0215",
            accessible=True,
        )]

    def select_device(self, path: str) -> None:
        return None

    def save_support_report(self, path: str) -> None:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            diagnostics.report_text(
                self._state, "/dev/hidraw-demo", self.capabilities, None
            ),
            encoding="utf-8",
        )
        if self.on_toast is not None:
            self.on_toast(f"Support report saved: {target.name}")

    def submit(self, method: str, *args, key: str | None = None) -> None:
        state = self._state
        try:
            if method == "polling":
                state.polling_rate = int(args[0])
            elif method == "active_stage":
                state.active_stage = int(args[0])
                state.dpi, state.dpi_y = state.stages[state.active_stage]
            elif method == "stage_dpi":
                index, x, y = int(args[0]), int(args[1]), int(args[2])
                state.stages[index] = (x, y)
                if index == state.active_stage:
                    state.dpi, state.dpi_y = x, y
            elif method == "stage_color":
                index, color = int(args[0]), str(args[1])
                state.stage_colors[index] = color
            elif method == "lift_off":
                state.lod_code = int(args[0])
                state.lod_mm = (state.lod_code + 6) / 10
            elif method == "debounce":
                state.debounce_ms = int(args[0])
            elif method == "motion_sync":
                state.motion_sync = bool(args[0])
            elif method == "sleep":
                state.sleep_seconds = int(args[0])
            elif method == "ripple":
                state.ripple_control = bool(args[0])
            elif method == "straight_line":
                state.straight_line = bool(args[0])
            elif method == "angle":
                state.angle_degrees = int(args[0])
                state.angle_enabled = bool(args[1])
            elif method == "performance":
                state.performance_mode = bool(args[0])
            elif method == "led":
                state.led_mode, state.led_brightness, state.led_speed = map(int, args[:3])
            elif method == "profile":
                state.profile = int(args[0])
        except (IndexError, TypeError, ValueError):
            return
        self._state = state
        self.on_state(copy.deepcopy(state), set())
