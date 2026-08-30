# MareTide Stability & Stowage AI Platform

MareTide is a premium marine stability simulation and real-time stowage automation dashboard. It integrates physical scale load sensors, active ballast tank management, automated and manual pumping, live inclinometers, and Voyage AIS map tracking into a unified dual-theme SCADA dashboard.

---

## 🏗️ System Architecture

The application is built as a microservices stack run simultaneously via an orchestration script:

```
                  ┌──────────────────────────────────────────┐
                  │   React SPA Dashboard (Port 3000)        │
                  └────────────────────┬─────────────────────┘
                                       │ WebSockets & REST APIs
                  ┌────────────────────▼─────────────────────┐
                  │   Node.js API Gateway (Port 8000)        │
                  └──────────┬────────────────────┬──────────┘
                             │ REST Auth          │ Telemetry Feed
     ┌───────────────────────▼──────┐    ┌────────▼──────────────────────┐
     │ Flask Auth Server (Port 5000)│    │ FastAPI Python Sidecar (8001) │
     └──────────────────────────────┘    └────────┬──────────────────────┘
                                                  │ Serial Link (COM Port)
                                         ┌────────▼──────────────────────┐
                                         │   ESP32 Physical Scale Load   │
                                         └───────────────────────────────┘
```

### 📁 Directory Layout

* **`dashboard_react/`**: React + TypeScript + Tailwind SPA frontend built on Vite.
* **`backend_node/`**: Node.js Express Gateway handling telemetry WebSockets and API forwarding.
* **`sidecar_python/`**: FastAPI engine connecting to hardware COM ports to read scale telemetry, calculate live vessel lists, and process active ballast pump cycles.
* **`templates/` & `server.py`**: Flask Authentication microservice managing secure sign-in and session management.
* **`run.py`**: Parent script executing and monitoring all services concurrently.

---

## ✨ Features Implemented

### 1. 🌓 Premium Light & Dark Themes
* Designed a responsive theme state toggled directly from the sidebar.
* **Light Theme (Default)**: Bright marine-blue gradient backdrop with white card panels (`#EAF4FF` base with `#ffffff` glass panels).
* **Dark Theme**: High-tech navy style (`#021024` base with `#052659` card structures).
* **Sidebar**: Retains its high-contrast gradient navy background (`linear-gradient(180deg, #021024 0%, #052659 100%)`) in both modes for a professional SCADA aesthetic.

### 2. 🚢 SCADA Digital Twin Monitoring
* Real-time SVG visualization of the ship's 8 ballast compartments (Port/Starboard, Bays 1-4).
* Interactive water level levels styled with dynamic sky-blue/ocean overlays and drop-shadowed high-contrast text metrics (`style={{ textShadow: '0 1px 3px rgba(2,16,36,0.95)' }}`).

### 3. 📉 Interactive Inclinometer
* Rotates the vessel cross-section SVG based on live roll (heel) angles.
* Outer dial ticks and degrees change styling adaptively to prevent muddy contrast.
* The hull border highlights dynamically depending on warning bounds:
  * **Safe (≤ 2.0°)**: Clean Emerald Green
  * **Warning (> 2.0°)**: Amber
  * **Danger (> 5.0°)**: Alert Red

### 4. 🗺️ Multi-Provider AIS Mapping
* Dynamic Leaflet map tracking vessel voyage path.
* Accessible map settings options configuration in the **Settings** panel to configure access tokens.
* Supports automatic dark/light map tiles based on current active dashboard theme for:
  * **Mapbox** (Light/Dark Vector layers)
  * **Stadia Maps** (Alidade Smooth/Smooth Dark)
  * **JawgMaps** (Light/Dark themes)
  * **Thunderforest** (Atlas/Transport-dark styles)
  * **OpenStreetMap** (Free fallback)

### 5. 🚰 Gradual Ballast Draining & Bay Preferences
* Implements manual pumping controls to transfer water between Port and Starboard.
* **Bay Filtering**: Targeted pumping allows selecting specific source/destination bays (Bays 1-4) or transfer to Sea discharge directly.
* Slowly drains tanks over time using active state machine parameters and provides visual feedback metrics.

---

### 6. 🛰️ Real ESP32 Hardware Telemetry Integration
* **Microcontroller Firmware:** [`esp32_sensor_sketch.ino`](file:///e:/HACKPROJ/MareTide%20Js/esp32_sensor_sketch.ino)
* **Baud Rate:** `115200` bps over USB UART.
* **Connected Sensors:** MPU-6050 (I2C SDA:21, SCL:22) for roll/pitch inclinometer, HC-SR04 (Trig:5, Echo:18) for ultrasonic ballast level depth, and SG90 servo (PWM:25) for ballast gate valve.
* **Multi-Line Stream Extraction:** Custom serial stream scanner seamlessly decodes multi-line JSON blocks, `---` block separators, and filters asynchronous boot/warning text without dropping packets.
* **Strict Load-Cell Isolation:** The HX711 scale interface on the ESP32 is quarantined and isolated from container cargo mass, gross weight, VGM, and stability calculations. Cargo mass is sourced strictly from SOLAS Document AI.

---

## 🚀 Setup & Launch

### Prerequisites
* **Node.js** (v18+)
* **Python 3.10+** (with virtual environment capability)
* **ESP32 Dev Board** (ESP32-WROOM-32 with MPU-6050 & HC-SR04)

### ESP32 Hardware Setup
1. Open `esp32_sensor_sketch.ino` in Arduino IDE or PlatformIO.
2. Select **ESP32 Dev Module** and the connected COM port.
3. Flash the firmware at 115200 baud.
4. In MareTide Dashboard **Settings > IoT Telemetry Link**, select **ESP32 Physical Port Link** and establish connection.

### Installation
1. Install Node dependencies:
   ```bash
   cd dashboard_react && npm install
   cd ../backend_node && npm install
   ```
2. Set up Python virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Execution
Run the system from the root folder:
```powershell
python run.py
```
Open your browser and navigate to:
```url
http://localhost:3000
```
*(Default login credentials: `admin@maretide.com` / `password123`)*

---

## 📚 Technical Documentation
* [ESP32 Sensor Audit](file:///e:/HACKPROJ/MareTide%20Js/docs/ESP32_SENSOR_AUDIT.md)
* [ESP32 Sensor Calibration Guide](file:///e:/HACKPROJ/MareTide%20Js/docs/ESP32_SENSOR_CALIBRATION.md)
* [ESP32 Hardware Integration Runbook](file:///e:/HACKPROJ/MareTide%20Js/docs/ESP32_INTEGRATION.md)

