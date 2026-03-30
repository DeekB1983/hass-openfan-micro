
## 🚀 Current Status - Change Log
**Version:** v1.0.4 (Stable Release)
**Home Assistant:** 2026.03.+ compatible (Earlier versions may work but all testing has been completed on 2026.03.+)

This release focuses on:
* Device stability
* Reduced API load
* Reliable real-time control of Fans

---
## ⚠️ Background (Why these changes were made)

## ⚙️🌀 Fan Behavior: Before vs After (V1.0.4)

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
## 📉 Key Improvement: Smart Polling (v1.0.3)

### Before:
* Polling every 5 seconds continuously
* Multiple endpoints per cycle
* ~32,000+ API calls/day

### After:
* Default polling: **60 seconds**
* Fast polling: **2 seconds (only after user interaction)**
* Secondary data polled less frequently
* ~1,650 API calls/day (idle)
* ~1,750–2,000 API calls/day (typical use if manually adjusting the fan via Home Assistant)

### Result:
✅ ~93.75%+ reduction in API load  
✅ Device remains stable long-term  
✅ Web UI stays responsive  

---
## 🧠 Smart Polling Behaviour (v1.0.3)

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

Earlier versions of this integration used **aggressive polling (~5s constantly)** which resulted in:

* OpenFAN Micro web UI becoming unresponsive
* Device dropping off the network
* High API load (~32,000+ requests/day)
* Required manual reboot to recover
* Potential port exhuastion
* Potential memory exhuastion

### Root cause:
> Excessive API calls and inefficient HTTP connection handling overwhelmed the microcontroller.   
> ⚠️ Note: This integration has been significantly optimised to prevent device instability caused by excessive API polling.

---
## 🌐 HTTP Optimisations (v1.0.3)
To prevent device overload:

* Disabled HTTP keep-alive
* Added delay between API requests
* Reduced duplicate calls
* Centralised polling via coordinator
* Split high-frequency vs low-frequency data

---
## 🔗 Device Web Interface (v1.0.3)
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
