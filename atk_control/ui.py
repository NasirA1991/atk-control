"""GTK4 / libadwaita interface for ATK Control.

The layout is intentionally a command-centre: a persistent navy sidebar, large
numeric telemetry tiles and angular accents.  It does not use the tabbed
preferences layout of RAWM Control.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import config, devices, diagnostics  # noqa: E402
from .protocol import clamp_dpi  # noqa: E402
from .state import MouseState  # noqa: E402

CSS = """
@define-color accent_bg_color #ff6b3d;
@define-color accent_color #ff8a62;
@define-color accent_fg_color #200b05;
window {
    background-color: @window_bg_color;
}
.brand-title {
    font-size: 14px;
    font-weight: 900;
    letter-spacing: 2.2px;
}
.brand-sub {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
    opacity: 0.5;
}
.sidebar {
    background-color: alpha(currentColor, 0.035);
    border-right: 1px solid alpha(currentColor, 0.08);
}
.nav-button {
    border-radius: 10px;
    padding: 9px 11px;
    background: transparent;
    color: alpha(currentColor, 0.72);
    font-weight: 600;
}
.nav-button:hover {
    background-color: alpha(currentColor, 0.07);
}
.nav-button.active {
    background-color: alpha(#ff6b3d, 0.16);
    color: #ff8a62;
    box-shadow: inset 3px 0 0 #ff6b3d;
}
.sidebar-card {
    background-color: alpha(currentColor, 0.055);
    border: 1px solid alpha(currentColor, 0.08);
    border-radius: 14px;
    padding: 13px;
}
.sidebar-device {
    font-size: 13px;
    font-weight: 800;
}
.sidebar-link {
    font-size: 10px;
    opacity: 0.58;
}
.page-title {
    font-size: 30px;
    font-weight: 900;
    letter-spacing: -0.8px;
}
.page-sub {
    font-size: 13px;
    opacity: 0.58;
}
.card {
    background-color: alpha(currentColor, 0.052);
    border: 1px solid alpha(currentColor, 0.075);
    border-radius: 18px;
    padding: 20px;
}
.hero-card {
    background-image: linear-gradient(128deg, alpha(#ff6b3d, 0.22), alpha(currentColor, 0.045) 58%);
    border: 1px solid alpha(#ff6b3d, 0.26);
    border-radius: 22px;
    padding: 26px;
}
.eyebrow {
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2.0px;
    opacity: 0.56;
}
.battery-number {
    font-size: 76px;
    font-weight: 900;
    letter-spacing: -4px;
    font-feature-settings: "tnum";
}
.battery-suffix {
    font-size: 26px;
    font-weight: 800;
    opacity: 0.65;
}
.hero-model {
    font-size: 19px;
    font-weight: 800;
}
.hero-sub {
    font-size: 12px;
    opacity: 0.6;
}
.metric-value {
    font-size: 28px;
    font-weight: 900;
    font-feature-settings: "tnum";
    letter-spacing: -0.8px;
}
.metric-unit {
    font-size: 12px;
    font-weight: 700;
    opacity: 0.5;
}
.metric-label {
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.6px;
    opacity: 0.5;
}
.metric-button {
    border-radius: 16px;
    padding: 16px;
    background-color: alpha(currentColor, 0.045);
    border: 1px solid alpha(currentColor, 0.07);
}
.metric-button:hover {
    background-color: alpha(currentColor, 0.075);
    border-color: alpha(#ff6b3d, 0.35);
}
.card-title {
    font-size: 15px;
    font-weight: 800;
}
.card-sub {
    font-size: 12px;
    opacity: 0.55;
}
.row-title {
    font-size: 13px;
    font-weight: 650;
}
.row-sub {
    font-size: 11px;
    opacity: 0.52;
}
.pill {
    border-radius: 8px;
    padding: 7px 13px;
    background-color: alpha(currentColor, 0.06);
    border: 1px solid alpha(currentColor, 0.09);
    font-weight: 700;
    font-size: 12px;
}
.pill:hover {
    background-color: alpha(currentColor, 0.10);
}
.pill.active {
    background-color: #ff6b3d;
    border-color: #ff6b3d;
    color: #1b0d08;
}
.status-pill {
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.2px;
    background-color: alpha(#49dbb1, 0.15);
    color: #63e8c2;
}
.status-pill.offline {
    background-color: alpha(currentColor, 0.07);
    color: alpha(currentColor, 0.5);
}
.status-pill.charging {
    background-color: alpha(#3dc6ff, 0.15);
    color: #65d4ff;
}
.notice {
    background-color: alpha(#ffb224, 0.10);
    border: 1px solid alpha(#ffb224, 0.25);
    border-radius: 12px;
    padding: 10px 14px;
}
.hero-badge {
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    background-color: alpha(currentColor, 0.09);
}
.stage-row {
    border-radius: 12px;
    padding: 8px 10px;
}
.stage-row.stage-active {
    background-color: alpha(#ff6b3d, 0.12);
    border: 1px solid alpha(#ff6b3d, 0.28);
}
.stage-index {
    font-size: 12px;
    font-weight: 900;
    color: alpha(currentColor, 0.42);
    font-feature-settings: "tnum";
}
.stage-active .stage-index {
    color: #ff8a62;
}
.mini-label {
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
    opacity: 0.42;
}
.mono {
    font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
    font-size: 11px;
}
.footer-note {
    font-size: 11px;
    opacity: 0.45;
}
.device-value {
    font-size: 12px;
    font-weight: 600;
    opacity: 0.82;
}
.danger {
    color: #ff7060;
}
"""


def _rgb_from_hex(value: str) -> tuple[float, float, float]:
    text = (value or "#ff6b3d").strip().lstrip("#")
    if len(text) != 6:
        text = "ff6b3d"
    try:
        return tuple(int(text[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (1.0, 0.42, 0.24)


def _gdk_rgba(value: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(value if value and value.startswith("#") else "#ff6b3d")
    rgba.alpha = 1.0
    return rgba


class BatteryRail(Gtk.DrawingArea):
    """Angled battery cells rather than a generic progress bar."""

    def __init__(self) -> None:
        super().__init__()
        self._percent = 0
        self._charging = False
        self._known = False
        self.set_content_height(36)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_state(self, percent: int | None, charging: bool | None) -> None:
        self._known = percent is not None
        self._percent = max(0, min(100, percent or 0))
        self._charging = bool(charging)
        self.queue_draw()

    def _draw(self, _area, ctx, width, height):
        if width <= 2:
            return
        cells = 28
        gap = 3.0
        skew = 4.0
        usable = width - gap * (cells - 1) - skew
        cell_w = max(1.0, usable / cells)
        filled = round_cells = int(round(self._percent / 100 * cells)) if self._known else 0
        if self._charging:
            color = (0.24, 0.78, 1.0)
        elif self._percent <= 15:
            color = (1.0, 0.32, 0.28)
        elif self._percent <= 35:
            color = (1.0, 0.72, 0.22)
        else:
            color = (0.29, 0.86, 0.72)
        for index in range(cells):
            x = index * (cell_w + gap)
            y = 6.0
            h = height - 12.0
            ctx.move_to(x + skew, y)
            ctx.line_to(x + cell_w + skew, y)
            ctx.line_to(x + cell_w, y + h)
            ctx.line_to(x, y + h)
            ctx.close_path()
            if index < filled:
                ctx.set_source_rgba(*color, 0.95)
            else:
                ctx.set_source_rgba(1, 1, 1, 0.10 if not self._charging else 0.08)
            ctx.fill()
        if self._charging:
            ctx.set_source_rgba(0.24, 0.78, 1.0, 0.8)
            ctx.rectangle(0, height - 2, width * self._percent / 100, 2)
            ctx.fill()


class BrandMark(Gtk.DrawingArea):
    def __init__(self, size: int = 44) -> None:
        super().__init__()
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self._draw)

    def _draw(self, _area, ctx, width, height):
        cx, cy = width / 2, height / 2
        radius = min(width, height) / 2 - 2
        for index in range(6):
            angle = -math.pi / 2 + index * math.pi / 3
            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            ctx.line_to(x, y) if index else ctx.move_to(x, y)
        ctx.close_path()
        ctx.set_source_rgba(1.0, 0.42, 0.24, 0.18)
        ctx.fill_preserve()
        ctx.set_line_width(2.0)
        ctx.set_source_rgba(1.0, 0.51, 0.33, 0.95)
        ctx.stroke()
        ctx.set_line_width(max(2.4, min(width, height) * 0.095))
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_source_rgba(1, 1, 1, 0.95)
        ctx.move_to(cx, cy - radius * 0.43)
        ctx.line_to(cx - radius * 0.40, cy + radius * 0.46)
        ctx.move_to(cx, cy - radius * 0.43)
        ctx.line_to(cx + radius * 0.40, cy + radius * 0.46)
        ctx.move_to(cx - radius * 0.21, cy + radius * 0.13)
        ctx.line_to(cx + radius * 0.21, cy + radius * 0.13)
        ctx.stroke()


class LightingPreview(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self._color = "#ff6b3d"
        self._mode = 1
        self._brightness = 1
        self.set_content_height(112)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def set_state(self, color: str, mode: int | None, brightness: int | None) -> None:
        self._color = color or "#ff6b3d"
        self._mode = mode if mode is not None else 1
        self._brightness = brightness if brightness is not None else 1
        self.queue_draw()

    def _draw(self, _area, ctx, width, height):
        r, g, b = _rgb_from_hex(self._color)
        intensity = (0.35, 0.62, 0.92)[max(0, min(2, self._brightness))]
        if self._mode == 0:
            intensity = 0.06
        cx, cy = width / 2, height / 2
        glow = cairo.RadialGradient(cx, cy, 4, cx, cy, min(width, height) * 0.46)
        glow.add_color_stop_rgba(0, r * intensity, g * intensity, b * intensity, 0.42 if self._mode else 0.03)
        glow.add_color_stop_rgba(1, r * intensity, g * intensity, b * intensity, 0.0)
        ctx.set_source(glow)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()

        ctx.set_line_width(2.0)
        ctx.set_source_rgba(1, 1, 1, 0.10)
        ctx.arc(cx, cy, min(width, height) * 0.31, 0, 2 * math.pi)
        ctx.stroke()

        ctx.set_line_width(5.0)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)
        ctx.arc(cx, cy, min(width, height) * 0.31, -math.pi * 0.82, math.pi * 0.82)
        ctx.set_source_rgba(r, g, b, 0.95 if self._mode else 0.10)
        ctx.stroke()

        ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(11)
        text = "OFF" if self._mode == 0 else ("BREATHING" if self._mode == 2 else "STEADY")
        ext = ctx.text_extents(text)
        ctx.move_to(cx - ext.width / 2, cy + 5)
        ctx.set_source_rgba(1, 1, 1, 0.7)
        ctx.show_text(text)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, worker, initial_page: str | None = None) -> None:
        super().__init__(title="ATK Control")
        self.worker = worker
        self._state: MouseState | None = None
        self._connected = False
        self._loading = False
        self._angle_timer = 0
        self._dpi_timers: dict[tuple[int, str], int] = {}
        self._lod_timer = 0
        self._tray_style = config.load().get("tray_icon_style", config.DEFAULT_TRAY_STYLE)
        self._buttons_signature = None

        self.set_default_size(1140, 900)
        self.set_size_request(860, 620)
        self._install_css()
        self._build_actions()
        self._build_ui()
        self._select_page(initial_page or "overview")

    # ------------------------------------------------------------------ css
    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode("utf-8"))
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _build_actions(self) -> None:
        action = Gio.SimpleAction.new("save-report", None)
        action.connect("activate", lambda *_: self._save_report())
        self.add_action(action)
        support = Gio.SimpleAction.new("open-support", None)
        support.connect("activate", lambda *_: self._open_support())
        self.add_action(support)

    # ------------------------------------------------------------------- ui
    @staticmethod
    def _label(text: str, css: str | None = None, xalign: float = 0.0,
               wrap: bool = False) -> Gtk.Label:
        label = Gtk.Label(label=text, xalign=xalign)
        label.set_wrap(wrap)
        if css:
            label.add_css_class(css)
        return label

    def _card(self, title: str | None = None, subtitle: str | None = None):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=13)
        card.add_css_class("card")
        if title:
            head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            head.append(self._label(title, "card-title"))
            if subtitle:
                head.append(self._label(subtitle, "card-sub", wrap=True))
            card.append(head)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        card.append(body)
        return card, body

    def _setting_row(self, title: str, subtitle: str, suffix: Gtk.Widget,
                     row: Gtk.Widget | None = None) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        box.set_valign(Gtk.Align.CENTER)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text.set_hexpand(True)
        text.append(self._label(title, "row-title"))
        if subtitle:
            text.append(self._label(subtitle, "row-sub", wrap=True))
        box.append(text)
        suffix.set_valign(Gtk.Align.CENTER)
        box.append(suffix)
        if row is not None:
            row.append(box)
        return box

    def _page(self, title: str, subtitle: str):
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        clamp = Adw.Clamp()
        clamp.set_maximum_size(920)
        clamp.set_tightening_threshold(680)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        root.set_margin_top(26)
        root.set_margin_bottom(34)
        root.set_margin_start(28)
        root.set_margin_end(28)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        heading.append(self._label(title, "page-title"))
        heading.append(self._label(subtitle, "page-sub", wrap=True))
        root.append(heading)
        clamp.set_child(root)
        scroller.set_child(clamp)
        return scroller, root

    def _build_ui(self) -> None:
        self.toast_overlay = Adw.ToastOverlay()
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header_title = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header_title.append(BrandMark(24))
        header_title.append(self._label("ATK CONTROL", "brand-sub"))
        header.set_title_widget(header_title)

        self.header_status = self._label("OFFLINE", "status-pill offline")
        self.header_status.set_valign(Gtk.Align.CENTER)
        self.header_status.set_margin_start(6)
        self.header_status.set_margin_end(6)

        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_tooltip_text("Refresh device state")
        refresh.connect("clicked", lambda *_: self.worker.refresh())

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_tooltip_text("Main menu")
        menu_button.set_menu_model(self._build_menu())
        header.pack_end(menu_button)
        header.pack_end(refresh)
        header.pack_end(self.header_status)

        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        root.append(self._build_sidebar())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.set_hexpand(True)
        self.notice = Gtk.Revealer()
        notice_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        notice_box.add_css_class("notice")
        notice_box.set_margin_top(10)
        notice_box.set_margin_start(22)
        notice_box.set_margin_end(22)
        self.notice_label = self._label("Waiting for an ATK/VXE mouse…", None, wrap=True)
        self.notice_label.set_hexpand(True)
        notice_box.append(self.notice_label)
        retry = Gtk.Button(label="Retry")
        retry.add_css_class("pill")
        retry.connect("clicked", lambda *_: self.worker.retry())
        notice_box.append(retry)
        self.notice.set_child(notice_box)
        self.notice.set_reveal_child(True)
        content.append(self.notice)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(170)
        self.stack.set_vexpand(True)
        self.stack.add_named(self._build_overview(), "overview")
        self.stack.add_named(self._build_performance(), "performance")
        self.stack.add_named(self._build_dpi(), "dpi")
        self.stack.add_named(self._build_lighting(), "lighting")
        self.stack.add_named(self._build_device(), "device")
        content.append(self.stack)
        root.append(content)
        self.toast_overlay.set_child(root)
        toolbar.add_top_bar(header)
        toolbar.set_content(self.toast_overlay)
        self.set_content(toolbar)

    def _build_menu(self):
        menu = Gio.Menu()
        menu.append("Refresh", "app.refresh")
        style_menu = Gio.Menu()
        for key, label in config.TRAY_STYLES:
            item = Gio.MenuItem.new(label, None)
            item.set_action_and_target_value("app.tray-style", GLib.Variant.new_string(key))
            style_menu.append_item(item)
        menu.append_submenu("Tray icon", style_menu)
        menu.append("Autostart at login", "app.autostart")
        menu.append("Save support report", "win.save-report")
        menu.append("Request device support", "win.open-support")
        menu.append("Open ATK HUB", "app.web-driver")
        menu.append("About ATK Control", "app.about")
        menu.append("Quit", "app.quit")
        return menu

    def _build_sidebar(self) -> Gtk.Widget:
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar.add_css_class("sidebar")
        sidebar.set_size_request(224, -1)
        sidebar.set_hexpand(False)

        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=11)
        brand.set_margin_top(20)
        brand.set_margin_bottom(22)
        brand.set_margin_start(16)
        brand.set_margin_end(16)
        brand.append(BrandMark(42))
        brand_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand_text.set_valign(Gtk.Align.CENTER)
        brand_text.append(self._label("ATK", "brand-title"))
        brand_text.append(self._label("COMMAND CENTER", "brand-sub"))
        brand.append(brand_text)
        sidebar.append(brand)

        nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        nav.set_margin_start(10)
        nav.set_margin_end(10)
        self.nav_buttons: dict[str, Gtk.Button] = {}
        for key, title, icon in (
            ("overview", "Overview", "go-home-symbolic"),
            ("performance", "Performance", "utilities-system-monitor-symbolic"),
            ("dpi", "DPI", "input-mouse-symbolic"),
            ("lighting", "Lighting", "display-brightness-symbolic"),
            ("device", "Device", "preferences-system-symbolic"),
        ):
            button = Gtk.Button()
            button.add_css_class("nav-button")
            child = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            child.append(Gtk.Image.new_from_icon_name(icon))
            child.append(self._label(title, None))
            button.set_child(child)
            button.connect("clicked", lambda _b, page=key: self._select_page(page))
            self.nav_buttons[key] = button
            nav.append(button)
        sidebar.append(nav)

        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        sidebar.append(spacer)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("sidebar-card")
        card.set_margin_start(12)
        card.set_margin_end(12)
        card.set_margin_bottom(14)
        self.sidebar_device = self._label("NO DEVICE", "sidebar-device")
        self.sidebar_link = self._label("Plug in a receiver", "sidebar-link", wrap=True)
        self.sidebar_battery = self._label("—", "metric-value")
        self.sidebar_battery.set_halign(Gtk.Align.START)
        card.append(self._label("CONNECTED", "eyebrow"))
        card.append(self.sidebar_device)
        card.append(self.sidebar_battery)
        card.append(self.sidebar_link)
        sidebar.append(card)
        version = self._label(f"v{config.VERSION}", "footer-note")
        version.set_margin_start(18)
        version.set_margin_bottom(14)
        sidebar.append(version)
        return sidebar

    def _select_page(self, page: str) -> None:
        if page not in self.nav_buttons:
            return
        self.stack.set_visible_child_name(page)
        for key, button in self.nav_buttons.items():
            if key == page:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    # -------------------------------------------------------------- overview
    def _build_overview(self) -> Gtk.Widget:
        page, root = self._page("Overview", "The state of your mouse, without the menus.")
        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=26)
        hero.add_css_class("hero-card")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        left.set_hexpand(True)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top.append(self._label("BATTERY", "eyebrow"))
        self.hero_charging = self._label("ON BATTERY", "hero-badge")
        top.append(self.hero_charging)
        left.append(top)
        value_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.battery_big = self._label("—", "battery-number")
        self.battery_big.set_valign(Gtk.Align.END)
        self.battery_suffix = self._label("%", "battery-suffix")
        self.battery_suffix.set_valign(Gtk.Align.END)
        self.battery_suffix.set_margin_bottom(16)
        value_row.append(self.battery_big)
        value_row.append(self.battery_suffix)
        left.append(value_row)
        self.battery_rail = BatteryRail()
        left.append(self.battery_rail)
        self.hero_model = self._label("No mouse connected", "hero-model")
        self.hero_sub = self._label("Waiting for a receiver", "hero-sub", wrap=True)
        left.append(self.hero_model)
        left.append(self.hero_sub)
        hero.append(left)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right.set_valign(Gtk.Align.CENTER)
        right.set_size_request(150, -1)
        self.hero_link = self._label("OFFLINE", "status-pill offline")
        self.hero_link.set_halign(Gtk.Align.END)
        right.append(self.hero_link)
        right.append(self._label("LINK", "eyebrow"))
        self.hero_receiver = self._label("—", "mono")
        right.append(self.hero_receiver)
        right.append(self._label("FIRMWARE", "eyebrow"))
        self.hero_firmware = self._label("—", "mono")
        right.append(self.hero_firmware)
        right.append(self._label("IDENTITY", "eyebrow"))
        self.hero_identity = self._label("—", "mono")
        right.append(self.hero_identity)
        hero.append(right)
        root.append(hero)

        metrics = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        metrics.set_homogeneous(True)
        self.metric_values: dict[str, Gtk.Label] = {}
        self.metric_dpi = self._metric("DPI", "—", "ACTIVE RESOLUTION", "dpi", "dpi")
        self.metric_polling = self._metric("POLLING", "—", "REPORT RATE", "performance", "polling")
        self.metric_profile = self._metric("PROFILE", "—", "ONBOARD BANK", "device", "profile")
        for widget in (self.metric_dpi, self.metric_polling, self.metric_profile):
            metrics.append(widget)
        root.append(metrics)

        quick, body = self._card("Quick control", "The three settings worth reaching most often.")
        self.dash_motion = Gtk.Switch()
        self.dash_motion.connect("notify::active", lambda w, _p: self._toggle("motion_sync", w, "dash"))
        self.dash_motion_row = self._setting_row(
            "Motion Sync", "Matches sensor sampling to the report interval.", self.dash_motion, body
        )
        self.dash_ripple = Gtk.Switch()
        self.dash_ripple.connect("notify::active", lambda w, _p: self._toggle("ripple", w, "dash"))
        self.dash_ripple_row = self._setting_row(
            "Ripple control", "Smooths tiny cursor jitter at low speeds.", self.dash_ripple, body
        )
        self.dash_line = Gtk.Switch()
        self.dash_line.connect("notify::active", lambda w, _p: self._toggle("straight_line", w, "dash"))
        self.dash_line_row = self._setting_row(
            "Straight-line correction", "Helps keep horizontal and vertical lines steady.", self.dash_line, body
        )
        more = Gtk.Button(label="Open performance controls")
        more.add_css_class("pill")
        more.set_halign(Gtk.Align.START)
        more.connect("clicked", lambda *_: self._select_page("performance"))
        body.append(more)
        root.append(quick)
        return page

    def _metric(self, title: str, value: str, caption: str, page: str,
                key: str) -> Gtk.Button:
        button = Gtk.Button()
        button.add_css_class("metric-button")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.append(self._label(title, "metric-label"))
        value_label = self._label(value, "metric-value")
        self.metric_values[key] = value_label
        box.append(value_label)
        box.append(self._label(caption, "metric-unit"))
        button.set_child(box)
        button.connect("clicked", lambda *_: self._select_page(page))
        return button

    # ----------------------------------------------------------- performance
    def _build_performance(self) -> Gtk.Widget:
        page, root = self._page("Performance", "Tune the polling link and the sensor's motion processing.")
        rate_card, rate_body = self._card(
            "Report rate",
            "Higher rates deliver fresher input; the 8K dongle makes them worthwhile.",
        )
        self.rate_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.poll_buttons: dict[int, Gtk.Button] = {}
        rate_body.append(self.rate_box)
        self.rate_hint = self._label("Waiting for a mouse…", "row-sub")
        rate_body.append(self.rate_hint)
        root.append(rate_card)

        motion, body = self._card("Tracking", "Settings applied directly to the mouse.")
        self.perf_sync = Gtk.Switch()
        self.perf_sync.connect("notify::active", lambda w, _p: self._toggle("motion_sync", w, "perf"))
        self.perf_sync_row = self._setting_row(
            "Motion Sync", "Aligns sensor sampling with the report interval.", self.perf_sync, body
        )
        self.perf_ripple = Gtk.Switch()
        self.perf_ripple.connect("notify::active", lambda w, _p: self._toggle("ripple", w, "perf"))
        self.perf_ripple_row = self._setting_row(
            "Ripple control", "Smooths small pixel-level jitter.", self.perf_ripple, body
        )
        self.perf_line = Gtk.Switch()
        self.perf_line.connect("notify::active", lambda w, _p: self._toggle("straight_line", w, "perf"))
        self.perf_line_row = self._setting_row(
            "Straight-line correction", "Stabilises near-horizontal and near-vertical movement.", self.perf_line, body
        )
        self.perf_mode = Gtk.Switch()
        self.perf_mode.connect("notify::active", lambda w, _p: self._toggle("performance", w, "perf"))
        self.perf_mode_row = self._setting_row(
            "Competitive performance mode", "Uses the vendor's competitive sensor profile.", self.perf_mode, body
        )
        self.perf_long = Gtk.Switch()
        self.perf_long.connect("notify::active", lambda w, _p: self._toggle("long_range", w, "perf"))
        self.perf_long_row = self._setting_row(
            "Long range", "Raises link robustness at a small power cost.", self.perf_long, body
        )
        root.append(motion)

        self.angle_card, angle_body = self._card(
            "Sensor rotation",
            "Rotate the sensor axis between -30 and +30 degrees.",
        )
        self.angle_switch = Gtk.Switch()
        self.angle_switch.connect("notify::active", lambda *_: self._angle_changed())
        self.angle_switch_row = self._setting_row(
            "Enable rotation", "Leave off for the normal sensor orientation.", self.angle_switch, angle_body
        )
        angle_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.angle_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -30, 30, 1)
        self.angle_scale.set_hexpand(True)
        self.angle_scale.set_draw_value(False)
        self.angle_scale.connect("value-changed", lambda *_: self._angle_changed())
        self.angle_value = self._label("0°", "mono")
        self.angle_value.set_size_request(44, -1)
        angle_box.append(self.angle_scale)
        angle_box.append(self.angle_value)
        angle_body.append(angle_box)
        root.append(self.angle_card)

        self.lod_card, lod_body = self._card(
            "Lift-off distance",
            "How far the mouse can be raised before tracking stops.",
        )
        self.lod_buttons_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lod_buttons: list[tuple[int, Gtk.Button]] = []
        for code, mm in ((1, 0.7), (4, 1.0), (11, 1.7)):
            button = Gtk.Button(label=f"{mm:.1f} mm")
            button.add_css_class("pill")
            button.connect("clicked", lambda _b, c=code: self._set_lod(c))
            self.lod_buttons.append((code, button))
            self.lod_buttons_box.append(button)
        lod_body.append(self.lod_buttons_box)
        self.lod_scale_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.lod_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 11, 1)
        self.lod_scale.set_hexpand(True)
        self.lod_scale.set_draw_value(False)
        self.lod_scale.connect("value-changed", lambda *_: self._lod_scale_changed())
        self.lod_value = self._label("1.0 mm", "mono")
        self.lod_scale_box.append(self.lod_scale)
        self.lod_scale_box.append(self.lod_value)
        lod_body.append(self.lod_scale_box)
        root.append(self.lod_card)

        timing, timing_body = self._card("Timing & power", "Stored on the mouse and kept across power cycles.")
        self.debounce_dd = Gtk.DropDown.new_from_strings(["—"])
        self.debounce_dd.connect("notify::selected", lambda *_: self._debounce_selected())
        self.debounce_row = self._setting_row(
            "Button debounce", "Higher values reject double clicks but add latency.", self.debounce_dd, timing_body
        )
        self.sleep_dd = Gtk.DropDown.new_from_strings(["—"])
        self.sleep_dd.connect("notify::selected", lambda *_: self._sleep_selected())
        self.sleep_row = self._setting_row(
            "Sleep timer", "Idle time before the mouse enters low power.", self.sleep_dd, timing_body
        )
        root.append(timing)
        return page

    # ------------------------------------------------------------------- dpi
    def _build_dpi(self) -> Gtk.Widget:
        page, root = self._page("DPI", "Each stage is a stored resolution with its own indicator colour.")
        active, active_body = self._card("Active resolution", "The stage the DPI button currently cycles to.")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.dpi_active_number = self._label("—", "battery-number")
        self.dpi_active_number.set_size_request(180, -1)
        row.append(self.dpi_active_number)
        active_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.dpi_active_meta = self._label("Waiting for a mouse", "row-title")
        self.dpi_active_note = self._label("", "row-sub", wrap=True)
        active_text.append(self.dpi_active_meta)
        active_text.append(self.dpi_active_note)
        row.append(active_text)
        active_body.append(row)
        root.append(active)

        stages, body = self._card(
            "Stages",
            "Edit X/Y resolution and colour, then activate the stage you want to use.",
        )
        self.dpi_rows = []
        for index in range(8):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class("stage-row")
            index_label = self._label(f"{index + 1:02d}", "stage-index")
            index_label.set_size_request(24, -1)
            row.append(index_label)
            dialog = Gtk.ColorDialog()
            dialog.set_with_alpha(False)
            color = Gtk.ColorDialogButton.new(dialog)
            color.set_tooltip_text("DPI indicator colour")
            color.set_valign(Gtk.Align.CENTER)
            color.connect("notify::rgba", lambda w, _p, i=index: self._color_changed(i, w))
            if not devices.default_capabilities().stage_colors:
                color.set_visible(False)
            row.append(color)
            x_label = self._label("X", "mini-label")
            row.append(x_label)
            x_spin = Gtk.SpinButton.new_with_range(10, 42000, 10)
            x_spin.set_numeric(True)
            x_spin.set_width_chars(5)
            x_spin.connect("value-changed", lambda w, i=index, axis="x": self._dpi_spin_changed(i, axis, w))
            row.append(x_spin)
            y_label = self._label("Y", "mini-label")
            row.append(y_label)
            y_spin = Gtk.SpinButton.new_with_range(10, 42000, 10)
            y_spin.set_numeric(True)
            y_spin.set_width_chars(5)
            y_spin.connect("value-changed", lambda w, i=index, axis="y": self._dpi_spin_changed(i, axis, w))
            row.append(y_spin)
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            row.append(spacer)
            status = self._label("", "mini-label")
            row.append(status)
            activate = Gtk.Button(label="Use")
            activate.add_css_class("pill")
            activate.connect("clicked", lambda _b, i=index: self._activate_stage(i))
            row.append(activate)
            body.append(row)
            self.dpi_rows.append({
                "row": row, "index": index_label, "color": color,
                "x": x_spin, "y": y_spin, "status": status, "activate": activate,
            })
        root.append(stages)
        note, note_body = self._card()
        note_body.append(self._label(
            "Changes are written to the mouse immediately and verified by reading them back. "
            "DPI stage count is kept unchanged in this version.",
            "footer-note", wrap=True,
        ))
        root.append(note)
        return page

    # -------------------------------------------------------------- lighting
    def _build_lighting(self) -> Gtk.Widget:
        page, root = self._page("Lighting", "The DPI indicator LED, mapped to the colour of each stage.")
        self.lighting_card, body = self._card(
            "DPI indicator",
            "A small colour cue for the active resolution.",
        )
        self.lighting_preview = LightingPreview()
        body.append(self.lighting_preview)
        body.append(self._label("EFFECT", "eyebrow"))
        self.light_mode_buttons: list[Gtk.Button] = []
        self.light_mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for index, label in enumerate(("Off", "Steady", "Breathing")):
            button = Gtk.Button(label=label)
            button.add_css_class("pill")
            button.connect("clicked", lambda _b, i=index: self._light_changed(i))
            self.light_mode_buttons.append(button)
            self.light_mode_box.append(button)
        body.append(self.light_mode_box)
        body.append(self._label("BRIGHTNESS", "eyebrow"))
        self.light_brightness_buttons: list[Gtk.Button] = []
        self.light_brightness_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for index, label in enumerate(("Low", "Medium", "High")):
            button = Gtk.Button(label=label)
            button.add_css_class("pill")
            button.connect("clicked", lambda _b, i=index: self._light_changed(self._light_mode(), i))
            self.light_brightness_buttons.append(button)
            self.light_brightness_box.append(button)
        body.append(self.light_brightness_box)
        body.append(self._label("SPEED", "eyebrow"))
        self.light_speed_buttons: list[Gtk.Button] = []
        self.light_speed_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        for index, label in enumerate(("Slow", "Medium", "Fast")):
            button = Gtk.Button(label=label)
            button.add_css_class("pill")
            button.connect("clicked", lambda _b, i=index: self._light_changed(self._light_mode(), self._light_brightness(), i))
            self.light_speed_buttons.append(button)
            self.light_speed_box.append(button)
        body.append(self.light_speed_box)
        root.append(self.lighting_card)

        colours, colours_body = self._card(
            "Stage colours",
            "Each DPI stage carries its own RGB value; edit them on the DPI page.",
        )
        self.light_colour_dots = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        colours_body.append(self.light_colour_dots)
        go = Gtk.Button(label="Edit stage colours")
        go.add_css_class("pill")
        go.set_halign(Gtk.Align.START)
        go.connect("clicked", lambda *_: self._select_page("dpi"))
        colours_body.append(go)
        root.append(colours)
        self.lighting_unavailable, unavailable_body = self._card()
        unavailable_body.append(self._label(
            "This mouse does not expose DPI lighting on the current firmware. "
            "Everything else still works.",
            "row-sub", wrap=True,
        ))
        root.append(self.lighting_unavailable)
        return page

    # ---------------------------------------------------------------- device
    def _build_device(self) -> Gtk.Widget:
        page, root = self._page("Device", "Identity, stored buttons and maintenance.")
        self.devices_card, devices_body = self._card(
            "Configuration devices",
            "Choose which receiver or cable to control when more than one is connected.",
        )
        self.devices_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        devices_body.append(self.devices_list)
        root.append(self.devices_card)

        support, support_body = self._card(
            "Missing your ATK/VXE mouse?",
            "Add it by sharing a read-only report from this device.",
        )
        support_text = self._label(
            "Save the report, review it, then attach it to the GitHub support "
            "request. The file contains device IDs, settings and raw configuration "
            "bytes — never the full RF identifier, USB serial or your host name.",
            "row-sub", wrap=True,
        )
        support_text.set_max_width_chars(78)
        support_text.set_hexpand(True)
        support_body.append(support_text)
        support_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        save_support = Gtk.Button(label="Save support report")
        save_support.add_css_class("pill")
        save_support.connect("clicked", lambda *_: self._save_report())
        open_support = Gtk.Button(label="Open support request")
        open_support.add_css_class("pill")
        open_support.connect("clicked", lambda *_: self._open_support())
        support_actions.append(save_support)
        support_actions.append(open_support)
        support_body.append(support_actions)
        support_body.append(self._label(
            "Terminal equivalent: atkctl support", "footer-note", wrap=True,
        ))
        root.append(support)

        details, body = self._card("Hardware", "Read directly from the configuration channel.")
        self.device_values: dict[str, Gtk.Label] = {}
        for label in ("Model", "Sensor", "Connection", "Firmware", "USB", "CID / MID", "Receiver", "Device revision"):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row.append(self._label(label, "row-title"))
            value = self._label("—", "device-value")
            value.set_hexpand(True)
            value.set_halign(Gtk.Align.END)
            row.append(value)
            body.append(row)
            self.device_values[label] = value
        root.append(details)

        self.profile_card, profile_body = self._card("Onboard profiles", "The mouse stores four complete configuration banks.")
        self.profile_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.profile_buttons: list[Gtk.Button] = []
        for number in range(1, 5):
            button = Gtk.Button(label=str(number))
            button.add_css_class("pill")
            button.set_size_request(48, -1)
            button.connect("clicked", lambda _b, n=number: self._profile_selected(n))
            self.profile_buttons.append(button)
            self.profile_box.append(button)
        profile_body.append(self.profile_box)
        root.append(self.profile_card)

        self.buttons_card, buttons_body = self._card(
            "Buttons", "Read-only view of what each button currently does.",
        )
        self.buttons_list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        buttons_body.append(self.buttons_list)
        root.append(self.buttons_card)

        integration, integration_body = self._card("Integration", "Desktop behaviour for this app.")
        self.autostart = Gtk.Switch()
        self.autostart.set_active(config.is_autostart_enabled())
        self.autostart.connect("notify::active", self._autostart_toggled)
        autostart_row = self._setting_row(
            "Autostart at login", "Start hidden in the tray when you sign in.",
            self.autostart, integration_body,
        )
        if os.environ.get("FLATPAK_ID"):
            self.autostart.set_sensitive(False)
            self.autostart.set_tooltip_text(
                "Flatpak applications cannot edit host autostart entries. "
                "Add ATK Control to your desktop's autostart settings manually."
            )
            autostart_row.set_tooltip_text(self.autostart.get_tooltip_text())
        style_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.style_buttons: dict[str, Gtk.Button] = {}
        for key, label in config.TRAY_STYLES:
            button = Gtk.Button(label=label)
            button.add_css_class("pill")
            button.connect("clicked", lambda _b, k=key: self._tray_style_selected(k))
            self.style_buttons[key] = button
            style_row.append(button)
        integration_body.append(style_row)
        actions_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hub_button = Gtk.Button(label="Open ATK HUB")
        hub_button.add_css_class("pill")
        hub_button.connect("clicked", lambda *_: self.get_application().activate_action("web-driver", None))
        actions_row.append(hub_button)
        integration_body.append(actions_row)
        root.append(integration)

        about, about_body = self._card("About", "Independent, local and intentionally offline.")
        about_body.append(self._label(
            f"ATK Control {config.VERSION} · GTK4 / libadwaita\n"
            "Not affiliated with ATK or VXE. Settings stay on your mouse and computer.",
            "row-sub", wrap=True,
        ))
        about_body.append(self._label(
            "Protocol recovered from the public ATK HUB web driver. No telemetry.",
            "footer-note", wrap=True,
        ))
        root.append(about)
        self._update_tray_style_buttons()
        return page

    # -------------------------------------------------------------- handlers
    def _toggle(self, method: str, switch: Gtk.Switch, scope: str) -> None:
        if self._loading:
            return
        self.worker.submit(method, bool(switch.get_active()), key=f"{method}:{scope}")

    def _angle_changed(self) -> None:
        if self._loading:
            return
        self.angle_value.set_text(f"{round(self.angle_scale.get_value())}°")
        if self._angle_timer:
            GLib.source_remove(self._angle_timer)
        self._angle_timer = GLib.timeout_add(350, self._send_angle)

    def _send_angle(self) -> bool:
        self._angle_timer = 0
        if not self._loading:
            self.worker.submit(
                "angle",
                round(self.angle_scale.get_value()),
                bool(self.angle_switch.get_active()),
                key="angle",
            )
        return False

    def _dpi_spin_changed(self, index: int, axis: str, spin: Gtk.SpinButton) -> None:
        if self._loading:
            return
        key = (index, axis)
        timer = self._dpi_timers.get(key)
        if timer:
            GLib.source_remove(timer)
        self._dpi_timers[key] = GLib.timeout_add(650, self._send_dpi, index)

    def _send_dpi(self, index: int) -> bool:
        for axis in ("x", "y"):
            timer = self._dpi_timers.pop((index, axis), 0)
            if timer:
                GLib.source_remove(timer)
        if self._loading or self._state is None:
            return False
        row = self.dpi_rows[index]
        caps = self._caps()
        x = clamp_dpi(int(round(row["x"].get_value())), caps.dpi_options)
        y = clamp_dpi(int(round(row["y"].get_value())), caps.dpi_options)
        self.worker.submit("stage_dpi", index, x, y, key=f"stage:{index}")
        return False

    def _activate_stage(self, index: int) -> None:
        if not self._loading:
            self.worker.submit("active_stage", index)

    def _color_changed(self, index: int, button: Gtk.ColorDialogButton) -> None:
        if self._loading:
            return
        rgba = button.get_rgba()
        color = "#{:02x}{:02x}{:02x}".format(
            round(rgba.red * 255), round(rgba.green * 255), round(rgba.blue * 255)
        )
        key = f"color:{index}"
        if getattr(self, "_color_timer", None):
            GLib.source_remove(self._color_timer)
        self._color_timer = GLib.timeout_add(
            250, lambda: (self.worker.submit("stage_color", index, color, key=key), False)[1]
        )

    def _set_lod(self, code: int) -> None:
        if not self._loading:
            self.worker.submit("lift_off", code)

    def _lod_scale_changed(self) -> None:
        code = int(round(self.lod_scale.get_value()))
        self.lod_value.set_text(f"{(code + 6) / 10:.1f} mm")
        if self._loading:
            return
        if self._lod_timer:
            GLib.source_remove(self._lod_timer)
        self._lod_timer = GLib.timeout_add(
            350, lambda: (self.worker.submit("lift_off", int(round(self.lod_scale.get_value())), key="lod"), False)[1]
        )

    def _debounce_selected(self) -> None:
        if self._loading or self._state is None:
            return
        options = self._caps().debounce_options
        index = self.debounce_dd.get_selected()
        if 0 <= index < len(options):
            self.worker.submit("debounce", options[index], key="debounce")

    def _sleep_selected(self) -> None:
        if self._loading or self._state is None:
            return
        options = self._caps().sleep_options
        index = self.sleep_dd.get_selected()
        if 0 <= index < len(options):
            self.worker.submit("sleep", options[index], key="sleep")

    def _light_mode(self) -> int:
        return getattr(self, "_light_mode_value", 0)

    def _light_brightness(self) -> int:
        return getattr(self, "_light_brightness_value", 1)

    def _light_speed(self) -> int:
        return getattr(self, "_light_speed_value", 1)

    def _light_changed(self, mode: int, brightness: int | None = None, speed: int | None = None) -> None:
        if self._loading:
            return
        brightness = self._light_brightness() if brightness is None else brightness
        speed = self._light_speed() if speed is None else speed
        self.worker.submit("led", mode, brightness, speed, key="led")

    def _profile_selected(self, number: int) -> None:
        if not self._loading:
            self.worker.submit("profile", number)

    def _autostart_toggled(self, switch: Gtk.Switch, _param) -> None:
        if self._loading:
            return
        enabled = bool(switch.get_active())
        if not config.set_autostart(enabled):
            self.toast("Could not update autostart.")

    def _tray_style_selected(self, style: str) -> None:
        app = self.get_application()
        app.activate_action("tray-style", GLib.Variant.new_string(style))
        self._tray_style = style
        self._update_tray_style_buttons()

    def _update_tray_style_buttons(self) -> None:
        for key, button in self.style_buttons.items():
            if key == self._tray_style:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    # --------------------------------------------------------------- updates
    def _caps(self) -> devices.Capabilities:
        model = None
        if self._state is not None and self._state.cid is not None:
            model = devices.MODEL_BY_CIDMID.get((self._state.cid, self._state.mid))
        receiver = None
        if self._state is not None and self._state.via_receiver and self._state.receiver_pid:
            receiver = devices.receiver_for(self._state.receiver_pid, self._state.receiver_name)
        return devices.capabilities_for(
            model=model,
            receiver=receiver,
            sensor_name=self._state.sensor if self._state else None,
            active_polling=self._state.polling_rate if self._state else 1000,
            debounce=self._state.debounce_ms if self._state else None,
            sleep=self._state.sleep_seconds if self._state else None,
            usb_name=self._state.usb_name if self._state else "",
        )

    def on_link(self, connected: bool, error: str | None) -> None:
        self._connected = connected
        if connected:
            self.notice.set_reveal_child(False)
            self.stack.set_sensitive(True)
            return
        self._state = None
        self.stack.set_sensitive(False)
        self.notice_label.set_text(error or "Waiting for an ATK/VXE mouse…")
        self.notice.set_reveal_child(True)
        self.header_status.set_text("OFFLINE")
        self.header_status.remove_css_class("charging")
        self.header_status.add_css_class("offline")
        self.hero_link.set_text("OFFLINE")
        self.hero_link.remove_css_class("charging")
        self.hero_link.add_css_class("offline")
        self.hero_receiver.set_text("—")
        self.battery_big.set_text("—")
        self.battery_suffix.set_text("")
        self.battery_rail.set_state(None, None)
        self.hero_charging.set_text("NO TELEMETRY")
        self.hero_model.set_text("No mouse connected")
        self.hero_sub.set_text("Plug in the 8K dongle or connect the mouse over USB.")
        self.hero_firmware.set_text("—")
        self.hero_identity.set_text("—")
        self.sidebar_device.set_text("NO DEVICE")
        self.sidebar_link.set_text("Waiting for a receiver")
        self.sidebar_battery.set_text("—")
        for label in self.device_values.values():
            label.set_text("—")
        self.dpi_active_number.set_text("—")
        self.metric_values["dpi"].set_text("—")
        self.metric_values["polling"].set_text("—")
        self.metric_values["profile"].set_text("—")
        self.dpi_active_meta.set_text("Waiting for a mouse")
        self.dpi_active_note.set_text("")

    def on_state(self, state: MouseState, changed: set[str]) -> None:
        self._state = state
        self._connected = True
        self.notice.set_reveal_child(bool(state.read_only))
        if state.read_only:
            self.notice_label.set_text(
                "Recognized ATK/VXE device, but this model is not in the supported "
                "database yet. Settings are read-only — save a report from the Device page."
            )
        self.stack.set_sensitive(True)
        self._loading = True
        try:
            caps = self._caps()
            self._update_header(state, caps)
            self._update_overview(state, caps)
            self._update_performance(state, caps)
            self._update_dpi(state, caps)
            self._update_lighting(state)
            self._update_device(state)
        finally:
            self._loading = False

    def _update_header(self, state: MouseState, caps) -> None:
        label = "USB"
        if not state.wired:
            ceiling = caps.link_ceiling
            label = "8K LINK" if ceiling >= 8000 else ("4K LINK" if ceiling >= 4000 else "1K LINK")
        self.header_status.set_text(label)
        self.header_status.remove_css_class("offline")
        if state.charging:
            self.header_status.add_css_class("charging")
        else:
            self.header_status.remove_css_class("charging")

    def _update_overview(self, state: MouseState, caps) -> None:
        if state.battery is None:
            self.battery_big.set_text("—")
            self.battery_suffix.set_text("")
        else:
            self.battery_big.set_text(str(max(0, min(100, state.battery))))
            self.battery_suffix.set_text("%")
        self.battery_rail.set_state(state.battery, state.charging)
        if state.charging:
            self.hero_charging.set_text("CHARGING")
        elif state.wired:
            self.hero_charging.set_text("USB POWER")
        else:
            self.hero_charging.set_text("ON BATTERY")
        self.hero_model.set_text(state.connected_name)
        firmware = state.firmware or ("not reported" if state.via_receiver else "unknown")
        self.hero_sub.set_text(f"{state.sensor} · FW {firmware} · {state.cid or '?'}, {state.mid or '?'}")
        link = state.link_label
        if state.wired:
            link_badge = "USB"
        else:
            ceiling = caps.link_ceiling
            link_badge = "8K LINK" if ceiling >= 8000 else ("4K LINK" if ceiling >= 4000 else "1K LINK")
        self.hero_link.set_text(link_badge)
        self.hero_link.remove_css_class("offline")
        if state.charging:
            self.hero_link.add_css_class("charging")
        self.hero_receiver.set_text(link)
        self.hero_firmware.set_text(
            state.firmware or ("not reported" if state.via_receiver else "—")
        )
        self.hero_identity.set_text(state.identity)
        self.hero_link.set_text(link_badge)
        self.sidebar_device.set_text(state.connected_name.upper())
        self.sidebar_battery.set_text(
            f"{state.battery}%" if state.battery is not None else "—"
        )
        self.sidebar_link.set_text(f"{link}\nFW {state.firmware or 'n/a'}")
        self.metric_values["dpi"].set_text(f"{state.dpi:,}")
        self.metric_values["polling"].set_text(f"{state.polling_rate:,} Hz")
        self.metric_values["profile"].set_text(
            f"{state.profile}/4" if state.profile else "—"
        )
        self._set_switch(self.dash_motion, state.motion_sync, self.dash_motion_row)
        self._set_switch(self.dash_ripple, state.ripple_control, self.dash_ripple_row)
        self._set_switch(self.dash_line, state.straight_line, self.dash_line_row)

    @staticmethod
    def _set_switch(switch: Gtk.Switch, value: bool | None, row: Gtk.Widget | None = None) -> None:
        if value is None:
            if row is not None:
                row.set_visible(False)
            return
        if row is not None:
            row.set_visible(True)
        if switch.get_active() != bool(value):
            switch.set_active(bool(value))

    def _update_performance(self, state: MouseState, caps) -> None:
        # report-rate pills
        for child in list(self.rate_box):
            self.rate_box.remove(child)
        self.poll_buttons.clear()
        for hz in caps.polling_rates:
            button = Gtk.Button(label=f"{hz:,}")
            button.add_css_class("pill")
            button.set_tooltip_text(f"{hz:,} Hz")
            if hz == state.polling_rate:
                button.add_css_class("active")
            button.connect("clicked", lambda _b, value=hz: self._set_polling(value))
            self.poll_buttons[hz] = button
            self.rate_box.append(button)
        self.rate_hint.set_text(
            f"Currently reporting at {state.polling_rate:,} Hz · "
            f"link ceiling {caps.link_ceiling:,} Hz"
        )
        self._set_switch(self.perf_sync, state.motion_sync, self.perf_sync_row)
        self._set_switch(self.perf_ripple, state.ripple_control, self.perf_ripple_row)
        self._set_switch(self.perf_line, state.straight_line, self.perf_line_row)
        self._set_switch(self.perf_mode, state.performance_mode, self.perf_mode_row)
        self.perf_mode_row.set_visible(bool(state.supports_performance_mode))
        self._set_switch(self.perf_long, state.long_range, self.perf_long_row)
        self.perf_long_row.set_visible(bool(state.supports_long_range))

        self.angle_card.set_visible(bool(state.supports_angle))
        if state.supports_angle:
            angle = state.angle_degrees or 0
            if self.angle_scale.get_value() != angle:
                self.angle_scale.set_value(angle)
            self.angle_value.set_text(f"{angle}°")
            self.angle_switch.set_active(bool(state.angle_enabled))

        self.lod_buttons_box.set_visible(not caps.lift_off_scale)
        self.lod_scale_box.set_visible(caps.lift_off_scale)
        if caps.lift_off_scale:
            code = state.lod_code or 4
            if self.lod_scale.get_value() != code:
                self.lod_scale.set_value(code)
            self.lod_value.set_text(f"{(code + 6) / 10:.1f} mm")
        else:
            for code, button in self.lod_buttons:
                if state.lod_code == code:
                    button.add_css_class("active")
                else:
                    button.remove_css_class("active")

        # ComboRow-like DropDowns.  The current value is added to the list by
        # capabilities_for so it can always be represented.
        debounce = [f"{v} ms" for v in caps.debounce_options]
        if self._dropdown_values(self.debounce_dd) != debounce:
            self.debounce_dd.set_model(Gtk.StringList.new(debounce))
        if state.debounce_ms in caps.debounce_options:
            self.debounce_dd.set_selected(caps.debounce_options.index(state.debounce_ms))
        self.debounce_dd.set_sensitive(state.debounce_ms is not None)
        sleep = [self._sleep_label(v) for v in caps.sleep_options]
        if self._dropdown_values(self.sleep_dd) != sleep:
            self.sleep_dd.set_model(Gtk.StringList.new(sleep))
        if state.sleep_seconds in caps.sleep_options:
            self.sleep_dd.set_selected(caps.sleep_options.index(state.sleep_seconds))
        self.sleep_dd.set_sensitive(state.sleep_seconds is not None)

    def _set_polling(self, hz: int) -> None:
        if not self._loading:
            self.worker.submit("polling", hz)

    @staticmethod
    def _sleep_label(seconds: int) -> str:
        if seconds < 60:
            return f"{seconds} s"
        if seconds % 60:
            return f"{seconds // 60} min {seconds % 60} s"
        return f"{seconds // 60} min"

    @staticmethod
    def _dropdown_values(dropdown: Gtk.DropDown) -> list[str]:
        model = dropdown.get_model()
        if model is None:
            return []
        return [model.get_string(i) for i in range(model.get_n_items())]

    def _update_dpi(self, state: MouseState, caps) -> None:
        self.dpi_active_number.set_text(f"{state.dpi:,}")
        self.dpi_active_meta.set_text(
            f"Stage {state.active_stage + 1} of {state.stage_count} · {state.dpi:,} × {state.dpi_y:,}"
        )
        self.dpi_active_note.set_text(
            f"{caps.sensor.name} · {caps.sensor.min_dpi:,}–{caps.sensor.max_dpi:,} DPI"
        )
        step = 10 if caps.sensor.family == "ultra" and caps.sensor.max_dpi <= 42000 else 50
        for index, row in enumerate(self.dpi_rows):
            visible = index < state.stage_count
            row["row"].set_visible(visible)
            if not visible:
                continue
            active = index == state.active_stage
            if active:
                row["row"].add_css_class("stage-active")
            else:
                row["row"].remove_css_class("stage-active")
            x, y = state.stages[index] if index < len(state.stages) else (0, 0)
            for spin, value in ((row["x"], x), (row["y"], y)):
                spin.get_adjustment().set_lower(caps.sensor.min_dpi)
                spin.get_adjustment().set_upper(caps.sensor.max_dpi)
                spin.get_adjustment().set_step_increment(step)
                spin.get_adjustment().set_page_increment(step * 10)
                if not spin.has_focus() and int(spin.get_value()) != value:
                    spin.set_value(value)
            if caps.stage_colors and state.supports_stage_colors:
                color = state.stage_colors[index] if index < len(state.stage_colors) else "#ff6b3d"
                current = row["color"].get_rgba()
                target = _gdk_rgba(color)
                if (abs(current.red - target.red) + abs(current.green - target.green)
                        + abs(current.blue - target.blue) > 0.005):
                    row["color"].set_rgba(target)
                row["color"].set_visible(True)
            else:
                row["color"].set_visible(False)
            row["status"].set_text("ACTIVE" if active else "")
            row["activate"].set_sensitive(not active)
            row["activate"].set_label("Active" if active else "Use")
        self._update_light_dots(state)

    def _update_light_dots(self, state: MouseState) -> None:
        for child in list(self.light_colour_dots):
            self.light_colour_dots.remove(child)
        for index in range(state.stage_count):
            color = state.stage_colors[index] if index < len(state.stage_colors) else "#ff6b3d"
            dot = Gtk.DrawingArea()
            dot.set_content_width(16)
            dot.set_content_height(16)
            rgba = _rgb_from_hex(color)

            def draw(_area, ctx, width, height, rgb=rgba):
                ctx.arc(width / 2, height / 2, 6.0, 0, 2 * math.pi)
                ctx.set_source_rgba(*rgb, 1.0)
                ctx.fill()

            dot.set_draw_func(draw)
            dot.set_tooltip_text(f"Stage {index + 1}: {color}")
            self.light_colour_dots.append(dot)

    def _update_lighting(self, state: MouseState) -> None:
        available = bool(state.supports_lighting)
        self.lighting_card.set_visible(available)
        self.lighting_unavailable.set_visible(not available)
        if not available:
            return
        mode = state.led_mode if state.led_mode is not None else 0
        brightness = state.led_brightness if state.led_brightness is not None else 1
        speed = state.led_speed if state.led_speed is not None else 1
        self._light_mode_value = mode
        self._light_brightness_value = brightness
        self._light_speed_value = speed
        for index, button in enumerate(self.light_mode_buttons):
            self._set_active(button, index == mode)
        for index, button in enumerate(self.light_brightness_buttons):
            self._set_active(button, index == brightness)
            button.set_sensitive(mode != 0)
        for index, button in enumerate(self.light_speed_buttons):
            self._set_active(button, index == speed)
            button.set_sensitive(mode != 0)
        color = state.stage_colors[state.active_stage] if (
            state.active_stage < len(state.stage_colors)
        ) else "#ff6b3d"
        self.lighting_preview.set_state(color, mode, brightness)

    @staticmethod
    def _set_active(button: Gtk.Button, active: bool) -> None:
        if active:
            button.add_css_class("active")
        else:
            button.remove_css_class("active")

    def _update_device(self, state: MouseState) -> None:
        self.device_values["Model"].set_text(state.connected_name)
        self.device_values["Sensor"].set_text(state.sensor or "—")
        self.device_values["Connection"].set_text(state.link_label)
        firmware = state.firmware
        if not firmware and state.via_receiver:
            firmware = "Not forwarded by receiver"
        self.device_values["Firmware"].set_text(firmware or "—")
        self.device_values["USB"].set_text(f"{state.vendor_id:04x}:{state.product_id:04x}")
        self.device_values["CID / MID"].set_text(state.identity)
        self.device_values["Receiver"].set_text(
            f"{state.receiver_name} (0x{state.receiver_pid:04x})" if state.receiver_pid else "—"
        )
        self.device_values["Device revision"].set_text(state.usb_bcd or "—")
        self._update_device_choices()
        self.profile_card.set_visible(state.profile is not None)
        for number, button in enumerate(self.profile_buttons, start=1):
            self._set_active(button, state.profile == number)

        signature = tuple((button.name, button.action) for button in state.buttons)
        if signature == self._buttons_signature:
            return
        self._buttons_signature = signature
        for child in list(self.buttons_list):
            self.buttons_list.remove(child)
        if not state.buttons:
            self.buttons_list.append(self._label(
                "Button assignments are not readable on this firmware.",
                "row-sub", wrap=True,
            ))
        else:
            for button in state.buttons:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                row.append(self._label(button.name, "row-title"))
                action = self._label(button.action, "device-value")
                action.set_hexpand(True)
                action.set_halign(Gtk.Align.END)
                row.append(action)
                self.buttons_list.append(row)

    def _update_device_choices(self) -> None:
        if not hasattr(self.worker, "available_devices"):
            self.devices_card.set_visible(False)
            return
        available = self.worker.available_devices()
        current = self.worker.device_path
        self.devices_card.set_visible(bool(available))
        for child in list(self.devices_list):
            self.devices_list.remove(child)
        for info in available:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            text.set_hexpand(True)
            receiver = devices.receiver_for(info.product_id, info.product_name)
            title = receiver.name if receiver else info.product_name
            text.append(self._label(title, "row-title"))
            kind = "receiver" if info.is_receiver else "mouse"
            state_text = f"{info.vendor_id:04x}:{info.product_id:04x} · {kind}"
            if not info.accessible:
                state_text += " · no permission"
            text.append(self._label(state_text, "row-sub"))
            row.append(text)
            if info.path == current:
                badge = self._label("IN USE", "status-pill")
                badge.set_valign(Gtk.Align.CENTER)
                row.append(badge)
            else:
                button = Gtk.Button(label="Use")
                button.add_css_class("pill")
                button.set_sensitive(info.accessible)
                button.connect("clicked", lambda _b, path=info.path: self.worker.select_device(path))
                row.append(button)
            self.devices_list.append(row)

    # ---------------------------------------------------------------- support
    def _open_support(self) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(config.SUPPORT_URL, None)
        except GLib.Error:
            self.toast("Could not open the GitHub support request.")

    def _save_report(self) -> None:
        if self._state is None:
            self.toast("Connect a mouse first.")
            return
        dialog = Gtk.FileDialog()
        dialog.set_title("Save ATK Control support report")
        dialog.set_initial_name(diagnostics.default_filename())
        dialog.save(self, None, self._report_saved)

    def _report_saved(self, dialog, result) -> None:
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        if gfile is None or not gfile.get_path() or self._state is None:
            return
        try:
            if hasattr(self.worker, "save_support_report"):
                self.worker.save_support_report(gfile.get_path())
                self.toast("Generating support report…")
            else:
                path = diagnostics.write_report(
                    gfile.get_path(), self._state, self.worker.device_path, self.worker.capabilities
                )
                self.toast(f"Saved {Path(path).name}")
        except Exception as exc:
            self.toast(f"Could not save report: {exc}")

    def toast(self, message: str) -> None:
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)
