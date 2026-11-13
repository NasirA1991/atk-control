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

For the models added since 0.9.0, a healthy read-only pass looks like this:

| Check | ATK A9 Ultimate | VXE R1 NK (NearLink) | ATK Dragonfly A9 Pro Max 2.0 |
| --- | --- | --- | --- |
| `status` → Mouse | `ATK A9 Ultimate` | `VXE R1 NK` | `ATK Dragonfly A9 Pro Max 2.0` |
| Link | `USB cable` or `ATK 8K Wireless Dongle` | `ATK NK mouse NANO dongle` or `USB cable` | `USB cable` or `ATK 8K NANO Dongle` |
| `caps` → Sensor | `PAW3950Ultra` (10–42000) | `PAW3395SE` (100–18000) | `PAW3395Ultra`, `PAW3950Ultra` or `PAW3950DM` by CID/MID |
| `caps` → Link ceiling | 4000 Hz on cable, 8000 Hz on the dongle | 1000 Hz | 8000 Hz on both links |
| DPI stages | as configured on the mouse | 4, not 8 | as configured on the mouse |
| Rotation / lighting / colours | yes / yes / yes | no / no / no | no / yes / yes |
| Buttons | named, e.g. `Back` | named, e.g. `Back` — not `Custom / unsupported` | named, e.g. `Back` |
| `status` → Dongle fw | wired: absent | `Dongle fw` line when a receiver is used | `1.0.19` on the dongle |

`status` also prints the CID/MID implicitly through the model name; if the
model reads `Unknown ATK/VXE mouse` on a receiver, the paired mouse did not
answer — wake it and retry.

`Lift-off` prints millimetres only when the stored level is mapped (`1`–`3`).
`Lift-off: level 6 (unmapped)` is not a failure: the `0xFF05` firmware stores a
vendor level, and the tested A9 Pro Max 2.0 keeps a level the app cannot name
yet. Please report that line — it is what maps the remaining levels.

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

- **ATK A9 Ultimate** — the PAW3950Ultra sensor comes from ATK HUB's model
  table, not from an owner's confirmation yet, so DPI has not been checked
  against the mouse itself. Its lift-off level (`6`) is not in the known
  1 mm / 2 mm map. The Performance page warns about the unmapped level; writing
  a verified value is allowed and verified by read-back.
- **VXE R1 SE+** — added from a report in 0.9.2, not write-tested yet. Its 1K
  receiver caps polling at 1000 Hz and the DPI table is the PAW3395SE one
  (100-18,000); DPI stages above that are rejected before the write.
- **VXE R1 NK** — no rotation, lighting, stage-colour or performance-mode
  controls, because the hardware does not expose them. Macros and
  keyboard/shortcut button classes are read-only.
- **ATK Dragonfly A9 Pro Max 2.0** — `0xFF05` path: no rotation and no way to
  add or remove DPI stages. Settings write to the active profile directly, and
  an owner confirmed they survive a power cycle. Lift-off reads as an unmapped
  level until the vendor's option list for this model is confirmed.

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

## Promotion criteria

A model is in one of three states; the [README](../README.md#supported-hardware)
shows the current one.

| Level | What it claims | What is required |
| --- | --- | --- |
| `recognised` | identity, battery and reads only | nothing: the identity is in the vendor catalogue |
| `experimental` | writes work, verified by read-back | an owner's report that decodes with the family's existing protocol |
| `verified` | the advertised controls are proven on that model | the checklist below, recorded in [PROTOCOL.md](PROTOCOL.md) |

The level is a field on the model entry in `atk_control/devices.py`; the app
banner, the README table and `atkctl status` all read it. A `verified` entry must
also carry its evidence (firmware, links, date, issue), which a unit test
enforces.

Writes are also gated per feature, not just per model. DPI writes are refused
while the sensor is unidentified, because the sensor selects the DPI encoding
and read-back cannot catch a wrong one: the same codec encodes and decodes the
value, which is how 0.9.1 shipped DPI five times too low for one model.

To move a model from experimental to verified, its owner runs this on the exact
mouse and posts the result:

1. reads are consistent on that link (`atkctl status`, `atkctl caps`);
2. each advertised setting is written, read back, and restored to its original
   value;
3. the values the app claims to commit survive a power cycle or reconnect;
4. the evidence is written into [PROTOCOL.md](PROTOCOL.md).

"The settings work" keeps a model experimental: it proves that writes land, not
that every control is correct. A control that cannot be restored from the app —
an unmapped lift-off level, for example — is not tested at all, and the
limitation is stated instead of being guessed at.

Experimental models are tracked with the `needs-verification` label on their
issue. The label comes off when the evidence lands and the README moves the model
to verified.
