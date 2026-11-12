# Testing a mouse

This guide is for **verifying a model that already has support** — either a
newly added model, or a setting that looks wrong. If your mouse is not
recognized at all, start with [Device support reports](DEVICE_REPORTS.md)
instead.

Testing is split in two:

1. **Read-only verification** — the script below. Safe to run any time; it does
   not change a single setting on the mouse.
2. **Reversible write checks** — only after the read-only pass looks right, and
   only one change at a time, restoring each value before moving on.

Close ATK Control and any `atkctl watch` before either step. The app takes a
per-device lock, so two writers cannot share one mouse.

## 1. Read-only verification

From a repository checkout:

```bash
./scripts/verify-device.sh
```

From an installed copy (AUR or `install.sh`) the script is not installed, so run
the same steps directly — they are all read-only:

```bash
atkctl --version
atkctl scan --all
atkctl status
atkctl caps
atkctl battery
atkctl support -o atk-verify.md
```

The AppImage bundles the GUI only, so use the Flatpak or a checkout for the CLI.
Inside Flatpak the sandbox has no access to your home directory by default, so
write the report into the app's own data directory and collect it from there:

```bash
flatpak run --command=atkctl io.github.atkcontrol.AtkControl status
flatpak run --command=atkctl io.github.atkcontrol.AtkControl support \
  -o "$HOME/.var/app/io.github.atkcontrol.AtkControl/atk-verify.md"
# the host can read the same file:
# ~/.var/app/io.github.atkcontrol.AtkControl/atk-verify.md
```

The script prints an environment section, the interface list, permissions,
status, capabilities and battery, then saves `atk-verify-<timestamp>.md`. That
file is either a normal device report or, when no configuration interface could
be opened, a discovery report. Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | A mouse answered and the report was written |
| `1` | Attention needed — read the notes above the summary |
| `2` | No supported ATK/VXE interface was found |
| `3` | Setup problem (no `atkctl`, bad option) |

Options: `-d /dev/hidrawN` for a specific interface, `-o DIR` for the report
directory, `--raw` to include the raw register window, `--no-report` to skip the
file.

### What the output should say

For the models added in 0.9.0, a healthy read-only pass looks like this:

| Check | ATK A9 Ultimate | VXE R1 NK (NearLink) |
| --- | --- | --- |
| `status` → Mouse | `ATK A9 Ultimate` | `VXE R1 NK` |
| Link | `USB cable` or `ATK 8K Wireless Dongle` | `ATK NK mouse NANO dongle` or `USB cable` |
| `caps` → Sensor | `Unknown sensor` (50–30000) | `PAW3395SE` (100–18000) |
| `caps` → Link ceiling | 4000 Hz on cable, 8000 Hz on the dongle | 1000 Hz |
| `caps` → DPI range | 50–30000 | 100–18000 |
| DPI stages | 4 (as configured on the mouse) | 4, not 8 |
| Rotation / lighting / colours | yes / yes / yes | no / no / no |
| Buttons | named, e.g. `Back` | named, e.g. `Back` — not `Custom / unsupported` |

`status` also prints the CID/MID implicitly through the model name; if the
model reads `Unknown ATK/VXE mouse` on a receiver, the paired mouse did not
answer — wake it and retry.

## 2. Reversible write checks

Only run these once the read-only pass is clean. Change one value, confirm it
survives a *reconnect* (unplug/replug or power-cycle the mouse), then restore
the original. The app verifies every write by reading it back, so a value the
firmware rejects shows up as an error instead of being silently applied.

Use `atkctl status` before and after each step to record the original value.

**Polling rate** — write a different rate and put it back:

```bash
atkctl polling 1000 && atkctl polling 4000   # A9 Ultimate on its cable
atkctl polling 500  && atkctl polling 1000   # R1 NK
```

Expect the new rate in `atkctl status` immediately, and again after a reconnect.

**DPI** — change one stage, then switch to it and back:

```bash
atkctl dpi 1600 --stage 2
atkctl stage 2 && atkctl stage 1
```

**Buttons** — remap one button, then restore defaults:

```bash
atkctl button 3 dpi_up
atkctl buttons-reset
```

**Sensor settings** — lift-off, debounce, sleep, Motion Sync, straight-line,
ripple:

```bash
atkctl lod 2
atkctl debounce 4
atkctl sleep 300
atkctl motion-sync on
atkctl straight-line off
atkctl ripple off
```

**Lighting and profiles** (A9 Ultimate only — the R1 NK has no lighting):

```bash
atkctl light steady --brightness high --speed fast
atkctl light off
atkctl profile 2 && atkctl profile 1
```

Report anything that is accepted but does not take effect, or that the firmware
rejects, with the exact command and the error text.

### Known limits to expect

- **ATK A9 Ultimate** — the sensor is not identified, so the DPI list stops at
  30,000, and the lift-off code the mouse reports (`6`) is not in the known
  1 mm / 2 mm map. The Performance page warns about the unmapped code; writing a
  verified value is allowed and verified by read-back.
- **VXE R1 NK** — no rotation, lighting, stage-colour or performance-mode
  controls, because the hardware does not expose them. Macros and
  keyboard/shortcut button classes are read-only.
- **ATK Dragonfly A9 Pro Max 2.0** — `0xFF05` path: no rotation and no way to
  add or remove DPI stages. Settings write to the active profile directly.

## 3. What to attach

Attach the `atk-verify-*.md` report, plus:

- the exact commands you ran and their output, for write checks;
- the firmware version shown by `atkctl status`;
- whether the mouse was on the cable, the receiver or both, if the problem only
  happens on one link.

The report is generated locally and contains no host name, RF identifier, USB
serial or file paths. Raw registers are omitted unless you pass `--raw`; only
include them when a maintainer asks, and review the file first.

## 4. Testing from Windows

The application is Linux-only because it talks to `/dev/hidraw` and uses udev.
If you only have Windows, WSL2 can work for the **CLI**:

```powershell
# elevated PowerShell, once
wsl --install -d Ubuntu
winget install --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID> --force      # --force is required for HID mice
usbipd attach --wsl --busid <BUSID>
```

```bash
ls -l /dev/hidraw*
git clone https://github.com/NasirA1991/atk-control
cd atk-control && ./scripts/verify-device.sh
```

Caveats: the attached mouse disappears from Windows while it is bound; each
re-enumeration (cable to receiver, wake, reset) needs a re-attach; WSL has no
udev unless systemd is enabled, so run the CLI as root or install the rule
inside the distro. The GUI and the tray need a real Linux session, so use a
live USB when a test depends on them.
