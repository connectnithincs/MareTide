# MARETIDE — REAL ESP32 HARDWARE INTEGRATION RUNBOOK

This runbook guides operators through flashing, wiring, connecting, and testing physical ESP32 hardware with the MareTide maritime decision-support platform.

---

## 1. End-to-End Data Pipeline

```
REAL SENSORS (MPU-6050 / HC-SR04)
        |
        v
ESP32 Microcontroller (esp32_sensor_sketch.ino)
        |
        v [115200 Baud UART / USB]
MareTide Python Sidecar (HardwareSerialAdapter)
        |
        v [extract_json_from_buffer]
Normalized Telemetry Model (NormalizedTelemetry)
        |
        v [HTTP / WebSocket :8001 -> :8000]
Node.js API Gateway (/ws/telemetry)
        |
        v [10Hz WebSocket Stream]
React Digital Twin & Line Monitor (SocketContext)
```

---

## 2. Firmware Flashing Procedure

### Prerequisites
* Arduino IDE 2.0+ or PlatformIO / `esptool.py`
* ESP32 Board Support Package (`esp32` by Espressif Systems v2.0.11+)
* Libraries:
  * `MPU6050` (Electronic Cats / I2Cdevlib)
  * `HX711` (bogde)
  * `ESP32Servo` (Kevin Harrington)

### Flashing via Arduino IDE
1. Open `esp32_sensor_sketch.ino`.
2. Connect ESP32 via Micro-USB / USB-C to host computer.
3. In **Tools > Board**, select **ESP32 Dev Module**.
4. In **Tools > Port**, select the detected COM port (e.g. `COM3` on Windows or `/dev/ttyUSB0` on Linux/macOS).
5. In **Tools > Upload Speed**, select **115200** or **921600**.
6. Click **Upload** ($\rightarrow$).

---

## 3. Starting Telemetry in MareTide

1. Start all services using `python run.py`.
2. Navigate to **System Settings** in the React Dashboard: `http://localhost:3000/`.
3. In the **IoT Telemetry Hardware Link** section:
   * Select **ESP32 Physical Port Link**.
   * Click **Scan Ports** to discover your connected ESP32 port.
   * Select the port and click **Establish COM Connection**.
4. Observe the top bar status badge transition to:
   `[CONNECTED — HARDWARE SENSOR]` with `[10Hz LIVE]` freshness.

---

## 4. Connection States & Diagnostic Rules

| State | Condition | UI Indicator | Action / Fallback |
| :--- | :--- | :--- | :--- |
| `CONNECTED` | Valid JSON packets arriving with age $< 2.0\text{s}$ | `[CONNECTED — HARDWARE SENSOR]` | Live hardware telemetry rendered in Digital Twin |
| `STALE` | Link active but no packet received for $> 2.0\text{s}$ | `[DELAY +Xs STALE]` | Displays preserved last verified physical state |
| `DISCONNECTED` | Serial port closed or no packet for $> 5.0\text{s}$ | `[BACKEND OFFLINE]` or `[DISCONNECTED]` | Falls back to safe deterministic default state |
| `SIMULATION` | Simulator engine active | `[SIMULATION MODE — SIMULATED TELEMETRY]` | Wave dynamics & simulated tilt model |

---

## 5. Physical Disturbance Bench Tests

1. **Inclinometer Tilt Test:**
   * Physically tilt the ESP32 breadboard to the right $\rightarrow$ Observe `roll` angle increase positively on the dashboard.
   * Physically tilt the ESP32 breadboard to the left $\rightarrow$ Observe `roll` angle decrease negatively.
2. **Ballast Tank Water Depth Test:**
   * Place an object / reflector closer to HC-SR04 ($< 15\text{ cm}$) $\rightarrow$ Observe `ballast_pct` increase towards 100%.
   * Move the object further away ($> 25\text{ cm}$) $\rightarrow$ Observe `ballast_pct` drop towards 0%.
3. **USB Disconnect Resilience Test:**
   * Unplug the USB cable $\rightarrow$ Backend flags `DISCONNECTED` without crashing.
   * Plug the USB cable back in $\rightarrow$ Backend automatically discovers port and re-establishes live telemetry.
