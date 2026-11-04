# Device reports

Compx Control includes a read-only support report so another COMPX-based mouse
can be supported without guesswork.

Generate it from the app with **Device → Save report**, or from a terminal:

```bash
compxctl report -o ~/compx-report.md
```

The report contains:

- distribution, kernel and session type;
- model name, sensor, USB IDs, reported firmware and CID/MID;
- battery/link telemetry;
- the settings the app can currently read;
- the read-only button map;
- no full RF identifier, USB serial number or home-directory paths.

It is written locally and is **never uploaded automatically**. Open the file,
check it, then attach it to the
[device support issue](https://github.com/NasirA1991/compx-control/issues/new?template=device-report.yml)
with a short description of what works and what does not.
