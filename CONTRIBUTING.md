# Contributing

## Device support reports

Use the device-support issue template. A useful report includes the mouse and
receiver identity, firmware version and a support report. Raw register bytes
are opt-in and should be reviewed before sharing.

## Write support for a new model

A new model must not be marked write-capable without evidence. At minimum:

1. Reads work consistently on the model.
2. Each enabled setting is tested on hardware with read-back verification.
3. The original value is restored after testing.
4. Power-cycle persistence is checked for settings the UI claims to commit.
5. The evidence is recorded in `docs/PROTOCOL.md`.

Unknown models must remain read-only.

## Code changes

- Run `python3 -m unittest discover -s tests -v`.
- Run `ruff check .` and `mypy atk_control`.
- Keep protocol changes small and explain the hardware evidence.
- Do not add network access or telemetry.
