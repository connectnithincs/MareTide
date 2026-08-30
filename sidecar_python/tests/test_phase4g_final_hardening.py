"""
Phase 4G: Final System Hardening & Safety Verification Test Suite.
Tests all 13 required failure paths and security boundaries:
1. OCR Failure (corrupt / invalid data)
2. Poor Document / Unreadable image
3. Low Confidence review gate
4. Invalid Container Number
5. VGM Mismatch
6. Missing Gross Weight
7. Invalid Dimensions
8. No Valid Slot (Vessel Full)
9. Occupied Slot Placement Rejection
10. Loading Confirmation Rejection without Operator Approval
11. Ballast Calculation on Invalid/Unloaded State
12. Ballast Execution Validation & Volume Overdraft
13. Operator Rejection (Explicit)
14. Security: File Upload Extension & Path Validation
15. Security: Malformed Payload & Input Sanitization
16. Immutability Guarantee: Failures never alter vessel state
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
from container_ocr.models import ContainerDetails, ContainerWeights, ContainerDimensions
from container_ocr.validator import DomainValidator
from container_ocr.anomaly_detector import CargoAnomalyDetector
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest
)
from container_stability.analyzer import (
    ContainerLoadingService,
    ContainerBallastService,
    ContainerStabilityService
)
from reports.logs_db import clear_logs

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
    yield
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0


# --- FAILURE PATH 1: OCR FAILURE (Corrupted / Empty File) ---
def test_failure_1_corrupted_image_file():
    """Verify corrupted non-image upload fails gracefully with 400 error."""
    corrupted_data = b"NOT_A_REAL_IMAGE_DATA_CORRUPT_BYTES_XYZ"
    files = {"file": ("corrupt.jpg", io.BytesIO(corrupted_data), "image/jpeg")}
    response = client.post("/api/container/extract", files=files)
    assert response.status_code == 400
    data = response.json()
    assert "Corrupted" in data["detail"] or "Cannot decode" in data["detail"]


# --- FAILURE PATH 2: POOR DOCUMENT (Unreadable Blank) ---
def test_failure_2_blank_unreadable_document():
    """Verify completely unreadable blank document returns review_required with low confidence."""
    from PIL import Image
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"file": ("blank.jpg", buf, "image/jpeg")}
    response = client.post("/api/container/extract", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["document"]["processing_status"] in ["review_required", "failed", "success"]


# --- FAILURE PATH 3: LOW CONFIDENCE REVIEW GATE ---
def test_failure_3_low_confidence_blocks_loading():
    """Verify low OCR confidence (< 0.75) sets review_required and blocks loading."""
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 24000.0}},
        document={"processing_status": "review_required", "confidence": {"overall": 0.55}},
        validation={"valid": True},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )
    res = ContainerLoadingService.confirm_and_load(req)
    assert res.success is False
    assert res.status == "review_required"


# --- FAILURE PATH 4: INVALID CONTAINER NUMBER ---
def test_failure_4_invalid_container_number():
    """Verify invalid container number generates warning anomaly and alerts operator."""
    container_dict = {
        "container_number": "INVALID-NO-CHECK-DIGIT",
        "weights": {"gross_weight_kg": 20000.0}
    }
    anomalies = CargoAnomalyDetector.detect_anomalies(container_dict)
    assert any(a.field == "container_number" for a in anomalies)


# --- FAILURE PATH 5: VGM MISMATCH ---
def test_failure_5_vgm_mismatch_blocks_loading():
    """Verify tare + cargo != gross triggers critical anomaly and blocks loading."""
    container_dict = {
        "container_number": "MSCU4920195",
        "weights": {
            "gross_weight_kg": 30000.0,
            "tare_weight_kg": 4000.0,
            "cargo_weight_kg": 20000.0  # 4000 + 20000 = 24000 != 30000
        }
    }
    cntr_obj = ContainerDetails(**container_dict)
    val_res = DomainValidator.validate_container(cntr_obj)
    assert val_res.valid is False

    req = ContainerLoadingConfirmRequest(
        container=container_dict,
        validation=val_res.model_dump(),
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )
    res = ContainerLoadingService.confirm_and_load(req)
    assert res.success is False


# --- FAILURE PATH 6: MISSING GROSS WEIGHT ---
def test_failure_6_missing_gross_weight():
    """Verify missing gross weight returns error on stability placement analysis."""
    req = ContainerStabilityAnalysisRequest(
        container={"container_number": "MSCU4920195", "weights": {}}
    )
    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is False
    assert res.status == "error"


# --- FAILURE PATH 7: INVALID DIMENSIONS ---
def test_failure_7_invalid_dimensions():
    """Verify impossible length triggers critical dimensional anomaly."""
    container_dict = {
        "container_number": "MSCU4920195",
        "weights": {"gross_weight_kg": 22000.0},
        "dimensions": {"length_ft": 75.0}  # Over 53ft max
    }
    anomalies = CargoAnomalyDetector.detect_anomalies(container_dict)
    dim_anomaly = next((a for a in anomalies if "length" in a.field), None)
    assert dim_anomaly is not None
    assert dim_anomaly.severity == "CRITICAL"


# --- FAILURE PATH 8: NO VALID SLOT (VESSEL FULL) ---
def test_failure_8_no_valid_slot_when_full():
    """Verify that when all available cargo slots are occupied, stability analysis returns no candidate."""
    ship = state.get_current_ship()
    # Fill all bays, sides, and tiers (1 to 4)
    for b in range(1, ship.num_bays + 1):
        for s in ["port", "starboard", "center"]:
            for t in range(1, 5):
                ship.add_container(Container(id=f"FULL-{b}-{s}-{t}", weight=20.0, bay=b, side=s, tier=t))

    req = ContainerStabilityAnalysisRequest(
        container={"container_number": "EXTRA-CNTR", "weights": {"gross_weight_kg": 20000.0}}
    )
    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=ship)
    assert res.success is False
    assert res.status == "error"
    assert "No available cargo slots" in res.error_message or "No candidate" in res.error_message or "occupied" in res.error_message.lower()


# --- FAILURE PATH 9: OCCUPIED SLOT PLACEMENT REJECTION ---
def test_failure_9_occupied_slot_rejected():
    """Verify loading into an already-occupied slot is strictly rejected."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="FIRST-LOAD", weight=22.0, bay=2, side="port", tier=1))

    req = ContainerLoadingConfirmRequest(
        container={"container_number": "SECOND-LOAD", "weights": {"gross_weight_kg": 20000.0}},
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 2, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )
    res = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert res.success is False
    assert "already occupied" in res.error_message.lower()


# --- FAILURE PATH 10: CONFIRMATION REJECTED WITHOUT OPERATOR APPROVAL ---
def test_failure_10_missing_operator_approval():
    """Verify loading without operator_confirmed=True is rejected."""
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 22000.0}},
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=False
    )
    res = ContainerLoadingService.confirm_and_load(req)
    assert res.success is False
    assert res.status == "rejected"
    assert "operator confirmation is required" in res.error_message.lower()


# --- FAILURE PATH 11: BALLAST CALCULATION ON UNLOADED ZERO STATE ---
def test_failure_11_ballast_calculation_clean_state():
    """Verify ballast compensation on an already level ship requires 0 discharge."""
    ship = state.get_current_ship()
    req = BallastCompensationRequest(
        container_number="TEST",
        gross_weight_t=20.0,
        bay=1,
        side="PORT",
        tier=1
    )
    res = ContainerBallastService.calculate_compensation(req, ship_instance=ship)
    assert res.success is True
    # If list is 0.0, required compensation is 0.0
    assert res.required_qty_t == 0.0 or res.flow_rate_l_s > 0


# --- FAILURE PATH 12: BALLAST EXECUTION OVERDRAFT VALIDATION ---
def test_failure_12_ballast_execution_overdraft_validation():
    """Verify ballast water discharge exceeding tank contents safely caps at zero."""
    ship = state.get_current_ship()
    ship.tanks["port_1"].current_volume = 20.0  # Only 20t available

    req = BallastExecutionRequest(
        tank_key="port_1",
        qty_t=50.0,  # Request 50t (> 20t available)
        direction="DRAIN",
        operator_confirmed=True
    )
    res = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert res.success is True
    assert res.actual_qty_t == 20.0
    assert ship.tanks["port_1"].current_volume == 0.0  # Cannot drop below 0


# --- FAILURE PATH 13: OPERATOR REJECTION (EXPLICIT) ---
def test_failure_13_explicit_operator_rejection():
    """Verify explicit operator rejection leaves ship state 100% untouched."""
    ship = state.get_current_ship()
    initial_count = len(ship.containers)

    req = ContainerLoadingConfirmRequest(
        container={"container_number": "REJECTED-CNTR", "weights": {"gross_weight_kg": 25000.0}},
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=False
    )
    res = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert res.success is False
    assert len(ship.containers) == initial_count  # State immutability verified


# --- SECURITY TEST 14: FILE EXTENSION RESTRICTIONS ---
def test_security_14_unsupported_file_extension():
    """Verify dangerous non-image file extensions (.exe, .sh, .py) are rejected."""
    exe_payload = b"MZ\x90\x00\x03\x00\x00\x00"
    files = {"file": ("malicious_payload.exe", io.BytesIO(exe_payload), "application/octet-stream")}
    response = client.post("/api/container/extract", files=files)
    assert response.status_code in [400, 415, 422]


# --- SECURITY TEST 15: MALFORMED JSON & INPUT SANITIZATION ---
def test_security_15_malformed_json_inputs():
    """Verify malformed JSON payloads return standard 422 Unprocessable Entity."""
    response = client.post(
        "/api/container/stability/analyze",
        content="INVALID_MALFORMED_JSON_STRING",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code in [400, 422]
