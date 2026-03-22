"""Low-level HTTP API client for OpenFAN Micro.

Features:
- Robust GET handling (JSON or plain text)
- Firmware compatibility (new/legacy fan status/set endpoints)
- Status payload normalization (top-level vs "data" container)
- LED control and 5V/12V supply switching per documented endpoints
"""
from __future__ import annotations

from typing import Any, Tuple, Optional
import logging
import json

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)


class OpenFanApi:
    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        # Tunables populated from options in __init__.py
        self._poll_interval: int = 5
        self._min_pwm: int = 0
        self._failure_threshold: int = 3
        self._stall_consecutive: int = 3

    # -------------------- HTTP helpers --------------------

async def _get_any(self, path: str) -> tuple[int, str, Optional[dict]]:
    url = f"http://{self._host}{path}"

    await asyncio.sleep(0.05)  # 🆕 small delay

    async with async_timeout.timeout(6):
        async with self._session.get(
            url,
            headers={"Connection": "close"}  # 🆕 disable keep-alive
        ) as resp:
            status = resp.status
            text = await resp.text()
            data = None
            try:
                data = await resp.json(content_type=None)
            except Exception:
                pass

    return status, text, data
    
    async def _get_json(self, path: str) -> dict:
        """HTTP GET that *requires* JSON. Raises on HTTP error or non-JSON."""
        status, text, data = await self._get_any(path)
        if status >= 400:
            _LOGGER.error("OpenFAN %s HTTP %s on %s: %s", self._host, status, path, text)
            raise RuntimeError(f"HTTP {status} for {path}")
        if not isinstance(data, dict):
            _LOGGER.error("OpenFAN %s expected JSON on %s but got: %s", self._host, path, text)
            raise RuntimeError(f"Non-JSON response for {path}")
        return data

    def _is_ok_payload(self, payload: Optional[dict], text: str = "") -> bool:
        """Return True if payload/text indicates success."""
        if isinstance(payload, dict):
            val = str(payload.get("status", "")).lower()
            if val in ("ok", "success", ""):
                return True
        # Some firmwares just return 'OK' or empty body on success
        if text.strip().upper() in ("OK", "SUCCESS", ""):
            return True
        return False

    # -------------------- FAN PWM / STATUS --------------------

    def _parse_status_payload(self, data: dict) -> Tuple[int, int]:
        """Normalize (rpm, pwm%) from possible layouts."""
        container: dict[str, Any] = data or {}
        if not ("rpm" in container or "pwm_percent" in container or "pwm" in container):
            container = container.get("data", {}) or {}

        rpm_raw = container.get("rpm", 0)
        pwm_raw = container.get("pwm_percent", container.get("pwm", container.get("pwm_value", 0)))

        try:
            rpm = int(float(rpm_raw))
        except Exception:
            rpm = 0
        try:
            pwm = int(float(pwm_raw))
        except Exception:
            pwm = 0

        return max(0, rpm), max(0, min(100, pwm))

    async def get_status(self) -> Tuple[int, int]:
        """Return (rpm, pwm_percent). Tries both new and legacy endpoints."""
        last_exc: Optional[Exception] = None
        for path in ("/api/v0/fan/status", "/api/v0/fan/0/status"):
            try:
                data = await self._get_json(path)
                # Some firmwares wrap in {"status":"ok","data":{...}}
                if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
                    data = data["data"]
                return self._parse_status_payload(data)
            except Exception as exc:
                last_exc = exc
                _LOGGER.debug("OpenFAN %s: get_status via %s failed: %r", self._host, path, exc)
        assert last_exc is not None
        raise last_exc

    async def set_pwm(self, value: int) -> dict[str, Any]:
        """Set PWM 0..100; supports both new and legacy endpoints.

        Treats non-JSON 'OK' responses as success.
        """
        value = max(0, min(100, int(value)))
        last_exc: Optional[Exception] = None
        for path in (f"/api/v0/fan/0/set?value={value}", f"/api/v0/fan/set?value={value}"):
            try:
                status, text, data = await self._get_any(path)
                if status < 400 and self._is_ok_payload(data, text):
                    return data or {"status": "ok"}
                raise RuntimeError(f"Bad response on {path}: {status} {text!r}")
            except Exception as exc:
                last_exc = exc
                _LOGGER.debug("OpenFAN %s: set_pwm via %s failed: %r", self._host, path, exc)
        assert last_exc is not None
        raise last_exc

    # -------------------- LED & SUPPLY VOLTAGE --------------------

    async def get_openfan_status(self) -> Tuple[bool, bool]:
        """Return (led_enabled, is_12v) from /api/v0/openfan/status."""
        data = await self._get_json("/api/v0/openfan/status")
        # expected: {"status":"ok","data":{"act_led_enabled":"true","fan_is_12v":"true"}}
        container = data.get("data", data)
        led_raw = str(container.get("act_led_enabled", "false")).strip().lower()
        v12_raw = str(container.get("fan_is_12v", "false")).strip().lower()
        led = led_raw in ("true", "1", "yes", "on")
        is_12v = v12_raw in ("true", "1", "yes", "on")
        return led, is_12v

    async def led_set(self, enabled: bool) -> dict:
        """Enable/disable activity LED (supported firmwares)."""
        path = "/api/v0/led/enable" if enabled else "/api/v0/led/disable"
        status, text, data = await self._get_any(path)
        if status >= 400:
            raise RuntimeError(f"LED set failed: {status} {text}")
        if not self._is_ok_payload(data, text):
            _LOGGER.debug("OpenFAN %s: LED set non-OK body: %s", self._host, data or text)
        return data or {"status": "ok"}

    async def set_voltage_12v(self, enabled: bool) -> dict:
        """Switch fan supply to 12V (True) or 5V (False). Requires confirm=true."""
        path = "/api/v0/fan/voltage/high?confirm=true" if enabled else "/api/v0/fan/voltage/low?confirm=true"
        status, text, data = await self._get_any(path)
        if status >= 400:
            raise RuntimeError(f"Voltage set failed: {status} {text}")
        if not self._is_ok_payload(data, text):
            _LOGGER.debug("OpenFAN %s: voltage set non-OK body: %s", self._host, data or text)
        return data or {"status": "ok"}
