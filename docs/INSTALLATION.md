# Installing ATK Control

ATK Control runs on Linux with GTK4 and libadwaita. The AUR package is the
recommended option on Arch-based distributions; Flatpak and AppImage are
self-contained alternatives that still need host access to the mouse.

> **Do not run ATK Control as root.** The application needs read/write access
> to the mouse's hidraw node, not superuser privileges. Install the udev rule
> described below instead.

## Choose an installation method

| Method | Best for | Dependency handling | udev rule |
| --- | --- | --- | --- |
| AUR (`atk-control`) | Arch Linux, CachyOS, EndeavourOS, Manjaro | Installed by the package | Included |
| Flatpak | Distribution-independent desktop install | Bundled app; GNOME runtime required | Manual, on the host |
| AppImage | Trying the app without installing packages | Uses host GTK/Python libraries | Manual, on the host |
| Source | Development or unsupported distributions | Host libraries | Manual or via `install.sh` |

The AUR and source installs put `atk-control` and `atkctl` on your `PATH`.
Flatpak and AppImage launch the app from their bundle; the Flatpak CLI is
available as `flatpak run --command=atkctl io.github.atkcontrol.AtkControl`.
The CLI does not require GTK, but every method requires the same hidraw
permissions.

## Requirements

- Linux with a graphical session for the app (the CLI can run headless).
- Python 3.10 or newer for source and AppImage installs.
- PyGObject, GTK4, libadwaita, pycairo and dbus-python for source and AppImage
  installs.
- A supported ATK/VXE mouse, its receiver or USB cable.
- Read/write access to `/dev/hidraw*` through the udev rule.

A StatusNotifierItem host is optional. KDE Plasma provides one; GNOME needs an
extension such as AppIndicator. The app works without a tray using
`atk-control --no-tray`.

## Arch Linux and derivatives (AUR)

Install the stable package:

```bash
paru -S atk-control
```

or with another AUR helper:

```bash
yay -S atk-control
```

For the latest development commit, install `atk-control-git` instead. The
package installs the desktop entry, icons, Python modules and the udev rule.
Reconnect the mouse or receiver once after installation so the new rule
applies.

If you build the checkout locally, `makepkg -si` in the repository uses the
local `PKGBUILD`. The published AUR package builds from the release tarball.

## Flatpak

Download the `.flatpak` bundle from the
[latest release](https://github.com/NasirA1991/atk-control/releases/latest),
then install it for your user:

```bash
flatpak install --user ./atk-control-0.9.2-x86_64.flatpak
flatpak run io.github.atkcontrol.AtkControl
```

The Flatpak CLI is available inside the sandbox:

```bash
flatpak run --command=atkctl io.github.atkcontrol.AtkControl status
```

The bundle does not contain the GNOME runtime. If Flatpak cannot fetch it
automatically, install it first:

```bash
flatpak install flathub org.gnome.Platform//50
```

The Flatpak exposes `/dev/hidraw*` through `--device=all`. It does **not**
install a host udev rule, so follow
[HID permissions](#hid-permissions) once. The tray requires a StatusNotifier
host on the host desktop; see
[Troubleshooting](TROUBLESHOOTING.md#the-tray-icon-is-missing).

To update:

```bash
flatpak update io.github.atkcontrol.AtkControl
```

To remove the app (user preferences remain in `~/.config/atk-control/`):

```bash
flatpak uninstall --user io.github.atkcontrol.AtkControl
```

## AppImage

Download the AppImage and its `SHA256SUMS` from the release page, verify it,
then make it executable:

```bash
sha256sum --check SHA256SUMS
chmod +x atk-control-0.9.2-x86_64.AppImage
./atk-control-0.9.2-x86_64.AppImage
```

The AppImage contains the application but **not** GTK, PyGObject or the other
Python bindings. Install the host packages first. On Arch:

```bash
sudo pacman -S python-gobject gtk4 libadwaita python-cairo python-dbus
```

On Debian/Ubuntu the package names are typically `python3-gi`,
`gir1.2-gtk-4.0`, `gir1.2-adw-1`, `python3-cairo` and `python3-dbus`. Package
names vary by distribution; install the equivalents for your system.

The AppImage also needs the [udev rule](#hid-permissions). To check the app
without a tray host:

```bash
./atk-control-0.9.2-x86_64.AppImage --no-tray
```

There is nothing to uninstall; delete the AppImage when finished.

## From source

Clone the repository and run the installer:

```bash
git clone https://github.com/NasirA1991/atk-control.git
cd atk-control
sudo ./install.sh
```

This installs under `/usr`, including the udev rule. For a per-user install
without sudo:

```bash
./install.sh --user
```

A per-user install writes to `~/.local` and does **not** install the udev
rule; follow [HID permissions](#hid-permissions). Add `~/.local/bin` to
`PATH` if the commands are not found.

`DESTDIR` is available for package staging. The installer does not use pip;
`uninstall.sh` removes `/usr` or `~/.local` installs.

To remove a source install:

```bash
sudo ./uninstall.sh
```

or, for a per-user install:

```bash
./uninstall.sh --user
```

`pip install .` is not supported. The Python metadata exists for development
tooling; pip would not install the desktop files, icons or udev rule.

## HID permissions

The udev rule grants the active local user access to the vendor HID
interfaces used by ATK/VXE devices. AUR and system `install.sh` installs put it
at:

```text
/usr/lib/udev/rules.d/71-atk-control.rules
```

For Flatpak, AppImage or a per-user source install, install the rule from a
checkout:

```bash
sudo install -Dm644 data/udev/71-atk-control.rules \
  /usr/lib/udev/rules.d/71-atk-control.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then unplug and reconnect the mouse or receiver. The rule uses `uaccess` and
`MODE="0660"` and matches the ATK/VXE vendor IDs `373b` and `3554`; it is
intentionally vendor-wide because receivers expose several interfaces. See
[SECURITY.md](../SECURITY.md) for the permission scope and its trade-offs.

Do not `chmod 777` the device or run the app with `sudo`. If permissions still
fail, check `ls -l /dev/hidraw*` and the troubleshooting guide.

## Runtime behaviour

With the window hidden, the tray polls battery every 30 seconds, full state
every 5 minutes and receiver liveness every 5 seconds. The main window is
created only when opened. On the development system, idle CPU was roughly
0.07–0.13%; actual usage depends on the desktop, receiver and tray visibility.

## Verify the installation

```bash
atkctl --version
atkctl scan
atk-control
```

`atkctl scan` should list a supported receiver or mouse. If it does not,
`atkctl scan --all` shows candidate ATK/VXE HID interfaces and why they were
not accepted. See [Troubleshooting](TROUBLESHOOTING.md) or generate a
[device support report](DEVICE_REPORTS.md).

## Related documentation

- [README](../README.md) — overview and quick start
- [CLI reference](CLI.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Device support reports](DEVICE_REPORTS.md)
