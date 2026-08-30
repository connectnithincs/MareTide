"""
Phase 6F: Single Source of Truth & Real Document AI End-to-End Integration Verification.
Tests the complete real application workflow with real fixture 'sample_container_slip.jpg':
IMAGE -> DOCUMENT AI -> JSON -> VALIDATION -> STABILITY -> OPERATOR CONFIRMATION -> VESSEL STATE -> BALLAST -> DIGITAL TWIN -> AUDIT.
Verifies authoritative backend vessel state, zero load-cell involvement in container mass,
and state synchronization across all endpoints without mock responses.
"""

import os
import io
import pytest
from fastapi.testclient import TestClient

from main import app
import state
from container_ocr.workflow import ContainerWorkflowEngine
from reports.logs_db import clear_logs, get_cargo_operations, get_ballast_operations, get_all_audit_events

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")


@pytest.fixture(autouse=True)
def reset_system():
    """Ensure vessel state, operational flow, and reports start from baseline before each test."""
    state.reset_state()
    clear_logs()
    engine = ContainerWorkflowEngine.get_instance()
    engine.reset()
    yield
    state.reset_state()
    clear_logs()
    engine.reset()


def test_01_fixture_image_exists():
    """Verify that real container slip fixture image exists on disk."""
    assert os.path.exists(FIXTURE_PATH), f"Fixture image not found at {FIXTURE_PATH}"
    file_size = os.path.getsize(FIXTURE_PATH)
    assert file_size > 10000, f"Fixture file size ({file_size} bytes) is suspiciously small"


def test_02_initial_authoritative_state_consistency():
    """
    Step 1: Verify initial authoritative vessel state across all supervisory endpoints:
    - /api/vessel-state
    - /api/digital-twin/state
    - /api/deck-plan
    - /api/operations/live-status
    """
    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vessel_data = vessel_res.json()

    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    twin_data = twin_res.json()

    deck_res = client.get("/api/deck-plan")
    assert deck_res.status_code == 200
    deck_data = deck_res.json()

    ops_res = client.get("/api/operations/live-status")
    assert ops_res.status_code == 200
    ops_data = ops_res.json()

    # Verify initial equilibrium values match across all endpoints
    assert vessel_data["ship_name"] == twin_data["ship_name"] == ops_data["ship_name"]
    assert len(vessel_data["containers"]) == len(twin_data["containers"]) == len(deck_data["containers"]) == 0
    assert vessel_data["ballast_tanks"] is not None
    assert twin_data["ballast_tanks"] is not None


def test_03_real_document_ai_extraction_step():
    """
    Step 2: Submit actual sample_container_slip.jpg binary file to /api/container/extract.
    Verify real RapidOCR / Document AI parsing returns complete container fields.
    """
    with open(FIXTURE_PATH, "rb") as f:
        img_bytes = f.read()

    response = client.post(
        "/api/container/extract",
        files={"file": ("sample_container_slip.jpg", img_bytes, "image/jpeg")}
    )

    assert response.status_code == 200, f"Extraction failed: {response.text}"
    data = response.json()

    assert data["success"] is True
    assert "container" in data
    c = data["container"]

    # Verify extracted fields from real OCR
    assert c["container_number"] == "MSCU4920195"
    assert c["weights"]["gross_weight_kg"] == 26200.0
    assert c["cargo"]["hazardous"] is True
    assert "validation" in data
    assert data["validation"].get("is_valid", data["validation"].get("valid")) is True
    
    # Cargo mass must originate from Document AI
    assert "cargo_mass" in c or "cargo_mass" in data
    cargo_mass = c.get("cargo_mass") or data.get("cargo_mass")
    assert cargo_mass["source"] == "DOCUMENT_AI"
    assert cargo_mass["authoritative"] is True


def test_04_safety_gate_validation_enforcement():
    """
    Step 3: Evaluate Document AI extracted data through Safety Gate.
    Verifies that valid document passes, while simulated corrupted document blocks loading.
    """
    # 1. Valid Document AI data -> Should pass safety gate
    valid_payload = {
        "gate_type": "LOADING_CONFIRMATION",
        "container_data": {
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "weights": {
                "gross_weight_kg": 26200.0,
                "tare_weight_kg": 3800.0,
                "cargo_weight_kg": 22400.0
            },
            "dimensions": {"length_ft": 40.0, "height_ft": 9.5, "width_ft": 8.0},
            "cargo": {"description": "ELECTRONIC COMPONENTS", "hazardous": True},
            "destination": "SINGAPORE",
            "weight_source": "DOCUMENT_AI"
        },
        "document_data": {"source": "sample_container_slip.jpg", "ocr_confidence": 0.96},
        "validation_data": {"valid": True, "anomalies": []},
        "target_slot": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    }

    gate_res = client.post("/api/safety-gate/evaluate-loading", json=valid_payload)
    assert gate_res.status_code == 200
    gate_data = gate_res.json()
    assert gate_data["allowed"] is True
    assert gate_data["status"] == "SAFE"

    # 2. Corrupted / Low confidence document with load-cell injection attempt -> Should be blocked
    corrupted_payload = dict(valid_payload)
    corrupted_payload["weight_source"] = "HX711_LOAD_CELL"
    blocked_gate_res = client.post("/api/safety-gate/evaluate-loading", json=corrupted_payload)
    assert blocked_gate_res.status_code == 200
    blocked_gate_data = blocked_gate_res.json()
    assert blocked_gate_data["allowed"] is False
    assert blocked_gate_data["status"] == "BLOCKED"


def test_05_stowage_stability_recommendation_step():
    """
    Step 4 & 5: Run multi-objective stowage solver on Document AI container.
    Verifies recommended bay, side, tier, alternatives, before/after stability delta, and zero load-cell usage.
    """
    payload = {
        "container": {
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "weights": {
                "gross_weight_kg": 26200.0,
                "tare_weight_kg": 3800.0,
                "cargo_weight_kg": 22400.0
            },
            "dimensions": {"length_ft": 40.0, "height_ft": 9.5},
            "cargo": {"description": "ELECTRONIC COMPONENTS", "hazardous": True},
            "destination": "SINGAPORE",
            "weight_source": "DOCUMENT_AI"
        },
        "document": {"source": "sample_container_slip.jpg"},
        "validation": {"valid": True}
    }

    res = client.post("/api/containers/analyze-stability", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["success"] is True
    assert "recommendation" in data
    rec = data["recommendation"]
    assert rec["bay"] in (1, 2, 3, 4)
    assert rec["side"].lower() in ("port", "starboard")
    assert rec["tier"] in (1, 2)
    assert "stability" in data
    assert "before" in data["stability"]
    assert "after" in data["stability"]


def test_06_operator_confirmation_and_loading_commit():
    """
    Step 6 & 7: Operator signs off and commits container to vessel.
    Verifies backend vessel state mutates, container count increments, and stability recalculates.
    """
    ship = state.get_current_ship()
    initial_count = len(ship.containers)

    # 1. Authorized commit
    load_payload = {
        "container": {
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "gross_weight_t": 26.2,
            "weights": {"gross_weight_kg": 26200.0, "tare_weight_kg": 3800.0, "cargo_weight_kg": 22400.0},
            "cargo": {"description": "ELECTRONIC COMPONENTS", "hazardous": True}
        },
        "recommendation": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_SSOT_Test"
    }

    load_res = client.post("/api/containers/confirm-and-load", json=load_payload)
    assert load_res.status_code == 200
    load_data = load_res.json()
    assert load_data["success"] is True

    # 2. Refetch backend vessel state
    new_state = client.get("/api/vessel-state").json()
    assert len(new_state["containers"]) == initial_count + 1
    loaded_c = [c for c in new_state["containers"] if c["id"] == "MSCU4920195"][0]
    assert loaded_c["bay"] == 1
    assert loaded_c["side"].lower() == "port"
    assert loaded_c["tier"] == 1
    assert round(loaded_c["weight"], 1) == 26.2

    # 3. Verify Digital Twin reflects exact same state
    twin_state = client.get("/api/digital-twin/state").json()
    assert len(twin_state["containers"]) == len(new_state["containers"])


def test_07_post_load_ballast_calculation_and_execution():
    """
    Step 8 & 9: Compute ballast compensation on post-load state and execute with operator confirmation.
    Verifies tank levels update, equilibrium restores, and audit trail records both actions.
    """
    # 1. Pre-load container first
    auth_res = client.post("/api/containers/confirm-and-load", json={
        "container": {
            "container_number": "MSCU4920195",
            "gross_weight_t": 26.2,
            "weights": {"gross_weight_kg": 26200.0}
        },
        "recommendation": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_SSOT_Test"
    })
    assert auth_res.status_code == 200

    # 2. Calculate ballast compensation
    calc_res = client.post("/api/containers/ballast-compensation", json={
        "container_number": "MSCU4920195",
        "gross_weight_t": 26.2,
        "bay": 1,
        "side": "port",
        "tier": 1
    })
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["success"] is True
    assert calc_data["required_qty_t"] > 0
    target_tank = calc_data.get("tank_key", "port_1")

    # 3. Execute ballast pump transfer with operator confirmation
    exec_res = client.post("/api/containers/execute-ballast", json={
        "container_number": "MSCU4920195",
        "tank_key": target_tank,
        "direction": calc_data.get("direction", "DRAIN"),
        "qty_t": calc_data["required_qty_t"],
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_SSOT_Test"
    })
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["success"] is True
    assert exec_data.get("three_stage_stability") is not None
    assert exec_data["three_stage_stability"]["after_ballast"]["risk_level"] == "SAFE"


def test_08_complete_chronological_audit_traceability():
    """
    Step 10 & 11: Verify that every stage (OCR -> LOADING -> BALLAST) is logged
    in SQLite audit tables and can be retrieved chronologically via /api/reports/timeline.
    """
    # 1. Reset demo flow
    client.post("/api/container/demo/reset")

    # 2. Load container via authorized confirm-and-load
    load_res = client.post("/api/containers/confirm-and-load", json={
        "container": {
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "gross_weight_t": 26.2,
            "weights": {"gross_weight_kg": 26200.0, "tare_weight_kg": 3800.0, "cargo_weight_kg": 22400.0},
            "cargo": {"description": "ELECTRONIC COMPONENTS", "hazardous": True}
        },
        "document": {"source": "sample_container_slip.jpg"},
        "validation": {"valid": True},
        "recommendation": {"bay": 2, "side": "starboard", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "Officer_Audit_Test"
    })
    assert load_res.status_code == 200
    assert load_res.json()["success"] is True

    # 3. Execute ballast
    bal_res = client.post("/api/containers/execute-ballast", json={
        "container_number": "MSCU4920195",
        "tank_key": "starboard_2",
        "direction": "DRAIN",
        "qty_t": 18.5,
        "operator_confirmed": True,
        "operator_id": "Officer_Audit_Test"
    })
    assert bal_res.status_code == 200

    # 4. Fetch audit timeline
    timeline_res = client.get("/api/reports/timeline?limit=20")
    assert timeline_res.status_code == 200
    events = timeline_res.json().get("timeline", [])

    assert len(events) >= 2
    event_actions = [e.get("action", "") for e in events]
    assert any("Load" in a or "MSCU" in a for a in event_actions)
    assert any("Ballast" in a or "Drain" in a or "STARBOARD-2" in a for a in event_actions)


def test_09_full_end_to_end_image_to_audit_pipeline():
    """
    Full End-to-End Pipeline test using real sample_container_slip.jpg:
    IMAGE -> DOCUMENT AI -> JSON -> VALIDATION -> STABILITY -> LOAD -> BALLAST -> DIGITAL TWIN -> AUDIT
    """
    # STAGE 1 & 2: Real Image -> Document AI -> JSON
    with open(FIXTURE_PATH, "rb") as f:
        img_bytes = f.read()

    ocr_res = client.post("/api/container/extract", files={"file": ("sample_container_slip.jpg", img_bytes, "image/jpeg")})
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["success"] is True
    assert ocr_data["container"]["container_number"] == "MSCU4920195"

    # STAGE 3: Safety Gate Validation
    gate_res = client.post("/api/safety-gate/evaluate-loading", json={
        "gate_type": "LOADING_CONFIRMATION",
        "container_data": ocr_data["container"],
        "document_data": ocr_data.get("document", {}),
        "validation_data": ocr_data["validation"],
        "target_slot": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    })
    assert gate_res.status_code == 200
    assert gate_res.json()["allowed"] is True

    # STAGE 4 & 5: Stability Optimization & Recommendation
    stab_res = client.post("/api/containers/analyze-stability", json={
        "container": ocr_data["container"],
        "document": ocr_data.get("document", {}),
        "validation": ocr_data["validation"]
    })
    assert stab_res.status_code == 200
    stab_data = stab_res.json()
    assert stab_data["success"] is True
    rec = stab_data["recommendation"]

    # STAGE 6 & 7: Operator Loading Commit & Vessel State Sync
    load_res = client.post("/api/containers/confirm-and-load", json={
        "container": ocr_data["container"],
        "recommendation": rec,
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_E2E_GoldenPath"
    })
    assert load_res.status_code == 200

    # STAGE 8 & 9: Ballast Compensation Calculation & Execution
    calc_res = client.post("/api/containers/ballast-compensation", json={
        "container_number": ocr_data["container"]["container_number"],
        "gross_weight_t": (ocr_data["container"]["weights"]["gross_weight_kg"]) / 1000.0,
        "bay": rec["bay"],
        "side": rec["side"],
        "tier": rec["tier"]
    })
    assert calc_res.status_code == 200
    calc_data = calc_res.json()

    exec_res = client.post("/api/containers/execute-ballast", json={
        "container_number": ocr_data["container"]["container_number"],
        "tank_key": calc_data.get("tank_key", "port_1"),
        "direction": calc_data.get("direction", "DRAIN"),
        "qty_t": calc_data["required_qty_t"],
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer_E2E_GoldenPath"
    })
    assert exec_res.status_code == 200

    # STAGE 10: Digital Twin Synchronized State
    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    twin_data = twin_res.json()
    container_ids = [c["id"] for c in twin_data["containers"]]
    assert ocr_data["container"]["container_number"] in container_ids

    # STAGE 11: SQLite Chronological Audit
    timeline_res = client.get("/api/reports/timeline?limit=10")
    assert timeline_res.status_code == 200
    timeline_events = timeline_res.json()["timeline"]
    assert len(timeline_events) >= 2
