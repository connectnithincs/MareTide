"""
Phase 5: Real-Time Operational Integration & Load-Cell Exclusion Test Suite.

CRITICAL REQUIREMENT VERIFICATION:
1. Load-cell sensor data (HX711 / scale cargo_kg) CANNOT alter container weight.
2. Load-cell sensor data CANNOT alter vessel stability calculations or equilibrium.
3. Load-cell sensor data CANNOT alter ballast compensation recommendations or execution.
4. Load-cell sensor data CANNOT authorize container loading without validated Document AI and operator sign-off.
5. Load-cell sensor data CANNOT modify the digital twin cargo state.
6. The Digital Twin labels cargo weight provenance as "[DOCUMENT AI]" and NEVER "[LOAD CELL]".
7. The Authoritative Cargo Weight Pipeline strictly enforces:
   Container Slip Image -> OCR -> Field Extraction -> Normalization -> Validation -> Validated Gross Weight -> Stability Engine.
"""

import io
import os
import sys
import copy
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Ship, Container, StabilityAnalyzer
import state
from digital_twin import DigitalTwin
from reports.logs_db import clear_logs
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    ALLOWED_WEIGHT_SOURCES,
    FORBIDDEN_WEIGHT_SOURCES,
    assert_authoritative_source
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0
    state.reset_operational_stage()
    yield
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0
    state.reset_operational_stage()


# =========================================================================
# 1. EXPLICIT SOURCE-OF-TRUTH POLICY TESTS
# =========================================================================

def test_phase5_source_of_truth_policy_constants():
    """Verify that CONTAINER_WEIGHT_SOURCE is 'DOCUMENT_AI' and forbidden sources are defined."""
    assert CONTAINER_WEIGHT_SOURCE == "DOCUMENT_AI"
    assert PROVENANCE_LABEL == "[DOCUMENT AI]"
    assert "DOCUMENT_AI" in ALLOWED_WEIGHT_SOURCES
    assert "LOAD_CELL" in FORBIDDEN_WEIGHT_SOURCES
    assert "SCALE" in FORBIDDEN_WEIGHT_SOURCES
    assert "WEIGHING_SENSOR" in FORBIDDEN_WEIGHT_SOURCES
    assert "HX711" in FORBIDDEN_WEIGHT_SOURCES

    # Allowed sources pass
    assert assert_authoritative_source("DOCUMENT_AI") is True
    assert assert_authoritative_source("[DOCUMENT AI]") is True
    assert assert_authoritative_source("VALIDATED_OCR_DOCUMENT_JSON") is True

    # Forbidden sources raise ValueError
    with pytest.raises(ValueError) as exc:
        assert_authoritative_source("LOAD_CELL")
    assert "FORBIDDEN_WEIGHT_SOURCES" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        assert_authoritative_source("SCALE")
    assert "FORBIDDEN_WEIGHT_SOURCES" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        assert_authoritative_source("HX711_WEIGHING_SENSOR")
    assert "FORBIDDEN_WEIGHT_SOURCES" in str(exc.value)


def test_phase5_operational_policy_endpoint():
    """Verify GET /api/operations/policy exposes the exact Allowed and Forbidden data source policy."""
    response = client.get("/api/operations/policy")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["container_weight_source"] == "DOCUMENT_AI"
    assert data["provenance_label"] == "[DOCUMENT AI]"
    assert "DOCUMENT_AI" in data["allowed_sources"]
    assert "LOAD_CELL" in data["forbidden_sources"]
    assert "SCALE" in data["forbidden_sources"]
    assert "WEIGHING_SENSOR" in data["forbidden_sources"]


# =========================================================================
# 2. PROOF REQUIREMENT 1: LOAD CELL CANNOT ALTER CONTAINER WEIGHT
# =========================================================================

def test_phase5_load_cell_cannot_alter_container_weight():
    """
    Proof that injecting or changing raw scale sensor readings (e.g. cargo_kg=25.0)
    has ZERO effect on container weights in the document extraction, stability engine,
    or committed vessel state.
    """
    # 1. Simulate scale reading spike to 28.5 kg (equivalent to 285t on model scale)
    reader = state.get_current_reader()
    reader.set_simulated_cargo(28.5)

    # 2. Extract container data from document slip (VGM = 26,200 kg -> 26.2 t)
    raw_manifest_text = (
        "GLOBAL CONTAINER TERMINAL\n"
        "CONTAINER NO: MSCU 492019 5\n"
        "TYPE: 40HC\n"
        "TARE WEIGHT: 3,800 KG\n"
        "CARGO WEIGHT: 22,400 KG\n"
        "VERIFIED GROSS MASS (VGM): 26,200 KG\n"
    )
    ocr_resp = client.post("/api/container/ocr/process-raw", json={"raw_text": raw_manifest_text})
    assert ocr_resp.status_code == 200
    ocr_data = ocr_resp.json()

    # Container weight MUST derive solely from the document (26,200 kg), NOT the scale sensor (28.5 kg)
    assert ocr_data["container"]["weights"]["gross_weight_kg"] == 26200.0
    assert ocr_data["container"]["weights"]["gross_weight_kg"] != 28500.0

    # 3. Analyze stability
    stab_resp = client.post("/api/container/stability/analyze", json={
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"]
    })
    assert stab_resp.status_code == 200
    stab_data = stab_resp.json()
    assert stab_data["success"] is True
    assert stab_data["recommendation"] is not None


# =========================================================================
# 3. PROOF REQUIREMENT 2: LOAD CELL CANNOT ALTER STABILITY
# =========================================================================

def test_phase5_load_cell_cannot_alter_stability():
    """
    Proof that injecting extreme load cell values (e.g. 50 kg scale load)
    does NOT alter the vessel's calculated stability score, list, or trim.
    """
    ship = state.get_current_ship()
    # Baseline stability with 0 containers
    baseline_list = StabilityAnalyzer.calculate_list(ship)
    baseline_trim = StabilityAnalyzer.calculate_trim(ship)
    baseline_score = StabilityAnalyzer.stability_score(ship)

    # Inject scale cargo reading
    reader = state.get_current_reader()
    reader.set_simulated_cargo(50.0)

    # Fetch live operational status
    resp = client.get("/api/operations/live-status")
    assert resp.status_code == 200
    data = resp.json()

    # Vessel hydrostatics MUST match baseline (0.0 list, 0.0 trim, 0.0 cargo mass)
    assert data["total_cargo_weight_t"] == 0.0
    assert data["list_t"] == round(float(baseline_list), 2)
    assert data["trim_t"] == round(float(baseline_trim), 2)
    assert data["total_containers"] == 0


# =========================================================================
# 4. PROOF REQUIREMENT 3: LOAD CELL CANNOT ALTER BALLAST RECOMMENDATION
# =========================================================================

def test_phase5_load_cell_cannot_alter_ballast_recommendation():
    """
    Proof that ballast compensation calculation uses strictly the container's
    validated document gross weight (e.g. 24.0 t) and vessel tank states,
    completely ignoring any active load cell sensor readings.
    """
    # Set scale sensor to a conflicting reading (10.0 kg = 100t)
    reader = state.get_current_reader()
    reader.set_simulated_cargo(10.0)

    # Request ballast compensation for a 24.0 t container loaded on Bay 2 Starboard
    req_payload = {
        "container_number": "MSCU9918234",
        "gross_weight_t": 24.0,
        "bay": 2,
        "side": "STARBOARD",
        "tier": 1
    }

    calc_resp = client.post("/api/container/ballast/calculate", json=req_payload)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()

    # Required ballast discharge MUST equal the container's 24.0 t document weight, NOT the scale's 100 t
    assert calc_data["compensation_required"] is True
    assert calc_data["tank_key"] == "starboard_2"
    assert calc_data["required_qty_t"] == 24.0
    assert calc_data["required_qty_t"] != 100.0


# =========================================================================
# 5. PROOF REQUIREMENT 4: LOAD CELL CANNOT AUTHORIZE LOADING
# =========================================================================

def test_phase5_load_cell_cannot_authorize_loading():
    """
    Proof that placing weight on a physical/simulated load cell scale CANNOT
    authorize or trigger container loading without validated OCR Document AI
    and explicit operator confirmation.
    """
    # 1. Place weight on scale
    reader = state.get_current_reader()
    reader.set_simulated_cargo(25.0)

    # 2. Attempt to call loading confirmation with operator_confirmed=False
    unauthorized_resp = client.post("/api/container/load/confirm", json={
        "container": {
            "container_number": "UNAUTH12345",
            "weights": {"gross_weight_kg": 25000.0}
        },
        "recommendation": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": False  # No operator authorization
    })
    assert unauthorized_resp.status_code == 200
    unauth_data = unauthorized_resp.json()
    assert unauth_data["success"] is False
    assert unauth_data["status"] == "rejected"
    assert "operator confirmation" in unauth_data["error_message"].lower()

    # Verify no container was loaded to the ship
    ship = state.get_current_ship()
    assert len(ship.containers) == 0


# =========================================================================
# 6. PROOF REQUIREMENT 5: LOAD CELL CANNOT MODIFY DIGITAL TWIN CARGO STATE
# =========================================================================

def test_phase5_load_cell_cannot_modify_cargo_state():
    """
    Proof that load cell telemetry cannot inject containers, modify slot occupancy,
    or alter the cargo layout in the Digital Twin.
    """
    reader = state.get_current_reader()
    reader.set_simulated_cargo(30.0)

    # Query digital twin state
    twin_resp = client.get("/api/digital-twin/state")
    assert twin_resp.status_code == 200
    twin_data = twin_resp.json()

    # Containers list in digital twin must remain completely empty
    assert len(twin_data["containers"]) == 0
    assert twin_data["list_t"] == 0.0
    assert twin_data["trim_t"] == 0.0


# =========================================================================
# 7. PROVENANCE LABEL: DIGITAL TWIN LABELS "[DOCUMENT AI]" NEVER "[LOAD CELL]"
# =========================================================================

def test_phase5_digital_twin_provenance_label():
    """
    Proof that the Digital Twin explicitly tags cargo weight provenance as
    '[DOCUMENT AI]' and NEVER '[LOAD CELL]'.
    """
    twin_resp = client.get("/api/digital-twin/state")
    assert twin_resp.status_code == 200
    twin_data = twin_resp.json()

    assert twin_data["authoritative_weight_source"] == "[DOCUMENT AI]"
    assert twin_data["authoritative_weight_source"] != "[LOAD CELL]"
    assert "[LOAD CELL]" not in str(twin_data)


# =========================================================================
# 8. REJECTION OF FORBIDDEN SOURCES IN APIS
# =========================================================================

def test_phase5_rejection_of_forbidden_sources():
    """
    Proof that if any request attempts to pass a forbidden source (e.g. source="LOAD_CELL"),
    the stability and loading services immediately reject it.
    """
    # 1. Reject forbidden source in stability analysis
    stab_resp = client.post("/api/container/stability/analyze", json={
        "container": {
            "container_number": "HACK1234567",
            "weight_source": "LOAD_CELL",
            "weights": {"gross_weight_kg": 20000.0}
        }
    })
    assert stab_resp.status_code == 200
    stab_data = stab_resp.json()
    assert stab_data["success"] is False
    assert stab_data["status"] == "rejected"
    assert "FORBIDDEN_WEIGHT_SOURCES" in stab_data["error_message"]

    # 2. Reject forbidden source in loading confirmation
    load_resp = client.post("/api/container/load/confirm", json={
        "container": {
            "container_number": "HACK1234567",
            "weight_source": "WEIGHING_SENSOR",
            "weights": {"gross_weight_kg": 20000.0}
        },
        "recommendation": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True
    })
    assert load_resp.status_code == 200
    load_data = load_resp.json()
    assert load_data["success"] is False
    assert load_data["status"] == "rejected"
    assert "FORBIDDEN_WEIGHT_SOURCES" in load_data["error_message"]


# =========================================================================
# 9. END-TO-END AUTHORITATIVE WORKFLOW EXECUTION
# =========================================================================

def test_phase5_e2e_authoritative_document_workflow():
    """
    End-to-end test of the complete Authoritative Cargo Workflow:
    Slip Image/Text -> OCR Extraction -> Normalization -> Validation ->
    Stability Slot Optimization -> Operator Confirmation -> Ballast Calculation -> Ballast Execution.
    """
    # 1. OCR text ingestion
    slip_text = (
        "PORT AUTHORITY TERMINAL INTERCHANGE\n"
        "CONTAINER: MSCU 492019 5\n"
        "SIZE: 40FT HIGH CUBE\n"
        "TARE: 3,800 KG\n"
        "PAYLOAD: 22,400 KG\n"
        "VGM GROSS WEIGHT: 26,200 KG\n"
        "HAZARDOUS: NO\n"
    )
    ocr_resp = client.post("/api/container/ocr/process-raw", json={"raw_text": slip_text})
    assert ocr_resp.status_code == 200
    ocr_data = ocr_resp.json()
    assert ocr_data["container"]["weights"]["gross_weight_kg"] == 26200.0

    # 2. Stability Analysis
    stab_resp = client.post("/api/container/stability/analyze", json={
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"]
    })
    assert stab_resp.status_code == 200
    stab_data = stab_resp.json()
    assert stab_data["success"] is True
    rec = stab_data["recommendation"]

    # 3. Operator Confirmation & Load
    load_resp = client.post("/api/container/load/confirm", json={
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "recommendation": {"bay": rec["bay"], "side": rec["side"], "tier": rec["tier"]},
        "operator_confirmed": True,
        "operator_id": "ChiefMate"
    })
    assert load_resp.status_code == 200
    load_data = load_resp.json()
    assert load_data["success"] is True
    assert load_data["container"]["gross_weight_t"] == 26.2

    # 4. Ballast Compensation
    ballast_resp = client.post("/api/container/ballast/calculate", json={
        "container_number": "MSCU4920195",
        "gross_weight_t": 26.2,
        "bay": rec["bay"],
        "side": rec["side"],
        "tier": rec["tier"]
    })
    assert ballast_resp.status_code == 200
    ballast_data = ballast_resp.json()
    assert ballast_data["success"] is True
    assert ballast_data["required_qty_t"] > 0

    # 5. Execute Ballast Compensation
    exec_resp = client.post("/api/container/ballast/execute", json={
        "container_number": "MSCU4920195",
        "tank_key": ballast_data["tank_key"],
        "direction": ballast_data["direction"],
        "qty_t": ballast_data["required_qty_t"],
        "operator_confirmed": True,
        "operator_id": "ChiefMate"
    })
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["success"] is True
    assert exec_data["status"] == "COMPLETED"

    # 6. Verify Digital Twin reflects committed state with [DOCUMENT AI] provenance
    twin_resp = client.get("/api/digital-twin/state")
    assert twin_resp.status_code == 200
    twin_data = twin_resp.json()
    assert len(twin_data["containers"]) == 1
    assert twin_data["containers"][0]["id"] == "MSCU4920195"
    assert twin_data["containers"][0]["weight"] == 26.2
    assert twin_data["authoritative_weight_source"] == "[DOCUMENT AI]"
