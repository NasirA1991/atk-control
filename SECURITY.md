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

## Device permission scope

The udev rule grants the active local user read/write access to every hidraw
node exposed by the supported vendor IDs. That includes the configuration
collection used by ATK Control, but also any input collection from a device
with the same vendor ID. A process running as the same user can therefore read
raw input events from those nodes without ATK Control being involved.

This vendor-wide match is a deliberate compatibility trade-off: interface
numbers and report descriptors vary across receivers and firmware revisions.
Narrowing the rule to the configuration collection is tracked as future work;
until then, install the rule only on machines where the signed-in user is
trusted with raw input access.
