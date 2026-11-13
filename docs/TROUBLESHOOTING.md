# Troubleshooting ATK Control

Start with the quick checks below. Most detection and permission problems are
solved by the udev rule or by waking the mouse.

```bash
atkctl --version
atkctl scan
atkctl scan --all
atkctl status
```

Run the GUI with `atk-control`. Use `atk-control --no-tray` if the tray host is
missing. For a reproducible diagnostic log, see [Debug logging](#debug-logging).

## First checks

- Wake the mouse and keep it within range of its receiver.
- Use the receiver or USB cable that belongs to the mouse. A 4K/8K dongle and a
  wired cable expose different USB IDs; both are normal.
- Reconnect the receiver after installing or updating the udev rule.
- Confirm that another copy of ATK Control, the tray app, or `atkctl watch` is
  not already holding the device.
- If the mouse is asleep, the receiver may still appear in `atkctl scan` while
  `atkctl status` reports that the paired mouse is asleep.

## The mouse is not detected

### `atkctl scan` shows nothing

1. Run `atkctl scan --all`. This lists every ATK/VXE vendor interface and the
   reason it was rejected.
2. Run `atkctl support` (or the Device page's **Save support report**) and
   attach the report to a
   [device support issue](https://github.com/NasirA1991/atk-control/issues/new).
   When no supported interface exists, the report is a discovery report that
   contains descriptors and usage pages.
3. Check `lsusb` for the mouse or receiver. A receiver that is present but has
   no paired mouse is not enough for a setting read.

If `scan --all` shows an interface with `0xFF05` and the mouse is an A9 Pro Max
2.0, the app may be in experimental or read-only mode. See
[Writes are rejected](#writes-are-rejected).

### The app says the paired mouse is asleep

The receiver is connected, but the mouse is not answering. Move the mouse,
press a button, or reconnect the receiver. Some VXE models sleep aggressively;
a quick movement is usually enough.

If this happens repeatedly, check the receiver's link and try the USB cable to
distinguish a wireless problem from a device problem.

### The wrong mouse is selected

Open **Device → Configuration devices** and choose the receiver you want. With
more than one receiver connected, ATK Control can switch automatically when
one mouse goes offline, but it will not wake a sleeping mouse. The CLI uses the
first supported device unless you pass `--device`.

## Permission denied

Typical error:

```text
atkctl: permission denied opening /dev/hidraw22
Install the udev rule ...
```

Install the rule and reload udev:

```bash
sudo install -Dm644 data/udev/71-atk-control.rules \
  /usr/lib/udev/rules.d/71-atk-control.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=hidraw
```

Then unplug and reconnect the mouse or receiver. The AUR and system
`install.sh` installs include the rule; Flatpak, AppImage and `--user` installs
do not. Details are in [INSTALLATION.md](INSTALLATION.md#hid-permissions).

Do **not** run the app with `sudo` and do not `chmod 777` the device. The
application is designed to run as your normal desktop user. If `ls -l
/dev/hidraw*` shows a group other than your user, check that the rule is
present and that you are in the active local session.

## Another process owns the mouse

ATK Control takes an advisory lock on each hidraw node. The GUI and CLI cannot
configure the same mouse at the same time.

Close, in this order:

1. a running `atkctl watch`;
2. the tray instance or main window;
3. any other ATK/VXE tool that opens the device.

Then retry. The lock is released automatically when the process exits.

## The tray icon is missing

ATK Control uses StatusNotifierItem. KDE Plasma supports it directly. GNOME
needs an AppIndicator/StatusNotifier extension; install and enable one, then
restart the app.

Check that a StatusNotifier watcher is running:

```bash
busctl --user list | grep -i StatusNotifier
```

If no watcher exists, ATK Control shows the main window and keeps running. The
app also hides the tray item when no mouse is connected, so an empty tray is
not necessarily an error.

If the tray icons look wrong, open the tray menu and choose another style.
The three built-in styles are Hex gauge, Signal bars and Reticle; the preview
is in the [README](../README.md#screenshots).

## Settings do not persist

ATK Control verifies every write by reading it back. On v1 devices, it then
performs a profile round-trip to commit the active profile to onboard storage;
this takes roughly 0.4 seconds. On the experimental A9 Pro Max 2.0 `0xFF05`
protocol, writes go directly to the active profile.

- Wait for the success toast or CLI result before unplugging the mouse.
- On multi-profile models, confirm you changed the active profile.
- Power-cycle the mouse after a write if you want to verify persistence.
- Some settings are firmware-managed and may be reset by a firmware update or
  a factory reset performed in ATK HUB.

If a setting reverts immediately, the write was probably rejected or the
device is read-only. Run `atkctl status` and check the support line.

## Battery or firmware is blank

The battery gauge is hidden when the mouse is asleep or has not reported a
valid percentage. Wake the mouse and retry; `atkctl battery` is a quick check.

Firmware is read from the mouse when the receiver forwards it. Some receivers
do not forward firmware, so the app shows “not forwarded by the receiver”
instead of inventing a value. ATK Control never flashes firmware; use ATK HUB
for firmware updates.

## Writes are rejected

A recognized but unverified model is intentionally read-only. This includes
the experimental catalog entries and unknown `0xFF05` identities. The UI shows
an **Experimental model recognition** notice and the CLI exits with status 4.

This is a safety feature: the app will not guess write commands for an
unverified transport. Generate a support report and open an issue with the
model, USB IDs, receiver type and the report. See
[Device support reports](DEVICE_REPORTS.md).

Some features are also model-dependent:

- `angle` is available only where the firmware exposes rotation.
- `add-stage`/`remove-stage` are not available on the A9 Pro Max 2.0 `0xFF05`
  path.
- 0.7 mm lift-off is limited to supported PAW3950/PAW3950DM sensors.
- `Competitive MAX 13K` sensor mode is read-only.

## Flatpak or AppImage problems

### The app starts but cannot see the mouse

Install the host udev rule and reconnect the device. Flatpak exposes
`/dev/hidraw*` through `--device=all`, but it cannot grant permissions that the
host udev rule has not granted. See
[INSTALLATION.md](INSTALLATION.md#hid-permissions).

### The Flatpak cannot find its runtime

The app bundle does not include the GNOME runtime. Install it first:

```bash
flatpak install flathub org.gnome.Platform//50
flatpak run io.github.atkcontrol.AtkControl
```

### The AppImage fails to start

The AppImage uses the host's GTK4, PyGObject, libadwaita, pycairo and
dbus-python. Install the distribution packages listed in
[INSTALLATION.md](INSTALLATION.md#appimage). Try:

```bash
./atk-control-0.9.2-x86_64.AppImage --no-tray
```

For a missing tray, see [The tray icon is missing](#the-tray-icon-is-missing).

## Debug logging

Run the GUI with debug logging:

```bash
atk-control --debug
```

or set the environment variable:

```bash
ATK_CONTROL_DEBUG=1 atk-control
```

The CLI accepts the global `--debug` flag:

```bash
atkctl --debug status
```

Debug logs go to stderr and include discovery and error details. They are not
a raw register dump; use the opt-in `--raw` report only when a maintainer
requests it.

## Reporting a bug

Include:

- ATK Control version (`atkctl --version`);
- distribution and desktop session;
- mouse model, USB IDs and receiver type;
- whether the mouse is wired or wireless;
- the exact command or UI action;
- the relevant debug log lines;
- a sanitized support report when hardware detection is involved.

Open an issue at
[github.com/NasirA1991/atk-control/issues](https://github.com/NasirA1991/atk-control/issues).
For a new device, use the device-report issue template and attach the report
described in [DEVICE_REPORTS.md](DEVICE_REPORTS.md).

## Related documentation

- [Installation](INSTALLATION.md)
- [CLI reference](CLI.md)
- [Device support reports](DEVICE_REPORTS.md)
- [Security and permissions](../SECURITY.md)
