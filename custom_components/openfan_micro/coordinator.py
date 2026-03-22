"""Coordinator with smart polling, reduced API calls, and stall detection."""
from __future__ import annotations
import logging
import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenFanApi

_LOGGER = logging.getLogger(__name__)


class OpenFanCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, api: OpenFanApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="OpenFAN Micro",
            update_interval=timedelta(seconds=5),
        )

        self.api = api

        # existing
        self._consecutive_failures = 0
        self._forced_unavailable = False
        self._consecutive_stall = 0
        self._notified_stall = False
        self._last_error: str | None = None

        # 🆕 smart polling
        self._fast_interval = 5
        self._slow_interval = 30
        self._last_active = time.monotonic()

        # 🆕 reduce API calls
        self._slow_counter = 0

    async def _async_update_data(self) -> dict:
        try:
            rpm, pwm = await self.api.get_status()

            self._consecutive_failures = 0
            self._forced_unavailable = False
            self._last_error = None

            # 🆕 fetch LED/12V less often
            self._slow_counter += 1

            if self._slow_counter >= 6:
                self._slow_counter = 0
                try:
                    led, is_12v = await self.api.get_openfan_status()
                except Exception:
                    led, is_12v = False, False
            else:
                prev = self.data or {}
                led = prev.get("led", False)
                is_12v = prev.get("is_12v", False)

            # stall detection (unchanged)
            min_pwm = int(getattr(self.api, "_min_pwm", 0) or 0)
            need = int(getattr(self.api, "_stall_consecutive", 3) or 3)

            stalled_now = (pwm > max(0, min_pwm)) and rpm == 0
            self._consecutive_stall = (self._consecutive_stall + 1) if stalled_now else 0
            stalled_flag = self._consecutive_stall >= need

            if stalled_flag and not self._notified_stall:
                self._notified_stall = True
                try:
                    self.hass.bus.async_fire(
                        "openfan_micro_stall", {"host": self.api._host}
                    )
                except Exception:
                    pass

            if not stalled_flag:
                self._notified_stall = False

            data = {
                "rpm": rpm,
                "pwm": pwm,
                "led": led,
                "is_12v": is_12v,
                "stalled": stalled_flag,
            }

            # 🆕 smart polling
            now = time.monotonic()

            if pwm > 0 or (now - self._last_active) < 60:
                new_interval = self._fast_interval
            else:
                new_interval = self._slow_interval

            if self.update_interval.total_seconds() != new_interval:
                _LOGGER.debug(
                    "OpenFAN polling interval change: %ss → %ss",
                    self.update_interval.total_seconds(),
                    new_interval,
                )
                self.update_interval = timedelta(seconds=new_interval)

            return data

        except Exception as err:
            self._last_error = str(err)
            self._consecutive_failures += 1

            if self._consecutive_failures >= self.api._failure_threshold:
                self._forced_unavailable = True

            raise UpdateFailed(f"Update failed: {err}") from err
