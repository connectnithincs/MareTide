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

## 🚀 Setup & Launch

### Prerequisites
* **Node.js** (v18+)
* **Python 3.10+** (with virtual environment capability)
* **ESP32 Dev Board** (Optional, for physical load scale testing)

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
*(Default login credentials are managed through the Flask Auth server interface)*
