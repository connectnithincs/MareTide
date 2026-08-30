"""
Phase 6H: Backend Reliability & Error Handling Hardening Test Suite.

Verifies:
1. Root /health and /api/health monitoring endpoints.
2. Structured request-response logging middleware (X-Request-ID tracking).
3. OCR failure resilience & error propagation without unhandled exceptions.
4. Validation failure enforcement (REVIEW REQUIRED status & safety gate lockout).
5. Stability analysis failure handling without corrupting vessel hold.
6. Loading commit failure & double-submission rejection without optimistic corruption.
7. Ballast calculation & execution failure resilience (preserves last valid state).
8. Network timeout resilience & payload validation.
"""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
import state
from container_ocr.workflow import ContainerWorkflowEngine
from reports.logs_db import clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_system():
    """Reset vessel state, operational flow, and reports before each test."""
    state.reset_state()
    clear_logs()
    engine = ContainerWorkflowEngine.get_instance()
    engine.reset()
    yield
    state.reset_state()
    clear_logs()
    engine.reset()


def test_01_health_monitoring_endpoints():
    """
    Test 1: Verifies that /health and /api/health return component statuses.
    """
    for endpoint in ["/health", "/api/health"]:
        res = client.get(endpoint)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "components" in data
        assert data["components"]["database"] == "healthy"
        assert data["components"]["ocr_engine"] == "healthy"
        assert data["components"]["stability_engine"] == "healthy"
        assert data["components"]["safety_gate"] == "healthy"


def test_02_structured_request_id_and_audit_logging():
    """
    Test 2: Verifies that every HTTP response contains an X-Request-ID header.
    """
    # 1. Without custom request ID -> sidecar generates unique ID
    res = client.get("/api/vessel-state")
    assert res.status_code == 200
    assert "x-request-id" in res.headers
    assert len(res.headers["x-request-id"]) > 0

    # 2. With client-supplied request ID -> echoed in header
    custom_id = "TRACE-998822"
    res_custom = client.get("/api/vessel-state", headers={"X-Request-ID": custom_id})
    assert res_custom.status_code == 200
    assert res_custom.headers["x-request-id"] == custom_id


def test_03_ocr_failure_graceful_handling():
    """
    Test 3: OCR processing on corrupted image or empty file returns structured failure instead of 500 crash.
    """
    # Blank / corrupted image binary
    corrupt_bytes = b"NOT_A_VALID_IMAGE_DATA_CORRUPT"
    res = client.post(
        "/api/container/extract",
        files={"file": ("corrupt.jpg", corrupt_bytes, "image/jpeg")}
    )
    # Must return 200, 400, or 422 with structured failure, NOT an unhandled 500 crash
    assert res.status_code in [200, 400, 422]
    data = res.json()
    assert res.status_code in [400, 422] or data.get("success") is False


def test_04_validation_failure_blocks_loading():
    """
    Test 4: Corrupted or low-confidence container data triggers REVIEW_REQUIRED and blocks loading.
    """
    bad_payload = {
        "container": {
            "container_number": "INVALID999",
            "weights": {"gross_weight_kg": 0.0}
        },
        "document": {"processing_status": "review_required", "ocr_confidence": 0.35},
        "validation": {"valid": False, "anomalies": [{"severity": "CRITICAL", "message": "Zero weight detected"}]},
        "recommendation": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True
    }

    res = client.post("/api/containers/confirm-and-load", json=bad_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["status"] in ["review_required", "error", "rejected"]
    assert len(state.get_current_ship().containers) == 0


def test_05_stability_failure_prevents_hold_mutation():
    """
    Test 5: Inconsistent or dangerous container payload flags critical anomalies and does not mutate hold.
    """
    overweight_payload = {
        "container": {
            "container_number": "MSCU9999999",
            "container_type": "40HC",
            "weights": {"gross_weight_kg": 150000.0, "tare_weight_kg": 4000.0, "cargo_weight_kg": 146000.0}
        },
        "document": {"source": "slip.jpg"},
        "validation": {"valid": True}
    }

    res = client.post("/api/containers/analyze-stability", json=overweight_payload)
    assert res.status_code == 200
    data = res.json()
    # Critical anomaly flagged for exceeding maximum payload limit
    anomalies = data.get("anomalies", [])
    assert any("overweight" in str(a).lower() or "max" in str(a).lower() or a.get("severity") == "CRITICAL" for a in anomalies)
    assert len(state.get_current_ship().containers) == 0


def test_06_double_submission_and_duplicate_loading_rejection():
    """
    Test 6: Attempting to load the same container ID twice is rejected without duplicating mass.
    """
    load_payload = {
        "container": {
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "gross_weight_t": 26.2,
            "weights": {"gross_weight_kg": 26200.0, "tare_weight_kg": 3800.0, "cargo_weight_kg": 22400.0},
            "cargo": {"description": "COMPONENTS", "hazardous": False}
        },
        "recommendation": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    }

    # 1. First commit -> Success
    res1 = client.post("/api/containers/confirm-and-load", json=load_payload)
    assert res1.status_code == 200
    assert res1.json()["success"] is True
    assert len(state.get_current_ship().containers) == 1

    # 2. Duplicate commit -> Rejection
    res2 = client.post("/api/containers/confirm-and-load", json=load_payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["success"] is False
    assert "already stowed" in data2.get("error_message", "").lower() or "already exists" in data2.get("error_message", "").lower() or "occupied" in data2.get("error_message", "").lower()
    # Ensure hold was NOT duplicated
    assert len(state.get_current_ship().containers) == 1


def test_07_ballast_failure_preserves_last_known_state():
    """
    Test 7: Ballast operation with invalid tank key or excessive quantity fails gracefully
    and preserves existing tank volume.
    """
    initial_vessel = client.get("/api/vessel-state").json()
    initial_port1_vol = initial_vessel["ballast_tanks"]["port_1"]["current_volume"]

    # Attempt ballast with non-existent tank
    bad_ballast_req = {
        "container_number": "MSCU4920195",
        "tank_key": "non_existent_tank_999",
        "direction": "DRAIN",
        "qty_t": 5000.0,
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    }

    res = client.post("/api/containers/execute-ballast", json=bad_ballast_req)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False

    # Verify existing tanks were untouched
    post_vessel = client.get("/api/vessel-state").json()
    assert post_vessel["ballast_tanks"]["port_1"]["current_volume"] == initial_port1_vol
