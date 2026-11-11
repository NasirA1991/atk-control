# Changelog

## Unreleased

- Added a discovery report for unrecognised ATK/VXE devices. `atkctl support`
  and the Device page now work when no supported mouse can be opened, listing
  each vendor HID interface, report descriptor, usage pages and report IDs.
  `atkctl scan --all` shows the same candidates. This is diagnostic only; no
  unsupported protocol is opened for writing.
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
