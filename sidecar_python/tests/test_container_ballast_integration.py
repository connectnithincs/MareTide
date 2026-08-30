"""
Unit & Integration Tests for Phase 3C: Automated Ballast Compensation Integration.
Tests the complete OCR -> Load -> Ballast compensation workflow, 3-stage stability reports,
operator confirmation gates, audit logging, and vessel state integrity.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from ship import Ship, Container, BallastTank, StabilityAnalyzer
from container_stability.models import (
    BallastCompensationRequest,
    BallastCompensationResponse,
    BallastExecutionRequest,
    BallastExecutionResponse,
    ContainerLoadingConfirmRequest,
    ContainerStabilityAnalysisRequest
)
from container_stability.analyzer import (
    ContainerStabilityService,
    ContainerLoadingService,
    ContainerBallastService
)
from reports.logs_db import get_ballast_operations, clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_logs():
    clear_logs()
    yield
    clear_logs()


def create_sample_ship_with_tanks():
    """Helper to create a fresh Ship instance with tanks and water."""
    ship = Ship(name="Test Ballast Vessel", num_bays=4)
    # Initialize standard ballast tanks with 100t water each
    for bay in range(1, 5):
        ship.tanks[f"port_{bay}"] = BallastTank(f"Port-{bay}", capacity=300.0, current_volume=100.0)
        ship.tanks[f"starboard_{bay}"] = BallastTank(f"Starboard-{bay}", capacity=300.0, current_volume=100.0)
    return ship


# --- TEST CASE 1: Compensation Required Calculation ---
def test_case_1_compensation_required():
    ship = create_sample_ship_with_tanks()
    # Load 25t container on starboard bay 2
    ship.add_container(Container(id="TEST-01", weight=25.0, bay=2, side="starboard", tier=1))

    req = BallastCompensationRequest(
        container_number="TEST-01",
        gross_weight_t=25.0,
        bay=2,
        side="STARBOARD",
        tier=1
    )

    res = ContainerBallastService.calculate_compensation(req, ship_instance=ship)
    assert res.success is True
    assert res.compensation_required is True
    assert res.status == "CONFIRM_COMPENSATION"
    assert res.tank_key == "starboard_2"
    assert res.required_qty_t == 25.0
    assert res.direction == "DRAIN"
    assert res.projected_stability is not None
    assert res.projected_stability.stability_score < res.current_stability.stability_score


# --- TEST CASE 2: No Compensation Required ---
def test_case_2_no_compensation_required():
    ship = create_sample_ship_with_tanks()
    # Ship is perfectly balanced with 0 cargo
    req = BallastCompensationRequest(
        container_number=None,
        gross_weight_t=0.0
    )

    res = ContainerBallastService.calculate_compensation(req, ship_instance=ship)
    assert res.success is True
    assert res.compensation_required is False
    assert res.status == "NO_COMPENSATION_REQUIRED"
    assert "optimal" in res.message.lower()


# --- TEST CASE 3: Compensation Calculation Failure Handling ---
def test_case_3_compensation_calculation_failure():
    ship = create_sample_ship_with_tanks()
    # Request invalid non-existent tank (e.g. bay 99)
    req = BallastCompensationRequest(
        container_number="TEST-ERR",
        gross_weight_t=20.0,
        bay=99,
        side="STARBOARD"
    )

    res = ContainerBallastService.calculate_compensation(req, ship_instance=ship)
    assert res.success is False
    assert res.status == "error"
    assert "does not exist" in res.error_message


# --- TEST CASE 4: Operator Confirmation Requirement ---
def test_case_4_operator_confirmation_gate():
    ship = create_sample_ship_with_tanks()
    initial_volume = ship.tanks["starboard_2"].current_volume

    # Attempt to execute ballast without operator confirmation
    req = BallastExecutionRequest(
        container_number="TEST-01",
        tank_key="starboard_2",
        direction="DRAIN",
        qty_t=25.0,
        operator_confirmed=False
    )

    res = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert res.success is False
    assert res.status == "rejected"
    assert "explicit operator confirmation" in res.error_message.lower()
    # Vessel tank volume must remain untouched
    assert ship.tanks["starboard_2"].current_volume == initial_volume


# --- TEST CASE 5: Ballast Workflow Execution ---
def test_case_5_ballast_workflow_execution():
    ship = create_sample_ship_with_tanks()
    initial_volume = ship.tanks["starboard_2"].current_volume
    drain_qty = 20.0

    req = BallastExecutionRequest(
        container_number="TEST-01",
        tank_key="starboard_2",
        direction="DRAIN",
        qty_t=drain_qty,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    res = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert res.success is True
    assert res.status == "COMPLETED"
    assert res.actual_qty_t == drain_qty
    # Verify live ship tank volume changed
    assert ship.tanks["starboard_2"].current_volume == initial_volume - drain_qty


# --- TEST CASE 6: Final 3-Stage Stability Verification ---
def test_case_6_three_stage_stability_verification():
    ship = create_sample_ship_with_tanks()
    before_metrics = StabilityAnalyzer.risk_level(ship)

    # 1. Load container
    ship.add_container(Container(id="STAGE-CONT", weight=30.0, bay=1, side="port", tier=1))

    # 2. Execute ballast drain
    req = BallastExecutionRequest(
        container_number="STAGE-CONT",
        tank_key="port_1",
        direction="DRAIN",
        qty_t=30.0,
        operator_confirmed=True
    )

    res = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert res.success is True
    report = res.three_stage_stability
    assert report is not None
    assert report.before_load is not None
    assert report.after_container is not None
    assert report.after_ballast is not None
    # After ballast list should return towards 0
    assert abs(report.after_ballast.list_t) < abs(report.after_container.list_t)


# --- TEST CASE 7: State Transition Correctness ---
def test_case_7_state_transition_correctness():
    ship = create_sample_ship_with_tanks()
    # 1. Calculate -> CONFIRM_COMPENSATION
    calc_res = ContainerBallastService.calculate_compensation(
        BallastCompensationRequest(gross_weight_t=15.0, bay=2, side="port"),
        ship_instance=ship
    )
    assert calc_res.status == "CONFIRM_COMPENSATION"

    # 2. Execute -> COMPLETED
    exec_res = ContainerBallastService.execute_compensation(
        BallastExecutionRequest(tank_key="port_2", qty_t=15.0, operator_confirmed=True),
        ship_instance=ship
    )
    assert exec_res.status == "COMPLETED"


# --- TEST CASE 8: Audit Logging in ballast_operations ---
def test_case_8_audit_logging():
    ship = create_sample_ship_with_tanks()
    req = BallastExecutionRequest(
        container_number="AUDIT-BALLAST-01",
        tank_key="starboard_1",
        direction="DRAIN",
        qty_t=18.0,
        operator_confirmed=True
    )

    res = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert res.success is True

    # Retrieve audit records from sqlite
    logs = get_ballast_operations(limit=10)
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["op_type"] == "Drain"
    assert latest["source"] == "STARBOARD-1"
    assert latest["dest"] == "Sea"
    assert latest["qty"] == 18.0


# --- TEST CASE 9: Vessel State Integrity ---
def test_case_9_vessel_state_integrity():
    ship = create_sample_ship_with_tanks()
    initial_containers_count = len(ship.containers)

    # Ballast movement must not remove, alter, or corrupt existing containers
    ship.add_container(Container(id="KEEP-01", weight=10.0, bay=1, side="starboard"))
    
    req = BallastExecutionRequest(
        tank_key="starboard_1",
        direction="DRAIN",
        qty_t=10.0,
        operator_confirmed=True
    )
    res = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert res.success is True
    assert len(ship.containers) == initial_containers_count + 1
    assert ship.containers[-1].id == "KEEP-01"


# --- TEST CASE 10: Full OCR -> Load -> Ballast Integration ---
def test_case_10_full_ocr_to_load_to_ballast_integration():
    # 1. OCR extracted payload simulation
    ocr_payload = {
        "container_number": "E2E9876543",
        "container_type": "40HC",
        "weights": {
            "gross_weight_kg": 24000.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 20200.0
        },
        "cargo": {"hazardous": False},
        "destination": "SINGAPORE"
    }

    # 2. Stability Analysis
    analysis_req = ContainerStabilityAnalysisRequest(container=ocr_payload)
    analysis_res = client.post("/api/container/stability/analyze", json=analysis_req.model_dump())
    assert analysis_res.status_code == 200
    rec = analysis_res.json()["recommendation"]
    assert rec is not None

    # 3. Operator Confirms Container Load
    load_req = ContainerLoadingConfirmRequest(
        container=ocr_payload,
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation=rec,
        operator_confirmed=True
    )
    load_res = client.post("/api/container/load/confirm", json=load_req.model_dump())
    assert load_res.status_code == 200
    load_data = load_res.json()
    assert load_data["success"] is True
    assert load_data["status"] == "LOADED"

    # 4. Calculate Ballast Compensation
    ballast_calc_req = BallastCompensationRequest(
        container_number=load_data["container"]["container_number"],
        gross_weight_t=load_data["container"]["gross_weight_t"],
        bay=load_data["loaded_position"]["bay"],
        side=load_data["loaded_position"]["side"],
        tier=load_data["loaded_position"]["tier"]
    )
    calc_res = client.post("/api/container/ballast/calculate", json=ballast_calc_req.model_dump())
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["success"] is True
    assert calc_data["compensation_required"] is True

    # 5. Operator Confirms and Executes Ballast Compensation
    exec_req = BallastExecutionRequest(
        container_number=load_data["container"]["container_number"],
        tank_key=calc_data["tank_key"],
        direction=calc_data["direction"],
        qty_t=calc_data["required_qty_t"],
        operator_confirmed=True,
        stability_before_load=load_data["stability_before"]
    )
    exec_res = client.post("/api/container/ballast/execute", json=exec_req.model_dump())
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["success"] is True
    assert exec_data["status"] == "COMPLETED"
    assert exec_data["three_stage_stability"] is not None
