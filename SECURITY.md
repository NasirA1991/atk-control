# Security policy

ATK Control writes to mouse EEPROM through a vendor HID protocol. Bugs in that
path can change device settings or, in the worst case, leave a device in an
unexpected state.

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** for this repository
(Security → Advisories → Report a vulnerability). Do not open a public issue
before a fix is available.

Include:

- mouse model, receiver model and firmware version
- the exact command or UI action
- whether the device still works and which settings changed
- `atk-control --debug` output
- a support report **without raw registers** unless requested privately

Never attach a full RF ID, serial number or raw register dump to a public issue.
