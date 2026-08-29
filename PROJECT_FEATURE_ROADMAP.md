# FEATURE IMPLEMENTATION ROADMAP

This roadmap outlines the current feature completion status, known issues, proposed additions, implementation specifications, and release priorities.

---

## 1. Feature Matrices

### Core Platform Status

| Feature Name | Status | Technical Implementation | Priority |
| :--- | :--- | :--- | :--- |
| **User Authentication** | 🟢 COMPLETE | Flask microservice session storage + single-use redirect tokens | 🔥 MUST HAVE |
| **Inclinometer Visualizer** | 🟢 COMPLETE | Dynamic SVG rotation pivoting on roll telemetry | 🔥 MUST HAVE |
| **SCADA Digital Twin** | 🟢 COMPLETE | Dynamic SVG compartments responding to ballast fill ratios | 🔥 MUST HAVE |
| **Telemetry State Machine** | 🟢 COMPLETE | Asynchronous daemon thread polling serial COM ports | 🔥 MUST HAVE |
| **AI Slot Recommendation** | 🟢 COMPLETE | Stability scoring search minimises combined list + trim | ⭐ HIGH VALUE |
| **YOLOv8 Security Zones** | 🟢 COMPLETE | Bounding box polygon intersection person detector | ⭐ HIGH VALUE |
| **Optic Flow Leak Detector** | 🟢 COMPLETE | Bitwise AND of motion mask and HSV white foam range | ⭐ HIGH VALUE |
| **Explainable AI Advice** | 🟢 COMPLETE | Shifts vector moments calculation and lists tank targets | 💡 NICE TO HAVE |
| **AIS Voyage Tracker** | ⚠️ BROKEN | Leaflet map with standard tiles and polyline route tracker | 🔥 MUST HAVE |
| **Python Sidecar Reqs** | 🔴 MISSING | FastAPI dependencies list | 🔥 MUST HAVE |

---

## 2. Technical Debt, Bugs & Broken Elements

### 1. AIS Voyage Track Crash
*   **Severity**: 🚨 CRITICAL (Crash)
*   **Description**: In `d:\MareTide Js\sidecar_python\main.py` line 681, the REST endpoint calls `client.get_current_track(imo)`. However, `MyShipTrackingClient` in `sidecar_python/voyage/myshiptracking.py` does not contain `get_current_track()`, only `get_vessel_track()`. This throws an `AttributeError` and crashes Leaflet track loading.
*   **Resolution Steps**: Modify `main.py:681` to call `client.get_vessel_track(imo)` and import mock helpers when API requests return credit/auth errors.
*   **Est. Effort**: 10 minutes (Low)

### 2. Missing Python Dependency List in JS Workspace
*   **Severity**: 🟠 HIGH (Documentation)
*   **Description**: The root of `d:\MareTide Js` does not contain a `requirements.txt` file, although the `README.md` instructs developers to install packages using `pip install -r requirements.txt`.
*   **Resolution Steps**: Create a `requirements.txt` file in `d:\MareTide Js` containing `fastapi`, `uvicorn`, `requests`, `opencv-python`, `ultralytics`, and `pyserial`.
*   **Est. Effort**: 5 minutes (Low)

### 3. Bypass Auth Vulnerability in Development Mode
*   **Severity**: 🟡 MEDIUM (Security)
*   **Description**: The Flask server in `d:\MareTide Js\server.py` immediately logs in as `admin@maretide.com` and bypasses credentials validation for every access.
*   **Resolution Steps**: Set `AUTO_LOGIN_IF_SESSION_EXISTS = False` and restore standard credentials verification screens once dashboard integration is complete.
*   **Est. Effort**: 15 minutes (Low)

---

## 3. Proposed Features & Release Phases

### Phase 1: Stability Enhancements (Short-term)

#### 1. Closed-Loop Automatic Ballast Pumping
*   **Why it fits**: The current system generates ballast advice but requires the operator to click "Execute Drain" or manually toggle pumps. This feature automatically triggers ballast compensation.
*   **Implementation Steps**:
    *   Add an "Auto-Compensation Mode" toggle in `SCADADigitalTwin.tsx`.
    *   Add a sidecar polling hook that monitors stability score. If score > 40 (Moderate/Warning) and mode is AUTO, automatically trigger gradual pump tasks to restore metacentric height.
    *   Log automated adjustments to `ballast_operations` database with trigger `AI-Auto`.
    *   **API Changes**: `POST /api/ballast/auto-toggle {enabled: bool}`
    *   **Difficulty**: Medium
    *   **Est. Time**: 4 hours
    *   **Priority**: 🔥 MUST HAVE

#### 2. Drag-and-Drop Cargo Planner
*   **Why it fits**: Users currently type container weights and bay coordinates into input forms. Drag-and-drop slotting provides a modern desktop container terminal experience.
*   **Implementation Steps**:
    *   Rebuild `DeckView.tsx` as an interactive SVG canvas or HTML5 drag-and-drop wrapper.
    *   Allow users to drag new containers from a "Staging Area" onto empty deck slots.
    *   On mouse hover, calculate stability impact dynamically using `/api/recommendations` and render preview shadows (Green = stable, Red = unsafe).
    *   **Frontend changes**: Rebuild `DeckView.tsx` with drag hooks.
    *   **Difficulty**: High
    *   **Est. Time**: 8 hours
    *   **Priority**: ⭐ HIGH VALUE

### Phase 2: Telemetry & Resilience (Mid-term)

#### 3. Automatic COM Port Reconnection Daemon
*   **Why it fits**: If the physical USB/Serial cable drops or disconnects during a demo, uvicorn/python serial loops crash and telemetry halts.
*   **Implementation Steps**:
    *   Add a background reconnection thread in `serial_reader.py`.
    *   If serial connection throws an exception, catch it, set state to "DISCONNECTED", and poll list ports every 2.0 seconds.
    *   Once the physical port reappears, automatically re-establish the baud link and restore live updates without requiring server restarts.
    *   **Difficulty**: Low
    *   **Est. Time**: 2 hours
    *   **Priority**: ⭐ HIGH VALUE

#### 4. Historical Telemetry Graphing Dashboard
*   **Why it fits**: Operators cannot see heel/trim trends during voyage transit, making it difficult to detect cargo shifting.
*   **Implementation Steps**:
    *   Add `Recharts` line graphs inside `DashboardOverview.tsx`.
    *   Poll historical telemetry records from SQLite `ballast_operations` / `cargo_operations`.
    *   Render line charts displaying Roll and Pitch history over a rolling 1-hour window.
    *   **API Changes**: `GET /api/telemetry/history`
    *   **Difficulty**: Low
    *   **Est. Time**: 3 hours
    *   **Priority**: 💡 NICE TO HAVE

### Phase 3: Scaling & Security (Long-term)

#### 5. Multi-Vessel Fleet Tracking Map
*   **Why it fits**: The Voyage Intelligence map currently tracks a single vessel. Fleet tracking allows fleet managers to view all active vessels on one screen.
*   **Implementation Steps**:
    *   Extend `VoyageIntelligence.tsx` to query multiple IMOs.
    *   Plot multiple Leaflet markers, color-coded by active vessel status (Green = Underway, Yellow = Anchor, Red = Alert).
    *   **Database Changes**: Create a `vessels` table mapping ship name, IMO, and active status.
    *   **Difficulty**: Medium
    *   **Est. Time**: 5 hours
    *   **Priority**: 🚀 FUTURE
