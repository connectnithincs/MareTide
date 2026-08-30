# MareTide — Final System Architecture (Phase 6F Release)

## Executive Summary
MareTide is an autonomous, AI-driven maritime container stowage optimization and dynamic ballast compensation system. It eliminates human calculation error, enforces strict SOLAS VGM safety gates, and provides explainable, real-time stability balancing for container vessels.

---

## 1. System Topology & Component Hierarchy

```
                                  ┌────────────────────────────────────────┐
                                  │      MARETIDE DASHBOARD (REACT + TS)   │
                                  │  • Container Slip AI (Phase 1 & 2)     │
                                  │  • Live Telemetry Twin (Phase 5)       │
                                  │  • Hackathon Demo Mode (Phase 6E)      │
                                  │  • Ballast & Valve Controller          │
                                  └───────────────────┬────────────────────┘
                                                      │ HTTP / WebSocket (8000)
                                                      ▼
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       FASTAPI SIDECAR BACKEND (PORT 8000)                                      │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                                │
│  ┌────────────────────────┐    ┌────────────────────────┐    ┌────────────────────────┐    ┌─────────────────┐ │
│  │ 1. DOCUMENT AI OCR     │───►│ 2. DOMAIN VALIDATION   │───►│ 3. ANOMALY DETECTION   │───►│ 4. STOWAGE PLAN   │ │
│  │ • RapidOCR ONNX CPU    │    │ • ISO 6346 Check Digit │    │ • SOLAS VGM Discrepancy│    │ • 8-Candidate   │ │
│  │ • Bilateral / Deskew   │    │ • Tare/Gross Sanity    │    │ • Hazmat Conflict      │    │   Multi-Obj     │ │
│  │ • Structured RegEx     │    │ • Dimensions / Type    │    │ • Overweight Block     │    │ • GM & Metacenter│ │
│  └────────────────────────┘    └────────────────────────┘    └────────────────────────┘    └────────┬────────┘ │
│                                                                                                     │          │
│                                                                                                     ▼          │
│  ┌────────────────────────┐    ┌────────────────────────┐    ┌────────────────────────┐    ┌─────────────────┐ │
│  │ 8. SQLITE AUDIT TRAIL  │◄───│ 7. 3-STAGE STABILITY   │◄───│ 6. BALLAST COMPENSATION│◄───│ 5. OPERATOR GATE│ │
│  │ • Cryptographic Hash   │    │ • Before / After / Bal │    │ • Counter-Moment Solver│    │ • Chief Officer │ │
│  │ • Event Provenance     │    │ • Hydrostatic Delta    │    │ • Pump Duration Est    │    │   Explicit Auth │ │
│  │ • Immutable Timeline   │    │ • Safety Risk Class    │    │ • Target Tank Selection│    │ • Atomic Commit │ │
│  └────────────────────────┘    └────────────────────────┘    └────────────────────────┘    └─────────────────┘ │
│                                                                                                                │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │
│  │ REAL-TIME TELEMETRY SUBSYSTEM (PHASE 5)                                                                    │ │
│  │ • Inclinometer, Tank Gauges, Flow Sensors, Strain Gauges, Barometer (LOAD-CELL ZERO USE ENFORCED)          │ │
│  │ • Adapter Hierarchy: In-Memory Vessel Simulator Engine ◄──► Serial/NMEA Hardware ◄──► WebSocket Polling   │ │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Subsystems

### Subsystem 1: Container Document Intelligence (Phase 1)
- **Engine**: Cached singleton ONNX Runtime CPU (`RapidOCREngine`), optional Groq Vision multimodal fallback.
- **Preprocessing**: Single-pass load, skew angle detection, contrast enhancement (CLAHE).
- **Extraction**: Regex & pattern parsing for ISO 6346, gross mass, tare mass, cargo mass, ISO size type, seal numbers, and IMDG/UN Hazmat codes.
- **Provenance**: Tagged with immutable metadata: `source: DOCUMENT_AI`, `origin: GATE_SLIP_OCR`.

### Subsystem 2: Domain Validation & Anomaly Detection (Phase 4A & 4E)
- **ISO 6346 Modulo-11**: Check digit verification across owner code, category, and serial.
- **SOLAS VGM Mass Invariance**: Enforces $|\text{Gross} - (\text{Tare} + \text{Cargo})| \le 500\,\text{kg}$. Any violation $>500\,\text{kg}$ triggers `CRITICAL ANOMALY` and locks loading.
- **Safety Gate**: Rejects anomalous, missing-weight, or unverified documents before stowage solver invocation.

### Subsystem 3: Multi-Objective Stowage Solver (Phase 4B & 4D)
- **Physics Engine**: Calculates transverse list moment ($M_T$), longitudinal trim moment ($M_L$), vertical center of gravity ($\text{KG}$), transverse metacenter ($\text{KM}_T$), and transverse metacentric height ($\text{GM}_T$).
- **Objective Function**: Minimizes list penalty, trim penalty, vertical height penalty, and stack weight limit violations.
- **Explainable Decision Engine**: Synthesizes natural language reasoning for Chief Officers.

### Subsystem 4: Human-in-the-Loop Operator Gates (Phase 2 & 5)
- **Loading Gate**: Unconfirmed loading requests (`operator_confirmed=False`) are rejected.
- **Ballast Gate**: Unconfirmed ballast requests (`operator_confirmed=False`) are rejected.
- **Zero Auto-Commit**: Vessel state is only mutated upon explicit operator authorization.

### Subsystem 5: Real-Time Telemetry & Digital Twin (Phase 5)
- **Telemetry Ingestion**: Ingests inclinometer list/trim, tank levels, flow rates, and strain gauges.
- **Zero-Load-Cell Enforcement**: Load-cell sensor data is completely excluded from container cargo weight, list, trim, stability, stowage, ballast, and audit calculations.

### Subsystem 6: Immutable SQLite Audit System (Phase 5 & 6)
- **Schema**: `cargo_operations`, `ballast_operations`, `container_loading_audits`, `operation_audit_events`.
- **Integrity**: Cryptographic hashing (`prev_event_hash` $\rightarrow$ `event_hash`) ensuring non-repudiation.

---

## 3. Data Integrity & Release Standards
- **Python Backend**: Python 3.14 / FastAPI / Pydantic V2 / OpenCV / RapidOCR / NumPy / SQLite3.
- **Frontend**: React 18 / TypeScript / Vite / TailwindCSS / Lucide Icons.
- **Test Coverage**: 321 automated unit and integration tests across 24 test suites with 100% pass rate.
