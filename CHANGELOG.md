# Changelog

## 0.7.0 — 2026-11-11

- Added experimental **full settings** support for the ATK Dragonfly A9 Pro Max
  2.0 family (`373b:11dc` dongle, `373b:1264` cable) and other known
  `0xFF05` devices. Supported controls: DPI stages and colours, polling rate,
  lift-off distance, button remapping/reset, lighting, profiles, Motion Sync,
  ripple, angle snap, debounce and sleep. Sensor rotation and DPI-stage
  add/remove are not exposed by the protocol.
- The implementation is a clean-room reimplementation of the public
  `Kamrulhasan12345/atk-hub-linux` protocol observations and the
  `noosxe/atk-tool` v2 work. It does not copy code from either project; the
  reference repository has no declared license.
- Unknown `0xFF05` identities remain read-only. Settings are written directly
  to the active profile; the v1 profile-bounce commit is not needed.
- This has **not been validated on physical A9 hardware**. The 125-test suite
  covers the frame checksum, command payloads, DPI/button/lighting setters and
  unknown-device fallback; v1 MAD R+ and VXE R1 Pro behaviour is regression
  tested separately. Bluetooth has no configuration channel.

## 0.6.1 — 2026-11-11

- Added experimental **battery-only** support for the ATK Dragonfly A9 Pro Max
  2.0 (`373b:11dc` dongle, `373b:1264` cable) and other `0xFF05` devices with
  a 64-byte report 8 collection. Charge level and voltage are read with the
  newer battery query; DPI, buttons, lighting and profiles remain disabled.
  This was implemented from the reporter's discovery report and the public v2
  reverse engineering in `noosxe/atk-tool` PR #15; it has not been tested on
  physical A9 hardware yet.
- `atkctl scan --all` labels these devices `supported (battery-only)`, and
  `atkctl support` writes a discovery report so the descriptor is captured.

## 0.6.0 — 2026-11-11

- Added a discovery report for unrecognised ATK/VXE devices. `atkctl support`
  and the Device page now work when no supported mouse can be opened, listing
  each vendor HID interface, report descriptor, usage pages and report IDs.
  `atkctl scan --all` shows the same candidates. This is diagnostic only; no
  unsupported protocol is opened for writing.
- Added `atkctl battery` and `atkctl watch` for scripts and status bars. Both
  are read-only; `watch` can print JSON lines and stop after a fixed sample count.
- Polling changes now write only the polling field instead of rewriting the
  whole system row, removing a read-modify-write race with stage changes.
- Preserved button-slot indexes when an individual button record fails its
  checksum, so remapping a later button cannot overwrite a different physical
  button. Unreadable slots are disabled in the UI and can be repaired by
  restoring defaults.
- Rejected implausible battery percentages and charging flags instead of
  displaying impossible values.
- Refreshed the device picker when the hidraw device list changes even if the
  rendered mouse state is unchanged.
- Re-registered the tray item when the StatusNotifier watcher restarts, and
  fell back to the main window when no watcher is available.
- Delivered failed tray actions as desktop notifications and tray-tooltip
  feedback when the window is hidden.
- Labeled the read-only Competitive MAX 13K sensor mode in the UI and CLI.
- Guarded the distribution lookup in support reports.
- Cached the tray icon and stopped emitting redundant StatusNotifier signals.
- Deferred loading the GTK window module until the window is opened.
- Added `atkctl --version`, removed dead lift-off constants, and dropped the
  stale CI branch filter.
- Documented the residual scope of the vendor-wide udev rule.

## 0.5.3 — 2026-11-08

- Added structured logging with `--debug` / `ATK_CONTROL_DEBUG=1`.
- Fixed stage-colour canonicalisation for callers passing a colour without `#`.
- Removed the unreachable long-range setting and its dead protocol/UI paths.
- Added profile-commit recovery and retry backoff after a failed poll.
- Added regression tests for colour canonicalisation, tray DPI events, retry
  backoff, lock-directory safety, CLI and transport.
- Added ruff/mypy CI checks, coverage reporting, version-source validation,
  scoped workflow permissions and pinned action commits.

## 0.5.2

- Fixed foreground polling while the window is visible.
- Fixed stage-colour redraws, tray DPI values/IDs, charging styling and
  light-theme drawing.
- Added per-stage colour debounce timers.
- Made local package versions derive from `config.VERSION`.
- Cleaned up uninstall autostart and installed the license file.

## 0.5.1

- Fixed the Flatpak tray bus-name generation.

## 0.5.0

- Removed the tray item while no mouse is connected.
