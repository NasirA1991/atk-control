# Changelog

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
