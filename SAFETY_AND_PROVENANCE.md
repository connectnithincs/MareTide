# MareTide — Safety Policy & Zero Load-Cell Provenance Manual

## Core Principle: Zero Load-Cell Usage Policy

### 1. Mandatory Authority Rule
In accordance with international maritime regulations (SOLAS Chapter VI, Regulation 2) and verified container mass standards, **container cargo mass MUST originate exclusively from verified Document AI / OCR interchange receipts**.

**Load-cell sensor data is strictly prohibited from influencing:**
1. Container gross weight (VGM)
2. Container tare weight
3. Cargo weight
4. Stowage slot optimization
5. Transverse list calculation ($M_T$)
6. Longitudinal trim calculation ($M_L$)
7. Vertical center of gravity (VCG / $\text{KG}$)
8. Stability safety score
9. Ballast compensation calculations
10. Chief Officer loading approval gates
11. Compliance audit records
12. Digital twin container mass attributes.

---

## 2. Provenance Architecture & Data Flow

```
                      [Physical Gate Interchange Slip]
                                     │
                                     ▼
                      [Document AI Neural OCR Pipeline]
                                     │
                                     ▼
                      [ISO 6346 & SOLAS VGM Normalization]
                                     │
                                     ▼
                      [CargoMassMetadata: DOCUMENT_AI]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
    [Stowage Physics Engine]                [Ballast Compensation Solver]
    (Mass: 26,200 kg from OCR)              (Mass: 26,200 kg from OCR)
                 │                                       │
                 ▼                                       ▼
    [Live Vessel State: 26.2t]              [SQLite Audit: DOCUMENT_AI]
```

---

## 3. Cryptographic Audit Invariance

Every container committed to the vessel records an immutable audit entry in SQLite with:
- `weight_source: "DOCUMENT_AI"`
- `gross_weight_kg`: Derived strictly from OCR extraction
- `operator_confirmed: true`
- `operator_id`: Authenticated Chief Officer identifier
- `event_hash`: SHA-256 hash chaining ensuring non-repudiation.

---

## 4. Safety Gates & Fail-Safe Mechanisms

| Threat / Anomaly | System Response | State Impact |
|:---|:---|:---|
| **VGM Mass Discrepancy ($>500\,\text{kg}$)** | `CRITICAL_ANOMALY` Flagged | Loading Gate **LOCKED** |
| **Invalid Check Digit** | `VALIDATION_WARNING` Flagged | Operator Review Required |
| **Overweight Container ($>35\,\text{t}$)** | Structural Overload Warning | Higher Tiers Prohibited |
| **Hazmat Separation Conflict** | Placement Incompatibility Flagged | Conflicting Bays Blocked |
| **Unconfirmed Loading Request** | HTTP `400 / Rejected` | Zero Vessel Mutation |
| **Unconfirmed Ballast Request** | HTTP `400 / Rejected` | Zero Pump Actuation |
