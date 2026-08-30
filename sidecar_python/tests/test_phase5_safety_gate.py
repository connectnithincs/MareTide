"""
Phase 5 Comprehensive Test Suite: Real-Time Operational Safety Gate for MareTide.

Validates all 8 safety rules and safety states:
Rule 1: Invalid OCR/document data -> BLOCKED.
Rule 2: Critical anomaly -> BLOCKED.
Rule 3: Invalid container identifier -> BLOCKED.
Rule 4: Missing gross weight -> BLOCKED.
Rule 5: Unsafe candidate placement (occupied slot or critical list/trim) -> BLOCKED.
Rule 6: Stale / disconnected telemetry -> REVIEW_REQUIRED / WARNING / BLOCKED.
Rule 7: Missing operator confirmation -> BLOCKED.
Rule 8: Load-cell data must NEVER satisfy any safety gate -> BLOCKED (Security Policy Violation).
Rule 9: Valid Document AI container -> SAFE.
Rule 10: Ballast Safety Gate overdraft/overflow protection.
Rule 11: REST API safety gate endpoints.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ship import Ship, BallastTank, Container
import state
from container_stability.models import (
    SafetyGateStatus,
    SafetyGateType,
    SafetyGateEvaluationRequest,
    SafetyGateEvaluationResult,
    StabilityMetrics
)
from container_stability.safety_gate import RealTimeSafetyGate
from container_stability.policy import CONTAINER_WEIGHT_SOURCE, PROVENANCE_LABEL
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_ship_state():
    """Ensure clean ship state for each test."""
    state.reset_state()


# Helper to build valid mock container data
def _valid_container_dict():
    return {
        "container_number": "MSCU4920195",
        "container_type": "40HC",
        "weights": {
            "gross_weight_kg": 26200.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 22400.0
        },
        "dimensions": {"length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5},
        "destination": "Rotterdam",
        "hazardous": False,
        "provenance": "[DOCUMENT AI]"
    }


def _valid_document_dict():
    return {
        "source": "slip_msc_01.jpg",
        "engine": "easyocr",
        "processing_status": "success",
        "timestamp": "2026-08-30T00:00:00Z"
    }


def _valid_validation_dict():
    return {
        "valid": True,
        "iso_6346": {
            "valid_format": True,
            "owner_code": "MSC",
            "category": "U",
            "serial_number": "492019",
            "check_digit": 5,
            "check_digit_valid": True
        },
        "weights": {
            "vgm_declared": True,
            "weight_consistent": True,
            "overweight": False
        },
        "warnings": []
    }


# -------------------------------------------------------------
# Rule 1: Invalid OCR / Document Data -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_1_invalid_document_data_blocks():
    """Verify corrupted or invalid document validation results in BLOCKED state."""
    cntr = _valid_container_dict()
    doc_corrupt = {"source": "bad.jpg", "processing_status": "corrupted"}
    val_invalid = {"valid": False, "warnings": ["Unreadable slip image", "Checksum mismatch"]}

    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr,
        document=doc_corrupt,
        validation=val_invalid,
        recommendation={"bay": 1, "side": "port", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result.allowed is False
    assert result.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result.reasons]
    assert "VALIDATION" in categories


# -------------------------------------------------------------
# Rule 2: Critical Anomaly -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_2_critical_anomaly_blocks():
    """Verify critical cargo anomaly (e.g. STRUCTURAL_OVERWEIGHT) blocks loading confirmation."""
    cntr = _valid_container_dict()
    anomalies = [
        {
            "anomaly_type": "STRUCTURAL_OVERWEIGHT",
            "severity": "CRITICAL",
            "message": "Gross weight (38.5t) exceeds ISO maximum operating limit of 32.5t."
        }
    ]

    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr,
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        anomalies=anomalies,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result.allowed is False
    assert result.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result.reasons]
    assert "ANOMALY" in categories


# -------------------------------------------------------------
# Rule 3: Invalid ISO Container Identifier -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_3_invalid_container_identifier_blocks():
    """Verify missing or invalid ISO container number format triggers BLOCKED."""
    cntr_invalid = _valid_container_dict()
    cntr_invalid["container_number"] = "INVALID99"
    val_invalid = _valid_validation_dict()
    val_invalid["iso_6346"]["valid_format"] = False
    val_invalid["iso_6346"]["check_digit_valid"] = False

    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr_invalid,
        document=_valid_document_dict(),
        validation=val_invalid,
        recommendation={"bay": 1, "side": "port", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result.allowed is False
    assert result.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result.reasons]
    assert "IDENTIFIER" in categories


# -------------------------------------------------------------
# Rule 4: Missing Gross Weight -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_4_missing_gross_weight_blocks():
    """Verify missing, 0, or negative gross weight blocks loading confirmation."""
    cntr_no_weight = _valid_container_dict()
    cntr_no_weight["weights"]["gross_weight_kg"] = None
    cntr_no_weight["gross_weight_kg"] = None
    cntr_no_weight["weight"] = None

    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr_no_weight,
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result.allowed is False
    assert result.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result.reasons]
    assert "WEIGHT" in categories


# -------------------------------------------------------------
# Rule 5: Candidate Placement / Slot Collision -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_5_occupied_slot_and_critical_stability_blocks():
    """Verify placing into an occupied slot or exceeding capsizing limits blocks loading."""
    ship = state.get_current_ship()
    # Pre-occupy Bay 1 Port Tier 1
    ship.add_container(Container(id="EXISTING123", weight=20.0, bay=1, side="port", tier=1))

    # Attempt to target the exact same slot
    result_collision = RealTimeSafetyGate.evaluate_loading_gate(
        container=_valid_container_dict(),
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        ship=ship,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result_collision.allowed is False
    assert result_collision.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result_collision.reasons]
    assert "SLOT" in categories

    # Also test critical stability limits
    crit_stab = StabilityMetrics(list_t=6.2, trim_t=1.0, stability_score=7.2, risk_level="CRITICAL")
    result_stability = RealTimeSafetyGate.evaluate_loading_gate(
        container=_valid_container_dict(),
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 2, "side": "port", "tier": 1},
        ship=ship,
        operator_confirmed=True,
        operator_id="ChiefOfficer",
        predicted_stability=crit_stab
    )

    assert result_stability.allowed is False
    assert result_stability.status == SafetyGateStatus.BLOCKED.value
    stab_categories = [r.category for r in result_stability.reasons]
    assert "STABILITY" in stab_categories


# -------------------------------------------------------------
# Rule 6: Telemetry Freshness & Connection Status
# -------------------------------------------------------------
def test_gate_rule_6_stale_or_disconnected_telemetry():
    """Verify disconnected telemetry flags review requirement on operational gating."""
    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=_valid_container_dict(),
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        telemetry={"connection_status": "DISCONNECTED", "stale_seconds": 12.0},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result.status in [SafetyGateStatus.REVIEW_REQUIRED.value, SafetyGateStatus.WARNING.value]
    categories = [r.category for r in result.reasons]
    assert "TELEMETRY" in categories


# -------------------------------------------------------------
# Rule 7: Missing Operator Confirmation -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_7_missing_operator_confirmation_blocks():
    """Verify missing operator confirmation or empty operator ID strictly blocks loading."""
    result_unconfirmed = RealTimeSafetyGate.evaluate_loading_gate(
        container=_valid_container_dict(),
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        operator_confirmed=False,
        operator_id="ChiefOfficer"
    )

    assert result_unconfirmed.allowed is False
    assert result_unconfirmed.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result_unconfirmed.reasons]
    assert "AUTHORIZATION" in categories


# -------------------------------------------------------------
# Rule 8: Load-Cell Data Never Satisfies Safety Gate -> BLOCKED
# -------------------------------------------------------------
def test_gate_rule_8_load_cell_data_forbidden():
    """Verify any load-cell sensor provenance triggers immediate security policy BLOCKED state."""
    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=_valid_container_dict(),
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer",
        weight_source="LOAD_CELL_SENSOR"
    )

    assert result.allowed is False
    assert result.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result.reasons]
    assert "POLICY" in categories
    assert "Security Policy Violation" in result.reasons[0].message


# -------------------------------------------------------------
# Rule 9: Valid Document AI Container -> SAFE
# -------------------------------------------------------------
def test_gate_rule_9_valid_document_ai_passes_safe():
    """Verify a valid Document AI container with operator approval passes safety gate as SAFE."""
    ship = state.get_current_ship()
    result = RealTimeSafetyGate.evaluate_loading_gate(
        container=_valid_container_dict(),
        document=_valid_document_dict(),
        validation=_valid_validation_dict(),
        recommendation={"bay": 1, "side": "port", "tier": 1},
        ship=ship,
        operator_confirmed=True,
        operator_id="ChiefOfficer",
        weight_source=CONTAINER_WEIGHT_SOURCE
    )

    assert result.allowed is True
    assert result.status == SafetyGateStatus.SAFE.value
    assert result.provenance in [PROVENANCE_LABEL, CONTAINER_WEIGHT_SOURCE, "[DOCUMENT AI]"]


# -------------------------------------------------------------
# Rule 10: Ballast Safety Gate Overdraft Protection
# -------------------------------------------------------------
def test_gate_rule_10_ballast_safety_gate_overdraft():
    """Verify ballast safety gate prevents overdraft (draining more water than tank holds)."""
    ship = state.get_current_ship()
    # Set Port Tank 1 to 20t
    ship.tanks["port_1"].current_volume = 20.0

    # Request drain of 50t (exceeds 20t)
    result_overdraft = RealTimeSafetyGate.evaluate_ballast_gate(
        tank_key="port_1",
        direction="DRAIN",
        qty_t=50.0,
        ship=ship,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result_overdraft.allowed is False
    assert result_overdraft.status == SafetyGateStatus.BLOCKED.value
    categories = [r.category for r in result_overdraft.reasons]
    assert "BALLAST" in categories
    assert "Overdraft violation" in result_overdraft.reasons[0].message

    # Valid drain of 10t
    result_valid = RealTimeSafetyGate.evaluate_ballast_gate(
        tank_key="port_1",
        direction="DRAIN",
        qty_t=10.0,
        ship=ship,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert result_valid.allowed is True
    assert result_valid.status == SafetyGateStatus.SAFE.value


# -------------------------------------------------------------
# Rule 11: REST API Safety Gate Endpoints
# -------------------------------------------------------------
def test_gate_rule_11_rest_api_safety_gate_endpoints():
    """Verify REST API routes /api/safety-gate/evaluate, /evaluate-loading, /status."""
    # 1. Status endpoint
    status_res = client.get("/api/safety-gate/status")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "ACTIVE"
    assert "Rule 8: Load-cell sensor data -> BLOCKED (Security Policy Violation)" in status_res.json()["enforced_rules"]

    # 2. Evaluate loading gate (Valid)
    load_payload = {
        "gate_type": "LOADING_CONFIRMATION",
        "container_data": _valid_container_dict(),
        "document_data": _valid_document_dict(),
        "validation_data": _valid_validation_dict(),
        "target_slot": {"bay": 1, "side": "port", "tier": 1},
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    }
    load_res = client.post("/api/safety-gate/evaluate-loading", json=load_payload)
    assert load_res.status_code == 200
    assert load_res.json()["allowed"] is True
    assert load_res.json()["status"] == "SAFE"

    # 3. Evaluate loading gate with forbidden load-cell source (Blocked)
    bad_payload = dict(load_payload)
    bad_payload["weight_source"] = "HX711_LOAD_CELL"
    bad_res = client.post("/api/safety-gate/evaluate-loading", json=bad_payload)
    assert bad_res.status_code == 200
    assert bad_res.json()["allowed"] is False
    assert bad_res.json()["status"] == "BLOCKED"
    assert bad_res.json()["reasons"][0]["category"] == "POLICY"
