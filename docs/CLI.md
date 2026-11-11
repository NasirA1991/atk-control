# `atkctl` command-line reference

`atkctl` configures ATK/VXE mice without starting the GTK application. It is
useful for scripts, keyboard shortcuts, status bars and headless sessions.

```bash
atkctl --version
atkctl status
atkctl battery
```

The CLI reads the mouse's current settings, verifies writes by reading them
back, and shares a per-device lock with the GUI. It does **not** import GTK, so
it works over SSH and in minimal sessions if the user has hidraw permission.

For installation and permissions, see [INSTALLATION.md](INSTALLATION.md). The
app's graphical workflow is described in the [README](../README.md).

## Global options

```text
atkctl [--device PATH] [--debug] [--version] COMMAND [OPTIONS]
```

| Option | Meaning |
| --- | --- |
| `--device PATH` | Use a specific hidraw node, for example `/dev/hidraw22`. |
| `--debug` | Enable debug logging to stderr. |
| `--version` | Print `atkctl <version>` and exit. |
| `-h`, `--help` | Show help for the CLI or a command. |

`--device` is a global option. Put it before the command:

```bash
atkctl --device /dev/hidraw22 status
```

If you omit it, `atkctl` uses the first supported mouse it can open. With more
than one receiver connected, the GUI's Device page is the easiest way to
choose; the CLI uses discovery order.

## Read-only commands

These commands never modify the mouse.

### `atkctl status [--json]`

Prints the model, connection, battery, firmware, DPI, polling rate, sensor
mode, lift-off distance, debounce, sleep timer and support status. With
`--json`, it prints a machine-readable object containing the `MouseState`
fields plus:

- `connection` — receiver or cable label;
- `link_ceiling` — maximum polling rate supported by the current link;
- `supported_polling_rates` — rates the app offers;
- `dpi_min`, `dpi_max` — sensor range.

RF identifiers are partially redacted in JSON output.

```bash
atkctl status
atkctl status --json | jq '{model: .model_name, battery, dpi, polling_rate}'
```

### `atkctl scan [--all]`

Lists detected ATK/VXE configuration interfaces. Without `--all`, only
supported devices are shown. With `--all`, every vendor interface is shown,
including unsupported ones, with a reason such as a missing `0xFF02`
collection or an unmapped `0xFF05` protocol.

```bash
atkctl scan
atkctl scan --all
```

`scan` is read-only and is the first command to try when the app cannot find
the mouse.

### `atkctl caps`

Prints the selected model's capabilities: sensor, DPI range and step, polling
rates, receiver link ceiling, and whether angle, DPI lighting, per-stage
colours and performance modes are exposed.

### `atkctl battery [--json]`

Reads battery percentage, charging state and voltage. `--json` prints one
object.

```bash
atkctl battery
atkctl battery --json
```

Battery is unknown when the mouse is asleep or the receiver has not forwarded
the reading. Wake the mouse and retry.

### `atkctl watch [--interval SECONDS] [--count N] [--json]`

Samples battery and link state until interrupted (Ctrl-C). The default interval
is 2 seconds; the accepted range is 0.2–60 seconds. `--count` stops after a
fixed number of samples. Each `--json` line is a separate object with a local
ISO-8601 `timestamp`.

```bash
atkctl watch
atkctl watch --interval 5
atkctl watch --count 10 --json
```

`watch` keeps the per-device lock for its entire run. Stop it before opening
the GUI or running a write command. For a one-shot status-bar update, use
`atkctl --device /dev/hidraw22 battery` instead.

### `atkctl report [--raw] [-o PATH]`

Writes a read-only support report. Without `-o`, it prints to stdout. Reports
redact RF/USB serial numbers, hostnames and paths. `--raw` adds the raw register
bytes and should only be used when a maintainer asks for them.

```bash
atkctl report
atkctl report -o ~/atk-report.md
atkctl report --raw -o ~/atk-report-raw.md
```

### `atkctl support [--raw] [-o PATH]`

Writes the same report to a file (default name
`atk-control-report-YYYYMMDD-HHMM.md`) and prints the support-request URL.
If no supported configuration interface can be opened, it writes a discovery
report listing the HID interfaces, usage pages, report IDs and descriptors
instead.

```bash
atkctl support
atkctl support -o ~/atk-a9-plus.md
```

Reports are generated locally and are never uploaded automatically. See
[DEVICE_REPORTS.md](DEVICE_REPORTS.md) for what is included.

## Write commands

Write commands are available only on a writable, known model. Experimental and
unknown devices are recognized but read-only; they exit with status 4.

### Polling and DPI

```bash
atkctl polling 1000          # 125, 250, 500, 1000, 2000, 4000 or 8000
atkctl dpi 1600              # active stage
atkctl dpi 1600 --y 1600 --stage 2
atkctl stage 2
```

The accepted polling rates are limited by the receiver and model; `atkctl caps`
shows the actual list. DPI must be inside the sensor's range and step. `--stage`
uses 1-based stage numbers, matching the UI.

### Sensor controls

```bash
atkctl motion-sync on
atkctl ripple off
atkctl straight-line on
atkctl sensor-mode competitive
atkctl sensor-mode max
atkctl lod 1
atkctl lod 0.7               # only sensors that expose 0.7 mm
atkctl debounce 4
atkctl sleep 120
atkctl angle 5
atkctl angle 0 --off
```

`performance on` is a convenience alias for the Basic/Competitive sensor
performance toggle. Use `sensor-mode` to choose `basic`, `competitive` or
`max` explicitly. Mode 3 (`Competitive MAX 13K`) can be read but is not
writable by ATK Control, so `sensor-mode` accepts only 0–2.

`lod` accepts a distance in millimetres or `low`, `medium`, `high`. The app
maps those names to the values the firmware exposes; 0.7 mm is available only
on supported PAW3950/PAW3950DM sensors. `angle` is available only where the
model exposes rotation; `--off` disables it.

`add-stage` and `remove-stage` add or remove the last DPI stage on v1 models.
They are not supported on the experimental A9 Pro Max 2.0 `0xFF05` protocol,
which exposes a fixed eight-stage table.

### Buttons

```bash
atkctl button 3 middle
atkctl button 6 disabled
atkctl buttons-reset
```

Button numbers are 1–6 and are shown by `atkctl status --json` in the `buttons`
array. Supported actions:

`left`, `right`, `middle`, `back`, `forward`, `dpi_cycle`, `dpi_up`,
`dpi_down`, `disabled`.

Macros, keyboard shortcuts and other ATK HUB button classes are not implemented.
Assigning a different standard action replaces the existing assignment; use
`buttons-reset` to restore defaults. The GUI disables remapping for a corrupted
button record until defaults are restored.

### Lighting and profiles

```bash
atkctl light steady
atkctl light breathing --brightness low --speed slow
atkctl light off
atkctl profile 2
```

`light` controls the DPI indicator LED: `off`, `steady` or `breathing`.
Brightness is `low`, `medium` or `high`; speed is `slow`, `medium` or `fast`.
Not every model exposes all effects. `profile` selects onboard bank 1–4 on
models with multiple profiles; the A9 Pro Max 2.0 uses direct writes to its
active profile.

## Scripting examples

Battery percentage for a status bar:

```bash
atkctl --device /dev/hidraw22 battery --json | jq -r '.battery'
```

Notify when the battery drops below 20%:

```bash
level=$(atkctl battery --json | jq -r '.battery')
if [ "$level" != "null" ] && [ "$level" -lt 20 ]; then
  notify-send "Mouse battery" "${level}% remaining"
fi
```

Poll while a game is running, without holding the lock indefinitely:

```bash
atkctl watch --interval 10 --count 60
```

Switch to a lower polling rate for battery life:

```bash
atkctl polling 1000
```

## Exit status and errors

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Protocol error, invalid value, or no supported device could be opened. |
| `3` | Permission denied; the udev rule is missing or not active. |
| `4` | The mouse is recognized but read-only (experimental or unmapped model). |
| `130` | Interrupted with Ctrl-C. |

Errors are printed to stderr. A successful setting is read back and verified;
`commit_settings()` is called after v1 writes to persist the active profile.
v2 `0xFF05` writes go directly to the active profile. If a write fails, the CLI
exits non-zero and may leave the mouse on its previous value.

If another process owns the mouse, the CLI cannot open it. Close the GUI, tray
instance or a running `atkctl watch`, then retry.

## Related documentation

- [Installation](INSTALLATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Device support reports](DEVICE_REPORTS.md)
- [Protocol notes](PROTOCOL.md)
