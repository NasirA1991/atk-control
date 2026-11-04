"""Application entry point: worker, window and tray wiring."""

from __future__ import annotations

import argparse
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import config  # noqa: E402
from .ui import MainWindow  # noqa: E402
from .worker import DemoWorker, DeviceWorker  # noqa: E402


class AtkApplication(Adw.Application):
    def __init__(self, start_hidden: bool = False, use_tray: bool = True,
                 page: str | None = None, demo: bool = False) -> None:
        super().__init__(application_id=config.APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.start_hidden = start_hidden
        self.use_tray = use_tray
        self.page = page
        self.demo = demo
        self.window: MainWindow | None = None
        self.tray = None
        self.worker = None
        self._held = False
        self._quitting = False
        self._activated_once = False
        self._latest_state = None
        self._latest_link: tuple[bool, str | None] = (False, None)
        self._low_battery_notified = False
        GLib.set_application_name(config.APP_NAME)
        GLib.set_prgname("atk-control")
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)

    # -- startup -----------------------------------------------------------
    def _on_startup(self, _app) -> None:
        self._install_icon_path()
        self._add_actions()
        preferences = config.load()
        live = float(preferences.get("live_refresh_seconds", 3.0))
        full = float(preferences.get("full_refresh_seconds", 30.0))
        if self.demo:
            self.worker = DemoWorker(
                self._state_from_thread, self._link_from_thread, self._toast_from_thread,
                live_seconds=live, full_seconds=full,
            )
        else:
            self.worker = DeviceWorker(
                self._state_from_thread, self._link_from_thread, self._toast_from_thread,
                live_seconds=live, full_seconds=full,
            )
        self.worker.start()

        if not self.use_tray:
            return
        try:
            from .tray import Tray

            tray = Tray(
                app_name=config.APP_NAME,
                on_open=self._show_window,
                on_quit=self._quit,
                on_refresh=self._refresh,
                on_polling=self._tray_polling,
                on_dpi=self._tray_dpi,
                on_motion=self._tray_motion,
                on_ripple=self._tray_ripple,
                on_straight=self._tray_straight,
                on_profile=self._tray_profile,
                on_style=self._tray_style,
                style=config.load().get("tray_icon_style", config.DEFAULT_TRAY_STYLE),
            )
            if tray.start():
                self.tray = tray
                self.hold()
                self._held = True
            else:
                print("atk-control: tray watcher unavailable", file=sys.stderr)
        except Exception as exc:  # tray is optional
            print(f"atk-control: tray unavailable: {exc}", file=sys.stderr)

    def _install_icon_path(self) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            theme = Gtk.IconTheme.get_for_display(display)
            icons = config.data_dir() / "icons"
            if icons.exists():
                theme.add_search_path(str(icons))
        Gtk.Window.set_default_icon_name("atk-control")

    def _add_actions(self) -> None:
        actions = (
            ("refresh", lambda *_: self._refresh()),
            ("quit", lambda *_: self._quit()),
            ("show", lambda *_: self._show_window()),
            ("about", lambda *_: self._about()),
            ("web-driver", lambda *_: self._open_web_driver()),
        )
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        style = Gio.SimpleAction.new_stateful(
            "tray-style",
            GLib.VariantType.new("s"),
            GLib.Variant.new_string(config.load().get("tray_icon_style", config.DEFAULT_TRAY_STYLE)),
        )
        style.connect("activate", self._on_tray_style_action)
        self.add_action(style)

        autostart = Gio.SimpleAction.new_stateful(
            "autostart",
            None,
            GLib.Variant.new_boolean(config.is_autostart_enabled()),
        )
        autostart.connect("activate", self._on_autostart_action)
        self.add_action(autostart)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.refresh", ["<Control>r"])

    # -- activation --------------------------------------------------------
    def _on_activate(self, _app) -> None:
        first = not self._activated_once
        self._activated_once = True
        if first and self.start_hidden and self.tray is not None:
            return
        window = self._ensure_window()
        window.set_visible(True)
        window.present()

    def _ensure_window(self) -> MainWindow:
        if self.window is None:
            assert self.worker is not None
            self.window = MainWindow(self.worker, initial_page=self.page)
            self.window.set_icon_name("atk-control")
            self.window.connect("close-request", self._on_close_request)
            self.add_window(self.window)
            self.window.on_link(*self._latest_link)
            if self._latest_state is not None:
                self.window.on_state(self._latest_state, set())
        return self.window

    def _on_close_request(self, _window) -> bool:
        if self.tray is not None and not self._quitting:
            self.window.set_visible(False)
            return True
        return False

    def _on_window_visibility(self, window, _param) -> None:
        if self.worker is not None:
            self.worker.set_foreground(bool(window.get_visible()))

    # -- thread dispatch ---------------------------------------------------
    def _state_from_thread(self, state, changed) -> None:
        GLib.idle_add(self._apply_state, state, changed)

    def _link_from_thread(self, connected: bool, error: str | None) -> None:
        GLib.idle_add(self._apply_link, connected, error)

    def _toast_from_thread(self, message: str) -> None:
        GLib.idle_add(self._apply_toast, message)

    def _apply_state(self, state, changed) -> bool:
        self._latest_state = state
        self._latest_link = (True, None)
        if self.window is not None:
            self.window.on_state(state, changed)
        if self.tray is not None:
            self.tray.update(state, True)
        if (
            state.battery is not None
            and state.battery <= 15
            and not state.charging
            and config.load().get("low_battery_notifications", True)
            and not self._low_battery_notified
        ):
            self._low_battery_notified = True
            note = Gio.Notification.new(f"{state.connected_name} battery low")
            note.set_body(f"{state.battery}% remaining — time to charge.")
            note.set_icon(Gio.ThemedIcon.new("battery-low-symbolic"))
            self.send_notification("low-battery", note)
        elif state.battery is None or state.battery > 20 or state.charging:
            self._low_battery_notified = False
        return False

    def _apply_link(self, connected: bool, error: str | None) -> bool:
        self._latest_link = (connected, error)
        if connected:
            self._latest_state = self.worker.state if self.worker else None
        else:
            self._latest_state = None
        if self.window is not None:
            self.window.on_link(connected, error)
        if self.tray is not None:
            self.tray.update(self._latest_state if connected else None, connected, error)
        return False

    def _apply_toast(self, message: str) -> bool:
        if self.window is not None:
            self.window.toast(message)
        return False

    # -- tray --------------------------------------------------------------
    def _tray_state(self):
        return self.worker.state if self.worker is not None else None

    def _tray_polling(self, hz: int) -> None:
        if self.worker is not None:
            self.worker.submit("polling", hz)

    def _tray_dpi(self, dpi: int) -> None:
        state = self._tray_state()
        if self.worker is not None and state is not None:
            self.worker.submit("stage_dpi", state.active_stage, dpi, dpi, key="tray-dpi")

    def _tray_motion(self, enabled: bool) -> None:
        if self.worker is not None:
            self.worker.submit("motion_sync", enabled)

    def _tray_ripple(self, enabled: bool) -> None:
        if self.worker is not None:
            self.worker.submit("ripple", enabled)

    def _tray_straight(self, enabled: bool) -> None:
        if self.worker is not None:
            self.worker.submit("straight_line", enabled)

    def _tray_profile(self, profile: int) -> None:
        if self.worker is not None:
            self.worker.submit("profile", profile)

    def _tray_style(self, style: str) -> None:
        preferences = config.load()
        preferences["tray_icon_style"] = style
        if not config.save(preferences):
            self._toast_from_thread("Could not save the tray style preference.")
        if self.tray is not None:
            self.tray.set_style(style)
        if self.window is not None:
            self.window._tray_style = style
            self.window._update_tray_style_buttons()
        self.change_action_state("tray-style", GLib.Variant.new_string(style))

    def _on_tray_style_action(self, _action, value) -> None:
        self._tray_style(value.get_string())

    def _on_autostart_action(self, action, _value) -> None:
        current = config.is_autostart_enabled()
        enabled = not current
        if config.set_autostart(enabled):
            action.set_state(GLib.Variant.new_boolean(enabled))
            if self.window is not None:
                self.window.autostart.set_active(enabled)

    # -- app actions -------------------------------------------------------
    def _show_window(self) -> None:
        window = self._ensure_window()
        window.set_visible(True)
        window.present()
        self.activate()

    def _refresh(self) -> None:
        if self.worker is None:
            return
        if self.worker.connected:
            self.worker.refresh()
        else:
            self.worker.retry()

    def _quit(self) -> None:
        self._quitting = True
        if self.worker is not None:
            self.worker.stop()
        if self._held:
            self.release()
            self._held = False
        self.quit()

    def _open_web_driver(self) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(config.HUB_URL, None)
        except GLib.Error as exc:
            if self.window is not None:
                self.window.toast(f"Could not open browser: {exc.message}")

    def _about(self) -> None:
        dialog = Adw.AboutDialog(
            application_name=config.APP_NAME,
            application_icon="atk-control",
            version=config.VERSION,
            developer_name="ATK Control contributors",
            comments=(
                "Native Linux configuration for ATK/VXE gaming mice, including "
                "the MAD R family and VXE R1. Built by reverse-engineering the public "
                "ATK HUB vendor protocol. Not affiliated with ATK or VXE."
            ),
            website=config.REPO_URL,
            issue_url=f"{config.REPO_URL}/issues",
            license_type=Gtk.License.MIT_X11,
        )
        dialog.present(self.window)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atk-control",
        description="Native Linux control centre for ATK/VXE gaming mice.",
    )
    parser.add_argument("--tray", action="store_true", help="start hidden in the tray")
    parser.add_argument("--no-tray", action="store_true", help="disable the tray icon")
    parser.add_argument("--demo", action="store_true", help="use a simulated MAD R")
    parser.add_argument(
        "--page",
        choices=["overview", "buttons", "performance", "dpi", "lighting", "device"],
        help="open a specific page",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {config.VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    app = AtkApplication(
        start_hidden=args.tray,
        use_tray=not args.no_tray,
        page=args.page,
        demo=args.demo,
    )
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    raise SystemExit(main())
