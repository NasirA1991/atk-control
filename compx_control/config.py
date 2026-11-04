"""Preferences, app metadata and autostart."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_ID = "io.github.compxcontrol.CompxControl"
APP_NAME = "Compx Control"
VERSION = "0.1.1"
REPO_URL = "https://github.com/NasirA1991/compx-control"
HUB_URL = "https://hub.atk.pro/"

TRAY_STYLES = [
    ("hex", "Hex gauge"),
    ("bars", "Signal bars"),
    ("bolt", "Bolt"),
]
DEFAULT_TRAY_STYLE = "hex"

DEFAULTS = {
    "start_hidden": False,
    "low_battery_notifications": True,
    "tray_icon_style": DEFAULT_TRAY_STYLE,
    "live_refresh_seconds": 3.0,
    "full_refresh_seconds": 30.0,
}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "compx-control"


def config_path() -> Path:
    return config_dir() / "config.json"


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        stored = json.loads(config_path().read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            data.update(stored)
    except (OSError, ValueError):
        pass
    return data


def save(data: dict) -> None:
    try:
        config_dir().mkdir(parents=True, exist_ok=True)
        config_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def autostart_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "autostart" / "compx-control.desktop"


AUTOSTART_CONTENT = """[Desktop Entry]
Type=Application
Name=Compx Control
Comment=Configure COMPX mice and show battery in the tray
Exec=compx-control --tray
Icon=compx-control
Terminal=false
Categories=Settings;HardwareSettings;
X-GNOME-Autostart-enabled=true
"""


def is_autostart_enabled() -> bool:
    return autostart_path().exists()


def set_autostart(enabled: bool) -> bool:
    path = autostart_path()
    try:
        if enabled:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(AUTOSTART_CONTENT, encoding="utf-8")
        elif path.exists():
            path.unlink()
        return True
    except OSError:
        return False


def data_dir() -> Path:
    env = os.environ.get("COMPX_CONTROL_DATA")
    if env:
        return Path(env)
    local = Path(__file__).resolve().parent.parent / "data"
    if local.exists():
        return local
    return Path("/usr/share/compx-control")
