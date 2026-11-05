"""Pure helpers for deciding when the GTK window needs to redraw.

Keeping this out of the GTK module makes the expensive-update contract
testable without importing GTK.
"""

from __future__ import annotations

from .state import MouseState


def state_signature(state: MouseState) -> tuple:
    """Fields whose values are actually rendered by the window.

    Deliberately excludes receiver_online, rf_id and voltage: those change
    frequently but are not displayed, and including them caused a full UI
    relayout every poll.
    """
    return (
        state.battery, state.charging, state.wired, state.read_only,
        state.model_name, state.brand, state.sensor, state.firmware,
        state.usb_bcd, state.cid, state.mid, state.receiver_name,
        state.receiver_pid, state.dpi, state.dpi_y, tuple(state.stages),
        tuple(state.stage_colors), state.active_stage, state.stage_count,
        state.polling_rate, state.lod_code, state.lod_mm, state.debounce_ms,
        state.motion_sync, state.sleep_seconds, state.ripple_control,
        state.straight_line, state.angle_degrees, state.angle_enabled,
        state.performance_mode, state.sensor_mode, state.long_range,
        state.led_mode, state.led_brightness, state.led_speed, state.profile,
        tuple((button.name, button.action, button.action_id) for button in state.buttons),
        state.supports_angle, state.supports_performance_mode,
        state.supports_sensor_max, state.supports_button_remap,
        state.supports_long_range, state.supports_lighting,
        state.supports_stage_colors,
    )
