# Contributing

## Device support reports

Use the device-support issue template. A useful report includes the mouse and
receiver identity, firmware version and a support report. Raw register bytes
are opt-in and should be reviewed before sharing.

## Model status and write support

A model is in one of three states. `README.md` shows the current state, and
`docs/TESTING.md#promotion-criteria` lists the checks behind each one.

### Read-only (catalog)

The identity is recognized from the vendor device list, or from a report that
has not been acted on. Identity, battery and readable settings are shown and
every write is rejected. This is the default for any new identity.

### Experimental

A read-only model becomes experimental when all of these are true:

1. a device report from the owner of that exact model is attached to an issue;
2. the report decodes completely with the protocol this app already implements
   for that family — no guessed field offsets or command numbers;
3. the capability flags come from that evidence, not from the marketing name.

Writes are enabled at this stage, every write is verified by read-back, and the
model stays labelled **experimental** in `README.md`. The issue is labelled
`needs-verification` and may be closed once support ships.

### Verified

An experimental model becomes verified only when the owner reports back from the
exact model on hardware and all of the following are recorded:

1. reads work consistently on that link;
2. each advertised setting is tested on hardware and verified by read-back;
3. the original value is restored after testing;
4. power-cycle persistence is checked for the settings the UI claims to commit;
5. the evidence is recorded in `docs/PROTOCOL.md`.

Until step 5 is written down, the model stays experimental. "The settings work"
proves that writes land, not that every advertised control is correct, so it is
not enough on its own. A control that cannot be restored from the app — an
unmapped lift-off level, for example — is not tested at all, and the limitation
is stated instead.

Unknown models must remain read-only.

## Code changes

- Run `python3 -m unittest discover -s tests -v`.
- Run `ruff check .` and `mypy atk_control`.
- Keep protocol changes small and explain the hardware evidence.
- Do not add network access or telemetry.
