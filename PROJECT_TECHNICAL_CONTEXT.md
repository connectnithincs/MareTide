# PROJECT TECHNICAL CONTEXT & AUDIT REPORT

This document contains the complete technical audit and reverse-engineering findings of the **MareTide / NAVI-AI Maritime Intelligence Platform** across the Streamlit/Flask python version (`d:\MareTide`), the JS React/Express/FastAPI/Flask microservices stack (`d:\MareTide Js`), and the standalone Voyage Intelligence Streamlit module (`c:\Users\conne\Downloads\maretide_voyage\maretide_voyage`).

---

## PHASE 1 — COMPLETE PROJECT INVENTORY

The platform exists in two parallel implementations: a Streamlit-based monolithic interface and a React-based microservices architecture. Below is the directory inventory and purpose analysis.

### 1. Monolithic Python Streamlit Workspace (`d:\MareTide`)
*   **Root Directory**: Contains orchestration scripts, environment configurations, firmware, and model weights.
    *   [run.py](file:///d:/MareTide/run.py): Python subprocess orchestrator that launches the Flask Authentication Server on port 5000 and the Streamlit Dashboard on port 8501, handles browser auto-open, and terminates both clean.
    *   [server.py](file:///d:/MareTide/server.py): Flask authentication microservice on port 5000 managing session storage and single-use redirect tokens.
    *   [esp32_sensor_sketch.ino](file:///d:/MareTide/esp32_sensor_sketch.ino): C++ Arduino sketch for physical ESP32 controller incorporating MPU-6050 (tilt), HC-SR04 (ultrasonic ballast sensor), HX711 (load cell scale), and a servo for the drain gate.
    *   [yolov8n.pt](file:///d:/MareTide/yolov8n.pt): Pre-trained YOLOv8 Nano model weights used for visual object detection.
    *   [requirements.txt](file:///d:/MareTide/requirements.txt): Declares Python dependencies (streamlit, flask, requests, pyserial, folium, ultralytics, etc.).
*   **`dashboard/`**: Streamlit dashboard components and core state engine.
    *   [dashboard/app.py](file:///d:/MareTide/dashboard/app.py): The main Streamlit monolithic interface (922 KB). It handles UI views, page routing (10 tabs), interactive SVGs, and telemetry thread bindings.
    *   [dashboard/ship.py](file:///d:/MareTide/dashboard/ship.py): Core domain models (`Ship`, `Container`, `BallastTank`), mathematical models (`StabilityAnalyzer`), and the slot recommendation engine (`RecommendationEngine`).
    *   [dashboard/serial_reader.py](file:///d:/MareTide/dashboard/serial_reader.py): Manages the background thread that parses JSON telemetry from COM ports or simulates physical scale activities (10Hz loop).
    *   [dashboard/digital_twin.py](file:///d:/MareTide/dashboard/digital_twin.py): Console-based digital twin renderer used for CLI debugging.
*   **`dashboard/navi_vision/`**: Asynchronous Computer Vision sub-module.
    *   [vision_manager.py](file:///d:/MareTide/dashboard/navi_vision/vision_manager.py): Singleton orchestrator that controls CV cameras, handles frame loops, and routes alerts to storage.
    *   [vision_yolo_runner.py](file:///d:/MareTide/dashboard/navi_vision/vision_yolo_runner.py): Asynchronous worker running YOLOv8 on Crew Safety and Sea Lane feeds.
    *   [ballast_detector.py](file:///d:/MareTide/dashboard/navi_vision/ballast_detector.py): Optic flow motion leak detector.
    *   [vision_decision.py](file:///d:/MareTide/dashboard/navi_vision/vision_decision.py): Alert severity classifier and recommendation mapper.
    *   [vision_db.py](file:///d:/MareTide/dashboard/navi_vision/vision_db.py): SQLite database manager for vision alerts (`vision_alerts.db`).
    *   [live_camera.py](file:///d:/MareTide/dashboard/navi_vision/live_camera.py): SharedWebcam reference-counted singleton that locks OpenCV hardware capture.
*   **`models/`, `services/`, `components/`, `utils/`, `theme/`**: Duplicated/modularized Voyage Intelligence files matching the standalone build.

### 2. JS React/Microservices Workspace (`d:\MareTide Js`)
*   **`dashboard_react/`**: React + TypeScript + Tailwind SPA.
    *   `src/components/`: Core UI components ([SCADADigitalTwin.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/SCADADigitalTwin.tsx), [Inclinometer.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/Inclinometer.tsx), [LiveMonitor.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/LiveMonitor.tsx), [AIVision.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/AIVision.tsx), [VoyageIntelligence.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/VoyageIntelligence.tsx)).
    *   `src/utils/api.ts`: API endpoints client using Axios.
*   **`backend_node/`**: Node.js Express Gateway & WebSocket Broadcaster.
    *   [backend_node/src/server.js](file:///d:/MareTide%20Js/backend_node/src/server.js): API Gateway on port 8000. Proxies calls to sidecar and Flask auth server, and broadcasts telemetry at 10Hz to `/ws/telemetry`.
*   **`sidecar_python/`**: FastAPI python computation and CV service on port 8001.
    *   [sidecar_python/main.py](file:///d:/MareTide%20Js/sidecar_python/main.py): REST and MJPEG video streaming endpoints.
    *   [sidecar_python/state.py](file:///d:/MareTide%20Js/sidecar_python/state.py): Asynchronous daemon thread running the telemetry state machine loop.
    *   `sidecar_python/reports/logs_db.py`: SQLite logging database manager (`maretide.db`).

---

## PHASE 2 — TECHNOLOGY STACK

| Layer | Technology | Version | Purpose |
| :--- | :--- | :--- | :--- |
| **Frontend** | React (TSX) / Streamlit | React v19.2.7 / Streamlit >= 1.35.0 | Web-based SCADA interface & quick Python prototype dashboard |
| **Backend (Node)** | Node.js / Express / ws | Node v18+ / Express v4.18.2 / ws v8.14.2 | API Gateway, token exchange proxy, and telemetry WebSocket server |
| **Backend (Python)** | FastAPI / Uvicorn / Flask | FastAPI v3.0 / Uvicorn v0.22+ / Flask >= 3.0.0 | FastAPI calculation sidecar / Flask authentication microservice |
| **Database** | SQLite | 3.x (native python client) | Logs operational sequences and AI vision alerts |
| **ORM** | Raw SQLite queries | N/A | High-throughput raw SQL statements to prevent database locks |
| **Authentication** | Flask Sessions & Tokens | Flask session client / UUID4 | Decrypts session cookies via proxy and validates one-time tokens |
| **AI/ML** | YOLOv8 (Ultralytics) | v8.0.0+ | Object detection on crew restricted zones and collision paths |
| **APIs** | REST & WebSockets | N/A | Integration links between React, Node, FastAPI, and Flask |
| **IoT / Serial** | PySerial / Arduino C++ | pyserial >= 3.5 | Communicates with ESP32 microcontrollers over UART |
| **Build Tools** | Vite / TypeScript / Oxlint | Vite v8.1.1 / TS v6.0.2 / Oxlint v1.71 | React bundle building and lightning-fast linting |

---

## PHASE 3 — APPLICATION PURPOSE

1.  **Problem Solved**: Vessel loading shifts listing (heel) and trim (pitch) angles. Symmetrical ballast and cargo planning are essential to prevent vessel capsize. This platform automates cargo placement calculations and performs active, real-time ballast pump scheduling to keep the vessel stable.
2.  **Intended Users**: Vessel operators, cargo officers, deck personnel, port logisticians, and safety captains.
3.  **Primary Workflow**: Scale load sensor detects cargo weight -> AI Advisor recommends optimal slot -> Operator places cargo -> System calculates ballast requirements -> Auto-drain pump discharges ballast water to compensate -> Digital Twin and Inclinometer reflect new stability.
4.  **Major Modules**: Digital Twin (visual SVG compartments), Live Telemetry Link (Serial/Simulation), AI Decision/Recommendation Engine (slot scoring & explainable pump recommendations), AI Vision Surveillance (restricted area person detection & collision alerts), and Voyage Intelligence (Leaflet live AIS tracking).
5.  **CRUD vs. SCADA**: Unlike standard database entry applications, this system processes real-time 10Hz serial stream calculations, runs OpenCV/YOLOv8 video analysis, dynamically generates custom SVG shapes based on active ballast/heel/trim values, and operates a background state machine reflecting physical scale states.

---

## PHASE 4 — FRONTEND DEEP ANALYSIS

### 1. React Frontend Framework (`dashboard_react/`)
*   **Vite Dev Server**: Listens on port 3000. Imports `Leaflet` for vessel coordinates tracking and `Recharts` for stability statistics.
*   **Digital Twin Rendering**: Rendered inside [SCADADigitalTwin.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/SCADADigitalTwin.tsx) using dynamic SVG elements. Compartment fill heights (`fillHeight`) are derived from `fill_ratio` values (0.0 to 1.0) and colored dynamically based on capacity limits (under 15% is low/light blue, over 85% is high/dark blue, else sky-blue).
*   **Inclinometer**: Located in [Inclinometer.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/Inclinometer.tsx). Uses CSS transitions `style={{ transform: 'rotate(' + roll + 'deg)' }}` to pivot a vessel cross-section SVG. The hull outline changes color adaptively (Green if roll <= 2.0°, Amber if <= 5.0°, Red if > 5.0°).
*   **Page Map Integration**: Rendered in [VoyageIntelligence.tsx](file:///d:/MareTide%20Js/dashboard_react/src/components/VoyageIntelligence.tsx) via `react-leaflet`. Reads custom Mapbox/JawgMaps/OSM access tokens from local storage and toggles dark map tiles on and off based on the active dark theme.

### 2. Monolithic Streamlit Frontend (`dashboard/app.py`)
*   Imports design tokens from `theme/design_system.py`. Uses custom CSS blocks injected via `st.markdown('<style>...', unsafe_allow_html=True)` to styling cards, sidebar panels, buttons, and custom layout slots.
*   Uses `streamlit-autorefresh` configured to trigger every 30 seconds for live AIS updates.

---

## PHASE 5 — BACKEND DEEP ANALYSIS

### 1. Python FastAPI Sidecar (`sidecar_python/`)
*   **Main Server**: [main.py](file:///d:/MareTide%20Js/sidecar_python/main.py) running on port 8001. Handles REST routing and exposes camera MJPEG streams `/api/video/{camera_id}` using `StreamingResponse(frame_generator)`.
*   **State Machine Thread**: [state.py](file:///d:/MareTide%20Js/sidecar_python/state.py) spawns a daemon thread executing `run_telemetry_loop()` at 10Hz. Telemetry parameters transition `iot_flow_stage` through:
    `WAITING_FOR_CARGO` -> (cargo placed >= 0.1kg) -> `PLACING_CARGO` -> (drain confirmed) -> `DRAINING` -> (ESP32 status becomes READY) -> `COMPLETED`.
*   **Stability Metrics**: Calculated on every tick using `StabilityAnalyzer`:
    *   $\text{List} = \text{Starboard Total Weight} - \text{Port Total Weight}$
    *   $\text{Trim} = \text{Aft Cargo Weight} - \text{Fore Cargo Weight}$
    *   $\text{Stability Score} = \max(\text{RollNorm}, \text{PitchNorm}, \text{ListNorm}, \text{TrimNorm})$

### 2. Node.js API Gateway (`backend_node/`)
*   Listens on port 8000. Uses Express. Broadcasts telemetry updates by fetching `/api/vessel-state` from the sidecar at 10Hz and pushing to active WebSocket clients on `/ws/telemetry`.

### 3. API Endpoints Table (Gateway Port 8000 / Sidecar Port 8001)

| Method | Endpoint | Purpose | Request | Response | Authentication | Backend Flow |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GET** | `/api/auth/exchange` | Exchange redirection token | `token` query | `{valid: true, user: email}` | None | Proxy to Flask `/api/validate_token` |
| **GET** | `/api/auth/session` | Check active session | Cookie Header | `{authenticated: bool}` | Cookie Session | Proxy to Flask `/api/check_session` |
| **GET** | `/api/vessel-state` | Fetch full vessel telemetry | None | Telemetry & state JSON | Session cookie | Fetch from `state.latest_telemetry` |
| **POST** | `/api/ballast/calculate-compensation` | Initiate cargo slot planning | `id, bay, side, tier` | `{success: true, stage}` | Session cookie | Validate weight space -> Set `planned_container` |
| **POST** | `/api/ballast/confirm-drain` | Trigger active pump drain | None | `{success: true}` | Session cookie | Send serial command -> Set state to `DRAINING` |
| **POST** | `/api/ballast/pump` | Manual water transfer | `from_side, to_side, amount, from_bay, to_bay` | `{success: true, message}` | Session cookie | Spawn async background uvicorn task to drain tanks |
| **GET** | `/api/recommendations` | Get optimal cargo slot & explainable AI pump advice | None | `{best_bay, best_side, explainable_recs}` | Session cookie | Analyze hull imbalances -> Generate vector shift math |
| **GET** | `/api/video/{camera_id}` | Retrieve MJPEG live video stream | None | multipart/x-mixed-replace | None | Direct feed from `VisionManager` opencv frame buffer |
| **GET** | `/api/voyage/track` | Fetch vessel voyage AIS coordinates | `imo` query | `[lat, lng]` array | Session cookie | Call `MyShipTrackingClient.get_vessel_track()` (**CRITICAL BUG DETECTED**) |

---

## PHASE 6 — DATABASE ANALYSIS

The application maintains two separate SQLite databases:
1.  **`sidecar_python/maretide.db`**: Configured for operational logging.
    *   **`cargo_operations`**: Logs container loads. Fields: `id` (INTEGER PK), `timestamp` (TEXT), `event` (TEXT e.g. LOAD), `container_id` (TEXT), `weight` (REAL), `bay` (INTEGER), `side` (TEXT), `tier` (INTEGER), `source` (TEXT e.g. ESP32/Simulation).
    *   **`ballast_operations`**: Logs active pumps. Fields: `id` (INTEGER PK), `timestamp` (TEXT), `op_type` (TEXT e.g. Drain/Transfer), `pump_mode` (TEXT e.g. Automatic/Manual), `source` (TEXT), `dest` (TEXT), `qty` (REAL), `remaining_src` (REAL), `final_dest` (REAL), `score_before` (REAL), `score_after` (REAL), `trigger_source` (TEXT e.g. AI/User).
2.  **`navi_vision/vision_alerts.db`**: Configured for Computer Vision security and collision warnings.
    *   **`vision_alerts`**: Logs CV detections. Fields: `id` (INTEGER PK), `category` (TEXT), `severity` (TEXT e.g. INFO, WARNING, EMERGENCY), `confidence` (REAL), `message` (TEXT), `recommendation` (TEXT), `camera` (TEXT), `timestamp` (REAL).

---

## PHASE 7 — AUTHENTICATION & SECURITY

1.  **Redirection Handshake**: Bypasses CORS constraints on cross-port redirects. The Flask server validates login credentials, generates a single-use UUID4 token valid for 60 seconds, and redirects the client browser to `http://localhost:3000/?token={token}`. The React frontend exchanges the token with the Node.js Gateway, which validates it against Flask's `/api/validate_token` endpoint.
2.  **Security Flaws / Hardcoded keys**:
    *   `FLASK_SECRET_KEY` defaults to `"maretide-secret-stability-key-2026"` in both `server.py` files if the environment variable is not defined.
    *   `d:\MareTide Js\server.py` index route contains a development bypass: it automatically logs in as `admin@maretide.com` and generates a token for every access, disabling authentication check features during local testing.
    *   Input sanitization lacks boundary verification on manual pump endpoints: `/api/ballast/pump` accepts negative `amount` weights, risking unexpected database records.

---

## PHASE 8 — AI/ML ANALYSIS

1.  **Models & Providers**: Utilizes a local YOLOv8 Nano model weights file ([yolov8n.pt](file:///d:/MareTide/yolov8n.pt)) running locally inside PyTorch or CPU mode.
2.  **Person Zone Intrusion Alert**: Filters predictions for Class 0 (`person`). Defines a restricted passage zone polygon inside the corridor frame. Uses OpenCV's `pointPolygonTest` to check if a person's bounding box center falls inside the safety bounds.
3.  **Collision Proximity Alarm**: Filters predictions for Classes 2, 7, 8 (`car`, `truck`, `boat`). Approximates distance using the bounding box pixel area. If box area > 28000 pixels, it triggers an `EMERGENCY` collision risk warning.
4.  **Explainable AI (XAI) Advice**: Generates human-readable descriptions of center of gravity (CG) shifts, detailing metacentric height changes, transverse center of gravity moments, and corrective volume transfers.

---

## PHASE 9 — EXTERNAL SERVICES & INTEGRATIONS

1.  **MyShipTracking API**: Handles live AIS tracking. Requests location details using `GET /api/v2/vessel?imo={imo}`. Falls back to simulated mock track coordinates if API responses return credentials or credit limit errors.
2.  **Open-Meteo & Marine API**: Queries current temperature, wind speed, wave heights, and daily forecasts based on coordinate parameters.
3.  **Mapbox / Stadia Maps / JawgMaps / Thunderforest**: Supports custom vector tile URLs when coordinate map tokens are entered in settings.

---

## PHASE 10 — COMPLETE DATA FLOW

### Telemetry & Automatic Ballast Compensation Flow:
1.  **Physical Sensor (ESP32)**: HX711 scale load sensor detects new cargo weight and broadcasts JSON telemetry over serial.
2.  **FastAPI Sidecar (state.py)**: Spawns `SerialTelemetryReader` thread, parses JSON, and updates `state.latest_telemetry`.
3.  **Express Gateway (server.js)**: Polls `/api/vessel-state` at 10Hz and broadcasts JSON payload to React via WebSocket `/ws/telemetry`.
4.  **React Frontend (LiveMonitor.tsx)**: Displays the new weight (e.g. 50 kg) on the dashboard and prompts user for slots.
5.  **User Action**: Operator selects slot "Bay 2 - Port" and clicks "Calculate Compensation".
6.  **FastAPI Sidecar**: Set `planned_container` values and transitions state to `CONFIRM_COMPENSATION`.
7.  **User Action**: Operator reviews the plan and clicks "Execute Drain".
8.  **FastAPI Sidecar**: Calls `reader.send_drain_command(cargo_weight)` and transitions state to `DRAINING`.
9.  **Physical ESP32**: Receives `DRAIN:weight` command over Serial, opens the servo gate valve, and illuminates `PUMP_LED`.
10. **Physical ESP32**: Ultrasonic distance sensor HC-SR04 measures declining water height. Once the target level is reached, the servo valve closes and status changes to `READY`.
11. **FastAPI Sidecar**: Telemetry loop detects `READY` status. It persists the cargo load to SQLite `cargo_operations`, updates virtual ballast levels, logs the ballast change to `ballast_operations`, and sets state to `COMPLETED`.
12. **React Frontend**: Refreshes metrics, resets scale overlays, and closes the loading modal.

---

## PHASE 11 — SYSTEM ARCHITECTURE

```text
                    ┌──────────────────┐
                    │  Operator Browser│
                    │   (React SPA)    │
                    └────────┬─────────┘
                             │
                             ▼ (Port 8000)
                    ┌──────────────────┐
                    │  Node.js Gateway │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
   (REST)     │                             │ (WS / REST)
              ▼ (Port 5000)                 ▼ (Port 8001)
     ┌──────────────────┐          ┌──────────────────┐
     │ Flask Auth Server│          │ FastAPI Sidecar  │
     └──────────────────┘          └────────┬─────────┘
                                            │
                             ┌──────────────┼──────────────┐
                             ▼              ▼              ▼
                         SQLITE DBs      YOLOv8      SERIAL LINK (COM)
                       (maretide.db)   (PyTorch)     (Physical ESP32)
```

---

## PHASE 12 — CONFIGURATION & ENVIRONMENT

*   `MYSHIPTRACKING_API_KEY`: Present (`f141c3c35e7ade2a15c965f394e05315`).
*   `FLASK_SECRET_KEY`: Defaults to `"maretide-secret-stability-key-2026"` in codebase, overridable via environment variables.
*   `AUTO_LOGIN_IF_SESSION_EXISTS`: Configured to `False` by default in development mode.
*   `ENABLE_SQLITE`: Set to `True` for database persistence.
*   `SIMULATION_MODE`: Configured via `vision_config.py` to dictate whether YOLO runs or falls back to simulation categories.

---

## PHASE 13 — TESTING & VERIFICATION

1.  **Test Coverage**: There is **no automated testing framework** (such as pytest, Jest, Vitest, or Cypress) configured in any of the workspaces. No test files or unit tests are present.
2.  **Verification**: Verified that the React project builds cleanly. The Vite configuration and Oxlint parser compiled all components, templates, and styles without error.

---

## PHASE 14 — DEPLOYMENT

### Development Startup Sequence (React Version):
1.  **Prepare Python Environment**:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    pip install fastapi uvicorn requests opencv-python ultralytics pyserial
    ```
2.  **Prepare Node Gateway & React Dashboard**:
    ```bash
    cd backend_node && npm install
    cd ../dashboard_react && npm install
    ```
3.  **Orchestrate Launch**:
    Run `python run.py` in the root of `d:\MareTide Js`. This starts:
    *   Flask Authentication Server: http://localhost:5000
    *   FastAPI Sidecar: http://localhost:8001
    *   Node Express Gateway: http://localhost:8000
    *   React Dashboard: http://localhost:3000
    Opens default browser directly to http://localhost:5000.

---

## PHASE 15 — CURRENT IMPLEMENTATION STATUS

| Feature | Status | Evidence | Missing Pieces / Issues |
| :--- | :--- | :--- | :--- |
| **Bypass Auth Mode** | 🟢 COMPLETE | `server.py` | None |
| **SCADA Twin SVG** | 🟢 COMPLETE | `SCADADigitalTwin.tsx` | None |
| **Inclinometer Dial** | 🟢 COMPLETE | `Inclinometer.tsx` | None |
| **Advisory Engine** | 🟢 COMPLETE | `ship.py` / `advisoryAPI` | None |
| **ESP32 Serial Link** | 🟢 COMPLETE | `serial_reader.py` / `.ino` | None |
| **YOLOv8 Detection** | 🟢 COMPLETE | `vision_yolo_runner.py` | None |
| **Gradual Pumping** | 🟢 COMPLETE | `main.py` (gradual task) | None |
| **API Key Check** | 🟢 COMPLETE | `myshiptracking.py` | None |
| **SQLite Logs** | 🟢 COMPLETE | `logs_db.py` / `maretide.db` | None |
| **AIS Voyage Map** | ⚠️ BROKEN | `main.py:681` call | Calls `client.get_current_track` which does not exist in `MyShipTrackingClient` (**CRITICAL BUG**) |
| **JS Python reqs** | 🔴 MISSING | Root folder | No `requirements.txt` file exists in `d:\MareTide Js` workspace |

---

## PHASE 16 — TECHNICAL DEBT & PROBLEMS

1.  **AIS Voyage Track Crash (CRITICAL)**: The endpoint `/api/voyage/track` invokes `client.get_current_track(imo)`. However, `MyShipTrackingClient` only defines `get_vessel_track(imo)`. This throws an `AttributeError` and crashes Leaflet track loading.
2.  **Missing Python dependencies list (HIGH)**: `d:\MareTide Js` has no `requirements.txt`. Developers must manually extract dependencies from python scripts.
3.  **Hardcoded Flask Secret Key (MEDIUM)**: Bypasses environment config controls, leaving session signing keys identical across installations.
4.  **Bypassed Authentication Screen (LOW)**: The login page is disabled in the JS setup since `/` auto-logs in and redirects instantly.

---

## PHASE 17 — ADDITIONAL FEATURE ROADMAP

*   *See [PROJECT_FEATURE_ROADMAP.md](file:///d:/MareTide/PROJECT_FEATURE_ROADMAP.md) for full implementation specifications.*

---

## PHASE 18 — HACKATHON / PRODUCT IMPROVEMENT

1.  **Drag-and-Drop Stowage Planning**: Adding a dynamic canvas to let cargo managers drag and place containers directly onto ship slots, recalculating stability live.
2.  **Automated Ballast Compensation Loop**: Implementing closed-loop control where the FastAPI sidecar automatically triggers pump transfers to restore metacentric height without requiring user confirmation clicks.
3.  **Historical Telemetry Trends**: Wiring Recharts graphs to display listing and trim trends over time, helping identify cargo shifts during voyage transits.
4.  **Security Hardening**: Resolving hardcoded secrets, validating inputs (e.g. pump amounts), and restoring the login credentials page in the React dashboard build.
5.  **Robust Serial Reconnection Daemon**: An automatic polling worker that detects USB drops and reconnects COM ports without interrupting app execution.

---

## PHASE 19 — FINAL blueprint

*   *See [PROJECT_ARCHITECTURE.md](file:///d:/MareTide/PROJECT_ARCHITECTURE.md) for the detailed final architectural blueprint.*
