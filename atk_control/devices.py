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
    "PAW3311": Sensor("PAW3311", "step50", 200, 15000),
    "PAW3315": Sensor("PAW3315", "step50", 200, 16000),
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
    Model(2, 114, "VXE R1 Ultra", "VXE", "PAW3395", 8000),
)

MODEL_BY_CIDMID: dict[tuple[int, int], Model] = {(m.cid, m.mid): m for m in MODELS}
MODEL_BY_USB: dict[tuple[int, int], Model] = {}
for _model in MODELS:
    for _usb in _model.usb_ids:
        MODEL_BY_USB[_usb] = _model


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

    @property
    def link_ceiling(self) -> int:
        if self.receiver is not None:
            return min(self.receiver.max_polling, self.model.max_polling if self.model else 8000)
        return min(1000, self.model.max_polling if self.model else 1000)


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
    ceiling = 1000
    if receiver is not None:
        ceiling = min(receiver.max_polling, model.max_polling if model else 8000)
    elif model is not None:
        ceiling = min(1000, model.max_polling)
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
    )


def default_capabilities() -> Capabilities:
    return capabilities_for(model=None, receiver=None)
