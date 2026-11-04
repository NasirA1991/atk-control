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
rm -rf "$DATA_ROOT"
rm -f "$PREFIX/bin/atk-control" "$PREFIX/bin/atkctl"
rm -f "$PREFIX/share/applications/io.github.atkcontrol.AtkControl.desktop"
rm -f "$PREFIX/share/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml"
for size in 16 32 48 64 128 256 512; do
    rm -f "$PREFIX/share/icons/hicolor/${size}x${size}/apps/atk-control.png"
done
rm -f "$PREFIX/share/icons/hicolor/scalable/apps/atk-control.svg"
if [ "$USER_INSTALL" -eq 0 ]; then
    rm -f "$PREFIX/lib/udev/rules.d/71-atk-control.rules"
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules || true
    fi
fi
echo "ATK Control removed. Your saved preferences were left in ~/.config/atk-control."
