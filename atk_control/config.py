"""Preferences, app metadata and autostart."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

APP_ID = "io.github.atkcontrol.AtkControl"
APP_NAME = "ATK Control"
VERSION = "0.5.2"
REPO_URL = "https://github.com/NasirA1991/atk-control"
ISSUES_URL = f"{REPO_URL}/issues"
SUPPORT_URL = f"{ISSUES_URL}/new?template=device-report.yml"
HUB_URL = "https://hub.atk.pro/"

TRAY_STYLES = [
    ("hex", "Hex gauge"),
    ("bars", "Signal bars"),
    ("reticle", "Reticle"),
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
    return Path(base) / "atk-control"


def config_path() -> Path:
    return config_dir() / "config.json"


def _valid_bool(value, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _valid_seconds(value, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        return default
    return min(number, maximum)


def sanitize(stored: object) -> dict:
    """Return only known, correctly typed preferences.

    A hand-edited or partially written config must never crash startup or
    smuggle arbitrary values into the refresh loop.
    """
    data = dict(DEFAULTS)
    if not isinstance(stored, dict):
        return data
    data["start_hidden"] = _valid_bool(stored.get("start_hidden"), DEFAULTS["start_hidden"])
    data["low_battery_notifications"] = _valid_bool(
        stored.get("low_battery_notifications"), DEFAULTS["low_battery_notifications"]
    )
    style = stored.get("tray_icon_style")
    if isinstance(style, str) and style in {key for key, _label in TRAY_STYLES}:
        data["tray_icon_style"] = style
    data["live_refresh_seconds"] = _valid_seconds(
        stored.get("live_refresh_seconds"), DEFAULTS["live_refresh_seconds"], 2.0, 120.0
    )
    data["full_refresh_seconds"] = _valid_seconds(
        stored.get("full_refresh_seconds"), DEFAULTS["full_refresh_seconds"], 10.0, 1800.0
    )
    if data["full_refresh_seconds"] < data["live_refresh_seconds"]:
        data["full_refresh_seconds"] = data["live_refresh_seconds"] * 5
    return data


def load() -> dict:
    try:
        stored = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS)
    return sanitize(stored)


def save(data: dict) -> bool:
    """Atomically persist only validated preference keys.

    Returns False when the preferences could not be written. Callers must not
    claim a preference was saved when this returns False.
    """
    payload = sanitize(data)
    target = config_path()
    temporary: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=".config-", suffix=".json", dir=target.parent, text=True
        )
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
        try:
            directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            pass
        return True
    except OSError:
        return False
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def autostart_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "autostart" / "atk-control.desktop"


AUTOSTART_CONTENT = """[Desktop Entry]
Type=Application
Name=ATK Control
Comment=Configure ATK/VXE mice and show battery in the tray
Exec=atk-control --tray
Icon=atk-control
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
    env = os.environ.get("ATK_CONTROL_DATA")
    if env:
        return Path(env)
    local = Path(__file__).resolve().parent.parent / "data"
    if local.exists():
        return local
    return Path("/usr/share/atk-control")
