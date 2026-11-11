# Requesting support for another mouse

ATK Control is built and extended from **read-only hardware reports**. If your
ATK or VXE mouse is not listed, or a setting does not work, a report is the
fastest way to get it supported.

## 1. Generate the report

In the app, open **Device → Missing your ATK/VXE mouse? → Save support report**.

Or from a terminal:

```bash
atkctl support
```

This writes a file named `atk-control-report-YYYYMMDD-HHMM.md` in the current
directory and prints the support-request URL. You can choose another location:

```bash
atkctl support -o ~/atk-r1-report.md
```

If ATK Control cannot open a supported configuration interface, it writes a
**discovery report** instead (`atk-control-discovery-*.md`). That report lists
every ATK/VXE HID interface, its USB ID, vendor usage pages, report IDs and
raw HID report descriptor. It does not open an unknown device for writing.
`atkctl scan --all` prints the same candidate interfaces without writing a
file. For an experimental battery-only `0xFF05` device, `atkctl support` also
returns this discovery report so the descriptor is captured alongside the
battery result.

`atkctl report` prints the same content to the terminal instead. If a
maintainer asks for raw bytes, add `--raw` (and review the result):

```bash
atkctl support --raw
atkctl report --raw
```

## 2. What is in it?

A normal report contains:

- distribution, kernel and session details;
- all detected ATK/VXE configuration interfaces;
- model, sensor, USB IDs, device revision, firmware and CID/MID;
- battery and link telemetry;
- every setting ATK Control can read;
- the read-only button map.

A discovery report is generated when no supported interface can be opened. It
contains the system details plus every ATK/VXE HID interface, its USB ID,
interface name, vendor usage pages, report IDs and HID report descriptor.

Raw register bytes are omitted by default. They are the most useful part when
adding a new model, but they are undocumented device data, so they are opt-in.
Enable **Include raw registers** in the app or pass `--raw` when asked.

It is generated locally and is **never uploaded automatically**.

## 3. What is removed?

- the full RF identifier (only the first byte remains);
- USB serial numbers;
- your host name and user file paths;
- raw register bytes, unless you explicitly opt in.

The report does include the USB product string and HID node names, which are
useful for identification. Please still open the file and give it a quick look
before uploading.

## 4. Open the support request

Go to the [device support issue](https://github.com/NasirA1991/atk-control/issues/new?template=device-report.yml),
fill in the model and USB IDs, and attach the `.md` file.

The ideal report includes:

1. the mouse connected **over its cable**, if it has one;
2. the mouse through **each receiver** you own (1K, 4K or 8K);
3. whether ATK Control detected the mouse as read-only;
4. which settings worked and which did not.

## What happens next

New models and receivers are added to the small device database only after the
identity and register layout are understood. A report is enough to start; any
write is tested against real hardware and verified by reading the value back.
