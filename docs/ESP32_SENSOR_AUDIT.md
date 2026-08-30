# MARETIDE — ESP32 HARDWARE & SENSOR AUDIT

## 1. Hardware Overview
* **Microcontroller:** ESP32 Dev Module (ESP32-WROOM-32, Xtensa dual-core 32-bit @ 240MHz).
* **Power & Logic:** 3.3V DC logic level, USB UART power & data connection.
* **Firmware Source:** `esp32_sensor_sketch.ino`

---

## 2. Hardware Pinout & Wiring

| Subsystem / Sensor | Pin / GPIO | Direction | Interface | Function |
| :--- | :--- | :--- | :--- | :--- |
| **MPU-6050 SDA** | GPIO 21 | Bidirectional | I2C Data | Communicates 6-axis IMU accelerometer data |
| **MPU-6050 SCL** | GPIO 22 | Output | I2C Clock | I2C master clock line |
| **HC-SR04 Trigger** | GPIO 5 | Output | Digital Pulse | 10µs ultrasonic emission trigger |
| **HC-SR04 Echo** | GPIO 18 | Input | Digital Timing | Measures echo return time (30ms timeout) |
| **HX711 DOUT** | GPIO 32 | Input | Serial Data | 24-bit scale ADC differential data output |
| **HX711 SCK** | GPIO 33 | Output | Serial Clock | 24-bit scale ADC clock output |
| **Gate Servo** | GPIO 25 | Output | LEDC PWM | Controls ballast discharge gate ($0^\circ$ to $80^\circ$) |
| **Pump LED** | GPIO 23 | Output | Digital HIGH/LOW | Indicates active ballast draining |
| **Warning LED** | GPIO 19 | Output | Digital HIGH/LOW | Indicates critical risk or capacity exceeded |

---

## 3. Communication Protocol
* **Physical Medium:** USB UART / Serial CDC
* **Baud Rate:** 115200 bps (8-N-1)
* **Sampling Rate:** 2 Hz (emitted every 500 ms)
* **Loop Rate:** ~50 Hz (20 ms internal non-blocking delay)

---

## 4. Telemetry Format

### Multi-Line JSON Block (with `---` separator)
```json
{
  "roll": 1.45,
  "pitch": -0.65,
  "distance": 12.00,
  "ballast_pct": 82.50,
  "cargo_kg": 0.00,
  "status": "IDLE",
  "risk": "SAFE"
}
---
```

---

## 5. Actual Sensor Inventory

| Sensor Name | Implemented in `.ino` | Physical Unit | Output Range | Presence in Hardware |
| :--- | :--- | :--- | :--- | :--- |
| **MPU-6050 (Inclinometer)** | YES | Degrees ($^\circ$) | Roll: $[-180, 180]$, Pitch: $[-90, 90]$ | **PRESENT** |
| **HC-SR04 (Ultrasonic)** | YES | Centimeters (cm) | Distance: $[10.0, 30.0]$, Ballast: $[0, 100\%]$ | **PRESENT** |
| **HX711 (Scale)** | YES | Kilograms (kg) | $[0.0, 30.0]$ kg | **PRESENT (ISOLATED)** |
| **Gate Servo** | YES | Degrees ($^\circ$) | $0^\circ$ (Closed) to $80^\circ$ (Open) | **PRESENT (ACTUATOR)** |
| **Anemometer** | NO | N/A | N/A | **NOT PRESENT** |
| **Flow Meter** | NO | N/A | Derived via Torricelli orifice equation | **NOT PRESENT** |
| **Hydrostatic Pressure** | NO | N/A | N/A | **NOT PRESENT** |
| **Thermometer** | NO | N/A | N/A | **NOT PRESENT** |
| **Salinity / Density** | NO | N/A | N/A | **NOT PRESENT** |
| **GPS Receiver** | NO | N/A | N/A | **NOT PRESENT** |

---

## 6. Critical Load-Cell Safety Invariant

```
+-------------------------------------------------------------------------+
|                        SOLAS VERIFIED GROSS MASS (VGM)                  |
|                                                                         |
|  Container Slip Document -> Document AI -> Validated JSON -> Stability  |
|                                                                         |
|  [ESP32 HX711 Load Cell] -> PURGED / QUARANTINED (Never enters VGM)     |
+-------------------------------------------------------------------------+
```

* Under no circumstances is the ESP32 load-cell reading utilized for container mass, vessel stability, or stowage optimization.
* Cargo mass originates exclusively from SOLAS-compliant Document AI.
