#!/usr/bin/env bash
# Remove ATK Control installed by install.sh.
set -euo pipefail
umask 022

PREFIX="/usr"
USER_INSTALL=0
UDEV_ONLY=0
DESTDIR="${DESTDIR:-}"
RULE_NAME="71-atk-control.rules"
ETC_RULE="/etc/udev/rules.d/$RULE_NAME"

usage() {
    cat <<'EOF'
Usage: ./uninstall.sh [OPTIONS]

Remove ATK Control files and the udev rules installed by install.sh.

Options:
  --user          remove a per-user install under ~/.local
  --prefix PATH   system prefix (default: /usr)
  --udev-only     remove only /etc/udev/rules.d/71-atk-control.rules (requires root)
  -h, --help      show this help

A system uninstall needs root. A per-user uninstall removes the user files; if
the host udev rule is present, run "sudo ./uninstall.sh --udev-only" afterwards.
EOF
}

die() {
    echo "uninstall.sh: $*" >&2
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
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1" ;;
    esac
done

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
        die "removing the host udev rule needs root; run: sudo ./uninstall.sh --udev-only"
    fi
    rm -f "$ETC_RULE"
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules || true
        udevadm trigger --subsystem-match=hidraw || true
    fi
    echo "Removed /etc/udev/rules.d/$RULE_NAME"
    exit 0
fi

if [ "$USER_INSTALL" -eq 1 ] && [ -n "$DESTDIR" ]; then
    die "DESTDIR cannot be combined with --user"
fi

if [ "$USER_INSTALL" -eq 1 ]; then
    PREFIX="$HOME/.local"
elif [ -z "$DESTDIR" ] && [ "$(id -u)" -ne 0 ]; then
    die "a system uninstall needs root; use sudo or pass --user"
fi

DATA_ROOT="$DESTDIR$PREFIX/share/atk-control"
LICENSE_ROOT="$DESTDIR$PREFIX/share/licenses/atk-control"
BIN_DIR="$DESTDIR$PREFIX/bin"
DESKTOP_DIR="$DESTDIR$PREFIX/share/applications"
METAINFO_DIR="$DESTDIR$PREFIX/share/metainfo"
ICON_ROOT="$DESTDIR$PREFIX/share/icons/hicolor"
RULE_DIR="$DESTDIR$PREFIX/lib/udev/rules.d"

rm -rf "$DATA_ROOT" "$LICENSE_ROOT"
rm -f "$BIN_DIR/atk-control" "$BIN_DIR/atkctl"
rm -f "$DESKTOP_DIR/io.github.atkcontrol.AtkControl.desktop"
rm -f "$METAINFO_DIR/io.github.atkcontrol.AtkControl.metainfo.xml"
for size in 16 32 48 64 128 256 512; do
    rm -f "$ICON_ROOT/${size}x${size}/apps/atk-control.png"
    rm -f "$ICON_ROOT/${size}x${size}/apps/io.github.atkcontrol.AtkControl.png"
done
rm -f "$ICON_ROOT/scalable/apps/atk-control.svg"
rm -f "$ICON_ROOT/scalable/apps/io.github.atkcontrol.AtkControl.svg"
rm -f "$RULE_DIR/$RULE_NAME"

# Autostart is not a preference worth preserving: it launches a binary that is
# no longer installed. Preferences under ~/.config/atk-control are kept.
# A staged uninstall must not touch the packager's real home directory.
autostart_cleaned=0
if [ -z "$DESTDIR" ]; then
    CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
    if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
        user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
        if [ -n "$user_home" ]; then
            CONFIG_HOME="$user_home/.config"
        fi
    fi
    rm -f "$CONFIG_HOME/autostart/atk-control.desktop"
    autostart_cleaned=1
fi

# The host rule is outside the prefix and may have been installed separately.
# A --user uninstall never touches it, even when run as root.
host_rule_left=0
if [ -z "$DESTDIR" ] && [ -e "$ETC_RULE" ]; then
    if [ "$USER_INSTALL" -eq 1 ]; then
        host_rule_left=1
    elif [ "$(id -u)" -eq 0 ]; then
        rm -f "$ETC_RULE"
    else
        host_rule_left=1
    fi
fi

# Remove only directories that are now empty; never delete a shared parent
# with other packages or user files in it.
remove_empty_dir() {
    if [ -d "$1" ]; then
        rmdir "$1" 2>/dev/null || true
    fi
}
if [ "$USER_INSTALL" -eq 1 ] || [ -n "$DESTDIR" ]; then
    for size in 16 32 48 64 128 256 512; do
        remove_empty_dir "$ICON_ROOT/${size}x${size}/apps"
        remove_empty_dir "$ICON_ROOT/${size}x${size}"
    done
    remove_empty_dir "$ICON_ROOT/scalable/apps"
    remove_empty_dir "$ICON_ROOT/scalable"
    remove_empty_dir "$ICON_ROOT"
    remove_empty_dir "$(dirname "$ICON_ROOT")"
    remove_empty_dir "$BIN_DIR"
    remove_empty_dir "$DESKTOP_DIR"
    remove_empty_dir "$METAINFO_DIR"
    remove_empty_dir "$RULE_DIR"
    remove_empty_dir "$(dirname "$RULE_DIR")"
    remove_empty_dir "$LICENSE_ROOT"
    remove_empty_dir "$(dirname "$LICENSE_ROOT")"
    if [ -n "$DESTDIR" ]; then
        remove_empty_dir "$DESTDIR$PREFIX/lib"
        remove_empty_dir "$DESTDIR$PREFIX/share"
        remove_empty_dir "$DESTDIR$PREFIX"
        # For a staged non-default prefix, remove the package directory created
        # above it (for example /opt/atk -> /opt), but never DESTDIR itself.
        case "$PREFIX" in
            */*/*)
                remove_empty_dir "$(dirname "$DESTDIR$PREFIX")"
                ;;
        esac
    fi
fi

if [ "$(id -u)" -eq 0 ] && command -v udevadm >/dev/null 2>&1; then
    udevadm control --reload-rules || true
    udevadm trigger --subsystem-match=hidraw || true
fi

if [ "$autostart_cleaned" -eq 1 ]; then
    echo "ATK Control removed. Autostart was cleaned up; saved preferences were left in ~/.config/atk-control."
else
    echo "ATK Control removed. Autostart was not touched; saved preferences were left in ~/.config/atk-control."
fi
if [ "$host_rule_left" -eq 1 ]; then
    echo "sudo ./uninstall.sh --udev-only is needed to remove the host udev rule."
fi
