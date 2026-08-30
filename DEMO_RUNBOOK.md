# MareTide — Live Hackathon Demonstration Runbook (3–5 Minutes)

## Objective
Present the complete, certified MareTide AI workflow to hackathon judges and maritime evaluators in under 5 minutes without manual data entry or technical glitches.

---

## Pre-Demo Checklist
1. **Start Backend & Frontend**:
   ```bash
   # Terminal 1: FastAPI Sidecar
   cd sidecar_python
   python -m uvicorn main:app --host 0.0.0.0 --port 8000

   # Terminal 2: React Dashboard
   cd dashboard_react
   npm run dev
   ```
2. **Open Browser**:
   - Navigate to `http://localhost:5173`
   - Click on **"Hackathon Demo Mode"** in the sidebar navigation.

---

## 5-Minute Script for Judges

### Minute 0:00 – 1:00: Problem & Initial Vessel State
- **Script**: *"Container ship capsize incidents like the MOL Comfort or Golden Ray often originate from misdeclared container weights and improper ballast management. MareTide automates gate interchange slip OCR, enforces SOLAS VGM safety gates, solves optimal stowage, and calculates physical ballast compensation in real-time."*
- **Action**: Show initial vessel equilibrium in the right-hand **Live Vessel Digital Twin** ($0$ containers, $0.0^\circ$ list, $0.0^\circ$ trim, `SAFE`).

### Minute 1:00 – 2:00: Scenario 1 (Golden Path Document AI Extraction)
- **Script**: *"We upload an official interchange slip. Our rapid ONNX neural OCR extracts the container number MSCU 492019 5, verified gross mass 26,200 kg, and detects UN 3480 Class 9 lithium battery cargo."*
- **Action**:
  1. Select **Scenario 1: Canonical Golden Path**.
  2. Click **Run Document AI Extraction**.
  3. Point out the badge: `PROVENANCE: [DOCUMENT AI] ONLY` (Zero Load-Cell sensor reliance).

### Minute 2:00 – 3:00: AI Stowage & Human-in-the-Loop Operator Gate
- **Script**: *"MareTide's multi-objective physics engine solves optimal placement across 8 candidate bays. It recommends Bay 1, Port, Tier 1 to maintain a low vertical center of gravity (VCG). Crucially, the AI does not auto-commit without human authorization."*
- **Action**:
  1. Click **Proceed to Multi-Objective Stowage Solver**.
  2. Review the explainable recommendations.
  3. Click **Authorize & Stow Container**.
  4. Observe the live digital twin updating instantly with the newly stowed container.

### Minute 3:00 – 4:00: Automated Ballast Re-Balancing & Pump Trigger
- **Script**: *"Stowing 26.2 tonnes on the port side induces a 2.5° list moment. MareTide automatically calculates that discharging 2.5 tonnes from Port Tank 1 will restore perfect equilibrium. The Chief Officer authorizes the pump transfer."*
- **Action**:
  1. Review the Ballast Compensation Card.
  2. Click **Authorize & Execute Ballast**.
  3. Review the **3-Stage Stability Table**:
     - `1. Before Load: 0.0° list`
     - `2. After Container: 2.5° list (Loaded)`
     - `3. After Ballast: 0.0° list (Equilibrium Restored)`
  4. Show the immutable SQLite audit record created for maritime compliance.

### Minute 4:00 – 5:00: Scenario 2 (Adversarial Safety Rejection Demo)
- **Script**: *"What happens when a fraudulent or erroneous slip arrives? In Scenario 2, the gate slip claims Tare 3,800 kg + Cargo 10,000 kg = Gross 28,000 kg, hiding a massive 14.2 tonne discrepancy."*
- **Action**:
  1. Select **Scenario 2: Critical Anomaly (VGM Mismatch)**.
  2. Click **Run Document AI Extraction**.
  3. Show the glowing red alert: `CRITICAL SAFETY ANOMALY DETECTED • LOAD LOCKED`.
  4. Show that MareTide strictly refuses to stow uncertified cargo, protecting vessel and crew safety.
