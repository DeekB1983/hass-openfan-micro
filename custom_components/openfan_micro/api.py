"""Low-level HTTP API client for OpenFAN Micro (firmware v20240319)."""
from __future__ import annotations
from typing import Any, Tuple, Optional
import logging
import aiohttp
import async_timeout
import json

_LOGGER = logging.getLogger(__name__)

class OpenFanApi:
    """API client for OpenFAN Micro."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        self._poll_interval: int = 5
        self._min_pwm: int = 0
        self._failure_threshold: int = 3
        self._stall_consecutive: int = 3

    # -------------------- HTTP helpers --------------------

    async def _get_any(self, path: str) -> tuple[int, str, Optional[dict]]:
        """HTTP GET returning (status, text, JSON if available)."""
        url = f"http://{self._host}{path}"
        async with async_timeout.timeout(6):
            async with self._session.get(url) as resp:
                status = resp.status
                text = await resp.text()
                data: Optional[dict] = None
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    # Not JSON, leave data=None
                    pass
        _LOGGER.debug("OpenFAN %s GET %s -> %s %s", self._host, path, status, data or text)
        return status, text, data

    async def _get_json(self, path: str) -> dict:
        """HTTP GET that requires JSON."""
        status, text, data = await self._get_any(path)
        if status >= 400:
            raise RuntimeError(f"HTTP {status} for {path}: {text}")
        if not isinstance(data, dict):
            try:
                data = json.loads(text)
            except Exception as exc:
                raise RuntimeError(f"Non-JSON response for {path}: {text}") from exc
        return data

    def _is_ok_payload(self, payload: Optional[dict], text: str = "") -> bool:
        """Return True if payload/text indicates success."""
        if isinstance(payload, dict):
            val = str(payload.get("status", "")).lower()
            if val in ("ok", "success", ""):
                return True
        if text.strip().upper() in ("OK", "SUCCESS", ""):
            return True
        return False

    # -------------------- FAN PWM / STATUS --------------------

    async def get_status(self) -> Tuple[int, int]:
        """Return (rpm, pwm_percent)."""
        data = await self._get_json("/api/v0/fan/status")
        return self._parse_status_payload(data)

    async def set_pwm(self, value: int) -> dict[str, Any]:
        """Set PWM 0..100 using the correct endpoint."""
        value = max(0, min(100, int(value)))
        path = f"/api/v0/fan/0/set?value={value}"

        _LOGGER.debug("OpenFAN Micro attempting PWM set to %s via endpoint %s", value, path)

        status, text, data = await self._get_any(path)

        _LOGGER.debug(
            "OpenFAN Micro set PWM %s via %s -> HTTP %s, response: %s",
            value, path, status, data or text
        )

        if status >= 400 or not self._is_ok_payload(data, text):
            raise RuntimeError(f"PWM set failed: {status}")

        return data or {"status": "ok"}

    def _parse_status_payload(self, data: dict) -> Tuple[int, int]:
        """Normalize RPM and PWM percent from API response."""
        container: dict[str, Any] = data.get("data", data)
        rpm = int(container.get("rpm", 0))
        pwm = int(container.get("pwm_percent", container.get("pwm", 0)))
        return max(0, rpm), max(0, min(100, pwm))

    # -------------------- LED & SUPPLY VOLTAGE --------------------

    async def get_openfan_status(self) -> Tuple[bool, bool]:
        """Return (led_enabled, is_12v)."""
        data = await self._get_json("/api/v0/openfan/status")
        container = data.get("data", data)
        led = str(container.get("act_led_enabled", "false")).lower() in ("true", "1", "yes", "on")
        is_12v = str(container.get("fan_is_12v", "false")).lower() in ("true", "1", "yes", "on")
        return led, is_12v

    async def led_set(self, enabled: bool) -> dict:
        """Enable/disable LED."""
        path = "/api/v0/led/enable" if enabled else "/api/v0/led/disable"
        status, text, data = await self._get_any(path)
        if status >= 400:
            raise RuntimeError(f"LED set failed: {status} {text}")
        if not self._is_ok_payload(data, text):
            _LOGGER.debug("OpenFAN Micro: LED set non-OK body: %s", data or text)
        return data or {"status": "ok"}

    async def set_voltage_12v(self, enabled: bool) -> dict:
        """Switch fan voltage to 12V or 5V."""
        path = "/api/v0/fan/voltage/high?confirm=true" if enabled else "/api/v0/fan/voltage/low?confirm=true"
        status, text, data = await self._get_any(path)
        if status >= 400:
            raise RuntimeError(f"Voltage set failed: {status} {text}")
        if not self._is_ok_payload(data, text):
            _LOGGER.debug("OpenFAN Micro: voltage set non-OK body: %s", data or text)
        return data or {"status": "ok"}
