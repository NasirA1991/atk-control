# ATK/VXE configuration protocol notes

This document is for maintainers and for auditing how ATK Control talks to
the mouse. End users do not need it.

## Transport

The configuration collection is `usage page 0xff02`, `usage 0x0002`. Linux
exposes it as a hidraw node. Commands use HID report id `0x08`:

```
08 <cmd> <status> <addr_hi> <addr_lo> <len> <data...> <checksum>
```

The 17 bytes (report id plus 16 payload bytes) sum to `0x55` modulo 256. Reads
use command `0x08`; writes use `0x07`. Battery, identity and firmware use
commands `0x04`, `0x10` and `0x12`.

The app verifies every reply checksum and reads every write back.

## Registers used

| Address | Meaning |
|---|---|
| `0x0000` | polling rate, DPI stage count, active stage (value/checksum pairs) |
| `0x000a` | lift-off distance |
| `0x000c` | four-byte DPI stage records |
| `0x002c` | DPI stage colours (four bytes per colour, in groups of two) |
| `0x004c` | DPI indicator LED effect, brightness, speed |
| `0x00a9` | debounce, Motion Sync, sleep, straight-line, ripple |
| `0x00b5` | sensor performance mode |
| `0x00bd` | sensor rotation angle and enable switch (may be unprogrammed) |
| `0x0060`–`0x0074` | read-only button assignments (four bytes each) |

Polling codes: `08`=125, `04`=250, `02`=500, `01`=1000, `10`=2000,
`20`=4000, `40`=8000 Hz.

## Receiver identification

Receivers use shared USB product IDs and answer for the paired mouse. The
mouse model therefore comes from CID/MID (`0x10`), resolved against the small
model table in `atk_control/devices.py`. Unknown models are deliberately
read-only.

Receiver ceilings currently known to the app: `373b:1040` (MAD 8K) = 8000 Hz,
`11a9`/`f505`/`f58d` = 4000 Hz, most 1K receivers = 1000 Hz.

## Hardware evidence

Verified on a MAD R + (CID/MID `2,54`, PAW3395) through the MAD 8K dongle
(`373b:1040`, USB revision 2.15) on CachyOS, kernel 7.3.1:

- read of identity, battery, two DPI stages, stage colours, advanced settings,
  sensor mode, lighting, profiles and buttons;
- reversible writes and read-back for polling (1000 → 8000 → 1000 Hz), DPI,
  active stage, stage colour, lift-off, debounce, Motion Sync, ripple,
  straight-line, sleep, performance mode and DPI LED;
- profile switch 1 → 2 → 1 with identical settings restored;
- receiver online telemetry.

The current firmware leaves the sensor-rotation row unprogrammed, so that
control is hidden. Firmware command `0x12` works after the wireless mouse has
answered CID/MID and is awake.

Verified on a VXE R1 Pro (CID/MID `2,8`, PAW3395) through its VXE 1K receiver
(`3554:f58a`, USB revision 1.09):

- identity, battery, four DPI stages, stage colours, advanced settings,
  sensor mode, lighting, profile and button reads;
- reversible writes with read-back for polling (1000 → 500 → 1000 Hz), DPI,
  active stage, stage colour, lift-off, debounce, Motion Sync, ripple,
  straight-line, sleep, performance mode and DPI LED;
- 1K receiver ceiling correctly limits the UI and CLI to 1000 Hz;
- sensor-rotation row is unprogrammed and the control is hidden;
- firmware command `0x12` returns the mouse firmware once awake.

## VXE 4K receiver

The same VXE R1 Pro was then tested through a VGN/VXE 4K receiver
(`3554:f505`, USB revision 1.09, product string `Compx VGN Dragonfly 4K
Receiver`). The mouse answered with CID/MID `2,8` once awake.

All of the 1K tests were repeated over this receiver, and additionally:

- 4K receiver ceiling was reported as 4000 Hz;
- polling 1000 → 4000 → 2000 → 1000 Hz was written and read back;
- all touched registers were restored byte-for-byte afterwards.

The receiver reports the paired mouse online over command `0x03`; the mouse
still has to be awake before its configuration channel answers.

## Safety

Only model-table entries can be written. Writes use local read-modify-write for
multi-field registers, and the controller verifies each value by reading it
back. Unknown models remain read-only.

## Credits

Protocol facts were recovered from the public ATK HUB WebHID driver and
corroborated with readback on physical hardware. ATK Control is independent
and not affiliated with ATK or VXE.

## Additional ATK HUB parity work

Validated against the VXE R1 Pro over the 4K receiver on 2026-11-04:

- firmware command `0x12` succeeds **after** the mouse has answered CID/MID;
  the tested unit reported `1.20`. The earlier read failure happened because the
  query was sent before the sleeping mouse was awake.
- lift-off codes follow the vendor UI: `1` = 1 mm, `2` = 2 mm, `3` = 0.7 mm
  (0.7 mm is only offered on PAW3950/PAW3950DM). The prior 1/4/11 mapping was
  wrong for this family.
- sensor sampling modes in register `0x00b5` are `0` Basic, `1` Competitive,
  `2` Competitive MAX and `3` Competitive MAX 13K. Mode `2` was written,
  verified and restored to `1`.
- the six button records at `0x0060` were written and read back. Forward was
  remapped to Back, then restored. Standard mouse and DPI actions are supported;
  macro/shortcut records are preserved.
- the DPI stage count was increased from four to five and reduced back to four;
  the final raw snapshot was restored. Stage count lives in the system row.

## Onboard profile commit

The COMPX EEPROM writes update the active working profile. They are visible to
immediate read-back but are not necessarily in flash. The firmware flushes the
working profile when the active profile changes.

ATK Control therefore commits after a write batch by switching to another
profile and back, preserving the original active profile. Verified on both
tested mice:

- VXE R1 Pro, profile 1, stage 1: 1200 DPI survived a full power cycle.
- MAD R +, profile 1, stage 2: 1200 DPI survived a full power cycle.

The test values were restored to the original 1600 DPI afterward.
