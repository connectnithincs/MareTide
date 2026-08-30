"""
Phase 5 Comprehensive Test Suite: Failure Recovery & Safe-State Handling.

Validates that the system FAILS SAFELY across all 20 operational failure paths:
1. OCR failure
2. Unreadable document
3. Invalid container number
4. VGM mismatch
5. Missing gross weight
6. Low OCR confidence / review required
7. Critical cargo anomaly
8. No available slot
9. Stability recommendation failure
10. Operator rejection
11. Vessel state changed after recommendation (Slot occupied in interim)
12. Telemetry disconnect
13. Stale telemetry
14. Ballast calculation failure
15. Ballast execution failure
16. Database failure
17. Frontend/backend disconnect (State persistence & recovery)
18. Hardware interface unavailable
19. Prohibited load-cell message
20. Duplicate operation request

RULE:
No failure may silently mutate vessel state.
"""

import sys
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ship import Ship, BallastTank, Container, StabilityAnalyzer
import state
from container_ocr.workflow import ContainerWorkflowEngine, WorkflowState, WorkflowTransitionError
from container_stability.safety_gate import RealTimeSafetyGate
from container_stability.models import (
    SafetyGateStatus,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest
)
from container_stability.analyzer import (
    ContainerLoadingService,
    ContainerBallastService,
    ContainerStabilityService
)
from telemetry.manager import TelemetryManager
from telemetry.models import TelemetrySource, ConnectionStatus, DataQuality
from reports.logs_db import clear_logs, log_operation_audit_event
from main import app

client = TestClient(app)

VALID_SLIP = """
CONTAINER SHIPPING ORDER
CONTAINER NO: MSCU4920195
TYPE: 40HC
MAX GROSS: 32500 KG
TARE: 3800 KG
CARGO: 22400 KG
GROSS: 26200 KG
DESTINATION: ROTTERDAM
VGM DECLARED: YES
HAZARDOUS: NO
"""


@pytest.fixture(autouse=True)
def reset_system():
    """Ensure clean state before each test."""
    state.reset_state()
    ContainerWorkflowEngine.get_instance().reset()
    clear_logs()


# 1. OCR Failure
def test_failure_1_ocr_failure_preserves_ship_state():
    """Verify OCR pipeline exception transitions workflow to FAILED without altering vessel state."""
    ship_before = state.get_current_ship()
    cnt_before = len(ship_before.containers)

    engine = ContainerWorkflowEngine.get_instance()
    with patch("container_ocr.service.default_service.process_raw_text", side_effect=RuntimeError("OCR engine crashed")):
        session = engine.initiate_workflow_from_text("CORRUPT DATA")
        assert session.current_state == WorkflowState.FAILED

    ship_after = state.get_current_ship()
    assert len(ship_after.containers) == cnt_before


# 2. Unreadable Document
def test_failure_2_unreadable_document_blocks():
    """Verify unreadable document stops before stability and never mutates ship."""
    ship = state.get_current_ship()
    unreadable_text = "??? --- UNREADABLE GARBAGE --- ???"

    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(unreadable_text)

    assert session.current_state in [WorkflowState.REVIEW_REQUIRED, WorkflowState.FAILED]
    assert len(ship.containers) == 0


# 3. Invalid Container Number
def test_failure_3_invalid_container_number_blocks():
    """Verify invalid ISO 6346 container number format fails safety gate."""
    cntr_data = {
        "container_number": "BAD123",
        "weights": {"gross_weight_kg": 20000.0}
    }
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr_data,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert gate_res.status == SafetyGateStatus.BLOCKED.value
    assert any(r.category == "IDENTIFIER" for r in gate_res.reasons)


# 4. VGM Mismatch
def test_failure_4_vgm_mismatch_blocks():
    """Verify tare + cargo vs gross difference > 1500kg blocks loading."""
    cntr_data = {
        "container_number": "MSCU4920195",
        "weights": {
            "gross_weight_kg": 28000.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 15000.0  # Sum = 18800 != 28000 (diff 9200kg)
        }
    }
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr_data,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert gate_res.status == SafetyGateStatus.BLOCKED.value


# 5. Missing Gross Weight
def test_failure_5_missing_gross_weight_blocks():
    """Verify container missing gross weight is blocked by safety gate."""
    cntr_data = {
        "container_number": "MSCU4920195",
        "weights": {"gross_weight_kg": None}
    }
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr_data,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert any(r.category == "WEIGHT" for r in gate_res.reasons)


# 6. Low OCR Confidence / Review Required
def test_failure_6_low_ocr_confidence_triggers_review():
    """Verify OCR review-required document routes to REVIEW_REQUIRED state and pauses."""
    engine = ContainerWorkflowEngine.get_instance()
    # Invalid check digit slip triggers validation failure -> REVIEW_REQUIRED
    invalid_check_digit_slip = """
    CONTAINER SHIPPING ORDER
    CONTAINER NO: MSCU4920198
    TYPE: 40HC
    GROSS: 26200 KG
    TARE: 3800 KG
    CARGO: 22400 KG
    DESTINATION: ROTTERDAM
    """
    session = engine.initiate_workflow_from_text(invalid_check_digit_slip)
    assert session.current_state == WorkflowState.REVIEW_REQUIRED
    ship = state.get_current_ship()
    assert len(ship.containers) == 0


# 7. Critical Cargo Anomaly
def test_failure_7_critical_cargo_anomaly_blocks():
    """Verify critical anomaly blocks safety gate."""
    cntr_data = {"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 25000.0}}
    anomalies = [{"anomaly_type": "STRUCTURAL_OVERWEIGHT", "severity": "CRITICAL", "message": "Severe overweight"}]
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=cntr_data,
        anomalies=anomalies,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert any(r.category == "ANOMALY" for r in gate_res.reasons)


# 8. No Available Slot
def test_failure_8_no_available_slot_handles_cleanly():
    """Verify fully stowed vessel returns failure without crashing or mutating ship."""
    ship = state.get_current_ship()
    # Fill all slots across all bays and tiers
    for bay in range(1, ship.num_bays + 1):
        for side in ["port", "starboard"]:
            for tier in range(1, 4):
                ship.add_container(Container(id=f"FULL_{bay}_{side}_{tier}", weight=20.0, bay=bay, side=side, tier=tier))

    initial_count = len(ship.containers)
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(VALID_SLIP)

    assert session.current_state == WorkflowState.FAILED
    assert "No available cargo slots" in (session.error_message or "")
    assert len(ship.containers) == initial_count


# 9. Stability Recommendation Failure
def test_failure_9_stability_recommendation_failure_halts():
    """Verify stability analysis failure marks workflow FAILED and preserves ship."""
    engine = ContainerWorkflowEngine.get_instance()
    with patch("container_stability.analyzer.ContainerStabilityService.analyze_container_placement", side_effect=Exception("Hydrostatic singularity")):
        session = engine.initiate_workflow_from_text(VALID_SLIP)
        assert session.current_state == WorkflowState.FAILED

    ship = state.get_current_ship()
    assert len(ship.containers) == 0


# 10. Operator Rejection
def test_failure_10_operator_rejection_halts_loading():
    """Verify explicit operator rejection stops workflow with zero cargo added."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(VALID_SLIP)
    op_id = session.operation_id

    session = engine.reject_workflow(op_id, reason="Rejected by Chief Officer", operator_id="ChiefOfficer")
    assert session.current_state == WorkflowState.FAILED

    ship = state.get_current_ship()
    assert len(ship.containers) == 0


# 11. Vessel State Changed After Recommendation
def test_failure_11_slot_occupied_before_load_confirmation():
    """Verify that if target slot becomes occupied after recommendation, loading is safely rejected."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(VALID_SLIP)
    op_id = session.operation_id

    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    rec = session.stability_response.recommendation

    # Another operation stows a container in the recommended slot in the interim
    ship = state.get_current_ship()
    ship.add_container(Container(id="INTERIM_CNTR", weight=25.0, bay=rec.bay, side=rec.side.lower(), tier=rec.tier))

    # Operator now attempts to confirm loading
    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    assert session.current_state == WorkflowState.FAILED
    assert "already occupied" in (session.error_message or "")
    # Vessel only contains the interim container, not the second container
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "INTERIM_CNTR"


# 12. Telemetry Disconnect
def test_failure_12_telemetry_disconnect_handled_safely():
    """Verify disconnected telemetry preserves last known state and creates alert without synthesizing data."""
    ship = state.get_current_ship()
    from digital_twin import DigitalTwin
    from telemetry.models import NormalizedTelemetry, VesselStateTelemetry, TelemetryMetadata

    mock_tel = NormalizedTelemetry(
        connection_status=ConnectionStatus.DISCONNECTED,
        vessel_state=VesselStateTelemetry(roll_deg=1.5, pitch_deg=0.2),
        metadata=TelemetryMetadata(data_quality=DataQuality.STALE, stale_seconds=20.0)
    )

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_tel)
    assert snapshot.connection_status == "DISCONNECTED"
    assert snapshot.roll_deg == 1.5
    assert any(a.alert_type == "TELEMETRY_DISCONNECTED" for a in snapshot.alerts)


# 13. Stale Telemetry
def test_failure_13_stale_telemetry_handling():
    """Verify stale telemetry (>5s delay) is tagged STALE and generates an operational alert."""
    ship = state.get_current_ship()
    from digital_twin import DigitalTwin
    from telemetry.models import NormalizedTelemetry, VesselStateTelemetry, TelemetryMetadata

    mock_tel = NormalizedTelemetry(
        connection_status=ConnectionStatus.CONNECTED,
        vessel_state=VesselStateTelemetry(roll_deg=2.0, pitch_deg=0.5),
        metadata=TelemetryMetadata(data_quality=DataQuality.STALE, stale_seconds=8.0)
    )

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_tel)
    assert snapshot.telemetry_freshness == "STALE"
    assert snapshot.stale_seconds == 8.0
    assert any(a.alert_type == "STALE_TELEMETRY" for a in snapshot.alerts)


# 14. Ballast Calculation Failure
def test_failure_14_ballast_calculation_failure_retains_loaded_state():
    """
    RULE: If loading succeeds but ballast calculation fails:
    -> retain the valid loaded state
    -> mark operation requiring attention
    -> do not fabricate ballast completion.
    """
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(VALID_SLIP)
    op_id = session.operation_id

    # Mock ballast calculation failure
    from container_stability.models import BallastCompensationResponse
    with patch("container_stability.analyzer.ContainerBallastService.calculate_compensation") as mock_calc:
        mock_calc.return_value = BallastCompensationResponse(
            success=False,
            status="error",
            compensation_required=False,
            error_message="Ballast optimization algorithm diverged"
        )
        session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

        assert session.current_state == WorkflowState.FAILED
        assert "Ballast optimization algorithm diverged" in (session.error_message or "")

    # Vessel state retains the loaded container
    ship = state.get_current_ship()
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "MSCU4920195"


# 15. Ballast Execution Failure
def test_failure_15_ballast_execution_failure_preserves_actual_state():
    """
    RULE: If ballast execution fails:
    -> preserve actual known vessel state
    -> mark operation incomplete
    -> require operator intervention
    -> never automatically retry irreversible hardware actions.
    """
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(VALID_SLIP)
    op_id = session.operation_id

    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    assert session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION

    # Mock ballast execution failure (e.g. valve failure)
    from container_stability.models import BallastExecutionResponse
    with patch("container_stability.analyzer.ContainerBallastService.execute_compensation") as mock_exec:
        mock_exec.return_value = BallastExecutionResponse(
            success=False,
            status="error",
            actual_qty_t=0.0,
            actual_qty_kg=0.0,
            error_message="Solenoid valve stuck closed on Port Tank 1"
        )
        session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

        assert session.current_state == WorkflowState.FAILED
        assert "Solenoid valve stuck closed" in (session.error_message or "")

    # Live vessel tanks remain untouched
    ship = state.get_current_ship()
    assert ship.tanks["port_1"].current_volume == 300.0


# 16. Database Failure Resilience
def test_failure_16_database_write_failure_resilience():
    """Verify database write failure does not crash workflow engine or mutate vessel illegally."""
    engine = ContainerWorkflowEngine.get_instance()
    with patch("reports.logs_db.log_operation_audit_event", side_effect=RuntimeError("SQLite disk locked")):
        session = engine.initiate_workflow_from_text(VALID_SLIP)
        assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION


# 17. Frontend/Backend Disconnect Resilience
def test_failure_17_session_persistence_and_recovery():
    """Verify session can be queried and resumed by ID across HTTP calls."""
    res_init = client.post("/api/container/workflow/initiate-text", json={"raw_text": VALID_SLIP})
    assert res_init.status_code == 200
    op_id = res_init.json()["operation_id"]

    # Reconnect / fetch session
    res_get = client.get(f"/api/container/workflow/session/{op_id}")
    assert res_get.status_code == 200
    assert res_get.json()["operation_id"] == op_id


# 18. Hardware Interface Unavailable
def test_failure_18_hardware_unavailable_fallback():
    """Verify unavailable serial COM port falls back to simulation safely."""
    mgr = TelemetryManager.get_instance()
    # Switch to hardware adapter with a non-existent port
    mgr.select_source(TelemetrySource.HARDWARE_SENSOR, port="COM_NON_EXISTENT")
    norm = mgr.get_latest_telemetry()
    assert norm is not None
    # Reset back to simulated
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)


# 19. Prohibited Load-Cell Message
def test_failure_19_prohibited_load_cell_rejected():
    """Verify prohibited load-cell payload triggers immediate safety gate block."""
    payload = {
        "gate_type": "LOADING_CONFIRMATION",
        "container_data": {"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 25000.0}},
        "weight_source": "LOAD_CELL_WEIGHING_SCALE",
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    }
    res = client.post("/api/safety-gate/evaluate-loading", json=payload)
    assert res.status_code == 200
    assert res.json()["allowed"] is False
    assert res.json()["status"] == "BLOCKED"
    assert res.json()["reasons"][0]["category"] == "POLICY"


# 20. Duplicate Operation Request
def test_failure_20_duplicate_operation_transition_rejected():
    """Verify illegal transitions or duplicate confirm attempts on completed sessions are rejected."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(VALID_SLIP)
    op_id = session.operation_id

    # Confirm load
    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    if session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION:
        session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    assert session.current_state == WorkflowState.COMPLETED

    # Attempt duplicate confirm_load_step on COMPLETED session
    with pytest.raises(WorkflowTransitionError):
        engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
