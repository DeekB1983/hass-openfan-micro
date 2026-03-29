# OpenFAN Micro — Home Assistant Integration

Custom integration for **OpenFAN Micro** devices, providing fan control, monitoring, and advanced automation with a focus on **stability, low resource usage, and responsiveness**.

> ⚠️ Note: This integration has been significantly optimised to prevent device instability caused by excessive API polling.

## 📦 Installation

### Option A — HACS (Recommended)

1. HACS → Integrations → ⋮ Custom repositories
2. Add Repsository: **Category** "Integration"
   ```
   https://github.com/DeekB1983/hass-openfan-micro
   ```
4. Find → Download **OpenFAN Micro** from HAC's
5. (Optional) Click “Need a different version?” and select v1.0.2_Test (Pre_Release of V1.0.3)
6. Restart Home Assistant
7. Settings → Devices & Services → Add Integration → OpenFAN Micro  
   Then enter the device IP and a friendly name  
   (Where xxx.xxx.xxx.xxx denotes the IP address + Fan Name)  
   Repeat per device if you have multiple devices\fan controllers
   ![brave_U922ETczsN](https://github.com/user-attachments/assets/ebacea07-2ce1-4f85-bee3-3d0889486b4e)

---

### Option B — Manual
1. Download the code.
2. Extract the ZIP.
3. Copy the files to:
```
/config/custom_components/openfan_micro/
```
4. Restart Home Assistant
5. Add the integration: Settings → Devices & Services → Add Integration → OpenFAN Micro

---

## 🚀 Current Status

**Version:** v1.0.4 (Beta Release)
**Home Assistant:** 2023.03.+ compatible

This release focuses on:

* Device stability
* Reduced API load
* Reliable real-time control

---

## ⚠️ Background (Why these changes were made)

Earlier versions of this integration used **aggressive polling (~5s constantly)** which resulted in:

* OpenFAN Micro web UI becoming unresponsive
* Device dropping off the network
* High API load (~32,000+ requests/day)
* Required manual reboot to recover
* Potential port exhuastion
* Potential memory exhuastion

### Root cause:

> Excessive API calls and inefficient HTTP connection handling overwhelmed the microcontroller.

---

## 📉 Key Improvement: Smart Polling

### Before:

* Polling every 5 seconds continuously
* Multiple endpoints per cycle
* ~32,000+ API calls/day

### After:

* Default polling: **60 seconds**
* Fast polling: **2 seconds (only after user interaction)**
* Secondary data polled less frequently

### Result:

* ~1,650 API calls/day (idle)
* ~1,750–2,000 API calls/day (typical use if manually adjusting the fan via Home Assistant)

✅ ~93.75%+ reduction in API load  
✅ Device remains stable long-term  
✅ Web UI stays responsive  

---

## ⚡ Features

### Core

* Fan control (0–100%)
* RPM sensor (`sensor.<name>_rpm`)
* Fan on/off control
* Fast response after changes (~0–5s)

### Device Controls

* LED switch (`switch.<name>_led`)
* 12V / 5V mode switch (`switch.<name>_12v_mode`)

### Reliability

* Availability gating (failure threshold)
* Stall detection:

  * Binary sensor
  * Home Assistant event
  * Persistent notification

### Advanced Control

* Temperature-based fan control:

  * Piecewise curve (°C → PWM)
  * Moving average smoothing
  * Deadband to prevent oscillation
  * Minimum PWM enforcement (via calibration)

### Diagnostics

* Built-in diagnostics export
* Debug logging with timestamps

---

## 🌐 API Requirements

Your OpenFAN Micro firmware must support:  

### Required

* `GET /api/v0/fan/status` → `{ rpm, pwm_percent }`
* `POST /api/v0/fan/set?value=XX` (or equivalent working endpoint)

### Optional

* `GET /api/v0/openfan/status`

  * `act_led_enabled`
  * `fan_is_12v`

* LED:

  * `/api/v0/led/enable`
  * `/api/v0/led/disable`

* Voltage:

  * `/api/v0/fan/voltage/high` (for 12v)
  * `/api/v0/fan/voltage/low` (for 5v)

  
Tested on OpenFAN Micro Firmware: v20240319
 
---

## 🧠 Smart Polling Behaviour

| Scenario          | Poll Interval                 |
| ----------------- | ----------------------------- |
| Idle              | 60 seconds                    |
| After HA control  | 2 seconds (≈6 seconds total) |
| LED / 12V refresh | Every ~6 minutes              |

### Behaviour:

1. User changes fan speed via the Home Assistant Integration
2. Immediate refresh triggered via Fast Polling
3. Fast polling (2s × 3 cycles)
4. Automatically returns to 60s polling after 3 fast polling cycles if no more PWM fan changes via HA are completed
5. Polling stays at 60 seconds if fan speed is changed via the MicroFan controller Web interface (Expected)

---

## ⚙️🌀 Fan Behavior: Before vs After 

| Feature | Before | After |
|---------|--------|-------|
| **Positional Argument Bug** | `async_turn_on()` failed with “takes 1 to 2 positional arguments but 3 were given” | Fixed method signature to match Home Assistant expectations |
| **Power On Speed** | Fan always started at 1% when turned on | Fan starts at **last user-set speed**, or **50% by default** if first time |
| **Turning Off** | Speed reset to 1% | Speed **retained**; next turn-on resumes last speed |
| **Home Assistant Slider** | Moving slider after off/on reset to 1% | Slider reflects **current or last speed**, consistent after off/on |
| **Automations** | Automations turning fan on had to explicitly set speed | Automations can turn fan on **without specifying speed**; last speed used automatically |
| **Debug / Attributes** | Limited visibility of last PWM | `last_speed` added to `extra_state_attributes` for easier monitoring |
| **User Experience** | Inconsistent, fan always “starts slow” | Smooth, predictable fan behavior ⚡🌀 |

> ⚠️ Note: The default startup speed of 50% applies only on the **first power-on**. After that, the fan remembers the last user-set speed automatically.

---

## 🌐 HTTP Optimisations

To prevent device overload:

* Disabled HTTP keep-alive
* Added delay between API requests
* Reduced duplicate calls
* Centralised polling via coordinator
* Split high-frequency vs low-frequency data

---

## 🔌 Entities

Per device:

* `fan.<name>`
* `sensor.<name>_rpm`
* `switch.<name>_led`
* `switch.<name>_12v_mode`
* `binary_sensor.<name>_stall`

---

## 🔧 First Run: Calibrate Minimum PWM

Required for proper operation.

Run:

```yaml
action: openfan_micro.calibrate_min
data:
  entity_id: fan.your_fan
  from_pct: 5
  to_pct: 40
  step: 2
  rpm_threshold: 120
  margin: 5
```

---

## 🌡️ Temperature Control

Enable:

```yaml
action: openfan_micro.set_temp_control
data:
  entity_id: fan.your_fan
  temp_entity: sensor.temperature
  temp_curve: "45=35, 60=60, 70=100"
```

Disable:

```yaml
action: openfan_micro.clear_temp_control
```

---

## 📊 Diagnostics

Download via:
Settings → Devices & Services → OpenFAN Micro → Download diagnostics

Includes:

* Current state
* Coordinator data
* Control logic state

---

## 🛠️ Debug Logging

```yaml
logger:
  logs:
    custom_components.openfan_micro: debug
```

---

## 🔗 Device Web Interface

A **“Visit Device”** button is available in Home Assistant, linking directly to the device’s web UI.

---

## 🧪 Troubleshooting

### Device becomes unresponsive

* Fixed in v1.0.3 via reduced polling
* Ensure you are running latest version

### Fan RPM updates are slow

* Expected:

  * 2s after control
  * 60s otherwise

### PWM stuck low

* Ensure calibration completed
* Check `min_pwm_calibrated`

---

## 🤝 Contributing

Issues and PRs welcome.

Please include:

* Diagnostics export
* Debug logs

---

## 🙏 Credits

* OpenFAN Micro hardware & firmware: **Sasa Karanovic**
* Original integration: **BeryJu, bitlisz1**
* This fork:

  * Stability improvements
  * Smart polling system
  * API optimisation
  * Enhanced diagnostics

---

## 📄 License

See LICENSE file in repository.
