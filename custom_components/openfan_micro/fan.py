"""Fan entity for OpenFAN Micro with last-speed memory and default first-on speed."""
from __future__ import annotations
from typing import Any
import logging

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add: AddEntitiesCallback,
) -> None:
    """Set up fan entity from config entry."""
    device = getattr(entry, "runtime_data", None)
    if device is None:
        _LOGGER.error("OpenFAN Micro: runtime_data is None (fan)")
        return
    async_add([OpenFan(device, entry)])


class OpenFan(CoordinatorEntity, FanEntity):
    """Fan entity for OpenFAN Micro with default first-on speed and last-speed memory."""

    _attr_supported_features = (
        FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.SET_SPEED
    )

    DEFAULT_FIRST_SPEED = 50  # % default speed for first power-on

    def __init__(self, device, entry: ConfigEntry) -> None:
        super().__init__(device.coordinator)
        self._device = device
        self._entry = entry
        self._host = getattr(device, "host", "unknown")
        self._attr_name = getattr(device, "name", "OpenFAN Micro")
        self._attr_unique_id = f"openfan_micro_fan_{self._host}"

        # Memory of last fan speed (percentage)
        self._last_speed: int | None = getattr(device, "ctrl_state", {}).get("last_speed")

    # ---- device info ----
    @property
    def device_info(self) -> dict[str, Any] | None:
        return self._device.device_info()

    @property
    def available(self) -> bool:
        base = super().available
        forced = getattr(self.coordinator, "_forced_unavailable", False)
        return base and not forced

    # ---- state ----
    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data or {}
        return int(data.get("pwm")) if "pwm" in data else None

    @property
    def is_on(self) -> bool | None:
        p = self.percentage
        return None if p is None else (p > 0)

    # ---- control ----
    async def async_set_percentage(self, percentage: int, **kwargs) -> None:
        """Set fan PWM and request fast poll."""
        opts = self._entry.options or {}
        min_pwm = int(opts.get("min_pwm", 0)) or 1
        if percentage > 0:
            percentage = max(min_pwm, int(percentage))

        try:
            await self._device.api.set_pwm(int(percentage))
            _LOGGER.debug(
                "OpenFAN Micro: PWM set to %s%% for host %s", percentage, self._host
            )
            # Remember last speed in memory and device ctrl_state
            self._last_speed = percentage
            if hasattr(self._device, "ctrl_state"):
                self._device.ctrl_state["last_speed"] = percentage
        except Exception as exc:
            _LOGGER.error("OpenFAN Micro: Failed to set PWM: %s", exc)
            raise

        if hasattr(self.coordinator, "force_fast_poll"):
            self.coordinator.force_fast_poll()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn fan on at specified percentage or remembered/default speed."""
        opts = self._entry.options or {}
        min_pwm = int(opts.get("min_pwm", 0)) or 1

        if percentage is None:
            # Determine speed: last speed, or ctrl_state, else default first-on
            if self._last_speed is not None:
                percentage = self._last_speed
            elif getattr(self._device, "ctrl_state", {}).get("last_speed") is not None:
                percentage = self._device.ctrl_state["last_speed"]
            else:
                percentage = self.DEFAULT_FIRST_SPEED  # first-time default
        await self.async_set_percentage(int(percentage))

    async def async_turn_off(self, **kwargs) -> None:
        """Turn fan off without resetting last speed."""
        try:
            await self._device.api.set_pwm(0)
            # Do NOT reset self._last_speed
        except Exception as exc:
            _LOGGER.error("OpenFAN Micro: Failed to turn off fan: %s", exc)
            raise

        if hasattr(self.coordinator, "force_fast_poll"):
            self.coordinator.force_fast_poll()

    # ---- attributes ----
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        opts = self._entry.options or {}
        ctrl = getattr(self._device, "ctrl_state", {}) or {}
        return {
            "min_pwm": int(opts.get("min_pwm", 0)),
            "min_pwm_calibrated": bool(opts.get("min_pwm_calibrated", False)),
            "temp_control_active": bool(ctrl.get("active", False)),
            "temp_entity": ctrl.get("temp_entity") or opts.get("temp_entity", ""),
            "temp_curve": ctrl.get("temp_curve") or opts.get("temp_curve", ""),
            "temp_avg": ctrl.get("temp_avg"),
            "last_target_pwm": ctrl.get("last_target_pwm"),
            "last_applied_pwm": ctrl.get("last_applied_pwm"),
            "last_speed": self._last_speed or ctrl.get("last_speed"),
            "temp_update_min_interval": int(
                ctrl.get("temp_update_min_interval", opts.get("temp_update_min_interval", 10))
            ),
            "temp_deadband_pct": int(ctrl.get("temp_deadband_pct", opts.get("temp_deadband_pct", 3))),
        }
