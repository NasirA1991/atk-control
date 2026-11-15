#!/usr/bin/env bash
# One-line installer for ATK Control. Served from main; downloads a release.
set -euo pipefail
umask 022

REPO="NasirA1991/atk-control"
MIN_VERSION="0.9.6"
APP_ID="io.github.atkcontrol.AtkControl"
AUR_PACKAGE="atk-control"
BASE_URL="${GET_SH_BASE_URL:-}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/atk-control"
STATE_FILE="$STATE_DIR/get-sh.state"
METHOD=""
VERSION=""
USER_INSTALL=0
ASSUME_YES=0
DRY_RUN=0
UNINSTALL=0
TMP_DIR=""
OS_ID=""
OS_LIKE=""
DISTRO=""
PREFIX="/usr"

usage() {
    cat <<'EOF'
ATK Control one-line installer (get.sh)

Usage:
  curl -fsSL https://raw.githubusercontent.com/NasirA1991/atk-control/main/get.sh | bash
  curl -fsSL https://raw.githubusercontent.com/NasirA1991/atk-control/main/get.sh | bash -s -- --user --yes

Options:
  --user            Install for the current user instead of system-wide.
  --method METHOD   aur, flatpak or tarball. Default: auto.
  --version VERSION Release to install, without the leading v (default: latest).
  --yes             Do not ask for confirmation. Requires a non-interactive plan.
  --dry-run         Print the plan and exit without downloading or changing files.
  --uninstall       Undo the last get.sh install recorded in the state file.
  -h, --help        Show this help.

The AUR method is offered on Arch-based systems first. On other systems get.sh
prefers Flatpak when installed, then the release tarball. The script never runs
sudo for the whole installer: it calls sudo only for install.sh, the udev rule,
or the package-manager commands shown in the plan.
EOF
}

die() {
    echo "get.sh: $*" >&2
    exit 1
}

log() {
    echo "get.sh: $*" >&2
}

load_os_release() {
    if [ ! -r /etc/os-release ]; then
        return 0
    fi
    OS_ID="$(grep -E '^ID=' /etc/os-release | head -n 1 | cut -d= -f2- | tr -d '"' || true)"
    OS_LIKE="$(grep -E '^ID_LIKE=' /etc/os-release | head -n 1 | cut -d= -f2- | tr -d '"' || true)"
    case " $OS_ID $OS_LIKE " in
        *arch*|*cachyos*|*endeavouros*|*manjaro*) DISTRO="arch" ;;
        *debian*|*ubuntu*|*linuxmint*|*pop*) DISTRO="debian" ;;
        *fedora*|*rhel*|*centos*) DISTRO="fedora" ;;
        *suse*) DISTRO="suse" ;;
        *) DISTRO="other" ;;
    esac
}

package_hint() {
    case "$DISTRO" in
        arch) echo "sudo pacman -S --needed curl tar coreutils" ;;
        debian) echo "sudo apt update && sudo apt install curl tar coreutils" ;;
        fedora) echo "sudo dnf install curl tar coreutils" ;;
        suse) echo "sudo zypper install curl tar coreutils" ;;
        *) echo "Install curl (or wget), tar and coreutils with your package manager." ;;
    esac
}

dependency_hint() {
    case "$DISTRO" in
        arch) echo "sudo pacman -S --needed python python-gobject gtk4 libadwaita python-cairo python-dbus" ;;
        debian) echo "sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-dbus" ;;
        fedora) echo "sudo dnf install python3 python3-gobject gtk4 libadwaita python3-cairo python3-dbus" ;;
        suse) echo "sudo zypper install python3 python3-gobject python3-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-dbus-python" ;;
        *) echo "Install Python 3, PyGObject, GTK4, libadwaita, pycairo and dbus-python." ;;
    esac
}

have() {
    command -v "$1" >/dev/null 2>&1
}

need_sudo() {
    have sudo || die "sudo is required for this method; install sudo or use --user --method tarball."
}

make_temp() {
    if [ -z "$TMP_DIR" ]; then
        TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/atk-control-get.XXXXXX")"
        trap 'rm -rf "$TMP_DIR"' EXIT
    fi
}

confirm() {
    if [ "$ASSUME_YES" -eq 1 ]; then
        return 0
    fi
    if [ ! -r /dev/tty ]; then
        die "no terminal for confirmation; rerun with --yes"
    fi
    printf '%s [y/N] ' "$1" > /dev/tty
    local answer=""
    read -r answer < /dev/tty || true
    case "$answer" in
        y|Y|yes|YES) return 0 ;;
        *) die "aborted" ;;
    esac
}

version_ge() {
    [ "$(printf '%s
%s
' "$1" "$2" | sort -V | head -n 1)" = "$2" ]
}

normalize_version() {
    local raw="$1"
    raw="${raw#v}"
    raw="${raw#V}"
    if ! printf '%s\n' "$raw" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
        die "invalid version '$1' (expected MAJOR.MINOR.PATCH)"
    fi
    VERSION="$raw"
}

latest_version() {
    if [ -n "$VERSION" ]; then
        return 0
    fi
    if [ -n "$BASE_URL" ]; then
        die "--version is required when GET_SH_BASE_URL is set"
    fi
    local json=""
    if have curl; then
        json="$(curl -fsSL --retry 2 "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || {
            die "could not read the latest release from GitHub; check the network or pass --version"
        }
    elif have wget; then
        json="$(wget -qO- "https://api.github.com/repos/$REPO/releases/latest" 2>/dev/null)" || {
            die "could not read the latest release from GitHub; check the network or pass --version"
        }
    else
        die "curl or wget is required"
    fi
    local tag=""
    tag="$(printf '%s\n' "$json" | grep -o '"tag_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n 1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
    if [ -z "$tag" ]; then
        if printf '%s' "$json" | grep -qi 'rate limit'; then
            die "GitHub API rate limit reached; pass --version with a release tag"
        fi
        die "could not determine the latest release; pass --version"
    fi
    normalize_version "$tag"
}

release_base() {
    if [ -n "$BASE_URL" ]; then
        printf '%s' "${BASE_URL%/}"
    else
        printf 'https://github.com/%s/releases/download/v%s' "$REPO" "$VERSION"
    fi
}

download() {
    local url="$1" out="$2"
    if have curl; then
        curl -fL --retry 2 --connect-timeout 20 -o "$out" "$url"
    elif have wget; then
        wget -q -O "$out" "$url"
    else
        die "curl or wget is required"
    fi
}

verify_asset() {
    local name="$1" line=""
    [ -f "$TMP_DIR/$name" ] || die "download did not produce $name"
    [ -f "$TMP_DIR/SHA256SUMS" ] || die "SHA256SUMS is missing"
    line="$(grep -E "^[0-9a-fA-F]{64}  $name$" "$TMP_DIR/SHA256SUMS" | head -n 1 || true)"
    if [ -z "$line" ]; then
        die "SHA256SUMS has no entry for $name"
    fi
    if ! (cd "$TMP_DIR" && printf '%s\n' "$line" | sha256sum -c -); then
        die "checksum verification failed for $name"
    fi
}

fetch_assets() {
    local base
    base="$(release_base)"
    mkdir -p "$TMP_DIR"
    log "downloading SHA256SUMS for $VERSION"
    download "$base/SHA256SUMS" "$TMP_DIR/SHA256SUMS"
    local name
    for name in "$@"; do
        log "downloading $name"
        download "$base/$name" "$TMP_DIR/$name"
        verify_asset "$name"
    done
}

extract_source() {
    local archive="$TMP_DIR/atk-control-$VERSION.tar.gz"
    tar -xzf "$archive" -C "$TMP_DIR"
    printf '%s/atk-control-%s' "$TMP_DIR" "$VERSION"
}

require_tools() {
    local missing=0
    if ! have tar; then log "missing tar."; missing=1; fi
    if ! have sha256sum; then log "missing sha256sum."; missing=1; fi
    if ! have curl && ! have wget; then log "missing curl or wget."; missing=1; fi
    if [ "$missing" -eq 1 ]; then
        log "install the missing tools with:"
        package_hint >&2
        exit 1
    fi
}

detect_method() {
    if [ -n "$METHOD" ]; then
        case "$METHOD" in
            aur|flatpak|tarball) ;;
            *) die "unknown method '$METHOD' (use aur, flatpak or tarball)" ;;
        esac
    else
        if [ "$DISTRO" = "arch" ]; then
            if have paru || have yay || { have git && have makepkg; }; then
                METHOD="aur"
            elif have flatpak; then
                METHOD="flatpak"
            else
                METHOD="tarball"
            fi
        elif have flatpak; then
            METHOD="flatpak"
        else
            METHOD="tarball"
        fi
    fi
}

print_plan() {
    cat <<EOF
ATK Control installer
  version : $VERSION
  method  : $METHOD
  scope   : $([ "$USER_INSTALL" -eq 1 ] && echo "user ($HOME/.local)" || echo "system ($PREFIX)")
  source  : $(release_base)
EOF
}

record_state() {
    local scope="system"
    [ "$USER_INSTALL" -eq 1 ] && scope="user"
    mkdir -p "$STATE_DIR"
    chmod 700 "$STATE_DIR"
    cat > "$STATE_FILE" <<EOF
METHOD=$METHOD
VERSION=$VERSION
SCOPE=$scope
DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF
    chmod 600 "$STATE_FILE"
}

state_value() {
    local key="$1"
    [ -f "$STATE_FILE" ] || return 0
    grep -E "^$key=" "$STATE_FILE" | head -n 1 | cut -d= -f2- || true
}

clear_state() {
    rm -f "$STATE_FILE"
}

install_aur() {
    if [ "$DISTRO" != "arch" ]; then
        die "--method aur is only supported on Arch-based systems"
    fi
    local helper=""
    if have paru; then helper="paru"; elif have yay; then helper="yay"; fi
    if [ -n "$helper" ]; then
        log "installing $AUR_PACKAGE with $helper"
        "$helper" -S --needed "$AUR_PACKAGE"
    elif have git && have makepkg; then
        log "installing $AUR_PACKAGE from the AUR with makepkg"
        git clone "https://aur.archlinux.org/$AUR_PACKAGE.git" "$TMP_DIR/aur-$AUR_PACKAGE"
        (cd "$TMP_DIR/aur-$AUR_PACKAGE" && makepkg -si)
    else
        die "neither paru/yay nor git+base-devel is available; install an AUR helper"
    fi
}

install_flatpak() {
    have flatpak || die "flatpak is not installed; choose --method tarball"
    fetch_assets "atk-control-$VERSION-x86_64.flatpak" "atk-control-$VERSION.tar.gz"
    if ! flatpak info --user org.gnome.Platform//50 >/dev/null 2>&1; then
        log "installing the GNOME runtime"
        flatpak remote-add --if-not-exists --user flathub https://flathub.org/repo/flathub.flatpakrepo
        flatpak install --user -y flathub org.gnome.Platform//50
    fi
    log "installing the Flatpak"
    flatpak install --user -y "$TMP_DIR/atk-control-$VERSION-x86_64.flatpak"
    need_sudo
    local src
    src="$(extract_source)"
    log "installing the host udev rule"
    sudo "$src/install.sh" --udev-only
}

run_source_install() {
    local src="$1"
    shift
    local output="" status=0
    set +e
    output="$("$src/install.sh" "$@" 2>&1)"
    status=$?
    set -e
    if [ "$status" -ne 0 ]; then
        printf '%s\n' "$output" >&2
        if printf '%s' "$output" | grep -Eqi 'missing|not installed|not found|required'; then
            log "the installer reported a dependency problem"
            log "install the missing packages with:"
            dependency_hint >&2
            if confirm "Open the dependency command now?"; then
                case "$DISTRO" in
                    arch) sudo pacman -S --needed python python-gobject gtk4 libadwaita python-cairo python-dbus ;;
                    debian) sudo apt install python3 python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-dbus ;;
                    fedora) sudo dnf install python3 python3-gobject gtk4 libadwaita python3-cairo python3-dbus ;;
                    suse) sudo zypper install python3 python3-gobject python3-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-dbus-python ;;
                    *) log "install the dependencies for your distribution, then rerun get.sh"; return 1 ;;
                esac
                set +e
                output="$("$src/install.sh" "$@" 2>&1)"
                status=$?
                set -e
                printf '%s\n' "$output" >&2
            fi
        fi
        return "$status"
    fi
    printf '%s\n' "$output"
}

install_tarball() {
    fetch_assets "atk-control-$VERSION.tar.gz"
    local src
    src="$(extract_source)"
    if ! "$src/install.sh" --help 2>/dev/null | grep -q -- '--udev-only'; then
        die "release v$VERSION is older than the installer requires; use --method aur or wait for the next release"
    fi
    if [ "$USER_INSTALL" -eq 1 ]; then
        log "installing for the current user"
        run_source_install "$src" --user
        need_sudo
        log "installing the host udev rule"
        sudo "$src/install.sh" --udev-only
    else
        need_sudo
        log "installing system-wide"
        run_source_install "$src"
    fi
}

uninstall_recorded() {
    if [ ! -f "$STATE_FILE" ]; then
        log "no get.sh state file at $STATE_FILE"
        cat >&2 <<EOF
Remove the installation with the method you used:
  AUR:      sudo pacman -Rns $AUR_PACKAGE
  Flatpak:  flatpak uninstall --user $APP_ID
  Tarball:  extract the matching release and run ./uninstall.sh or sudo ./uninstall.sh
EOF
        return 0
    fi
    METHOD="$(state_value METHOD)"
    VERSION="$(state_value VERSION)"
    local scope
    scope="$(state_value SCOPE)"
    [ -n "$VERSION" ] || die "state file has no VERSION"
    if [ "$METHOD" = "tarball" ]; then
        fetch_assets "atk-control-$VERSION.tar.gz"
        local src
        src="$(extract_source)"
        if [ "$scope" = "user" ]; then
            log "removing the per-user install"
            "$src/uninstall.sh" --user
            need_sudo
            sudo "$src/uninstall.sh" --udev-only
        else
            need_sudo
            sudo "$src/uninstall.sh"
        fi
    elif [ "$METHOD" = "flatpak" ]; then
        flatpak uninstall --user -y "$APP_ID"
        need_sudo
        sudo rm -f /etc/udev/rules.d/71-atk-control.rules
        sudo udevadm control --reload-rules
        sudo udevadm trigger --subsystem-match=hidraw
    elif [ "$METHOD" = "aur" ]; then
        need_sudo
        sudo pacman -Rns "$AUR_PACKAGE"
    else
        die "state file has an unknown METHOD '$METHOD'"
    fi
    clear_state
}

main() {
    local arg
    while [ "$#" -gt 0 ]; do
        arg="$1"
        case "$arg" in
            --user) USER_INSTALL=1; shift ;;
            --method) [ "$#" -ge 2 ] || die "--method needs a value"; METHOD="$2"; shift 2 ;;
            --version) [ "$#" -ge 2 ] || die "--version needs a value"; normalize_version "$2"; shift 2 ;;
            --yes) ASSUME_YES=1; shift ;;
            --dry-run) DRY_RUN=1; shift ;;
            --uninstall) UNINSTALL=1; shift ;;
            -h|--help) usage; exit 0 ;;
            *) die "unknown option '$arg' (see --help)" ;;
        esac
    done

    if [ "$(id -u)" -eq 0 ]; then
        die "Run as your normal user; get.sh uses sudo only for the steps that need it."
    fi

    load_os_release
    if [ "$USER_INSTALL" -eq 1 ]; then
        PREFIX="$HOME/.local"
    fi

    if [ "$UNINSTALL" -eq 1 ]; then
        if [ "$DRY_RUN" -eq 1 ]; then
            if [ -f "$STATE_FILE" ]; then
                echo "Would uninstall $(state_value METHOD) $(state_value VERSION) recorded in $STATE_FILE"
            else
                echo "No get.sh state file; would print per-method uninstall commands"
            fi
            return 0
        fi
        make_temp
        uninstall_recorded
        return 0
    fi

    latest_version
    detect_method
    require_tools
    if [ "$METHOD" != "aur" ] && ! version_ge "$VERSION" "$MIN_VERSION"; then
        die "release v$VERSION is older than the installer requires; use --method aur or wait for the next release"
    fi

    if [ "$METHOD" != "aur" ]; then
        make_temp
    fi

    print_plan
    if [ "$METHOD" = "tarball" ] && [ "$USER_INSTALL" -eq 0 ]; then
        need_sudo
    elif [ "$METHOD" = "flatpak" ]; then
        need_sudo
    fi
    confirm "Proceed?"
    if [ "$DRY_RUN" -eq 1 ]; then
        log "dry run: no download or installation performed"
        return 0
    fi

    case "$METHOD" in
        aur) install_aur ;;
        flatpak) install_flatpak ;;
        tarball) install_tarball ;;
    esac
    record_state
    log "installed ATK Control $VERSION with $METHOD; state saved to $STATE_FILE"
}

main "$@"
