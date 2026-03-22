from __future__ import annotations
import logging
import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OpenFanApi

_LOGGER = logging.getLogger(__name__)


class OpenFanCoordinator(DataUpdateCoordinator[dict]):
    """Production coordinator with smart polling + fast response on control."""

    def __init__(self, hass: HomeAssistant, api: OpenFanApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="OpenFAN Micro",
            update_interval=timedelta(seconds=30),  # default slow polling
        )

        self.api = api

        # --- reliability tracking ---
        self._consecutive_failures = 0
        self._forced_unavailable = False
        self._last_error: str | None = None

        # --- stall detection ---
        self._consecutive_stall = 0
        self._notified_stall = False

        # --- smart polling ---
        self._fast_interval = 5
        self._slow_interval = 30

        # number of fast cycles after a change (IMPORTANT)
        self._fast_cycles_remaining = 0

        # reduce secondary API calls
        self._slow_counter = 0

    # =========================================================
    # 🔥 FAST POLL TRIGGER (called from fan.py)
    # =========================================================

    def force_fast_poll(self) -> None:
        """Trigger immediate refresh + short burst of fast polling."""
        self._fast_cycles_remaining = 3  # ← 3 cycles = ~15 seconds responsiveness
        self.update_interval = timedelta(seconds=self._fast_interval)

        _LOGGER.debug(
            "[%s] OpenFAN: fast poll requested (%s cycles)",
            time.strftime("%H:%M:%S"),
            self._fast_cycles_remaining,
        )

        # Force immediate refresh (bypasses HA debounce)
        self.hass.async_create_task(self._async_force_refresh())

    async def _async_force_refresh(self) -> None:
        """Force immediate refresh safely."""
        try:
            _LOGGER.debug("[%s] OpenFAN: forcing immediate refresh", time.strftime("%H:%M:%S"))
            await self.async_refresh()
        except Exception as err:
            _LOGGER.debug("OpenFAN: force refresh failed: %r", err)

    # =========================================================
    # 🔄 MAIN UPDATE LOOP
    # =========================================================

    async def _async_update_data(self) -> dict:
        try:
            rpm, pwm = await self.api.get_status()

            # --- reset failures ---
            self._consecutive_failures = 0
            self._forced_unavailable = False
            self._last_error = None

            # =====================================================
            # 📉 REDUCE SECONDARY API CALLS
            # =====================================================
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

            # =====================================================
            # 🧠 STALL DETECTION
            # =====================================================
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
                    _LOGGER.debug("[%s] OpenFAN: stall detected", time.strftime("%H:%M:%S"))
                except Exception:
                    pass

            if not stalled_flag:
                self._notified_stall = False

            # =====================================================
            # 📦 FINAL DATA
            # =====================================================
            data = {
                "rpm": int(rpm),
                "pwm": int(pwm),
                "led": bool(led),
                "is_12v": bool(is_12v),
                "stalled": stalled_flag,
            }

            # =====================================================
            # ⚡ FAST → SLOW TRANSITION LOGIC (CRITICAL)
            # =====================================================
            if self._fast_cycles_remaining > 0:
                self._fast_cycles_remaining -= 1

                _LOGGER.debug(
                    "[%s] OpenFAN: fast polling (%s cycles remaining)",
                    time.strftime("%H:%M:%S"),
                    self._fast_cycles_remaining,
                )

                if self._fast_cycles_remaining == 0:
                    self.update_interval = timedelta(seconds=self._slow_interval)
                    _LOGGER.debug(
                        "[%s] OpenFAN: returning to slow polling (%ss)",
                        time.strftime("%H:%M:%S"),
                        self._slow_interval,
                    )

            # =====================================================
            # 🪵 DEBUG OUTPUT
            # =====================================================
            _LOGGER.debug(
                "[%s] OpenFAN: poll result rpm=%s pwm=%s led=%s 12v=%s stalled=%s",
                time.strftime("%H:%M:%S"),
                data["rpm"],
                data["pwm"],
                data["led"],
                data["is_12v"],
                data["stalled"],
            )

            return data

        except Exception as err:
            self._last_error = str(err)
            self._consecutive_failures += 1

            fail_thresh = int(getattr(self.api, "_failure_threshold", 3) or 3)
            if self._consecutive_failures >= fail_thresh:
                self._forced_unavailable = True

            _LOGGER.error(
                "[%s] OpenFAN update failed (%s): %r",
                time.strftime("%H:%M:%S"),
                getattr(self.api, "_host", "?"),
                err,
            )

            raise UpdateFailed(f"Failed to update OpenFAN Micro: {err}") from err
