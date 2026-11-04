# Compx Control

[![CI](https://github.com/NasirA1991/compx-control/actions/workflows/ci.yml/badge.svg)](https://github.com/NasirA1991/compx-control/actions/workflows/ci.yml)
[![Release](https://github.com/NasirA1991/compx-control/actions/workflows/release.yml/badge.svg)](https://github.com/NasirA1991/compx-control/actions/workflows/release.yml)
[![AUR](https://img.shields.io/aur/version/compx-control?label=AUR)](https://aur.archlinux.org/packages/compx-control)
[![AUR git](https://img.shields.io/aur/version/compx-control-git?label=AUR%20git)](https://aur.archlinux.org/packages/compx-control-git)
[![License](https://img.shields.io/github/license/NasirA1991/compx-control)](LICENSE)

Native **GTK4 / libadwaita** control centre for COMPX-based gaming mice —
MAD R, VXE R1 and their close relatives — with no browser tab, Windows VM or
vendor background service.

Compx Control talks directly to the mouse over its vendor HID collection. The
tray icon stays visible with live battery, and every setting is written to the
mouse itself, so it keeps working when the app is closed.

![Overview](docs/screenshots/overview.png)

<sub>Screenshots are rendered by the built-in demo mode (`--demo`).</sub>

> **Hardware status:** the **MAD R +** on its **8K dongle** has been verified on
> real hardware for the features below. The rest of the MAD R family and the
> VXE R1 family share the same configuration protocol, but have not each been
> individually tested yet. If you have one, a
> [read-only report](docs/DEVICE_REPORTS.md) is very welcome.

## Features

- **Tray icon with live battery** — three deliberately different designs:
  *Hex gauge*, *Signal bars* and *Bolt*. Pick one under **Device → Tray icon** or
  from the tray menu. Charging state and link type live in the tooltip, with
  quick actions for polling, DPI, Motion Sync, ripple control and profiles.
- **8K polling** — 125 Hz through 8000 Hz, limited intelligently by the actual
  receiver. The app reads the link type and never offers a rate the transport
  cannot carry.
- **DPI** — separate X/Y resolution, up to eight stored stages, per-stage
  indicator colours, and one-click stage activation. The active stage is the
  one the mouse's DPI button cycles through.
- **Sensor control** — Motion Sync, ripple control, straight-line correction,
  competitive performance mode, lift-off distance, debounce, sleep timer and
  sensor rotation (on firmware that exposes it).
- **DPI indicator LED** — off, steady or breathing, with brightness and speed.
- **Onboard profiles** — switch between the four configuration banks stored in
  the mouse.
- **Button overview** — read-only view of what each physical button currently
  does.
- **CLI** (`compxctl`) for scripts, keybinds and status bars. Setters read the
  value back and fail loudly if the mouse kept something else.
- **Offline and private** — no telemetry, no cloud account, no vendor service.

![Performance](docs/screenshots/performance.png)
![DPI](docs/screenshots/dpi.png)
![Lighting](docs/screenshots/lighting.png)

### Tray icon styles

![Tray icon styles](docs/screenshots/tray-styles.png)

The angular hexagon and signal-bar designs are intentionally unlike the tray
icons used by other mouse utilities, so they are easy to tell apart at a glance.

## Install

Release builds are produced by GitHub Actions and attached to every `v*`
release.

| Format | Best for | What it bundles |
|---|---|---|
| **AUR** `compx-control` / `compx-control-git` | Arch, CachyOS, EndeavourOS | source; builds against your system |
| **Flatpak** `.flatpak` | any distro with Flatpak | GNOME runtime: Python, GTK4, libadwaita, PyGObject, dbus-python |
| **AppImage** `.AppImage` | quick run anywhere with GTK4 installed | the app only; host provides GTK4/PyGObject |
| **Source tarball** | packaging and auditing | source + installer |

### Arch / CachyOS (AUR)

```bash
paru -S compx-control-git     # latest main, rebuilt on updates
paru -S compx-control         # latest tagged release
```

Both are published: [compx-control](https://aur.archlinux.org/packages/compx-control)
· [compx-control-git](https://aur.archlinux.org/packages/compx-control-git).

### Flatpak

Download `compx-control-<version>-x86_64.flatpak` from the
[Releases page](https://github.com/NasirA1991/compx-control/releases), then:

```bash
flatpak install --user ./compx-control-0.1.0-x86_64.flatpak
flatpak run io.github.compxcontrol.CompxControl
```

The Flatpak is self-contained and exposes `/dev/hidraw*` via `--device=all`.
You still need the host udev permission described below.

### AppImage

```bash
chmod +x compx-control-0.1.0-x86_64.AppImage
./compx-control-0.1.0-x86_64.AppImage
```

The AppImage intentionally bundles only the application and uses the host's
Python 3, PyGObject, GTK4, libadwaita, pycairo and dbus-python. Install them
with:

```bash
# Arch / CachyOS
sudo pacman -S python-gobject gtk4 libadwaita python-cairo python-dbus hicolor-icon-theme
# Debian / Ubuntu
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 python3-cairo python3-dbus hicolor-icon-theme
# Fedora
sudo dnf install python3-gobject gtk4 libadwaita python3-cairo python3-dbus hicolor-icon-theme
```

A fully self-contained bundle is the Flatpak above.

## Permissions

The vendor HID collection is `/dev/hidrawN`, normally owned by root. The AUR
package installs the correct rule for you. For the AppImage, Flatpak, or a
source checkout, install it once:

```bash
sudo tee /usr/lib/udev/rules.d/71-compx-control.rules >/dev/null <<'RULE'
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", TAG+="uaccess", MODE="0660"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3554", TAG+="uaccess", MODE="0660"
RULE
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then unplug and reconnect the mouse or receiver. The rule grants access to the
ATK/COMPX (`373b`) and older VXE (`3554`) HID devices.

## Usage

```bash
compx-control                # window + tray
compx-control --tray         # start minimised in the tray
compx-control --no-tray      # window only
compx-control --demo         # simulated MAD R, no hardware required
```

Close the window to keep the app in the tray; **Quit** from the tray menu (or
`Ctrl+Q`) exits.

### CLI

`compxctl` works without GTK and is safe to use in scripts:

```bash
compxctl status
compxctl status --json
compxctl polling 8000
compxctl dpi 1600
compxctl dpi 1600 --stage 3
compxctl stage 2
compxctl motion-sync on
compxctl ripple on
compxctl straight-line off
compxctl lod 0.7
compxctl debounce 2
compxctl sleep 300
compxctl performance on
compxctl profile 2
compxctl light steady --brightness high --speed slow
compxctl report                 # read-only report for a support issue
compxctl caps
compxctl scan
```

Every setter reads the device back and exits non-zero if the mouse did not
confirm the change.

### Tray on GNOME

GNOME needs an AppIndicator/StatusNotifier extension, for example
*AppIndicator and KStatusNotifierItem Support*. KDE Plasma, XFCE, sway/waybar
and other StatusNotifier hosts work out of the box.

## Supported devices

The protocol is shared across the current COMPX mouse family. Model and
capabilities are selected from the mouse's own CID/MID identity, not just the
USB product id, because receivers are shared between models.

| Model | Link | Status |
|---|---|---|
| **MAD R +** | 8K dongle (`373b:1040`) | **Verified on hardware** — battery, polling to 8000 Hz, DPI stages and colours, Motion Sync, ripple, straight-line correction, LOD, debounce, sleep, performance mode, DPI LED, profiles, buttons (read-only) |
| MAD R, MAD R MAJOR, MAD R MAJOR+ | cable / 8K dongle | Same protocol and capability family; not individually tested |
| VXE R1, R1 Pro, R1 Pro Max | cable / receiver | Model entries and receiver ceilings included; hardware verification pending |
| Other COMPX mice | any | Detected read-only until a model entry is added |

**Not yet exposed in 0.1.0:** button remapping, macros, firmware updates and
changing the number of DPI stages. Button assignments are shown read-only. The
stock 4K receiver path will be added and tested when the hardware is available.

### Add your mouse

Use **Device → Save report** (or `compxctl report`). The file is generated
locally, redacts the full RF identifier, and is not uploaded. Review it, then
attach it to a
[device support issue](https://github.com/NasirA1991/compx-control/issues/new?template=device-report.yml).
See [docs/DEVICE_REPORTS.md](docs/DEVICE_REPORTS.md) for details.

## Why does firmware show "not reported by receiver"?

Some receivers, including the MAD 8K dongle, do not forward the mouse firmware
version command. The app shows this honestly instead of inventing a version.
Over a direct USB cable the firmware can usually be read.

## Privacy

Compx Control has no network code. It does not phone home, does not upload
device data, and does not require an account. Settings are stored on the mouse;
window preferences are a small JSON file in `~/.config/compx-control/`.

## License

MIT. See [LICENSE](LICENSE).

Compx Control is an independent project and is not affiliated with ATK, VXE,
MAD or COMPX.
