"""StatusNotifierItem tray icon with a compact quick-action menu.

Three icons share the same data but not the same silhouette: a hexagonal battery
gauge, a transparent four-bar level indicator, and a reticle with percentage.
They are intentionally unlike the tray icon of RAWM Control.
"""

from __future__ import annotations

import math
import os
from typing import Callable

import cairo
import dbus
import dbus.mainloop.glib
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop

from . import devices
from .config import DEFAULT_TRAY_STYLE, TRAY_STYLES
from .state import MouseState

SNI_IFACE = "org.kde.StatusNotifierItem"
MENU_IFACE = "com.canonical.dbusmenu"
WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"

ID_STATUS = 1
ID_SEP1 = 2
ID_POLLING = 3
ID_DPI = 4
ID_PROFILE = 5
ID_MOTION = 6
ID_RIPPLE = 7
ID_SEP2 = 8
ID_OPEN = 9
ID_REFRESH = 10
ID_STYLE = 11
ID_QUIT = 12
ID_POLLING_BASE = 30
ID_DPI_BASE = 40
ID_PROFILE_BASE = 60
ID_STYLE_BASE = 80

ICON_SIZE = 64
STYLE_KEYS = [key for key, _label in TRAY_STYLES]
ACCENT = (1.0, 0.42, 0.24)
CYAN = (0.19, 0.84, 0.77)
INK = (0.035, 0.04, 0.055)
WHITE = (1.0, 1.0, 1.0)


def _dbus_pixmap(pixmap: list[tuple[int, int, bytes]]):
    """Convert raw ARGB tuples into the exact a(iiay) DBus type."""
    items = []
    for width, height, data in pixmap:
        items.append(dbus.Struct(
            (
                dbus.Int32(width),
                dbus.Int32(height),
                dbus.Array(data, signature="y"),
            ),
            signature="iiay",
        ))
    return dbus.Array(items, signature="(iiay)")


def _argb_pixmap(surface: cairo.ImageSurface) -> list[tuple[int, int, bytes]]:
    surface.flush()
    data = bytes(surface.get_data())
    width, height = surface.get_width(), surface.get_height()
    stride = surface.get_stride()
    out = bytearray(width * height * 4)
    for y in range(height):
        row = data[y * stride:y * stride + width * 4]
        for x in range(width):
            b, g, r, a = row[x * 4:x * 4 + 4]
            out[(y * width + x) * 4:(y * width + x) * 4 + 4] = bytes((a, r, g, b))
    return [(width, height, bytes(out))]


def _canvas():
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, ICON_SIZE, ICON_SIZE)
    ctx = cairo.Context(surface)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    return surface, ctx


def _rounded(ctx, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def _hex(ctx, cx, cy, radius):
    for index in range(6):
        angle = -math.pi / 2 + index * math.pi / 3
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        if index == 0:
            ctx.move_to(x, y)
        else:
            ctx.line_to(x, y)
    ctx.close_path()


def _text(ctx, value, cx, cy, size, color=WHITE, outline=0.0):
    ctx.select_font_face("DejaVu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    ctx.set_font_size(size)
    ext = ctx.text_extents(value)
    x = cx - ext.width / 2 - ext.x_bearing
    y = cy - ext.height / 2 - ext.y_bearing
    ctx.move_to(x, y)
    ctx.text_path(value)
    if outline:
        ctx.set_line_width(outline)
        ctx.set_source_rgba(*INK, 0.92)
        ctx.stroke_preserve()
    ctx.set_source_rgba(*color, 1.0)
    ctx.fill()


def _level_color(state: MouseState | None, connected: bool):
    if not connected or state is None or state.battery is None:
        return (0.55, 0.57, 0.62)
    level = state.battery
    if state.charging:
        return CYAN
    if level <= 15:
        return (1.0, 0.32, 0.31)
    if level <= 35:
        return (1.0, 0.72, 0.22)
    return (0.33, 0.86, 0.47)


def _battery_text(state: MouseState | None, connected: bool) -> str:
    if not connected or state is None or state.battery is None:
        return "—"
    return str(max(0, min(100, state.battery)))


def render_hex_icon(state: MouseState | None, connected: bool):
    surface, ctx = _canvas()
    color = _level_color(state, connected)
    charging = connected and state is not None and bool(state.charging)
    border = CYAN if charging else (ACCENT if connected else (0.42, 0.44, 0.48))
    _hex(ctx, 32, 32, 29)
    ctx.set_source_rgba(*INK, 0.94)
    ctx.fill_preserve()
    ctx.set_line_width(3.6)
    ctx.set_source_rgba(*border, 0.98)
    ctx.stroke()

    # A clipped inner fill gives the gauge a clear level even in monochrome.
    if connected and state is not None and state.battery is not None:
        level = max(0, min(100, state.battery)) / 100.0
        ctx.save()
        _hex(ctx, 32, 32, 26)
        ctx.clip()
        ctx.set_source_rgba(*color, 0.16)
        ctx.rectangle(4, 62 - 56 * level, 56, 56 * level)
        ctx.fill()
        ctx.restore()

    value = _battery_text(state, connected)
    size = 27 if len(value) <= 2 else 20
    _text(ctx, value, 32, 35, size, WHITE, 1.8)

    # A cyan border is the charging cue.
    if charging:
        ctx.set_source_rgba(*CYAN, 0.95)
        ctx.arc(48, 12, 4.0, 0, 2 * math.pi)
        ctx.fill()
        ctx.set_line_width(1.4)
        ctx.set_source_rgba(*INK, 0.9)
        ctx.stroke()
    if not connected:
        ctx.set_line_width(3.0)
        ctx.set_source_rgba(*ACCENT, 0.8)
        ctx.move_to(21, 21)
        ctx.line_to(43, 43)
        ctx.move_to(43, 21)
        ctx.line_to(21, 43)
        ctx.stroke()
    return _argb_pixmap(surface)


def render_bars_icon(state: MouseState | None, connected: bool):
    """Transparent four-bar level indicator: no frame, no text, no glyph."""
    surface, ctx = _canvas()
    color = _level_color(state, connected)
    if connected and state is not None and state.battery is not None:
        level = max(0, min(100, state.battery))
    else:
        level = 0

    bar_width = 9.0
    gap = 4.5
    total = 4 * bar_width + 3 * gap
    start_x = (ICON_SIZE - total) / 2
    baseline = 55.0
    heights = (16.0, 26.0, 36.0, 46.0)
    for index, bar_height in enumerate(heights):
        x = start_x + index * (bar_width + gap)
        _rounded(ctx, x, baseline - bar_height, bar_width, bar_height, 3.0)
        # One lit bar per quarter, plus a faint full track for context.
        if connected and level >= (index + 1) * 25 - 8:
            ctx.set_source_rgba(*color, 1.0)
        elif connected and level > index * 25:
            ctx.set_source_rgba(*color, 0.48)
        else:
            ctx.set_source_rgba(1.0, 1.0, 1.0, 0.13)
        ctx.fill()
    return _argb_pixmap(surface)


def render_reticle_icon(state: MouseState | None, connected: bool):
    """A transparent aiming reticle with the percentage inside."""
    surface, ctx = _canvas()
    color = _level_color(state, connected) if connected else (0.55, 0.57, 0.62)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    ctx.set_line_width(4.2)
    ctx.set_source_rgba(*color, 0.98)
    arm = 14.0
    near = 10.0
    far = 54.0
    mid = 24.0
    for sx, sy, dx, dy in (
        (near, near, 1, 1),
        (far, near, -1, 1),
        (far, far, -1, -1),
        (near, far, 1, -1),
    ):
        ctx.move_to(sx + dx * arm, sy)
        ctx.line_to(sx, sy)
        ctx.line_to(sx, sy + dy * arm)
    ctx.stroke()

    value = _battery_text(state, connected)
    size = 25 if len(value) <= 2 else 19
    _text(ctx, value, 32, 34, size, WHITE, 2.0)

    if connected and state is not None and state.charging:
        ctx.set_line_width(2.4)
        ctx.set_source_rgba(*CYAN, 1.0)
        ctx.arc(32, 6.5, 3.0, 0, 2 * math.pi)
        ctx.stroke()
    return _argb_pixmap(surface)


_RENDERERS = {
    "hex": render_hex_icon,
    "bars": render_bars_icon,
    "reticle": render_reticle_icon,
}


def render_tray_icon(state: MouseState | None, connected: bool,
                      style: str = DEFAULT_TRAY_STYLE):
    return _RENDERERS.get(style, render_hex_icon)(state, connected)


class TrayMenu(dbus.service.Object):
    """DBusMenu at the conventional /MenuBar path.

    Keeping the menu in a separate object is friendlier to hosts that do not
    like the menu sharing the StatusNotifierItem object path.
    """

    def __init__(self, bus_name, tray: "Tray") -> None:
        super().__init__(bus_name, "/MenuBar")
        self.tray = tray

    @dbus.service.method(MENU_IFACE, in_signature="iias", out_signature="(ia{sv}av)")
    def GetLayout(self, parent_id, recursion_depth, property_names):
        return self.tray.GetLayout(parent_id, recursion_depth, property_names)

    @dbus.service.method(MENU_IFACE, in_signature="aias", out_signature="a(ia{sv})")
    def GetGroupProperties(self, ids, property_names):
        return self.tray.GetGroupProperties(ids, property_names)

    @dbus.service.method(MENU_IFACE, in_signature="is", out_signature="v")
    def GetProperty(self, item_id, name):
        return self.tray.GetProperty(item_id, name)

    @dbus.service.method(MENU_IFACE, in_signature="isvu", out_signature="")
    def Event(self, item_id, event_id, data, timestamp):
        return self.tray.Event(item_id, event_id, data, timestamp)

    @dbus.service.method(MENU_IFACE, in_signature="a(isvu)", out_signature="")
    def EventGroup(self, events):
        return self.tray.EventGroup(events)

    @dbus.service.method(MENU_IFACE, in_signature="i", out_signature="b")
    def AboutToShow(self, item_id):
        self.LayoutUpdated(self.tray._revision, 0)
        return False

    @dbus.service.method(MENU_IFACE, in_signature="ai", out_signature="aiai")
    def AboutToShowGroup(self, ids):
        self.LayoutUpdated(self.tray._revision, 0)
        return (dbus.Array([], signature="i"), dbus.Array([], signature="i"))

    @dbus.service.signal(MENU_IFACE, signature="ui")
    def LayoutUpdated(self, revision, parent):
        return None

    @dbus.service.signal(MENU_IFACE, signature="a(ia{sv})a(ias)")
    def ItemsPropertiesUpdated(self, updated, removed):
        return None


class Tray(dbus.service.Object):
    """Small SNI host with a native DBusMenu quick panel."""

    def __init__(
        self,
        app_name: str,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
        on_refresh: Callable[[], None],
        on_polling: Callable[[int], None],
        on_dpi: Callable[[int], None],
        on_motion: Callable[[bool], None],
        on_ripple: Callable[[bool], None],
        on_profile: Callable[[int], None],
        on_style: Callable[[str], None],
        style: str = DEFAULT_TRAY_STYLE,
    ) -> None:
        DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()
        self.app_name = app_name
        self.on_open = on_open
        self.on_quit = on_quit
        self.on_refresh = on_refresh
        self.on_polling = on_polling
        self.on_dpi = on_dpi
        self.on_motion = on_motion
        self.on_ripple = on_ripple
        self.on_profile = on_profile
        self.on_style = on_style
        self.style = style if style in STYLE_KEYS else DEFAULT_TRAY_STYLE
        self.state: MouseState | None = None
        self.connected = False
        self.caps = devices.default_capabilities()
        self.polling_rates = [125, 250, 500, 1000]
        self._message = "Waiting for an ATK/VXE mouse"
        self._icon = render_tray_icon(None, False, self.style)
        self._revision = 1
        self._status = "Passive"

        # StatusNotifier hosts identify the item by this bus name.  Outside
        # Flatpak a PID-suffixed name avoids stale-instance collisions.  Inside
        # Flatpak the PID is always 2, so use the manifest-approved app name;
        # fall back to an app-scoped suffix if an old instance owns it.
        flatpak_id = os.environ.get("FLATPAK_ID")
        if flatpak_id:
            sni_name = f"{flatpak_id}.StatusNotifierItem"
            try:
                self.bus_name = dbus.service.BusName(sni_name, self.bus, do_not_queue=True)
            except dbus.DBusException:
                sni_name = f"{flatpak_id}.StatusNotifierItem.{os.urandom(4).hex()}"
                self.bus_name = dbus.service.BusName(sni_name, self.bus, do_not_queue=True)
        else:
            sni_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
            self.bus_name = dbus.service.BusName(sni_name, self.bus, do_not_queue=True)
        dbus.service.Object.__init__(self, self.bus_name, "/StatusNotifierItem")
        self.menu = TrayMenu(self.bus_name, self)

    # -- lifecycle --------------------------------------------------------
    def start(self) -> bool:
        try:
            watcher = self.bus.get_object(WATCHER, WATCHER_PATH)
            watcher.RegisterStatusNotifierItem(
                self.bus_name.get_name(), dbus_interface=WATCHER
            )
        except dbus.DBusException:
            return False
        return True

    def update(self, state: MouseState | None, connected: bool,
               message: str | None = None) -> None:
        self.state = state
        self.connected = connected and state is not None
        if self.connected and state is not None:
            self.caps = devices.capabilities_for(
                model=devices.MODEL_BY_CIDMID.get((state.cid, state.mid)),
                receiver=devices.receiver_for(state.receiver_pid, state.receiver_name)
                if state.via_receiver and state.receiver_pid else None,
                sensor_name=state.sensor,
                active_polling=state.polling_rate,
                debounce=state.debounce_ms,
                sleep=state.sleep_seconds,
            )
            self.polling_rates = self.caps.polling_rates
            self._message = (
                f"{state.connected_name} — {state.battery if state.battery is not None else '?'}% · "
                f"{state.link_label}" + (", charging" if state.charging else "")
            )
            self._status = "Active"
        else:
            self._message = message or "No ATK/VXE mouse connected"
            self._status = "Passive"
        self._icon = render_tray_icon(state, self.connected, self.style)
        self._revision += 1
        self._emit("NewIcon")
        self._emit("NewToolTip")
        self._emit("NewTitle")
        self.NewStatus(self._status)
        self.menu.LayoutUpdated(self._revision, 0)

    def set_style(self, style: str) -> None:
        if style not in STYLE_KEYS or style == self.style:
            return
        self.style = style
        self._icon = render_tray_icon(self.state, self.connected, style)
        self._revision += 1
        self._emit("NewIcon")
        self.menu.LayoutUpdated(self._revision, 0)

    def _emit(self, signal: str) -> None:
        try:
            getattr(self, signal)()
        except Exception:
            pass

    # -- SNI properties ---------------------------------------------------
    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def Activate(self, x, y):
        self.on_open()

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def SecondaryActivate(self, x, y):
        self.on_refresh()

    @dbus.service.method(SNI_IFACE, in_signature="is", out_signature="")
    def Scroll(self, delta, orientation):
        return None

    @dbus.service.method(SNI_IFACE, in_signature="ii", out_signature="")
    def ContextMenu(self, x, y):
        return None

    @dbus.service.method(SNI_IFACE, in_signature="s", out_signature="")
    def ProvideXdgActivationToken(self, token):
        return None

    @dbus.service.signal(SNI_IFACE, signature="")
    def NewIcon(self):
        return None

    @dbus.service.signal(SNI_IFACE, signature="")
    def NewToolTip(self):
        return None

    @dbus.service.signal(SNI_IFACE, signature="")
    def NewTitle(self):
        return None

    @dbus.service.signal(SNI_IFACE, signature="s")
    def NewStatus(self, status):
        return None

    def _sni_properties(self):
        pixmap = _dbus_pixmap(self._icon)
        tooltip = dbus.Struct(
            (
                dbus.String(self._message),
                pixmap,
                dbus.String(self.app_name),
                dbus.String(self._message),
            ),
            signature="sa(iiay)ss",
        )
        values = {
            "Category": dbus.String("ApplicationStatus"),
            "Id": dbus.String("atk-control"),
            "Title": dbus.String(self.app_name),
            "Status": dbus.String(self._status),
            # Empty IconName makes hosts use the dynamic IconPixmap instead of
            # the static application icon (which has no battery digits).
            "IconName": dbus.String(""),
            "IconPixmap": pixmap,
            "OverlayIconName": dbus.String(""),
            "OverlayIconPixmap": dbus.Array([], signature="(iiay)"),
            "AttentionIconName": dbus.String(""),
            "AttentionIconPixmap": dbus.Array([], signature="(iiay)"),
            "AttentionMovieName": dbus.String(""),
            "ToolTip": tooltip,
            "ItemIsMenu": dbus.Boolean(True),
            "Menu": dbus.ObjectPath("/MenuBar"),
            "IconThemePath": dbus.String(""),
        }
        return dbus.Dictionary(values, signature="sv")

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="ss", out_signature="v")
    def Get(self, interface, prop):
        props = self._sni_properties()
        if prop not in props:
            raise dbus.exceptions.DBusException(
                f"org.freedesktop.DBus.Error.UnknownProperty: {prop}"
            )
        return props[prop]

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        return self._sni_properties()

    @dbus.service.method("org.freedesktop.DBus.Properties",
                         in_signature="ssv", out_signature="")
    def Set(self, interface, prop, value):
        return None

    @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
    def PropertiesChanged(self, interface, changed, invalidated):
        return None

    # -- menu -------------------------------------------------------------
    def _rate(self) -> int:
        return self.state.polling_rate if self.state else 1000

    def _dpi(self) -> int:
        return self.state.dpi if self.state else 1600

    def _items(self) -> list[dict]:
        connected = self.connected and self.state is not None
        state = self.state
        items: list[dict] = [
            {"id": ID_STATUS, "label": self._message, "enabled": False},
            {"id": ID_SEP1, "type": "separator"},
        ]
        children = []
        for hz in self.polling_rates:
            children.append({
                "id": ID_POLLING_BASE + hz,
                "label": f"{hz} Hz",
                "enabled": connected,
                "toggle-type": "checkmark",
                "toggle-state": 1 if connected and self._rate() == hz else 0,
            })
        items.append({
            "id": ID_POLLING,
            "label": "Polling rate",
            "enabled": connected,
            "children": children,
            "children-display": "submenu",
        })
        dpi_children = []
        for value in (400, 800, 1600, 3200, 6400):
            dpi_children.append({
                "id": ID_DPI_BASE + value,
                "label": f"{value} DPI",
                "enabled": connected,
                "toggle-type": "checkmark",
                "toggle-state": 1 if connected and self._dpi() == value else 0,
            })
        items.append({
            "id": ID_DPI,
            "label": "Active DPI",
            "enabled": connected,
            "children": dpi_children,
            "children-display": "submenu",
        })
        if connected and state is not None and state.profile:
            profile_children = []
            for number in range(1, 5):
                profile_children.append({
                    "id": ID_PROFILE_BASE + number,
                    "label": f"Profile {number}",
                    "enabled": True,
                    "toggle-type": "checkmark",
                    "toggle-state": 1 if state.profile == number else 0,
                })
            items.append({
                "id": ID_PROFILE,
                "label": f"Profile {state.profile} of 4",
                "enabled": True,
                "children": profile_children,
                "children-display": "submenu",
            })
        items.append({
            "id": ID_MOTION,
            "label": "Motion Sync",
            "enabled": connected and state is not None and state.motion_sync is not None,
            "toggle-type": "checkmark",
            "toggle-state": 1 if connected and state is not None and state.motion_sync else 0,
        })
        items.append({
            "id": ID_RIPPLE,
            "label": "Ripple control",
            "enabled": connected and state is not None and state.ripple_control is not None,
            "toggle-type": "checkmark",
            "toggle-state": 1 if connected and state is not None and state.ripple_control else 0,
        })
        items.append({"id": ID_SEP2, "type": "separator"})
        items.append({"id": ID_OPEN, "label": "Open ATK Control", "enabled": True})
        items.append({"id": ID_REFRESH, "label": "Refresh", "enabled": True})
        style_children = []
        for key, label in TRAY_STYLES:
            style_children.append({
                "id": ID_STYLE_BASE + STYLE_KEYS.index(key),
                "label": label,
                "enabled": True,
                "toggle-type": "checkmark",
                "toggle-state": 1 if key == self.style else 0,
            })
        items.append({
            "id": ID_STYLE,
            "label": "Tray icon",
            "enabled": True,
            "children": style_children,
            "children-display": "submenu",
        })
        items.append({"id": ID_QUIT, "label": "Quit", "enabled": True})
        return items

    def _by_id(self, item_id: int) -> dict | None:
        for item in self._items():
            if item["id"] == item_id:
                return item
            for child in item.get("children", []):
                if child["id"] == item_id:
                    return child
        return None

    @staticmethod
    def _props(item: dict) -> dict:
        props = {
            "label": item.get("label", ""),
            "enabled": item.get("enabled", True),
            "visible": True,
        }
        if item.get("type") == "separator":
            props["type"] = "separator"
        if item.get("toggle-type"):
            props["toggle-type"] = item["toggle-type"]
            props["toggle-state"] = item.get("toggle-state", 0)
        if item.get("children-display"):
            props["children-display"] = item["children-display"]
        return props

    def _layout_struct(self, item: dict, revision: int):
        children = [
            self._layout_struct(child, revision)
            for child in item.get("children", [])
        ]
        return dbus.Struct(
            (
                dbus.Int32(item["id"]),
                dbus.Dictionary(self._props(item), signature="sv"),
                dbus.Array(children, signature="(ia{sv}av)"),
            ),
            signature="(ia{sv}av)",
        )

    @dbus.service.method(MENU_IFACE, in_signature="iias", out_signature="(ia{sv}av)")
    def GetLayout(self, parent_id, recursion_depth, property_names):
        if parent_id in (0, -1):
            root = {"id": 0, "children": self._items()}
            return self._layout_struct(root, self._revision)
        item = self._by_id(parent_id)
        if item is None:
            return self._layout_struct({"id": 0, "children": []}, self._revision)
        return self._layout_struct(item, self._revision)

    @dbus.service.method(MENU_IFACE, in_signature="aias", out_signature="a(ia{sv})")
    def GetGroupProperties(self, ids, property_names):
        result = []
        for item_id in ids:
            item = self._by_id(item_id)
            if item is not None:
                result.append(dbus.Struct(
                    (dbus.Int32(item_id), dbus.Dictionary(self._props(item), signature="sv")),
                    signature="(ia{sv})",
                ))
        return result

    @dbus.service.method(MENU_IFACE, in_signature="is", out_signature="v")
    def GetProperty(self, item_id, name):
        item = self._by_id(item_id)
        props = self._props(item) if item else {}
        return dbus.Dictionary(props, signature="sv").get(name, "")

    @dbus.service.method(MENU_IFACE, in_signature="isvu", out_signature="")
    def Event(self, item_id, event_id, data, timestamp):
        if event_id != "clicked":
            return
        if item_id == ID_OPEN:
            self.on_open()
        elif item_id == ID_REFRESH:
            self.on_refresh()
        elif item_id == ID_QUIT:
            self.on_quit()
        elif item_id == ID_MOTION and self.state is not None:
            self.on_motion(not bool(self.state.motion_sync))
        elif item_id == ID_RIPPLE and self.state is not None:
            self.on_ripple(not bool(self.state.ripple_control))
        elif item_id - ID_POLLING_BASE in self.polling_rates:
            self.on_polling(item_id - ID_POLLING_BASE)
        elif item_id - ID_DPI_BASE in (400, 800, 1600, 3200, 6400):
            self.on_dpi(item_id - ID_DPI_BASE)
        elif ID_PROFILE_BASE < item_id < ID_PROFILE_BASE + 5:
            self.on_profile(item_id - ID_PROFILE_BASE)
        elif ID_STYLE_BASE <= item_id < ID_STYLE_BASE + len(STYLE_KEYS):
            self.on_style(STYLE_KEYS[item_id - ID_STYLE_BASE])

    @dbus.service.method(MENU_IFACE, in_signature="a(isvu)", out_signature="")
    def EventGroup(self, events):
        for event in events:
            try:
                item_id, event_id, data, timestamp = event
                if event_id == "clicked":
                    self.Event(item_id, event_id, data, timestamp)
            except Exception:
                continue

    @dbus.service.method(MENU_IFACE, in_signature="i", out_signature="b")
    def AboutToShow(self, item_id):
        self.LayoutUpdated(self._revision, 0)
        return False

    @dbus.service.method(MENU_IFACE, in_signature="ai", out_signature="aiai")
    def AboutToShowGroup(self, ids):
        self.LayoutUpdated(self._revision, 0)
        return (dbus.Array([], signature="i"), dbus.Array([], signature="i"))

    @dbus.service.signal(MENU_IFACE, signature="ui")
    def LayoutUpdated(self, revision, parent):
        return None

    @dbus.service.signal(MENU_IFACE, signature="a(ia{sv})a(ias)")
    def ItemsPropertiesUpdated(self, updated, removed):
        return None
