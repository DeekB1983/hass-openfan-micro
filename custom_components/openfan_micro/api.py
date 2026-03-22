"""Low-level HTTP API client for OpenFAN Micro (hardened)."""
from __future__ import annotations

from typing import Any, Tuple, Optional
import logging
import asyncio

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


class OpenFanApi:
    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session

        # Tunables
        self._poll_interval: int = 5
        self._min_pwm: int = 0
        self._failure_threshold: int = 3
        self._stall_consecutive: int = 3

    # -------------------- HTTP helpers --------------------

    async def _get_any(self, path: str) -> tuple[int, str, Optional[dict]]:
        """HTTP GET that returns (status_code, text, json_or_none)."""
        url = f"http://{self._host}{path}"

        # 🆕 small delay to avoid hammering device
        await asyncio.sleep(0.05)

        async with async_timeout.timeout(6):
            async with self._session.get(
                url,
                headers={"Connection": "close"},  # 🆕 disable keep-alive
            ) as resp:
                status = resp.status
                text = await resp.text()
                data = None
                try:
                    data = await resp.json(content_type=None)
                except Exception:
                    pass

        _LOGGER.debug("OpenFAN %s GET %s -> %s %s", self._host, path, status, data or text)
        return status, text, data

    async def _get_json(self, path: str) -> dict:
        status, text, data = await self._get_any(path)

        if status >= 400:
            raise RuntimeError(f"HTTP {status} for {path}")

        if not isinstance(data, dict):
            raise RuntimeError(f"Non-JSON response for {path}: {text}")

        return data

    def _parse_status_payload(self, data: dict) -> Tuple[int, int]:
        container = data or {}

        if not ("rpm" in container or "pwm_percent" in container):
            container = container.get("data", {}) or {}

        rpm = int(float(container.get("rpm", 0)))
        pwm = int(float(container.get("pwm_percent", container.get("pwm", 0))))

        return max(0, rpm), max(0, min(100, pwm))

    # -------------------- FAN --------------------

    async def get_status(self) -> Tuple[int, int]:
        """Return (rpm, pwm_percent)."""
        data = await self._get_json("/api/v0/fan/status")
        return self._parse_status_payload(data)

    async def set_pwm(self, value: int) -> dict[str, Any]:
        value = max(0, min(100, int(value)))

        status, text, data = await self._get_any(f"/api/v0/fan/set?value={value}")

        if status >= 400:
            raise RuntimeError(f"PWM set failed: {status} {text}")

        return data or {"status": "ok"}

    # -------------------- LED & VOLTAGE --------------------

    async def get_openfan_status(self) -> Tuple[bool, bool]:
        data = await self._get_json("/api/v0/openfan/status")

        container = data.get("data", data)

        led = str(container.get("act_led_enabled", "false")).lower() in ("true", "1", "on")
        is_12v = str(container.get("fan_is_12v", "false")).lower() in ("true", "1", "on")

        return led, is_12v
