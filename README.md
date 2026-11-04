# ATK Control

<p align="center">
  <img src="data/icons/hicolor/scalable/apps/atk-control.svg" width="112" alt="ATK Control icon">
</p>

<p align="center">
  <strong>A native GTK4 control centre for ATK/VXE gaming mice.</strong><br>
  Polling, DPI, buttons, lighting, profiles and a live battery tray — without a
  browser tab, Windows VM or vendor service.
</p>

<p align="center">
  <a href="https://github.com/NasirA1991/atk-control/actions/workflows/ci.yml"><img src="https://github.com/NasirA1991/atk-control/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/NasirA1991/atk-control/actions/workflows/release.yml"><img src="https://github.com/NasirA1991/atk-control/actions/workflows/release.yml/badge.svg" alt="Release"></a>
  <a href="https://aur.archlinux.org/packages/atk-control"><img src="https://img.shields.io/aur/version/atk-control?label=AUR" alt="AUR"></a>
  <a href="https://aur.archlinux.org/packages/atk-control-git"><img src="https://img.shields.io/aur/version/atk-control-git?label=AUR%20git" alt="AUR git"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/NasirA1991/atk-control" alt="License"></a>
</p>

## Quick install

### Arch, CachyOS or EndeavourOS

Use whichever AUR helper you normally use:

```bash
paru -S atk-control     # paru
yay -S atk-control      # yay
```

The stable AUR package pins the release tarball's SHA-256. `atk-control-git`
tracks main and therefore uses `SKIP`, as VCS packages do. For the latest main
branch, install `atk-control-git` instead. Other
distributions can download the latest Flatpak or AppImage from
[Releases](https://github.com/NasirA1991/atk-control/releases), or read the
[full installation instructions](#install).

**On this page:** [Features](#features) · [Supported devices](#supported-devices) · [Installation](#install) · [CLI](#cli) · [Troubleshooting](#troubleshooting) · [Permissions](#permissions) · [Support](#missing-your-mouse)

![Overview](docs/screenshots/overview.png)

<sub>Screenshots are rendered by the built-in demo mode (`--demo`).</sub>

> **Hardware status:** the **MAD R +** on its **8K dongle** and the **VXE R1
> Pro** on both its **1K** and **4K** receivers have been verified on real
> hardware. Other ATK/VXE models share the configuration protocol but have not
> each been individually tested. [Request support for your mouse](#missing-your-mouse)
> and it can be added.

## Features

- **Tray icon with live battery** — three deliberately different designs:
  *Hex gauge*, *Signal bars* and *Reticle*. Pick one under **Device → Tray icon**
  or from the tray menu. Charging state and link type live in the tooltip, with
  quick actions for polling, DPI, Motion Sync, ripple control and profiles.
  The icon itself uses a dynamic battery pixmap, so the percentage is visible
  in the panel as well as the tooltip. The item is removed while no mouse is
  connected and restored automatically when a mouse comes back. Left click
  opens the window; right click opens the quick menu; middle click refreshes.
- **8K / 4K polling** — 125 Hz through 8000 Hz, limited intelligently by the
  actual receiver. The app reads the link type and never offers a rate the
  transport cannot carry.
- **DPI** — separate X/Y resolution, up to eight stored stages, per-stage
  indicator colours, add/remove stages, and one-click stage activation. The
  active stage is the one the mouse's DPI button cycles through.
- **Sensor sampling modes** — Basic, Competitive and Competitive MAX, with the
  same trade-off descriptions as ATK HUB. MAX is enabled only for models where
  it has been verified.
- **Sensor control** — Motion Sync, ripple control, straight-line correction,
  lift-off distance, debounce, sleep timer and sensor rotation (on firmware
  that exposes it).
- **DPI indicator LED** — off, steady or breathing, with brightness and speed.
- **Onboard profiles** — switch between the four configuration banks stored in
  the mouse.
- **Button remapping** — assign standard mouse and DPI actions to the left,
  right, middle, back, forward and bottom buttons, with a recoverable
  restore-defaults action. Remapping is enabled only for verified models;
  elsewhere the button map is read-only. Existing macro/shortcut assignments
  are preserved individually but are explicitly overwritten by a full reset.
- **Firmware awareness** — shows the firmware the mouse is actually running and
  links to ATK HUB for updates. ATK Control never flashes firmware itself.
- **CLI** (`atkctl`) for scripts, keybinds and status bars. Setters read the
  value back and fail loudly if the mouse kept something else.
- **Offline and private** — no telemetry, no cloud account, no vendor service.
  Raw support bytes are opt-in, and a per-device lock prevents the GUI and CLI
  from fighting over one hidraw stream.

![Buttons](docs/screenshots/buttons.png)
![Performance](docs/screenshots/performance.png)
![DPI](docs/screenshots/dpi.png)
![Lighting](docs/screenshots/lighting.png)

### Tray icon styles

![Tray icon styles](docs/screenshots/tray-styles.png)

The angular hexagon and transparent bar/reticle designs are intentionally unlike
the tray icons used by other mouse utilities.

## Install

Release builds are produced by GitHub Actions and attached to every `v*`
release.

| Format | Best for | What it bundles |
|---|---|---|
| **AUR** `atk-control` / `atk-control-git` | Arch, CachyOS, EndeavourOS | source; builds against your system |
| **Flatpak** `.flatpak` | any distro with Flatpak | GNOME runtime: Python, GTK4, libadwaita, PyGObject, dbus-python |
| **AppImage** `.AppImage` | quick run anywhere with GTK4 installed | the app only; host provides GTK4/PyGObject |
| **Source tarball** | packaging and auditing | source + installer |

### Arch / CachyOS (AUR)

```bash
# Use your normal AUR helper; for example:
paru -S atk-control        # paru, latest tagged release
yay -S atk-control         # yay
paru -S atk-control-git    # latest main, rebuilt on updates
```

Both are published: [atk-control](https://aur.archlinux.org/packages/atk-control)
· [atk-control-git](https://aur.archlinux.org/packages/atk-control-git).

`atk-control` supersedes the earlier `compx-control` package and declares the
old package name as replaced.

### Flatpak

Download `atk-control-<version>-x86_64.flatpak` from the
[Releases page](https://github.com/NasirA1991/atk-control/releases), replacing
`<version>` with the latest version, then:

```bash
flatpak install --user ./atk-control-<version>-x86_64.flatpak
flatpak run io.github.atkcontrol.AtkControl
```

The Flatpak is self-contained and exposes `/dev/hidraw*` via `--device=all`.
You still need the host udev permission described below.

### AppImage

```bash
chmod +x atk-control-<version>-x86_64.AppImage
./atk-control-<version>-x86_64.AppImage
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

A fully self-contained bundle is the Flatpak above. Every release also includes
`SHA256SUMS`; verify a download with:

```bash
sha256sum -c SHA256SUMS
```

### From source

```bash
git clone https://github.com/NasirA1991/atk-control.git
cd atk-control
./install.sh
```

This installs the launchers, desktop entry, icons and udev rule. The same
GTK4/PyGObject dependencies listed for the AppImage are required.

## Performance

Native GTK4/Python, not Electron. The main window is created only when opened;
tray-only operation is designed to leave a wireless mouse alone.

<details>
<summary>Idle usage measurements</summary>

| Mode | Idle CPU | RSS | PSS |
|---|---|---|---|
| Tray only, window never created | ~0.05–0.13% | ~76 MB | ~49 MB |
| Window open, idle | ~0.07–0.13% | ~131 MB | ~78 MB |

RSS counts shared GTK libraries; PSS is the fairer figure. The Flatpak shares
its runtime with other GNOME apps, so its PSS is usually lower. The window only
relayouts when a displayed value actually changes; hidden battery polling is
every 30 seconds, full refresh every 5 minutes, and the receiver liveness ping
every 5 seconds.
</details>

## Safety and concurrency

Writes are verified by reading them back, then committed to the active onboard
profile so they survive a power cycle. A per-device lock prevents the GUI and
CLI from racing; failed writes and partial button resets are recovered as far
as the protocol allows. Button remapping and Competitive MAX are enabled only
for individually verified models.

<details>
<summary>Implementation details</summary>

- Rejected values are re-read so the UI reverts to the confirmed state.
- Adding a DPI stage preflights the shared colour row and preserves the
  neighbouring stage's bytes.
- A failed button reset attempts to restore the original mappings and reports
  exactly what happened.
- Preferences are type-checked and written atomically; a corrupted JSON file
  cannot crash startup.
</details>

## Permissions

The vendor HID collection is `/dev/hidrawN`, normally owned by root. The AUR
package installs the correct rule for you. For the AppImage, Flatpak, or a
source checkout, install it once:

```bash
sudo tee /usr/lib/udev/rules.d/71-atk-control.rules >/dev/null <<'RULE'
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="373b", TAG+="uaccess", MODE="0660"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="3554", TAG+="uaccess", MODE="0660"
RULE
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then unplug and reconnect the mouse or receiver. The rule grants access to the
ATK (`373b`) and VXE (`3554`) HID devices.

The rule and the Flatpak's `--device=all` permission are deliberately broad:
Linux exposes the vendor HID collection as a generic `/dev/hidrawN` node, and
the app validates the collection at the descriptor level before using it. The
Flatpak has no network permission and no privileged helper. Do not run the GUI
as root; the udev rule is the supported permission path.

## Usage

```bash
atk-control                # window + tray
atk-control --tray         # start minimised in the tray
atk-control --no-tray      # window only
atk-control --demo         # simulated MAD R, no hardware required
```

Close the window to keep the app in the tray; **Quit** from the tray menu (or
`Ctrl+Q`) exits.

### CLI

`atkctl` works without GTK and is safe to use in scripts:

```bash
atkctl status
atkctl status --json
atkctl polling 8000
atkctl dpi 1600
atkctl dpi 1600 --stage 3
atkctl stage 2
atkctl motion-sync on
atkctl ripple on
atkctl straight-line off
atkctl lod 1
atkctl debounce 2
atkctl sleep 300
atkctl sensor-mode competitive
atkctl button 5 back
atkctl buttons-reset
atkctl add-stage
atkctl remove-stage
atkctl profile 2
atkctl light steady --brightness high --speed slow
atkctl support                # save a sanitized support report
atkctl report                 # print the same report
atkctl caps
atkctl scan
```

Every setter reads the device back and exits non-zero if the mouse did not
confirm the change. The GUI and CLI share a per-device lock, so quit the GUI
(or its tray process) before using `atkctl` on the same mouse.

### Tray on GNOME

GNOME needs an AppIndicator/StatusNotifier extension, for example
*AppIndicator and KStatusNotifierItem Support*. KDE Plasma, XFCE, sway/waybar
and other StatusNotifier hosts work out of the box.

## Troubleshooting

### “No permission for /dev/hidraw…” 
Install the udev rule under [Permissions](#permissions), then unplug and
reconnect the receiver. The AUR package installs it automatically.

### The mouse is not detected, or the app says it is asleep
Move the mouse to wake it. The receiver must also be connected. If two mice are
connected, the app switches to the other one when the selected mouse goes
offline.

### The tray icon is missing or has no menu
GNOME needs a StatusNotifier/AppIndicator extension. On KDE/XFCE, left click
opens the window, right click opens the quick menu, and middle click refreshes.
If an older ATK Control process is still running, quit it completely and
relaunch. The **Signal bars** style is intentionally text-free; choose
**Hex gauge** or **Reticle** to see the percentage in the icon.

### “Device is already controlled by another ATK Control process”
Only one GUI/CLI process may own a hidraw node. Quit the other window or tray
process before running `atkctl` on the same mouse.

### Settings went back to defaults after powering the mouse off
Use **0.4.8 or newer**. ATK Control commits the active onboard profile after
each change; older builds did not. If the latest build still loses a setting,
save a support report from the Device page.

### The firmware version is blank
Not every receiver forwards the query. Wake the mouse and refresh; if it still
does not appear, use ATK HUB for firmware information and updates.

## Supported devices

The protocol is shared across the current ATK/VXE mouse family. Model and
capabilities are selected from the mouse's own CID/MID identity, not just the
USB product id, because receivers are shared between models.

| Model | Link | Status |
|---|---|---|
| **MAD R +** | 8K dongle (`373b:1040`) | **Verified on hardware** — battery, polling to 8000 Hz, DPI stages and colours, Motion Sync, ripple, straight-line correction, LOD, debounce, sleep, sensor mode, DPI LED, profiles and button reads; button remap and MAX are enabled from ATK HUB protocol evidence; DPI and profile commits survive power cycles |
| MAD R, MAD R MAJOR, MAD R MAJOR+ | cable / 8K dongle | Same protocol and capability family; not individually tested |
| **VXE R1 Pro** | 1K / 4K receiver (`3554:f58a` / `3554:f505`) | **Verified on hardware** — polling up to 4K, DPI stages/colours and add/remove, Motion Sync, ripple, straight-line, LOD, debounce, sleep, sensor modes including MAX, DPI LED, button remapping, firmware reporting and settings that survive power cycles |
| VXE R1, VXE R1 Pro Max | cable / receiver | Model entries and receiver ceilings included; not individually tested |
| Other ATK/VXE mice | any | Detected read-only until a model entry is added |

The MAD R + is an 8K-receiver mouse; that is the configuration verified here.
When more than one receiver is connected, the **Device → Configuration devices**
card lets you switch between them. If the selected mouse is unplugged, switched
off or asleep, ATK Control detects the offline receiver and tries the other
detected mouse automatically, updating the tray and window to the one that
answers.

## Missing your mouse?

ATK Control is built to grow across the ATK/VXE family. If your mouse is not
listed, or a receiver is not recognised, send a **read-only device report**:

1. Open **Device → Missing your ATK/VXE mouse? → Save support report**.
2. Review the generated `.md` file.
3. Attach it to a [mouse support request](https://github.com/NasirA1991/atk-control/issues/new?template=device-report.yml).

From a terminal this is:

```bash
atkctl support
```

The report includes the device identity and every setting ATK Control can read.
It never includes the full RF identifier, USB serial number or host name, and
nothing is uploaded automatically. Raw register bytes are **opt-in**: enable
*Include raw registers* in the save dialog, or run `atkctl support --raw`, only
when maintainers ask for them. [More about device reports](docs/DEVICE_REPORTS.md).

![Device and support report](docs/screenshots/device.png)

**Not yet exposed:** macro recording, complex keyboard-shortcut assignments,
receiver pairing, factory reset, direction calibration and configuration
import/export. Those remain in ATK HUB. Existing macro or shortcut button
assignments are preserved and shown as *Custom / unsupported* unless you
explicitly reset all button mappings.

## Firmware

ATK Control reads the firmware version when the mouse is awake and the receiver
forwards the query. It does **not** flash firmware itself. Use **Device →
Firmware → Firmware updates in ATK HUB** for that; your settings stay on the
mouse.

Firmware reporting is best-effort: if the version is briefly unavailable after
wake, move the mouse or refresh. Some receivers take a moment to forward the
query, and some combinations may not report it at all.

## Privacy

ATK Control has no network code. It does not phone home, does not upload
device data, and does not require an account. Settings are stored on the mouse;
window preferences are a small JSON file in `~/.config/atk-control/`.

Support reports are only created when you ask for one. Raw register bytes are
omitted unless you opt in, and the app never uploads anything. Review the file
before attaching it to a public issue.

## License

MIT. See [LICENSE](LICENSE).

ATK Control is an independent project and is not affiliated with ATK or VXE.
It is developed with AI assistance; hardware writes are verified on real
devices where the supported-device table says so.
