# OpenFAN Micro — Home Assistant Integration

Custom integration for **OpenFAN Micro** devices, providing fan control, monitoring, and advanced automation with a focus on **stability, low resource usage, and responsiveness**.

## 📦 Installation

### Option A — HACS (Recommended)

1. HACS → Integrations → ⋮ Custom repositories
2. Add Repsository: **Category** "Integration"
   ```
   https://github.com/DeekB1983/hass-openfan-micro
   ```
4. Find → Download **OpenFAN Micro** from HAC's
5. (Optional) Click “Need a different version?” and select v1.0.3 \ v1.0.4 (Currently v1.0.4 is the latest\default version)
6. Restart Home Assistant
7. Settings → Devices & Services → Add Integration → OpenFAN Micro  
   Then enter the device IP and a friendly name  
   (Where xxx.xxx.xxx.xxx denotes the IP address + Fan Name)  
   Repeat per device if you have multiple OpenFan Micro controllers
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
## 🔧 First Run: Calibrate Minimum PWM
Run once per device to find the minimum PWM that your fan can reliably spin at.  
When executed this will sweep the PWM values for your fan and detect minimum value that your fan can reliably spin at.  
Once complete it stores the result in options as min_pwm and marks the fan as calibrated.  
This can be achieved by going to "Developer Tools → Actions → openfan_micro.calibrate_min"

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
Example Screenshot:
![brave_1nEliYdmD0](https://github.com/user-attachments/assets/21bc5667-e7a7-4d33-9e5a-68c8df16627b)

---
## ⚡ Features

### Core
* Fan control (0–100%)
* RPM sensor (`sensor.<name>_rpm`)
* Fan on/off control
* Fast response after changes (~0–5s) - This behaviour changes in v1.0.3, See smart polling section in ChangeLog.md.

### Device Controls
* LED switch (`switch.<name>_led`)
* 12V / 5V mode switch (`switch.<name>_12v_mode`)

### Reliability
* Availability gating (failure threshold, 3 consecutive failures)
* Stall detection:
  * Binary sensor
  * Home Assistant event
  * Persistent notification

### Advanced Temperature Control
* Temperature-based fan control:
  * Piecewise curve (°C → PWM)
  * Moving average smoothing
  * Deadband to prevent oscillation
  * Minimum PWM enforcement (via calibration)
 
### Entities
Per device:

* `fan.<name>`
* `sensor.<name>_rpm`
* `switch.<name>_led`
* `switch.<name>_12v_mode`
* `binary_sensor.<name>_stall`

### Diagnostics
* Built-in diagnostics export
* Debug logging with timestamps

---
## 🌐 API Requirements

Your OpenFAN Micro firmware must support:  
### Required
* `GET /api/v0/fan/status` → `{ rpm, pwm_percent }`
* `POST /api/v0/fan/set?value=XX` → `{ "status": "ok", "message": "Setting PWM to XX", }` (XX should be a number like 30)

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
## 🌡️ Temperature Control

The temperature control for the fan is software based and can be achieved by going to:  
"Developer Tools → Actions → openfan_micro.set_temp_control"

Enable:
```yaml
action: openfan_micro.set_temp_control
data:
  entity_id: fan.your_fan
  temp_entity: sensor.temperature
  temp_curve: "30=40, 40=50, 55=100"
```
The temperature curve can be adjusted as requiured, based on above example:
(Temp=FanSpeed)
 * 30 degrees celcius = 40% PWM Value
 * 40 degrees celcius = 50% PWM Value
 * 55 degrees celcius = 100% PWM Value
   
Example Screenshot:
 ![brave_gDeR4aVy42](https://github.com/user-attachments/assets/40420226-fd37-4e71-bc7b-11ee2b961b6c)

To disable temperature based fan control run the following:
"Developer Tools → Actions → openfan_micro.clear_temp_control"

Disable:
```yaml
action: openfan_micro.clear_temp_control
```
Example Screenshot:
<img width="1632" height="344" alt="image" src="https://github.com/user-attachments/assets/dece2f6c-078f-414b-8f9a-58ac060c1bc6" />

---
# 🏠🌀 Lovelace Usage 

The fan entity works seamlessly with Home Assistant Lovelace controls.

## Example: Fan Control Card
```yaml
type: tile
entity: fan.openfan_micro
features:
  - type: fan-speed
```

## Example: Slider Card
```yaml
type: entities
entities:
  - entity: fan.openfan_micro
    name: Fan-Name
```

## Example: Horizontal Fan Control
```yaml
type: horizontal-stack
cards:
  - type: tile
    entity: fan.openfan_micro
    features:
      - type: fan-speed
```

## Example: RPM Display Card
```yaml
type: gauge
entity: sensor.openfan_micro_fan_rpm
name: Fan RPM
min: 0
max: 5000
```

## Example: RPM Graph
```yaml
type: history-graph
entities:
  - sensor.openfan_micro_fan_rpm
hours_to_show: 24
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
## 🤝 Contributing
Issues and PRs welcome.
Please include:
* Diagnostics export
* Debug logs

---
## 🙏 Credits
* OpenFAN Micro hardware & firmware: **Sasa Karanovic**
* Original integration: **BeryJu, bitlisz1**
* This fork includes:
  * Stability improvements
  * Smart polling system
  * API optimisation
  * Reliable real-time control of Fans
  * Enhanced diagnostics

---
## 📄 License

See LICENSE file in repository.
