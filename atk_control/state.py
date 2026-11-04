"""UI-facing device state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Button:
    name: str
    action: str
    raw: str = ""
    action_id: str = ""


@dataclass
class MouseState:
    # Identity / link
    vendor_id: int = 0
    product_id: int = 0
    usb_name: str = ""
    cid: int | None = None
    mid: int | None = None
    model_name: str = ""
    brand: str = "ATK"
    sensor: str = ""
    firmware: str = ""
    usb_bcd: str = ""
    via_receiver: bool = False
    receiver_name: str = ""
    receiver_pid: int | None = None
    rf_id: str = ""
    receiver_online: bool | None = None
    wired: bool = False
    read_only: bool = False

    # Telemetry
    battery: int | None = None
    charging: bool | None = None
    voltage_mv: int | None = None

    # DPI
    dpi: int = 800
    dpi_y: int = 800
    stages: list[tuple[int, int]] = field(default_factory=list)
    active_stage: int = 0
    stage_count: int = 1
    stage_colors: list[str] = field(default_factory=list)

    # Performance
    polling_rate: int = 1000
    lod_code: int | None = None
    lod_mm: float | None = None
    debounce_ms: int | None = None
    motion_sync: bool | None = None
    sleep_seconds: int | None = None
    ripple_control: bool | None = None
    straight_line: bool | None = None
    angle_enabled: bool | None = None
    angle_degrees: int | None = None
    performance_mode: bool | None = None
    sensor_mode: int | None = None
    long_range: bool | None = None

    # Lighting
    led_mode: int | None = None
    led_brightness: int | None = None
    led_speed: int | None = None

    # Stored configuration
    profile: int | None = None
    profile_count: int = 4
    buttons: list[Button] = field(default_factory=list)

    # Support flags discovered while reading
    supports_angle: bool = False
    supports_performance_mode: bool = False
    supports_sensor_max: bool = False
    supports_button_remap: bool = False
    supports_long_range: bool = False
    supports_lighting: bool = False
    supports_stage_colors: bool = False

    @property
    def connected_name(self) -> str:
        return self.model_name or self.usb_name or "ATK/VXE mouse"

    @property
    def identity(self) -> str:
        if self.cid is None or self.mid is None:
            return "—"
        return f"{self.cid}, {self.mid}"

    @property
    def link_label(self) -> str:
        if self.wired:
            return "USB cable"
        if self.via_receiver:
            return self.receiver_name or "Wireless receiver"
        return "2.4 GHz wireless"
