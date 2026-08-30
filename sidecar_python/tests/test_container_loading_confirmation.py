"""
Unit & Integration Tests for Phase 3B: OCR-Driven Container Loading Confirmation.
Tests safety rules, atomic live vessel state commits, audit logging, failure handling, and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from ship import Ship, Container, StabilityAnalyzer
from container_stability.models import (
    ContainerLoadingConfirmRequest,
    ContainerLoadingConfirmResponse
)
from container_stability.analyzer import ContainerLoadingService
from reports.logs_db import get_container_loading_audits, clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_database_and_state():
    """Clean logs and create a fresh test ship before and after each test."""
    clear_logs()
    yield
    clear_logs()


def create_sample_ship():
    """Helper to create a fresh Ship instance with 4 bays and standard ballast tanks."""
    ship = Ship(name="Test Vessel", num_bays=4)
    return ship


# --- TEST CASE 1: Successful Confirmation & Loading ---
def test_case_1_successful_confirmation():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU1234567",
            "container_type": "40HC",
            "weights": {
                "gross_weight_kg": 25000.0,
                "tare_weight_kg": 3800.0,
                "cargo_weight_kg": 21200.0
            },
            "cargo": {"hazardous": False, "description": "Auto Parts"},
            "destination": "SINGAPORE"
        },
        document={"processing_status": "success"},
        validation={"valid": True, "iso_6346_valid": True},
        recommendation={"bay": 2, "side": "STARBOARD", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is True
    assert response.status == "LOADED"
    assert response.loaded_position.bay == 2
    assert response.loaded_position.side == "STARBOARD"
    assert response.loaded_position.tier == 1
    assert response.container.container_number == "MSCU1234567"
    assert response.container.gross_weight_t == 25.0
    assert response.audit_id is not None


# --- TEST CASE 2: Missing Gross Weight Rejection ---
def test_case_2_missing_gross_weight():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU1234567",
            "container_type": "40HC",
            "weights": {"gross_weight_kg": 0.0},
            "cargo": {"hazardous": False}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 2, "side": "STARBOARD", "tier": 1},
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is False
    assert response.status == "error"
    assert "gross weight" in response.error_message.lower()
    # Live ship state must not have any containers
    assert len(ship.containers) == 0


# --- TEST CASE 3: Invalid OCR Validation Rejection ---
def test_case_3_invalid_ocr_validation():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "INVALID999",
            "weights": {"gross_weight_kg": 20000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": False, "errors": ["ISO 6346 Checksum Failed"]},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is False
    assert "validation failed" in response.error_message.lower()
    assert len(ship.containers) == 0


# --- TEST CASE 4: Review-Required Document Blocked ---
def test_case_4_review_required_document():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU1234567",
            "weights": {"gross_weight_kg": 20000.0}
        },
        document={"processing_status": "review_required"},
        validation={"valid": True},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is False
    assert response.status == "review_required"
    assert "review is required" in response.error_message.lower()
    assert len(ship.containers) == 0


# --- TEST CASE 5: Missing Recommendation Rejection ---
def test_case_5_missing_recommendation():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU1234567",
            "weights": {"gross_weight_kg": 20000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation=None,
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is False
    assert "no valid recommendation" in response.error_message.lower()
    assert len(ship.containers) == 0


# --- TEST CASE 6: Occupied Slot Rejection ---
def test_case_6_occupied_slot():
    ship = create_sample_ship()
    # Pre-occupy slot Bay 2 / STARBOARD / Tier 1
    existing_container = Container(id="EXISTING-01", weight=18.0, bay=2, side="starboard", tier=1)
    ship.add_container(existing_container)
    assert len(ship.containers) == 1

    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU9999999",
            "weights": {"gross_weight_kg": 22000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 2, "side": "STARBOARD", "tier": 1},
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is False
    assert "already occupied" in response.error_message.lower()
    # Ensure original container was not replaced and count remains 1
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "EXISTING-01"


# --- TEST CASE 7: Successful Vessel-State Update ---
def test_case_7_vessel_state_update():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU7778889",
            "container_type": "20GP",
            "weights": {"gross_weight_kg": 18500.0},
            "cargo": {"hazardous": True, "imdg_class": "Class 9"}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 3, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is True
    assert ship.slot_occupied(3, "port", 1) is True
    assert ship.total_cargo_weight() == 18.5
    assert response.stability_before is not None
    assert response.stability_after is not None
    assert response.stability_delta is not None


# --- TEST CASE 8: Failed Load Leaves State Unchanged (Atomicity) ---
def test_case_8_failed_load_leaves_state_unchanged():
    ship = create_sample_ship()
    initial_containers_count = len(ship.containers)
    initial_cargo_weight = ship.total_cargo_weight()

    # Attempt to load with unconfirmed operator flag
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU1122334",
            "weights": {"gross_weight_kg": 25000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=False
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is False
    assert response.status == "rejected"
    assert len(ship.containers) == initial_containers_count
    assert ship.total_cargo_weight() == initial_cargo_weight


# --- TEST CASE 9: Correct Audit Record ---
def test_case_9_correct_audit_record():
    ship = create_sample_ship()
    request = ContainerLoadingConfirmRequest(
        container={
            "container_number": "AUDIT1234567",
            "container_type": "40HC",
            "weights": {"gross_weight_kg": 24000.0},
            "cargo": {"hazardous": False}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 2, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )

    response = ContainerLoadingService.confirm_and_load(request, ship_instance=ship)
    assert response.success is True

    # Retrieve audit records from sqlite db
    audits = get_container_loading_audits(limit=10)
    assert len(audits) >= 1
    latest = audits[0]
    assert latest["container_number"] == "AUDIT1234567"
    assert latest["gross_weight_t"] == 24.0
    assert latest["gross_weight_kg"] == 24000.0
    assert latest["bay"] == 2
    assert latest["side"] == "PORT"
    assert latest["tier"] == 1
    assert latest["operation_result"] == "SUCCESS"
    assert latest["operator_confirmed"] is True


# --- TEST CASE 10: Existing APIs Remain Functional ---
def test_case_10_existing_apis_remain_functional():
    # 1. API endpoint /api/container/load/confirm
    payload = {
        "container": {
            "container_number": "RESTCONFIRM1",
            "weights": {"gross_weight_kg": 21000.0}
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True},
        "recommendation": {"bay": 1, "side": "STARBOARD", "tier": 1},
        "operator_confirmed": True
    }
    res = client.post("/api/container/load/confirm", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "LOADED"

    # 2. Audit endpoint /api/container/load/audit
    audit_res = client.get("/api/container/load/audit")
    assert audit_res.status_code == 200
    assert isinstance(audit_res.json(), list)

    # 3. Existing vessel state endpoint
    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vessel_data = vessel_res.json()
    assert "ship_name" in vessel_data
    assert "stability_score" in vessel_data

    # 4. Existing recommendations endpoint
    rec_res = client.get("/api/recommendations")
    assert rec_res.status_code == 200

    # 5. Existing container stability analyze endpoint
    stab_res = client.post("/api/container/stability/analyze", json={
        "container": {
            "container_number": "ANALYZE01",
            "weights": {"gross_weight_kg": 22000.0}
        }
    })
    assert stab_res.status_code == 200
    assert stab_res.json()["success"] is True
