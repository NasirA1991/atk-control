<p align="center">
  <img src="data/icons/hicolor/scalable/apps/atk-control.svg" width="104" alt="ATK Control icon">
</p>

<h1 align="center">ATK Control</h1>

<p align="center">
  <strong>Native GTK4 control centre for ATK and VXE gaming mice.</strong><br>
  DPI, polling, buttons, lighting and onboard profiles on Linux, with a live
  battery tray and a scriptable CLI.
</p>

<p align="center">
  <a href="https://github.com/NasirA1991/atk-control/actions/workflows/ci.yml"><img src="https://github.com/NasirA1991/atk-control/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/NasirA1991/atk-control/releases/latest"><img src="https://img.shields.io/github/v/release/NasirA1991/atk-control?label=release" alt="Latest release"></a>
  <a href="https://aur.archlinux.org/packages/atk-control"><img src="https://img.shields.io/aur/version/atk-control?label=AUR" alt="AUR"></a>
  <a href="https://aur.archlinux.org/packages/atk-control-git"><img src="https://img.shields.io/aur/version/atk-control-git?label=AUR%20git" alt="AUR git"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/NasirA1991/atk-control" alt="MIT licence"></a>
</p>

ATK Control is an independent, local-first desktop application for configuring
ATK and VXE mice. It talks to the mouse's vendor HID interface directly, so
settings are written to the mouse instead of being held in a browser profile.
There is no account, telemetry, network client or root daemon.

It is a native alternative to ATK HUB for everyday settings, with a tray
battery indicator and a CLI for scripting. ATK HUB remains the vendor tool for
firmware updates and the features listed under [Limitations](#limitations).

**Start here:** [Supported hardware](#supported-hardware) ·
[Quick start](#quick-start) · [Features](#features) · [CLI](#cli) ·
[Troubleshooting](#troubleshooting) · [Documentation](#documentation)

<img src="docs/screenshots/overview.png" width="860" alt="ATK Control overview showing battery, DPI, polling and quick controls">

<sub>Overview using demo data. The interface follows the system light or dark
theme.</sub>

## Supported hardware

Only models tested on physical hardware count as verified. A family name does
not mean every variant has been tested, and “full settings” refers only to the
features exposed by that model's firmware.

### Tested hardware

| Device | Receiver | Status |
| --- | --- | --- |
| **ATK MAD R+** | 8K | **Verified** |
| **VXE R1 Pro** | 1K, 4K | **Verified** |
| **ATK Dragonfly A9 Pro Max 2.0** | Wired, 8K dongle | **Experimental** |

**Verified** means the exact model was tested with ATK Control.
**Experimental** means the protocol is implemented but has not been tested on
that hardware. The A9 uses USB `373b:11dc` (8K dongle) or `373b:1264`
(wired), and supports no rotation, DPI stage count changes or Bluetooth
configuration.

### Other recognized hardware

| Hardware | Status | Notes |
| --- | --- | --- |
| Other MAD R family models (MAD R, MAD R MAJOR, MAD R MAJOR+) | Recognized | Not individually tested |
| Other VXE R1 family models (R1, R1 Pro Max) | Recognized | Not individually tested |
| ATK X1 Pro Max, ATK A9 Plus NearLink, VXE R1 Ultra | Recognized | Not individually tested |
| 26 additional ATK/VXE models | **Read-only** | Model and sensor recognized; writes disabled until verified |
| Other ATK/VXE mice | **Read-only** | Discovery reports only |

**Recognized** hardware uses its model entry; some controls may be unavailable.
**Read-only** hardware can be identified and reported, but settings writes are
deliberately blocked. The read-only catalog covers selected F1, X1, Z1, U2, A9,
VXE R1 SE/R1S+, V3 and X3 models.

Receiver support matters as much as the mouse model:

- 1K receiver: up to 1000 Hz.
- VXE 4K receiver: up to 4000 Hz.
- MAD 8K receiver: up to 8000 Hz.

ATK Control caps polling at the receiver's link ceiling. A 4K dongle cannot
reach 8K, and a wired connection may have different limits. Run `atkctl caps`
or open the Device page for the actual values.

Missing your model, or a setting not working? Generate a
[device support report](#device-support-reports). That is the fastest way to
add evidence-backed support.

## Quick start

### Arch Linux and derivatives (AUR)

```bash
paru -S atk-control
# or
yay -S atk-control
```

Use `atk-control-git` for the latest development commit. The AUR package
installs the desktop files, dependencies and udev rule.

### Flatpak

Download the bundle from the
[latest release](https://github.com/NasirA1991/atk-control/releases/latest),
then install it for your user:

```bash
flatpak install --user ./atk-control-0.8.0-x86_64.flatpak
flatpak run io.github.atkcontrol.AtkControl
```

The Flatpak needs the GNOME runtime and the
[host udev rule](docs/INSTALLATION.md#hid-permissions). It exposes
`/dev/hidraw*` through `--device=all`.

### AppImage

```bash
chmod +x atk-control-0.8.0-x86_64.AppImage
./atk-control-0.8.0-x86_64.AppImage
```

The AppImage uses the host's GTK4, PyGObject and dbus-python packages. It also
needs the [udev rule](docs/INSTALLATION.md#hid-permissions).

**Full instructions:** [Installation](docs/INSTALLATION.md) covers
dependencies, source installs, udev setup, updates and uninstalling. Installing
with `pip` is not supported.

## Features

### Configure the mouse

- **DPI stages** — set X and Y resolution, switch the active stage, and edit
  per-stage colours where the model exposes them.
- **Polling rate** — choose 125–8000 Hz within the receiver and sensor limits.
- **Sensor controls** — lift-off distance, debounce, sleep timer, Motion Sync,
  ripple control, straight-line correction and rotation where supported.
- **Sensor modes** — Basic, Competitive and Competitive MAX where the firmware
  allows them. Competitive MAX 13K is read-only.
- **Buttons** — remap the five main buttons plus the optional bottom button to
  standard mouse, DPI or disabled actions, and restore defaults.
- **Lighting** — DPI indicator modes (off, steady, breathing) with brightness
  and speed where the model supports them.
- **Profiles** — four onboard banks on supported v1 models. The experimental
  A9 Pro Max 2.0 writes directly to its active profile.

### Use it your way

- **Tray integration** — live battery, charging state, quick DPI/profile
  changes and receiver switching.
- **CLI** — `atkctl` exposes status, battery, scanning, reports and every
  supported setting without starting GTK.
- **Demo mode** — explore the interface with synthetic data using
  `atk-control --demo`.
- **Native and lightweight** — GTK4/libadwaita, with the main window created
  only when opened.

<details>
<summary>Resource use and hidden polling</summary>

The hidden tray polls battery every 30 seconds, full state every 5 minutes and
receiver liveness every 5 seconds. That keeps failover responsive without
continuously reading every register. On the development test system, idle CPU
was roughly 0.07–0.13% after the 0.4.7 UI and polling changes. Exact usage
depends on the desktop, receiver and whether the tray is visible.

</details>

### Reliability and privacy

- Reads are checked against protocol limits; writes are verified by reading
  the value back.
- v1 settings are committed to the mouse by a profile round-trip. The app does
  not keep a hidden settings copy.
- A per-device lock prevents the GUI and CLI from writing at the same time.
- No network client, telemetry or account. Support reports are generated
  locally and are never uploaded automatically.
- Firmware is read-only. ATK Control does not flash firmware.

![Tray icon styles: Hex gauge, Signal bars and Reticle](docs/screenshots/tray-styles.png)

<sub>Tray styles can be changed from the tray menu. The battery reading is
live, and the tray item is hidden when no mouse is connected.</sub>

## Screenshots

| Buttons | Performance |
| --- | --- |
| <img src="docs/screenshots/buttons.png" width="430" alt="Buttons page with button assignments"> | <img src="docs/screenshots/performance.png" width="430" alt="Performance page with polling and sensor options"> |
| **DPI** | **Lighting** |
| <img src="docs/screenshots/dpi.png" width="430" alt="DPI page with stages and resolution"> | <img src="docs/screenshots/lighting.png" width="430" alt="Lighting page with DPI indicator controls"> |

<sub>Demo data. Labels and available controls vary by model and firmware.</sub>

## Getting started

Start the app from your application menu or with:

```bash
atk-control
```

The first supported mouse is selected automatically. Use the **Device** page to
choose a receiver when more than one is connected; ATK Control can fail over to
another connected mouse when the selected one goes offline.

The window can be closed to the tray. Use the tray menu to reopen it, refresh
the device or quit. `atk-control --no-tray` runs without a tray host, and
`atk-control --tray` starts hidden where the desktop supports it. On GNOME you
need a StatusNotifier/AppIndicator extension; see
[Troubleshooting](docs/TROUBLESHOOTING.md#the-tray-icon-is-missing).

## CLI

`atkctl` is the headless counterpart. It is useful for keybinds, status bars,
scripts and checking a mouse over SSH.

```bash
atkctl status                 # model, battery, DPI, polling, sensor state
atkctl battery               # percentage, charging and voltage
atkctl scan                  # supported receivers and mice
atkctl scan --all            # include unsupported ATK/VXE interfaces
atkctl dpi 1600 --stage 2    # set a DPI stage
atkctl polling 1000          # set the report rate
atkctl button 3 middle       # remap a button
atkctl light breathing       # DPI indicator effect
atkctl watch --count 10      # sample battery/link state
atkctl support               # save a sanitized support report
```

Run `atkctl --help` or see the [CLI reference](docs/CLI.md) for every command,
JSON output, exit codes and more examples.

> **Concurrency:** the GUI and CLI share a per-device lock. Stop `atkctl watch`
> before opening the app, and do not run two writers against the same mouse.
> `atkctl watch` holds the lock until it exits.

## Limitations

- Support is model-specific. A listed family does not mean every variant has
  been verified on hardware.
- Polling is capped by the receiver and model; see
  [Supported hardware](#supported-hardware).
- The ATK A9 Pro Max 2.0 `0xFF05` path is experimental. It has no rotation
  control and no way to add or remove stages. Settings work over the dongle or
  USB cable; Bluetooth exposes no configuration interface.
- Some known models are recognized but read-only until their transport is
  verified. Experimental catalog entries never write.
- Firmware flashing is not implemented. Use [ATK HUB](https://hub.atk.pro) for firmware updates.
- Macro recording, keyboard-shortcut assignment, config import/export,
  receiver pairing and factory reset are not implemented. Existing macro or
  shortcut assignments are preserved and shown as unsupported.
- Competitive MAX 13K sensor mode can be read but not selected.
- ATK Control does not require root and should not be run as root.

When a feature is missing, a [support report](#device-support-reports) is more
useful than guessing a write command. It records the model, protocol and
descriptor without opening an unknown device for writing.

## Security, permissions and privacy

### Local by design

ATK Control has no network client, no telemetry and no account system. It does
not upload settings or reports. Preferences are stored locally in
`~/.config/atk-control/` with mode `0600`. The app opens ATK HUB or the
support page in your browser only when you choose those buttons; it does not
embed or fetch either page.

### HID permissions

Writing settings requires read/write access to the mouse's hidraw node. The
project ships a udev rule that grants the active local user access through
`uaccess`. It matches the ATK/VXE vendor IDs `373b` and `3554`, so it is
intentionally broader than one product ID.

AUR and system `install.sh` install the rule. Flatpak, AppImage and per-user
installs need it once on the host:

```bash
sudo install -Dm644 data/udev/71-atk-control.rules \
  /usr/lib/udev/rules.d/71-atk-control.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then reconnect the mouse. Do not run the application with `sudo` and do not
`chmod 777` the device. See [Installation](docs/INSTALLATION.md#hid-permissions)
and [SECURITY.md](SECURITY.md) for the full permission scope.

### Write safety

- Values are validated against protocol and sensor limits.
- Successful writes are read back.
- v1 writes are committed with a profile round-trip that takes roughly 0.4
  seconds; the original profile is restored if the round-trip fails.
- Button reset keeps a recovery copy and restores the previous map if the
  write fails.
- Unknown models and read-only catalog entries reject writes instead of guessing.
- The GUI and CLI use the same per-device lock.

### Support reports

Reports contain the model, USB IDs, firmware, link state, readable settings,
button map and sanitized system details. RF/USB serials, hostnames and paths
are redacted by default. Raw register bytes are opt-in and are never uploaded
automatically. Read [Device support reports](docs/DEVICE_REPORTS.md) before
sharing one.

## Troubleshooting

| Problem | Where to look |
| --- | --- |
| Mouse not detected, or the receiver says the mouse is asleep | [Detection](docs/TROUBLESHOOTING.md#the-mouse-is-not-detected) |
| `permission denied` on `/dev/hidraw*` | [Permissions](docs/TROUBLESHOOTING.md#permission-denied) |
| “Another ATK Control instance is configuring this mouse” | [Device lock](docs/TROUBLESHOOTING.md#another-process-owns-the-mouse) |
| Tray icon missing or not updating | [Tray](docs/TROUBLESHOOTING.md#the-tray-icon-is-missing) |
| Settings revert after a power cycle | [Persistence](docs/TROUBLESHOOTING.md#settings-do-not-persist) |
| Writes are rejected or controls are disabled | [Read-only models](docs/TROUBLESHOOTING.md#writes-are-rejected) |
| Flatpak or AppImage does not start | [Packaging](docs/TROUBLESHOOTING.md#flatpak-or-appimage-problems) |

For a reproducible log, run `atk-control --debug` or `atkctl --debug status`.
The full guide is in [Troubleshooting](docs/TROUBLESHOOTING.md).

## Device support reports

If your mouse is missing, detected but read-only, or a setting does not work:

1. Open **Device → Save support report**, or run `atkctl support`.
2. Review the file; it is generated locally and redacts sensitive identifiers.
3. Attach it to the [device report issue](https://github.com/NasirA1991/atk-control/issues/new)
   with the model, USB IDs and receiver type.

If no supported configuration interface can be opened, ATK Control writes a
**discovery report** instead. It lists every ATK/VXE HID interface, usage page,
report ID and descriptor, without opening an unknown device for writing.
`atkctl scan --all` shows the same candidates in the terminal.

Raw register bytes are opt-in (`atkctl support --raw`). Use them only when a
maintainer asks. See [Device support reports](docs/DEVICE_REPORTS.md) for the
full contents and privacy rules.

<img src="docs/screenshots/device.png" width="720" alt="Device page showing configuration devices, report actions and hardware details">

## Documentation

| Document | Contents |
| --- | --- |
| [Documentation index](docs/README.md) | All guides, grouped for users and contributors |
| [Installation](docs/INSTALLATION.md) | AUR, Flatpak, AppImage, source, dependencies, udev and uninstall |
| [CLI reference](docs/CLI.md) | Every command, JSON output, exit codes and scripting examples |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Detection, permissions, tray, persistence and packaging problems |
| [Device support reports](docs/DEVICE_REPORTS.md) | What to send, what is redacted and how to open a support request |
| [Protocol notes](docs/PROTOCOL.md) | v1 and v2 hardware protocol, registers and evidence (maintainers) |
| [Changelog](CHANGELOG.md) | Release history and notable fixes |
| [Contributing](CONTRIBUTING.md) | Development setup, tests and pull requests |
| [Security](SECURITY.md) | Permission scope, local-only design and reporting vulnerabilities |

## Contributing

Bug reports, hardware reports and focused pull requests are welcome. For device
support, include a sanitized report and state what was physically tested. For
code, run the test suite and keep unknown or unverified devices read-only.

Start with [CONTRIBUTING.md](CONTRIBUTING.md) and the
[documentation index](#documentation). Report security issues privately as
described in [SECURITY.md](SECURITY.md).

## License and project information

ATK Control is released under the [MIT License](LICENSE). It is an independent
community project and is not affiliated with ATK, VXE, MADLIONS or the ATK HUB
team.

ATK Control is developed with AI assistance. Hardware and protocol claims are
based on the evidence linked in the issues and documentation; features that
have not been tested on a specific model are labelled experimental or
read-only rather than presented as verified.

Firmware is not modified or distributed by this project. ATK HUB is the vendor
tool for firmware updates and for features not implemented here.
