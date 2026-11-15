#!/usr/bin/env bash
# Install ATK Control from this checkout.
#
#   sudo ./install.sh             system-wide under /usr
#   ./install.sh --user           per-user under ~/.local
#   sudo ./install.sh --udev-only install only the host udev rule in /etc
#   DESTDIR=... ./install.sh      package staging (no root required)
set -euo pipefail
umask 022

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="/usr"
USER_INSTALL=0
UDEV_ONLY=0
SKIP_DEPS=0
DESTDIR="${DESTDIR:-}"
RULE_NAME="71-atk-control.rules"
RULE_SOURCE="$ROOT/data/udev/$RULE_NAME"

usage() {
    cat <<'EOF'
Usage: ./install.sh [OPTIONS]

Install ATK Control, or install only the host udev rule.

Options:
  --user          install into ~/.local (no sudo); the udev rule is not installed
  --prefix PATH   system prefix (default: /usr)
  --udev-only     install only /etc/udev/rules.d/71-atk-control.rules (requires root)
  --skip-deps     skip the Python/GTK dependency check
  -h, --help      show this help

A system install needs root. DESTDIR is supported for package staging and skips
the dependency check. --udev-only is for Flatpak and AppImage users.
EOF
}

die() {
    echo "install.sh: $*" >&2
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --user) USER_INSTALL=1; shift ;;
        --prefix)
            [ $# -ge 2 ] || die "--prefix needs a path"
            PREFIX="$2"
            shift 2
            ;;
        --udev-only) UDEV_ONLY=1; shift ;;
        --skip-deps) SKIP_DEPS=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

if [ ! -f "$RULE_SOURCE" ]; then
    die "missing udev rule: $RULE_SOURCE"
fi

if [ -z "$PREFIX" ]; then
    die "--prefix cannot be empty"
fi

if [ "$UDEV_ONLY" -eq 1 ]; then
    if [ "$USER_INSTALL" -eq 1 ]; then
        die "--udev-only cannot be combined with --user"
    fi
    if [ -n "$DESTDIR" ]; then
        die "--udev-only cannot be used with DESTDIR"
    fi
    if [ "$(id -u)" -ne 0 ]; then
        die "installing the udev rule needs root; run: sudo ./install.sh --udev-only"
    fi
    command -v udevadm >/dev/null 2>&1 || die "udevadm is required for --udev-only"

    install -Dm644 "$RULE_SOURCE" "/etc/udev/rules.d/$RULE_NAME"
    udevadm control --reload-rules
    udevadm trigger --subsystem-match=hidraw
    echo "Installed /etc/udev/rules.d/$RULE_NAME"
    echo "Replug the mouse or receiver, then open ATK Control again."
    exit 0
fi

if [ "$USER_INSTALL" -eq 0 ] && [ -z "$DESTDIR" ]; then
    case "$PREFIX" in
        /usr|/usr/local) ;;
        *)
            echo "Warning: udev does not read $PREFIX/lib/udev/rules.d on a normal system." >&2
            echo "Install the host rule once with: sudo ./install.sh --udev-only" >&2
            ;;
    esac
fi

if [ "$USER_INSTALL" -eq 1 ] && [ -n "$DESTDIR" ]; then
    die "DESTDIR cannot be combined with --user"
fi

if [ "$USER_INSTALL" -eq 1 ]; then
    PREFIX="$HOME/.local"
    DATA_ROOT="$HOME/.local/share/atk-control"
    INSTALL_DATA_ROOT="$DATA_ROOT"
    BIN_DIR="$HOME/.local/bin"
    LICENSE_DIR="$HOME/.local/share/licenses/atk-control"
    ICON_ROOT="$HOME/.local/share/icons/hicolor"
    DESKTOP_DIR="$HOME/.local/share/applications"
    METAINFO_DIR="$HOME/.local/share/metainfo"
    RULE_DIR=""
else
    DATA_ROOT="$DESTDIR$PREFIX/share/atk-control"
    INSTALL_DATA_ROOT="$PREFIX/share/atk-control"
    BIN_DIR="$DESTDIR$PREFIX/bin"
    LICENSE_DIR="$DESTDIR$PREFIX/share/licenses/atk-control"
    ICON_ROOT="$DESTDIR$PREFIX/share/icons/hicolor"
    DESKTOP_DIR="$DESTDIR$PREFIX/share/applications"
    METAINFO_DIR="$DESTDIR$PREFIX/share/metainfo"
    RULE_DIR="$DESTDIR$PREFIX/lib/udev/rules.d"
fi

if [ "$USER_INSTALL" -eq 0 ] && [ -z "$DESTDIR" ] && [ "$(id -u)" -ne 0 ]; then
    die "a system install needs root; use sudo or pass --user"
fi

# Check dependencies before copying anything. Packagers set DESTDIR and own the
# dependency graph themselves, so staging skips this check.
if [ "$SKIP_DEPS" -eq 0 ] && [ -z "$DESTDIR" ]; then
    deps_ok=1
    deps_reason=""
    if ! command -v python3 >/dev/null 2>&1; then
        deps_ok=0
        deps_reason="python3 is missing"
    elif ! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); from gi.repository import Gtk, Adw' >/dev/null 2>&1; then
        deps_ok=0
        deps_reason="PyGObject with GTK 4.0 or libadwaita (Adw 1) is missing"
    elif ! python3 -c 'import cairo, dbus' >/dev/null 2>&1; then
        deps_ok=0
        deps_reason="pycairo or dbus-python is missing"
    fi

    if [ "$deps_ok" -eq 0 ]; then
        os_id=""
        os_like=""
        if [ -r /etc/os-release ]; then
            # shellcheck disable=SC1091
            . /etc/os-release
            os_id="${ID:-}"
            os_like="${ID_LIKE:-}"
        fi
        case " $os_id $os_like " in
            *" arch "*|*" cachyos "*|*" endeavouros "*)
                deps_command="pacman -S --needed python python-gobject gtk4 libadwaita python-cairo python-dbus"
                ;;
            *" debian "*|*" ubuntu "*)
                deps_command="apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-dbus"
                ;;
            *" fedora "*)
                deps_command="dnf install python3 python3-gobject gtk4 libadwaita python3-cairo python3-dbus"
                ;;
            *" opensuse"*|*" suse"*)
                deps_command="zypper install python3 python3-gobject python3-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-dbus-python"
                ;;
            *)
                deps_command="python3, PyGObject with Gtk 4.0 and Adw 1, pycairo and dbus-python"
                ;;
        esac
        echo "Missing runtime dependencies for ATK Control: $deps_reason." >&2
        echo "Install them with:" >&2
        echo "  $deps_command" >&2
        exit 1
    fi
fi

echo "Installing ATK Control into ${DATA_ROOT}"

install -d "$DATA_ROOT" "$BIN_DIR" "$DESKTOP_DIR" "$METAINFO_DIR"
rm -rf "$DATA_ROOT/atk_control"
cp -r "$ROOT/atk_control" "$DATA_ROOT/atk_control"
find "$DATA_ROOT/atk_control" -type d -name __pycache__ -prune -exec rm -rf {} +
rm -rf "$DATA_ROOT/data"
cp -r "$ROOT/data" "$DATA_ROOT/data"
chmod -R u=rwX,go=rX "$DATA_ROOT"

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
        install -Dm644 "$src" "$ICON_ROOT/${size}x${size}/apps/io.github.atkcontrol.AtkControl.png"
    fi
done
install -Dm644 "$ROOT/data/icons/hicolor/scalable/apps/atk-control.svg" \
    "$ICON_ROOT/scalable/apps/atk-control.svg"
install -Dm644 "$ROOT/data/icons/hicolor/scalable/apps/atk-control.svg" \
    "$ICON_ROOT/scalable/apps/io.github.atkcontrol.AtkControl.svg"
install -Dm644 "$ROOT/data/applications/io.github.atkcontrol.AtkControl.desktop" \
    "$DESKTOP_DIR/io.github.atkcontrol.AtkControl.desktop"
install -Dm644 "$ROOT/data/metainfo/io.github.atkcontrol.AtkControl.metainfo.xml" \
    "$METAINFO_DIR/io.github.atkcontrol.AtkControl.metainfo.xml"
install -Dm644 "$ROOT/LICENSE" "$LICENSE_DIR/LICENSE"

if [ -n "$RULE_DIR" ]; then
    install -Dm644 "$RULE_SOURCE" "$RULE_DIR/$RULE_NAME"
fi

if [ -z "$DESTDIR" ]; then
    if [ "$USER_INSTALL" -eq 0 ] && command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f "$ICON_ROOT" 2>/dev/null || true
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
    echo "sudo ./install.sh --udev-only is needed once for device access."
else
    echo
    echo "Reconnect the mouse or receiver once so the new udev permission applies."
fi
