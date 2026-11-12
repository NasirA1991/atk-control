"""Supported ATK/VXE mice, sensors and transport capabilities."""

from __future__ import annotations

from dataclasses import dataclass

from .protocol import (
    DEFAULT_DEBOUNCE_OPTIONS,
    DEFAULT_SLEEP_OPTIONS,
    POLLING_CODES,
    RECEIVER_CEILINGS,
    RECEIVER_NAMES,
    dpi_values,
)


@dataclass(frozen=True)
class Sensor:
    name: str
    family: str
    min_dpi: int
    max_dpi: int

    def options(self) -> list[int]:
        return dpi_values(self.min_dpi, self.max_dpi, self.family)


SENSORS: dict[str, Sensor] = {
    "PAW3395": Sensor("PAW3395", "step50", 100, 30000),
    "PAW3395SE": Sensor("PAW3395SE", "step50", 100, 18000),
    "PAW3950": Sensor("PAW3950", "step50", 50, 36000),
    "PAW3950Ultra": Sensor("PAW3950Ultra", "ultra", 10, 42000),
    "PAW3950DM": Sensor("PAW3950DM", "step50", 50, 36000),
    "PAW3395Ultra": Sensor("PAW3395Ultra", "step50", 100, 30000),
    "PAW3311": Sensor("PAW3311", "step50", 200, 15000),
    "PAW3315": Sensor("PAW3315", "step50", 200, 16000),
    "CORE26K": Sensor("CORE26K", "step50", 50, 26000),
}

UNKNOWN_SENSOR = Sensor("Unknown sensor", "step50", 50, 30000)


@dataclass(frozen=True)
class Model:
    cid: int
    mid: int
    name: str
    brand: str
    sensor: str
    max_polling: int = 8000
    angle_supported: bool = True
    dpi_lighting: bool = True
    stage_colors: bool = True
    performance_mode: bool = False
    sensor_max: bool = False
    button_remap: bool = False
    bottom_button: bool = True
    usb_ids: tuple[tuple[int, int], ...] = ()
    # Some firmware stores a factory-default button assignment as class 0
    # instead of the explicit class-1 value.  Read that back as the slot's
    # default action rather than "Custom / unsupported".
    normalizes_default_buttons: bool = False
    # Experimental entries are recognized from the public ATK HUB catalog but
    # have not been hardware-validated by this project. They stay read-only.
    experimental: bool = False

    @property
    def sensor_profile(self) -> Sensor:
        return SENSORS.get(self.sensor, UNKNOWN_SENSOR)


# The MAD R family and common VXE R1 variants.  Values are deliberately
# conservative: a control appears only when the family is known to expose it.
MODELS: tuple[Model, ...] = (
    Model(2, 47, "MAD R MAJOR", "ATK", "PAW3950", 8000, bottom_button=False,
          usb_ids=((0x373B, 0x103E),)),
    Model(2, 49, "MAD R", "ATK", "PAW3395", 8000, bottom_button=False,
          usb_ids=((0x373B, 0x103F),)),
    Model(2, 54, "MAD R +", "ATK", "PAW3395", 8000, sensor_max=True,
          button_remap=True, bottom_button=False, usb_ids=((0x373B, 0x104B),)),
    Model(2, 55, "MAD R MAJOR+", "ATK", "PAW3950", 8000, bottom_button=False,
          usb_ids=((0x373B, 0x104C),)),
    Model(2, 133, "MAD R", "ATK", "PAW3950Ultra", 8000, bottom_button=False,
          usb_ids=((0x373B, 0x132B),)),
    Model(2, 7, "VXE R1 Pro", "VXE", "PAW3395", 8000),
    Model(2, 8, "VXE R1 Pro", "VXE", "PAW3395", 8000, sensor_max=True,
          button_remap=True),
    Model(2, 11, "VXE R1", "VXE", "PAW3395", 8000),
    Model(2, 12, "VXE R1", "VXE", "PAW3395", 8000),
    Model(2, 27, "VXE R1 Pro Max", "VXE", "PAW3395", 8000,
          usb_ids=((0x3554, 0xF58C),)),
    Model(2, 28, "VXE R1 Pro Max", "VXE", "PAW3395", 8000,
          usb_ids=((0x3554, 0xF58C),)),
    Model(2, 125, "VXE R1 Pro", "VXE", "PAW3950Ultra", 8000,
          usb_ids=((0x373B, 0x1272),)),
    Model(2, 126, "VXE R1 Pro Max", "VXE", "PAW3950Ultra", 8000,
          usb_ids=((0x373B, 0x1273),)),
    Model(2, 127, "VXE R1", "VXE", "PAW3950Ultra", 8000,
          usb_ids=((0x373B, 0x1271),)),
    Model(2, 39, "ATK X1 Pro Max", "ATK", "PAW3950", 8000,
          usb_ids=((0x373B, 0x1017),)),
    Model(2, 83, "ATK A9 Plus NearLink", "ATK", "PAW3395", 1000),
    # The A9 Ultimate answers CID/MID 1,3: a different CID family from the
    # older 2,x mice, but on the same 0xff02 register layout.  The sensor is
    # not identified yet, so the DPI table stays at the conservative
    # 50-30,000 step-50 range that the unit's own stage records decode with.
    Model(1, 3, "ATK A9 Ultimate", "ATK", "Unknown sensor", 8000,
          button_remap=True, usb_ids=((0x373B, 0x11B6),)),
    Model(2, 114, "VXE R1 Ultra", "VXE", "PAW3395", 8000),
)

# Recognized from the ATK HUB device catalog (v3.2.27) but not validated on
# hardware by this project.  Keep these read-only: the catalog records the
# model/sensor, not proof that the unit uses the v1 16-byte transport or that
# every write is safe.  Promote a model into MODELS only after a report and a
# hardware test.  USB IDs are intentionally omitted for shared receivers; the
# mouse identity (CID/MID) is the reliable key.
EXPERIMENTAL_MODELS: tuple[Model, ...] = (
    Model(2, 36, "ATK F1 Pro", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 37, "ATK F1 Pro Max", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 38, "ATK X1 Pro", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 40, "ATK Z1 Pro", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 41, "ATK Z1 Pro Max", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 42, "ATK F1 Ultimate", "ATK", "PAW3950Ultra", 8000,
          bottom_button=False, stage_colors=False, experimental=True),
    Model(2, 43, "ATK X1 Ultra", "ATK", "PAW3950Ultra", 8000, experimental=True),
    Model(2, 45, "ATK F1 Ultra", "ATK", "PAW3950Ultra", 8000,
          bottom_button=False, stage_colors=False, experimental=True),
    Model(2, 46, "ATK X1 Ultimate", "ATK", "PAW3950Ultra", 8000,
          bottom_button=False, experimental=True),
    Model(2, 50, "ATK F1 Extreme", "ATK", "PAW3950Ultra", 8000,
          bottom_button=False, stage_colors=False, experimental=True),
    Model(2, 53, "ATK Z1 Ultra", "ATK", "PAW3950Ultra", 8000, experimental=True),
    Model(2, 64, "ATK U2 Mini", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 65, "ATK U2 Ultimate", "ATK", "PAW3950Ultra", 8000, experimental=True),
    Model(2, 66, "ATK U2 Ultra", "ATK", "PAW3950", 8000, experimental=True),
    Model(2, 85, "ATK A9 Pro Max", "ATK", "PAW3395Ultra", 1000,
          stage_colors=False, experimental=True),
    Model(2, 87, "ATK A9 Ultra", "ATK", "PAW3950Ultra", 8000,
          stage_colors=False, experimental=True),
    Model(2, 99, "ATK A9", "ATK", "PAW3395SE", 1000,
          stage_colors=False, experimental=True),
    Model(2, 100, "ATK U2 Pro Max", "ATK", "PAW3395Ultra", 8000,
          experimental=True),
    Model(2, 29, "VXE R1 SE", "VXE", "PAW3395SE", 1000, experimental=True),
    Model(2, 31, "VXE R1 SE+", "VXE", "PAW3395SE", 1000, experimental=True),
    Model(2, 63, "VXE R1S+", "VXE", "PAW3311", 1000, experimental=True),
    Model(2, 72, "VXE V3", "VXE", "PAW3311", 1000, experimental=True),
    Model(2, 73, "VXE V3 Pro", "VXE", "PAW3395SE", 1000, experimental=True),
    Model(2, 121, "VXE X3", "VXE", "PAW3315", 1000, experimental=True),
    Model(2, 122, "VXE X3 Pro", "VXE", "PAW3395SE", 1000, experimental=True),
    Model(2, 123, "VXE X3 Turbo", "VXE", "PAW3395SE", 1000, experimental=True),
)

MODEL_BY_CIDMID: dict[tuple[int, int], Model] = {
    (m.cid, m.mid): m for m in MODELS + EXPERIMENTAL_MODELS
}
MODEL_BY_USB: dict[tuple[int, int], Model] = {}
for _model in MODELS + EXPERIMENTAL_MODELS:
    for _usb in _model.usb_ids:
        MODEL_BY_USB[_usb] = _model

# The A9 Pro Max 2.0 generation uses the 0xff05 protocol.  Its identity table
# overlaps CID/MID values used by older mice, so it must be looked up
# separately from the v1 table.
V2_MODELS: tuple[Model, ...] = (
    Model(2, 1, "ATK Dragonfly A9 Pro Max 2.0", "ATK", "PAW3395Ultra", 8000,
          angle_supported=False, dpi_lighting=True, stage_colors=True,
          performance_mode=True, sensor_max=True, button_remap=True,
          bottom_button=True,
          usb_ids=((0x373B, 0x11DC), (0x373B, 0x1264))),
    Model(2, 14, "ATK Dragonfly A9 Pro Max 2.0", "ATK", "PAW3950Ultra", 8000,
          angle_supported=False, dpi_lighting=True, stage_colors=True,
          performance_mode=True, sensor_max=True, button_remap=True,
          bottom_button=True,
          usb_ids=((0x373B, 0x11DC), (0x373B, 0x1264))),
    Model(2, 27, "ATK Dragonfly A9 Pro Max 2.0", "ATK", "PAW3950DM", 8000,
          angle_supported=False, dpi_lighting=True, stage_colors=True,
          performance_mode=True, sensor_max=True, button_remap=True,
          bottom_button=True,
          usb_ids=((0x373B, 0x11DC), (0x373B, 0x1264))),
    # VXE R1 NK (NearLink) reuses CID/MID 2,8, which the v1 table maps to the
    # older wired VXE R1 Pro, but it speaks 0xff05.  Its receiver (373b:1216)
    # also answers for an R1 S NK (2,9) and for the A9 Plus, so the identity -
    # never the USB id - picks the model.  The firmware reports a factory
    # default button as class 0 and the mouse has no lighting, stage colours,
    # rotation or performance-mode hardware.
    Model(2, 8, "VXE R1 NK", "VXE", "PAW3395SE", 1000,
          angle_supported=False, dpi_lighting=False, stage_colors=False,
          performance_mode=False, sensor_max=False, button_remap=True,
          bottom_button=True,
          usb_ids=((0x373B, 0x1216), (0x373B, 0x124C)),
          normalizes_default_buttons=True),
)
V2_MODEL_BY_CIDMID: dict[tuple[int, int], Model] = {
    (model.cid, model.mid): model for model in V2_MODELS
}

@dataclass(frozen=True)
class Receiver:
    product_id: int
    name: str
    max_polling: int


def receiver_for(product_id: int, usb_name: str = "") -> Receiver | None:
    if product_id not in RECEIVER_CEILINGS:
        if not any(word in usb_name.lower() for word in ("dongle", "receiver")):
            return None
    name = RECEIVER_NAMES.get(product_id, usb_name or "Wireless receiver")
    if "vxe" in usb_name.lower() and product_id in (0x11A9, 0xF505, 0xF58D):
        name = "VXE 4K Dongle"
    return Receiver(
        product_id=product_id,
        name=name,
        max_polling=RECEIVER_CEILINGS.get(product_id, 1000),
    )


def v2_model_for(cid: int | None, mid: int | None,
                 vendor_id: int, product_id: int,
                 usb_name: str = "") -> Model | None:
    if cid is None or mid is None:
        # The dongle can be paired with another mouse.  Require the identity
        # command before enabling writes; the USB ID alone is not proof.
        return None
    return V2_MODEL_BY_CIDMID.get((cid, mid))


def model_for(cid: int | None, mid: int | None,
              vendor_id: int, product_id: int,
              usb_name: str = "") -> Model | None:
    if cid is not None and mid is not None:
        model = MODEL_BY_CIDMID.get((cid, mid))
        if model is not None:
            return model
    model = MODEL_BY_USB.get((vendor_id, product_id))
    if model is not None:
        return model
    return None


def fallback_name(usb_name: str) -> str:
    name = usb_name.strip() or "ATK/VXE Mouse"
    lowered = name.lower()
    for word in ("compx", "atk", "vxe"):
        if lowered.startswith(word):
            return name[len(word):].strip() or name.upper()
    return name


@dataclass
class Capabilities:
    name: str
    brand: str
    sensor: Sensor
    model: Model | None
    receiver: Receiver | None
    polling_rates: list[int]
    lift_off_choices: list[tuple[int, float]]
    debounce_options: list[int]
    sleep_options: list[int]
    dpi_lighting: bool
    stage_colors: bool
    angle: bool
    performance_mode: bool
    sensor_max: bool
    button_remap: bool
    profiles: bool
    bottom_button: bool
    dpi_options: list[int]
    link_ceiling: int = 1000


def _with_current(values: list[int], current: int | None) -> list[int]:
    result = list(dict.fromkeys(values))
    if current is not None and current not in result:
        result.append(current)
        result.sort()
    return result


def capabilities_for(
    *,
    model: Model | None,
    receiver: Receiver | None,
    sensor_name: str | None = None,
    active_polling: int = 1000,
    debounce: int | None = None,
    sleep: int | None = None,
    usb_name: str = "",
) -> Capabilities:
    sensor = model.sensor_profile if model else SENSORS.get(sensor_name or "", UNKNOWN_SENSOR)
    if receiver is not None:
        ceiling = min(receiver.max_polling, model.max_polling if model else 8000)
    elif model is not None:
        # A wired link is 1 kHz unless the mouse itself reports a faster rate:
        # the A9 Ultimate answers 4000 Hz while plugged in.
        ceiling = min(model.max_polling, max(1000, active_polling))
    else:
        ceiling = 1000
    polling = [hz for _code, hz in POLLING_CODES if hz <= ceiling]
    polling = _with_current(polling, active_polling)

    # The vendor UI exposes 1 mm / 2 mm for the current ATK/VXE mice; PAW3950
    # and PAW3950DM additionally expose a 0.7 mm option (code 3).
    choices = [(1, 1.0), (2, 2.0)]
    if sensor.name in ("PAW3950", "PAW3950DM"):
        choices.insert(0, (3, 0.7))
    name = model.name if model else fallback_name(usb_name)
    brand = model.brand if model else ("VXE" if "vxe" in usb_name.lower() else "ATK")
    model_source = model
    return Capabilities(
        name=name,
        brand=brand,
        sensor=sensor,
        model=model_source,
        receiver=receiver,
        polling_rates=polling,
        lift_off_choices=choices,
        debounce_options=_with_current(list(DEFAULT_DEBOUNCE_OPTIONS), debounce),
        sleep_options=_with_current(list(DEFAULT_SLEEP_OPTIONS), sleep),
        dpi_lighting=model.dpi_lighting if model else True,
        stage_colors=model.stage_colors if model else True,
        angle=model.angle_supported if model else True,
        performance_mode=model.performance_mode if model else False,
        sensor_max=model.sensor_max if model else False,
        button_remap=model.button_remap if model else False,
        profiles=True,
        bottom_button=model.bottom_button if model else True,
        dpi_options=sensor.options(),
        link_ceiling=ceiling,
    )


def default_capabilities() -> Capabilities:
    return capabilities_for(model=None, receiver=None)
