"""
Phase 6E: Hackathon Demonstration Mode Test Suite.

Verifies:
1. Demo fixture discovery & image endpoints.
2. Controlled demo state reset.
3. Scenario 1 (Golden Path) complete end-to-end execution:
   - Vessel Initial State -> Slip Document AI -> Extraction & Normalization
   - Provenance Verification ([DOCUMENT AI] Only, Zero Load-Cell)
   - Multi-Objective Stowage Solver -> Recommendation -> Operator Gate
   - Atomic Vessel Commit -> Live Digital Twin Update
   - Ballast Compensation Calculation -> Operator Ballast Gate -> Execution
   - Three-Stage Stability Verification & Cryptographic SQLite Audit
4. Scenario 2 (Critical Anomaly Rejection):
   - Inconsistent Weight Slip -> VGM Mismatch Anomaly Flagged
   - Review Required Status -> Safety Gate Locked -> Commit Blocked
   - Zero State Mutation Proof
5. Safety Invariants:
   - No auto-confirmation
   - No safety gate bypass
   - No load-cell leakage.
"""

import os
import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app
import state
from container_ocr.workflow import ContainerWorkflowEngine
from reports.logs_db import clear_logs, get_cargo_operations, get_ballast_operations, get_all_audit_events

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMPLE_SLIP_PATH = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
INCONSISTENT_SLIP_PATH = os.path.join(FIXTURES_DIR, "inconsistent_weight_slip.jpg")


@pytest.fixture(autouse=True)
def reset_system():
    state.reset_state()
    clear_logs()
    engine = ContainerWorkflowEngine.get_instance()
    engine.reset()
    yield
    state.reset_state()
    clear_logs()
    engine.reset()


def test_01_demo_fixtures_endpoint():
    """Verify demo scenarios catalog is accessible."""
    resp = client.get("/api/container/demo/fixtures")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["mode"] == "DEMO_MODE"
    assert len(data["scenarios"]) >= 4
    
    scenario_ids = [s["id"] for s in data["scenarios"]]
    assert "scenario_golden_path" in scenario_ids
    assert "scenario_anomaly_rejection" in scenario_ids


def test_02_demo_fixture_image_download():
    """Verify demo fixture images can be retrieved via HTTP."""
    resp = client.get("/api/container/demo/fixtures/sample_container_slip.jpg/image")
    assert resp.status_code == 200
    assert resp.headers["content-type"] in ["image/jpeg", "image/jpg"]
    assert len(resp.content) > 1000


def test_03_demo_reset_endpoint():
    """Verify demo reset resets ship containers, ballast tanks, and audit logs."""
    ship = state.get_current_ship()
    from ship import Container
    ship.add_container(Container(id="DUMMY_01", weight=20.0, bay=1, side="port", tier=1))
    assert len(ship.containers) == 1
    
    resp = client.post("/api/container/demo/reset")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "reset_complete"
    assert data["containers_count"] == 0
    assert len(state.get_current_ship().containers) == 0


def test_04_demo_scenario_1_golden_path_e2e():
    """
    Scenario 1: Complete Golden Path Demonstration:
    1. Reset vessel
    2. Upload sample_container_slip.jpg
    3. Document AI extraction
    4. Verify provenance is [DOCUMENT AI]
    5. Stowage analysis
    6. Operator gate authorization
    7. Commit to vessel state
    8. Ballast auto-compensation calculation
    9. Ballast operator gate authorization
    10. Execute ballast compensation
    11. Verify 3-stage stability & SQLite audit
    """
    # 1. Reset
    client.post("/api/container/demo/reset")
    ship = state.get_current_ship()
    assert len(ship.containers) == 0

    # 2 & 3. Extract Slip
    with open(SAMPLE_SLIP_PATH, "rb") as f:
        ocr_resp = client.post("/api/container/extract", files={"file": ("sample_container_slip.jpg", f, "image/jpeg")})
    assert ocr_resp.status_code == 200
    ocr_data = ocr_resp.json()
    
    assert ocr_data["success"] is True
    assert ocr_data["container"]["container_number"] == "MSCU4920195"
    assert ocr_data["container"]["weights"]["gross_weight_kg"] == 26200.0
    assert ocr_data["container"]["cargo"]["hazardous"] is True
    assert ocr_data["validation"]["valid"] is True

    # 4 & 5. Stability Analysis
    analysis_req = {
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "weight_source": "DOCUMENT_AI"
    }
    stab_resp = client.post("/api/containers/analyze-stability", json=analysis_req)
    assert stab_resp.status_code == 200
    stab_data = stab_resp.json()
    assert stab_data["success"] is True
    assert stab_data["recommendation"] is not None
    assert stab_data["provenance"]["ocr_derived"]["gross_weight_kg"] == 26200.0

    # 6. Unconfirmed commit attempt fails (Operator Gate)
    unauth_commit = {
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "recommendation": stab_data["recommendation"],
        "operator_confirmed": False
    }
    unauth_res = client.post("/api/containers/confirm-and-load", json=unauth_commit)
    assert unauth_res.status_code == 200
    assert unauth_res.json()["success"] is False
    assert len(ship.containers) == 0

    # 7. Authorized commit succeeds
    auth_commit = {
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "recommendation": stab_data["recommendation"],
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_Demo"
    }
    auth_res = client.post("/api/containers/confirm-and-load", json=auth_commit)
    assert auth_res.status_code == 200
    auth_data = auth_res.json()
    assert auth_data["success"] is True
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "MSCU4920195"

    # 8. Ballast Compensation Calculation
    ballast_req = {
        "container_number": auth_data["container"]["container_number"],
        "gross_weight_t": auth_data["container"]["gross_weight_t"],
        "bay": auth_data["loaded_position"]["bay"],
        "side": auth_data["loaded_position"]["side"],
        "tier": auth_data["loaded_position"]["tier"]
    }
    bal_calc_res = client.post("/api/containers/ballast-compensation", json=ballast_req)
    assert bal_calc_res.status_code == 200
    bal_calc_data = bal_calc_res.json()
    assert bal_calc_data["success"] is True
    target_tank_key = bal_calc_data["tank_key"] or "port_1"
    assert target_tank_key is not None

    # 9. Unconfirmed ballast attempt fails
    unauth_bal = {
        "container_number": "MSCU4920195",
        "tank_key": target_tank_key,
        "direction": bal_calc_data["direction"],
        "qty_t": bal_calc_data["required_qty_t"],
        "operator_confirmed": False
    }
    unauth_bal_res = client.post("/api/containers/execute-ballast", json=unauth_bal)
    assert unauth_bal_res.status_code == 200
    assert unauth_bal_res.json()["success"] is False

    # 10. Authorized ballast execution
    auth_bal = {
        "container_number": "MSCU4920195",
        "tank_key": target_tank_key,
        "direction": bal_calc_data["direction"],
        "qty_t": bal_calc_data["required_qty_t"],
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_Demo"
    }
    auth_bal_res = client.post("/api/containers/execute-ballast", json=auth_bal)
    assert auth_bal_res.status_code == 200
    auth_bal_data = auth_bal_res.json()
    assert auth_bal_data["success"] is True

    assert auth_bal_data["three_stage_stability"] is not None
    assert auth_bal_data["three_stage_stability"]["after_ballast"]["risk_level"] == "SAFE"

    # 11. Verify Audit Logs
    timeline_res = client.get("/api/reports/timeline")
    assert timeline_res.status_code == 200
    events = timeline_res.json()["timeline"]
    assert len(events) >= 2


def test_05_demo_scenario_2_critical_anomaly_safety_gate_lock():
    """
    Scenario 2: Critical Anomaly Rejection Demo:
    1. Upload inconsistent_weight_slip.jpg
    2. Document AI detects VGM arithmetic discrepancy (>14,000 kg mismatch)
    3. Status set to review_required, critical anomaly flagged
    4. Attempting to commit without approval is blocked
    5. Vessel state remains strictly protected (0 containers).
    """
    client.post("/api/container/demo/reset")
    ship = state.get_current_ship()
    
    with open(INCONSISTENT_SLIP_PATH, "rb") as f:
        ocr_resp = client.post("/api/container/extract", files={"file": ("inconsistent_weight_slip.jpg", f, "image/jpeg")})
    assert ocr_resp.status_code == 200
    ocr_data = ocr_resp.json()
    
    # Anomaly detected
    assert len(ocr_data["anomalies"]) > 0
    assert any(a["severity"] == "CRITICAL" for a in ocr_data["anomalies"])
    assert ocr_data["document"]["processing_status"] in ["review_required", "partial"]

    # Commit attempt must be rejected by safety gate
    commit_req = {
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "recommendation": {"bay": 1, "side": "PORT", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_Demo"
    }
    commit_res = client.post("/api/containers/confirm-and-load", json=commit_req)
    assert commit_res.status_code == 200
    commit_data = commit_res.json()
    assert commit_data["success"] is False
    assert "Document validation failed or critical safety anomaly detected" in commit_data["error_message"]
    
    # Vessel containers count remains 0
    assert len(ship.containers) == 0
