# ATK Control documentation

The [project README](../README.md) is the place to start for an overview,
supported hardware and quick installation. These guides go into detail.

## For users

| Guide | What it covers |
| --- | --- |
| [Installation](INSTALLATION.md) | AUR, Flatpak, AppImage, source installs, dependencies and udev |
| [CLI reference](CLI.md) | Every command, JSON output, exit codes and scripting |
| [Troubleshooting](TROUBLESHOOTING.md) | Detection, permissions, tray, persistence and packaging problems |
| [Device support reports](DEVICE_REPORTS.md) | What to send, what is redacted and how to request support |
| [Testing a mouse](TESTING.md) | Read-only verification, reversible write checks and the WSL2 caveat |

## For contributors

| Guide | What it covers |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | Development setup, tests, linting and pull requests |
| [Protocol notes](PROTOCOL.md) | v1 and v2 hardware protocol, registers and evidence |
| [Security policy](../SECURITY.md) | Permission scope, local-only design and reporting vulnerabilities |
| [Changelog](../CHANGELOG.md) | Release history and notable fixes |

## Conventions

- Installation commands assume the release matching the files in this
  repository. Use the assets from the [latest release](https://github.com/NasirA1991/atk-control/releases/latest).
- Commands that write settings require the mouse's hidraw permissions; see
  [Installation](INSTALLATION.md#hid-permissions).
- Raw register data is opt-in and should only be shared when a maintainer asks
  for it.
- The application never needs root. See the
  [security section](../README.md#security-and-permissions).
