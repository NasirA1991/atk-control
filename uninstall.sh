#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="/usr"
USER_INSTALL=0
if [ "${1:-}" = "--user" ]; then
    USER_INSTALL=1
    PREFIX="$HOME/.local"
fi

if [ "$USER_INSTALL" -eq 0 ] && [ "$(id -u)" -ne 0 ]; then
    echo "A system uninstall needs root; use sudo or pass --user." >&2
    exit 1
fi

DATA_ROOT="$PREFIX/share/atk-control"
LICENSE_ROOT="$PREFIX/share/licenses/atk-control"
rm -rf "$DATA_ROOT" "$LICENSE_ROOT"
rm -f "$PREFIX/bin/atk-control" "$PREFIX/bin/atkctl"
rm -f "$PREFIX/share/applications/io.github.atkcontrol.AtkControl.desktop"
rm -f "$PREFIX/share/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml"
for size in 16 32 48 64 128 256 512; do
    rm -f "$PREFIX/share/icons/hicolor/${size}x${size}/apps/atk-control.png"
    rm -f "$PREFIX/share/icons/hicolor/${size}x${size}/apps/io.github.atkcontrol.AtkControl.png"
done
rm -f "$PREFIX/share/icons/hicolor/scalable/apps/atk-control.svg"
rm -f "$PREFIX/share/icons/hicolor/scalable/apps/io.github.atkcontrol.AtkControl.svg"

# Autostart is not a preference worth preserving: it launches a binary that is
# no longer installed. Preferences under ~/.config/atk-control are kept.
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    if [ -n "$user_home" ]; then
        CONFIG_HOME="$user_home/.config"
    fi
fi
rm -f "$CONFIG_HOME/autostart/atk-control.desktop"

if [ "$USER_INSTALL" -eq 0 ]; then
    rm -f "$PREFIX/lib/udev/rules.d/71-atk-control.rules"
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules || true
    fi
fi
echo "ATK Control removed. Autostart was cleaned up; saved preferences were left in ~/.config/atk-control."
