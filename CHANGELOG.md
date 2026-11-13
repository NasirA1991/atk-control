# Changelog

## 0.9.5 — 2026-11-14

The support process now lives in the model table instead of in prose.

- **One support level per model.** `Model.support` is `recognised` (read-only),
  `experimental` (writable, not tested control by control) or `verified`
  (tested, with evidence). It replaces the `experimental` boolean, which meant
  "read-only" in code while the README used "Experimental" for writable models —
  the same word for two opposite things. The app banner, `atkctl status`, support
  reports, the README table and the promotion rules all read this one field.
- **Verified entries carry their evidence.** `Model.evidence` records the issue,
  firmware, links and date, and a test fails if a verified entry has none. The
  two verified models now carry what was actually tested.
- **Writes are gated per feature.** DPI writes are refused while the model's
  sensor is unidentified: the sensor selects the DPI encoding, so the same wrong
  codec encoded and decoded the value and read-back could not catch it. That is
  the 0.9.1 A9 Ultimate bug (DPI five times too low); polling, buttons and the
  rest stay available, which is what an unidentified sensor should block.
- **Model-table invariants are tests**: every entry declares a known level, every
  sensor name exists in `SENSORS`, and no identity is duplicated inside a table.
- The README hardware section is split into Verified, Experimental and
  Recognised, and the family entries that are writable on inherited evidence
  (MAD R MAJOR and relatives, X1 Pro Max, R1 Ultra and others) are listed as
  experimental instead of "recognized / not individually tested", which read as
  weaker than their actual access.

## 0.9.4 — 2026-11-14

Fixes from an external code review of 0.9.1, verified against the tree before
each change. Every item below has a regression test.

- **State and safety**
  - `commit_settings()` reads the active profile from the mouse instead of
    trusting the cached state. A profile changed with the mouse's own button, or
    by another tool, was silently reverted by the save.
  - A failed identity read on a later refresh no longer drops the known model.
    It used to count as a normal poll miss and downgrade a PAW3950Ultra mouse to
    an unknown step-50 one, misreading every DPI value five-fold.
  - The v1 controller refuses writes itself when the model is read-only. Only the
    worker and the CLI checked before, so a direct caller could write to an
    experimental model.
  - `atkctl dpi --stage 0` is rejected. It used to be falsy and silently edit the
    active stage; `--stage` is 1-based.
- **One source of capabilities.** The worker now publishes the controller's own
  capabilities with the state, and the window and tray consume them instead of
  rebuilding from the model tables. A cabled A9 Pro Max 2.0 offered 125-1000 Hz
  in the GUI while `atkctl` offered up to 8000 Hz, and the tray resolved every
  mouse through the v1 table, so an R1 NK appeared as "VXE R1 Pro".
- **Timing**
  - a receiver that never answers command `0x03` is skipped after three misses
    instead of costing 1.8 s on every live poll;
  - a sleeping mouse costs one exchange per identity attempt instead of three: a
    failed connect is 1.8 s rather than 5.4 s.
- **Transport**
  - `0xFF05` memory replies are matched against the requested address, so a late
    reply can no longer be read as the next chunk and shift the DPI table that
    the following write sends back;
  - `--debug` now reaches the controller and the transport instead of being
    dropped in the CLI;
  - `0xFF05` support reports include the memory blocks (DPI table, sensor mode,
    LED, buttons). They were empty, so a `--raw` report from an unknown v2 mouse
    carried no device bytes at all.
- `373b:1216` (the NearLink NANO receiver) is in the receiver ceiling table now,
  instead of being detected only by its product name.
- `0xFF05` setters apply the same local checks as v1: polling must be in the
  link's rate list, stage colours and button remapping must be supported, and
  lift-off must be one of the model's choices.
- The v2 notice no longer claims the firmware is unvalidated; it says what is
  true (read-back verified, not yet verified control-by-control).

## 0.9.3 — 2026-11-13

- Wrote down what the two status words actually mean, because the README and
  `CONTRIBUTING.md` disagreed. **Verified** now means the contribution
  checklist: each advertised setting tested on that exact model, read back,
  restored, power-cycle checked, and the evidence recorded in
  `docs/PROTOCOL.md`. **Experimental** is now an explicit tier below it: an
  owner's report plus the family's proven transport, writes enabled and verified
  by read-back, but not tested control by control. The ladder and the checks are
  in [docs/TESTING.md](docs/TESTING.md) and
  [CONTRIBUTING.md](CONTRIBUTING.md).
- Accordingly the **ATK Dragonfly A9 Pro Max 2.0 returns to experimental**. Its
  owner confirmed that settings work and persist across a power cycle on both
  links, which is enough to keep it writable but not enough for the verified
  claim added in 0.9.1; that claim was ahead of the evidence. Nothing changes in
  the app. Once the control-by-control checks are recorded in `docs/PROTOCOL.md`
  it moves back to verified.
- Experimental models are tracked with a `needs-verification` label on their
  issue, which may be closed as soon as support ships.

## 0.9.2 — 2026-11-13

- Added **experimental support for the VXE R1 SE+** (CID/MID `2,31`, firmware
  `3.15`, over the `373b:1085` 1K receiver). It was already recognized from the
  read-only catalog; the owner's report shows a complete `0xFF02` register set —
  four user DPI stages inside the sensor table, the six standard button records,
  a readable rotation row and lighting — so polling, DPI stages and colours,
  lift-off, debounce, sleep timer, Motion Sync, straight-line, ripple, rotation,
  lighting, profiles and button remapping are now writable. The sensor stays
  PAW3395SE with the 100-18,000 DPI table, which matches the retail
  specification. No write has been tested on hardware yet.
- The read-only catalog drops to 25 entries, since `2,31` moved into the
  supported model table.

## 0.9.1 — 2026-11-13

- Promoted the **ATK Dragonfly A9 Pro Max 2.0** from experimental to verified.
  The hardware owner tested both links (`373b:1264` cable, `373b:11dc` 8K
  dongle) and confirmed that settings are written correctly and survive a power
  cycle. Its identity table, sensor, polling ceiling and capability flags were
  already correct in 0.9.0. (Reversed in 0.9.3: the confirmation did not cover
  each control, which is what the verified claim requires.)
- **Lift-off on `0xFF05` mice is a vendor level, not millimetres.** The value is
  `config[5] + 1`, so a firmware that uses levels outside the known 1/2/3 map
  used to display `Lift-off: unknown`, which looked like a read failure. It now
  prints `Lift-off: level 6 (unmapped)`, the Device page note says the same, and
  the report keeps the raw number. Mapping the extra levels needs the vendor's
  option list for that model.
- The **receiver firmware** is now read for `0xFF05` receivers (command `0x88`)
  and shown in `atkctl status`, the Device page and support reports. The A9 Pro
  Max 2.0 reports mouse `1.0.14` and dongle `1.0.19`; previously only the mouse
  version was visible.
- Corrected the **ATK A9 Ultimate sensor** to `PAW3950Ultra`. ATK HUB's own model
  table lists CID/MID `1,3` as an Ultimate-tier mouse with that sensor, and the
  unit's stage records decode as 400/800/1600/3200 under the ultra encoding
  instead of 2000/4000/8000/16000 under step-50. The DPI values it displayed
  were therefore five times too high, and a DPI set from the app landed five
  times too low on the mouse. The DPI list was also capped at 30,000 instead of
  42,000.
- Cross-checked the `0xFF05` command map and the CID/MID table against the
  reference reverse engineering: all command numbers, the memory map and the
  identity entries for `2,1`, `2,8`, `2,14` and `2,27` agree.

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
