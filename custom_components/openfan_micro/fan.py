"""Fan entity for OpenFAN Micro with min-PWM clamp, fast-polling, and debug attributes."""
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
    """Fan entity for OpenFAN Micro."""

    _attr_supported_features = (
        FanEntityFeature.SET_PERCENTAGE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    
    def __init__(self, device, entry: ConfigEntry) -> None:
        super().__init__(device.coordinator)
        self._device = device
        self._entry = entry
        self._host = getattr(device, "host", "unknown")
        self._attr_name = getattr(device, "name", "OpenFAN Micro")
        self._attr_unique_id = f"openfan_micro_fan_{self._host}"

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
        min_pwm = int(opts.get("min_pwm", 0))
        if int(percentage) > 0:
            percentage = max(min_pwm, int(percentage))

        try:
            await self._device.api.set_pwm(int(percentage))
            _LOGGER.debug(
                "OpenFAN Micro: PWM set to %s%% for host %s", percentage, self._host
            )
        except Exception as exc:
            _LOGGER.error("OpenFAN Micro: Failed to set PWM: %s", exc)
            raise

        # ⚡ Request fast poll immediately to update HA
        if hasattr(self.coordinator, "force_fast_poll"):
            self.coordinator.force_fast_poll()

        async def async_turn_on(
            self,
            percentage: int | None = None,
            preset_mode: str | None = None,
            **kwargs,
        ) -> None:
            if percentage is None:
                percentage = max(
                    1, self._entry.options.get("min_pwm", 0) or 1
                )
            await self.async_set_percentage(int(percentage))

    async def async_turn_off(self, **kwargs) -> None:
        await self._device.api.set_pwm(0)
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
            "temp_update_min_interval": int(
                ctrl.get("temp_update_min_interval", opts.get("temp_update_min_interval", 10))
            ),
            "temp_deadband_pct": int(ctrl.get("temp_deadband_pct", opts.get("temp_deadband_pct", 3))),
        }
