# MareTide — API Reference Manual (Phase 6F Release)

## Base URL
- Sidecar API: `http://localhost:8000`
- WebSocket Telemetry: `ws://localhost:8000/api/telemetry/ws`

---

## 1. Container Document Intelligence (Phase 1 & 4)

### `POST /api/container/extract`
Extracts structured container data, weights, dimensions, and anomalies from an uploaded slip image.
- **Form Data**:
  - `file` (or `image`): Binary image (`.jpg`, `.png`, `.webp`, `.tiff`, max 15MB).
  - `engine` (optional): OCR engine override (`"rapidocr"`, `"groq"`, `"mock"`).
- **Response `200 OK`**:
```json
{
  "success": true,
  "container": {
    "container_number": "MSCU4920195",
    "container_type": "40HC",
    "weights": {
      "gross_weight_kg": 26200.0,
      "tare_weight_kg": 3800.0,
      "cargo_weight_kg": 22400.0,
      "weight_source": "DOCUMENT_AI"
    },
    "dimensions": { "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5 },
    "cargo": { "hazardous": true, "un_number": "UN 3480", "imdg_class": "Class 9" },
    "destination": "Singapore",
    "iso_type_code": "45G1"
  },
  "validation": { "valid": true, "errors": [], "warnings": [] },
  "anomalies": [],
  "document": { "confidence": 0.94, "processing_status": "verified" }
}
```

---

## 2. Container Stability & Stowage Solver (Phase 2 & 4)

### `POST /api/container/stability/analyze` (Alias: `/api/containers/analyze-stability`)
Calculates optimal slot placement for an extracted container without mutating vessel state.
- **Request Body**:
```json
{
  "container": { ... },
  "document": { ... },
  "validation": { ... },
  "weight_source": "DOCUMENT_AI"
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "recommendation": { "bay": 1, "side": "PORT", "tier": 1, "score": 98.4 },
  "candidates": [ ... ],
  "stability_before": { "list_t": 0.0, "trim_t": 0.0, "stability_score": 100.0, "risk_level": "SAFE" },
  "stability_after": { "list_t": 2.5, "trim_t": 0.8, "stability_score": 88.5, "risk_level": "SAFE" },
  "explainable_reasons": [
    "Recommended Bay 1 Tier 1 for low VCG vertical center of gravity optimization."
  ]
}
```

---

## 3. Human-in-the-Loop Loading Confirmation (Phase 2 & 5)

### `POST /api/container/load/confirm` (Alias: `/api/containers/confirm-and-load`)
Atomically commits container to live vessel upon explicit operator sign-off.
- **Request Body**:
```json
{
  "container": { ... },
  "recommendation": { "bay": 1, "side": "PORT", "tier": 1 },
  "operator_confirmed": true,
  "operator_id": "ChiefOfficer_Smith"
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "status": "LOADED",
  "container": { "container_number": "MSCU4920195", "gross_weight_t": 26.2 },
  "loaded_position": { "bay": 1, "side": "PORT", "tier": 1 },
  "message": "Container successfully committed to live vessel state."
}
```

---

## 4. Ballast Auto-Compensation (Phase 3 & 5)

### `POST /api/container/ballast/calculate` (Alias: `/api/containers/ballast-compensation`)
Computes counter-moment ballast water transfer required to restore equilibrium.
- **Request Body**:
```json
{
  "container_number": "MSCU4920195",
  "gross_weight_t": 26.2,
  "bay": 1,
  "side": "PORT",
  "tier": 1
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "compensation_required": true,
  "tank_key": "port_1",
  "affected_tank": "PORT-1",
  "direction": "DRAIN",
  "required_qty_t": 2.5,
  "est_duration_sec": 45.0,
  "projected_stability": { "list_t": 0.0, "trim_t": 0.0, "risk_level": "SAFE" }
}
```

### `POST /api/container/ballast/execute` (Alias: `/api/containers/execute-ballast`)
Executes operator-confirmed ballast pump discharge.
- **Request Body**:
```json
{
  "container_number": "MSCU4920195",
  "tank_key": "port_1",
  "direction": "DRAIN",
  "qty_t": 2.5,
  "operator_confirmed": true,
  "operator_id": "ChiefOfficer_Smith"
}
```
- **Response `200 OK`**:
```json
{
  "success": true,
  "affected_tank": "PORT-1",
  "actual_qty_t": 2.5,
  "three_stage_stability": {
    "before_load": { "list_t": 0.0, "trim_t": 0.0, "risk_level": "SAFE" },
    "after_container": { "list_t": 2.5, "trim_t": 0.8, "risk_level": "SAFE" },
    "after_ballast": { "list_t": 0.0, "trim_t": 0.0, "risk_level": "SAFE" }
  }
}
```

---

## 5. Hackathon Demonstration Endpoints (Phase 6E)

### `GET /api/container/demo/fixtures`
Returns registered demo scenarios and metadata.

### `GET /api/container/demo/fixtures/{filename}/image`
Returns binary fixture image for demonstration loading.

### `POST /api/container/demo/reset`
Atomically resets vessel containers, ballast tanks, and audit logs for clean demonstration execution.
