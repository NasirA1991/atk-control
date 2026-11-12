# Changelog

## 0.9.0 — 2026-11-12

- Added **experimental support for the ATK A9 Ultimate** (CID/MID `1,3`,
  `373b:11b6` cable and `373b:11d9` 8K dongle). It speaks the `0xFF02`
  protocol, so polling, DPI stages and colours, lift-off, debounce, sleep,
  Motion Sync, straight-line, ripple, rotation, lighting, profiles and button
  remapping are enabled. The sensor is not identified yet, so the DPI list stops
  at 30,000, and the lift-off code the unit reports (`6`) is not in the known
  1 mm / 2 mm map, so the UI keeps warning about it until it is confirmed. The
  `373b:11d9` dongle is now named in the Device page.
- Added **experimental support for the VXE R1 NK (NearLink)** over `0xFF05`
  (CID/MID `2,8`, `373b:1216` NANO receiver / `373b:124c` cable). Polling, DPI,
  lift-off, debounce, sleep, Motion Sync, straight-line, ripple, profiles and
  button remapping are enabled; the model has no rotation, lighting, stage
  colours or performance-mode hardware, so those pages stay hidden. The
  receiver also answers for an R1 S NK (`2,9`), so the model still comes from
  CID/MID only.
- Wired links are no longer capped at 1 kHz when the mouse reports a faster
  rate. The A9 Ultimate reports 4000 Hz on its cable, so `atkctl caps` and the
  Device page now show a 4 kHz ceiling instead of contradicting the mouse.
- `0xFF05` battery replies now expose the pack voltage (percent, then millivolts
  little endian), which restores the voltage line the 0.6.1 battery-only path
  reported and the 0.7.0 rewrite dropped.
- `0xFF05` replies with status `0x73` are treated as unsolicited device events
  instead of being matched against the command in flight.
- The R1 NK firmware reports eight DPI slots regardless of how many are
  configured and stores a slot's factory-default button as class `0`; unused
  0 DPI slots are trimmed so they cannot be selected, and class `0` is decoded
  as the slot default for models that declare it.
- Support reports now name the configuration protocol (`0xFF02` or `0xFF05`).
- Neither new model has been validated on physical hardware by the project yet.
  Both were implemented from the reporters' device reports and, for the R1 NK,
  from a command-by-command mapping of the vendor channel.

## 0.8.0 — 2026-11-11

- Added an **experimental device catalog** derived from the public ATK HUB
  device list. Twenty-six ATK F1/X1/Z1/U2/A9 and VXE R1 SE/R1S+/V3/X3
  identities are now recognized by CID/MID, together with the CORE26K sensor
  (50–26,000 DPI). These models are deliberately **read-only**: identity,
  battery and readable settings are shown, but every write is rejected until
  the transport and commands are verified on that hardware.
- The UI explains why a catalog model is read-only, disables settings pages,
  and points at the report workflow. `atkctl status` labels the state and
  `atkctl` rejects writes with a clear error. This is recognition, not a claim
  of full support.
- Kept the catalog separate from verified models so a shared receiver or a
  CID/MID collision cannot silently enable unsafe writes. Promotion to full
  support still requires a device report and hardware testing.

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
