#!/usr/bin/env bash
# Install ATK Control from this checkout.
#
#   sudo ./install.sh             system-wide under /usr
#   ./install.sh --user           per-user under ~/.local
#   DESTDIR=... ./install.sh      package staging (no root required)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="/usr"
USER_INSTALL=0
DESTDIR="${DESTDIR:-}"

usage() {
    cat <<'EOF'
Usage: ./install.sh [--user] [--prefix PATH]

  --user          install into ~/.local (no sudo); the udev rule is not installed
  --prefix PATH   system prefix (default: /usr)
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --user) USER_INSTALL=1; shift ;;
        --prefix) PREFIX="${2:?missing prefix}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
    esac
done

if [ "$USER_INSTALL" -eq 1 ]; then
    if [ -n "$DESTDIR" ]; then
        echo "DESTDIR cannot be combined with --user" >&2
        exit 2
    fi
    PREFIX="$HOME/.local"
    DATA_ROOT="$HOME/.local/share/atk-control"
    INSTALL_DATA_ROOT="$DATA_ROOT"
    BIN_DIR="$HOME/.local/bin"
    ICON_ROOT="$HOME/.local/share/icons/hicolor"
    DESKTOP_DIR="$HOME/.local/share/applications"
    METAINFO_DIR="$HOME/.local/share/metainfo"
    RULE_DIR=""
else
    DATA_ROOT="$DESTDIR$PREFIX/share/atk-control"
    INSTALL_DATA_ROOT="$PREFIX/share/atk-control"
    BIN_DIR="$DESTDIR$PREFIX/bin"
    ICON_ROOT="$DESTDIR$PREFIX/share/icons/hicolor"
    DESKTOP_DIR="$DESTDIR$PREFIX/share/applications"
    METAINFO_DIR="$DESTDIR$PREFIX/share/metainfo"
    RULE_DIR="$DESTDIR$PREFIX/lib/udev/rules.d"
fi

if [ "$USER_INSTALL" -eq 0 ] && [ -z "$DESTDIR" ] && [ "$(id -u)" -ne 0 ]; then
    echo "A system install needs root; use sudo or pass --user." >&2
    exit 1
fi

echo "Installing ATK Control into ${DATA_ROOT}"

install -d "$DATA_ROOT" "$BIN_DIR" "$DESKTOP_DIR" "$METAINFO_DIR"
rm -rf "$DATA_ROOT/atk_control"
cp -r "$ROOT/atk_control" "$DATA_ROOT/atk_control"
find "$DATA_ROOT/atk_control" -type d -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$DATA_ROOT/data"
cp -r "$ROOT/data" "$DATA_ROOT/data"

cat > "$BIN_DIR/atk-control" <<EOF
#!/bin/sh
PYTHONPATH="$INSTALL_DATA_ROOT\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m atk_control "\$@"
EOF
cat > "$BIN_DIR/atkctl" <<EOF
#!/bin/sh
PYTHONPATH="$INSTALL_DATA_ROOT\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m atk_control.cli "\$@"
EOF
chmod 755 "$BIN_DIR/atk-control" "$BIN_DIR/atkctl"

for size in 16 32 48 64 128 256 512; do
    src="$ROOT/data/icons/hicolor/${size}x${size}/apps/atk-control.png"
    if [ -f "$src" ]; then
        install -Dm644 "$src" "$ICON_ROOT/${size}x${size}/apps/atk-control.png"
    fi
done
install -Dm644 "$ROOT/data/icons/hicolor/scalable/apps/atk-control.svg" \
    "$ICON_ROOT/scalable/apps/atk-control.svg"
install -Dm644 "$ROOT/data/applications/io.github.atkcontrol.AtkControl.desktop" \
    "$DESKTOP_DIR/io.github.atkcontrol.AtkControl.desktop"
install -Dm644 "$ROOT/data/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml" \
    "$METAINFO_DIR/io.github.atkcontrol.AtkControl.metainfo.xml"

if [ -n "$RULE_DIR" ]; then
    install -Dm644 "$ROOT/data/udev/71-atk-control.rules" "$RULE_DIR/71-atk-control.rules"
fi

if [ -z "$DESTDIR" ]; then
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t "$(dirname "$ICON_ROOT")" 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    if [ -n "$RULE_DIR" ] && [ "$(id -u)" -eq 0 ] && command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules
        udevadm trigger --subsystem-match=hidraw
    fi
fi

echo
echo "Installed:"
echo "  atk-control"
echo "  atkctl"
if [ "$USER_INSTALL" -eq 1 ]; then
    echo
    echo "The udev rule was not installed for a per-user install. To give your"
    echo "user access to the mouse, run:"
    echo "  sudo install -Dm644 data/udev/71-atk-control.rules /usr/lib/udev/rules.d/71-atk-control.rules"
    echo "  sudo udevadm control --reload-rules && sudo udevadm trigger --subsystem-match=hidraw"
    echo "Then unplug and reconnect the mouse or receiver."
    case ":$PATH:" in
        *":$HOME/.local/bin:"*) ;;
        *) echo; echo "Add ~/.local/bin to PATH to run atk-control and atkctl." ;;
    esac
else
    echo
    echo "Reconnect the mouse or receiver once so the new udev permission applies."
fi
