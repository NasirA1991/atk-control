# COMPX configuration protocol notes

This document is for maintainers and for auditing how Compx Control talks to
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
model table in `compx_control/devices.py`. Unknown models are deliberately
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
control is hidden. Firmware command `0x12` is not forwarded by this dongle.

## Safety

Only model-table entries can be written. Writes use local read-modify-write for
multi-field registers, and the controller verifies each value by reading it
back. Unknown models remain read-only.

## Credits

Protocol facts were recovered from the public ATK HUB WebHID driver and
corroborated with readback on physical hardware. Compx Control is independent
and not affiliated with ATK, VXE or COMPX.
