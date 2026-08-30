"""
Phase 5 Comprehensive End-to-End Operational Scenario Verification Suite.

Tests the full actual lifecycle:
REAL / SYNTHETIC CONTAINER SLIP IMAGE / TEXT
-> DOCUMENT AI OCR
-> JSON
-> VALIDATION
-> ANOMALY DETECTION
-> STABILITY OPTIMIZATION
-> OPERATOR REVIEW
-> LOADING CONFIRMATION
-> LIVE VESSEL STATE
-> BALLAST CALCULATION
-> OPERATOR BALLAST CONFIRMATION
-> BALLAST EXECUTION
-> DIGITAL TWIN UPDATE
-> FINAL STABILITY VERIFICATION
-> AUDIT LOG

Enforces ZERO LOAD-CELL POLICY: Container weight originates exclusively from [DOCUMENT AI].

Scenarios Tested:
1. NORMAL CONTAINER E2E
2. HEAVY CONTAINER E2E
3. HAZARDOUS CONTAINER E2E
4. VGM MISMATCH BLOCKING
5. INVALID CONTAINER NUMBER IDENTIFIER REJECTION
6. LOW OCR CONFIDENCE REVIEW BRANCHING
7. NO AVAILABLE SLOT SAFE HANDLING
8. UNSAFE PLACEMENT GATE BLOCKING
9. OPERATOR EXPLICIT REJECTION
10. TELEMETRY DISCONNECT PERSISTENCE & ALERTS
11. STALE TELEMETRY HANDLING
12. BALLAST FAILURE PRESERVATION & ATTENTION
13. DUPLICATE OPERATION IDEMPOTENCY
14. LOAD-CELL SENSOR DATA EXCLUSION ENFORCEMENT
"""

import sys
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import state
from ship import Ship, BallastTank, Container, StabilityAnalyzer
from container_ocr.workflow import ContainerWorkflowEngine, WorkflowState, WorkflowTransitionError
from container_stability.safety_gate import RealTimeSafetyGate
from container_stability.models import (
    SafetyGateStatus,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest
)
from container_stability.analyzer import (
    ContainerStabilityService,
    ContainerLoadingService,
    ContainerBallastService
)
from telemetry.manager import TelemetryManager
from telemetry.models import TelemetrySource, ConnectionStatus, DataQuality
from digital_twin import DigitalTwin
from reports.logs_db import clear_logs, get_operation_timeline, get_all_audit_events
from main import app

client = TestClient(app)

SAMPLE_CLEAN_SLIP = """
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

SAMPLE_HEAVY_SLIP = """
CONTAINER SHIPPING ORDER
CONTAINER NO: CMAU7391024
TYPE: 40HC
MAX GROSS: 35000 KG
TARE: 4200 KG
CARGO: 28300 KG
GROSS: 32500 KG
DESTINATION: HAMBURG
VGM DECLARED: YES
HAZARDOUS: NO
"""

SAMPLE_HAZARDOUS_SLIP = """
CONTAINER SHIPPING ORDER
CONTAINER NO: MSCU4920195
TYPE: 40HC
MAX GROSS: 32500 KG
TARE: 3800 KG
CARGO: 22400 KG
GROSS: 26200 KG
HAZARDOUS: YES
UN NUMBER: UN1993
IMDG CLASS: 3.1
DESTINATION: ANTWERP
VGM DECLARED: YES
"""


@pytest.fixture(autouse=True)
def reset_system():
    """Ensure clean state before each test scenario."""
    state.reset_state()
    ContainerWorkflowEngine.get_instance().reset()
    clear_logs()


# -------------------------------------------------------------
# Scenario 1: Normal Container Full End-to-End Workflow
# -------------------------------------------------------------
def test_scenario_1_normal_container_e2e():
    """
    Validates complete 10-stage lifecycle for standard container:
    Document -> OCR -> Validated -> Stability Analyzed -> Operator Approved ->
    Loaded -> Ballast Calculated -> Ballast Approved -> Ballast Executed ->
    Digital Twin Updated -> Verified -> Completed.
    """
    engine = ContainerWorkflowEngine.get_instance()
    ship = state.get_current_ship()

    # Initial ship state (0 containers, 4 tanks filled at 300t)
    assert len(ship.containers) == 0
    assert ship.tanks["port_1"].current_volume == 300.0

    # 1. Document Received -> OCR -> Stability Analysis
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    assert session.container_id == "MSCU4920195"
    assert session.stability_response is not None
    assert session.stability_response.recommendation is not None
    rec = session.stability_response.recommendation
    assert rec.tier == 1

    # 2. Operator Loading Confirmation
    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    assert session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "MSCU4920195"
    assert ship.containers[0].weight == 32.5

    # 3. Operator Ballast Authorization
    session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    assert session.current_state == WorkflowState.COMPLETED
    assert session.ballast_execution is not None
    assert session.ballast_execution.success is True

    # 4. Digital Twin Verification
    mgr = TelemetryManager.get_instance()
    norm = mgr.get_latest_telemetry()
    dt = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=norm)
    assert len(dt.containers) == 1
    assert dt.containers[0]["id"] == "MSCU4920195"
    assert dt.containers[0]["weight"] == 32.5
    assert dt.provenance_map["cargo_weight"] == "[DOCUMENT AI]"

    # 5. Audit Trail Verification
    timeline = get_operation_timeline(op_id)
    assert len(timeline) >= 9
    event_types = [e["event_type"] for e in timeline]
    assert "DOCUMENT_RECEIVED" in event_types
    assert "LOADING" in event_types
    assert "LOADED" in event_types
    assert "BALLAST_EXECUTING" in event_types
    assert "COMPLETED" in event_types


# -------------------------------------------------------------
# Scenario 2: Heavy Container VCG Bottom-Tier Optimization
# -------------------------------------------------------------
def test_scenario_2_heavy_container_e2e():
    """
    Validates heavy container (35.0t) placement in Tier 1 bottom slot for low VCG,
    calculating necessary anti-heeling ballast discharge.
    """
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_HEAVY_SLIP)
    op_id = session.operation_id

    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    rec = session.stability_response.recommendation
    assert rec.tier == 1, "Heavy container must be assigned Tier 1 for low vertical center of gravity"

    # Confirm loading & ballast
    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    if session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION:
        session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    assert session.current_state == WorkflowState.COMPLETED
    ship = state.get_current_ship()
    assert len(ship.containers) == 1
    assert ship.containers[0].weight == 35.0


# -------------------------------------------------------------
# Scenario 3: Hazardous Cargo Open Deck Position
# -------------------------------------------------------------
def test_scenario_3_hazardous_container_e2e():
    """
    Validates dangerous goods (Class 3.1, UN1993) container:
    Operator reviews hazardous cargo, proceeds to placement analysis,
    verifying Tier 1 open deck placement for emergency firefighting.
    """
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_HAZARDOUS_SLIP)
    op_id = session.operation_id

    # If review flag is raised for hazardous cargo, operator reviews and approves
    if session.current_state == WorkflowState.REVIEW_REQUIRED:
        session = engine.approve_review_and_analyze(
            op_id,
            operator_id="ChiefOfficer",
            operator_notes="DG Class 3.1 Flammable Liquid verified with port authority."
        )

    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    rec = session.stability_response.recommendation
    assert rec is not None
    assert rec.tier == 1, "Hazardous cargo must be assigned Tier 1 for emergency accessibility"


# -------------------------------------------------------------
# Scenario 4: VGM Mismatch Blocks Loading
# -------------------------------------------------------------
def test_scenario_4_vgm_mismatch_blocks_loading():
    """
    Validates that a severe discrepancy between Gross Weight and Tare+Cargo (>= 1500kg)
    is caught by the RealTimeSafetyGate and blocks loading confirmation.
    """
    mismatch_data = {
        "container_number": "MSCU4920195",
        "weights": {
            "gross_weight_kg": 29000.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 18000.0  # Sum = 21800 != 29000 (diff 7200kg)
        }
    }
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=mismatch_data,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert gate_res.status == SafetyGateStatus.BLOCKED.value
    assert any(r.category == "WEIGHT" for r in gate_res.reasons)


# -------------------------------------------------------------
# Scenario 5: Invalid Container Identifier Rejected
# -------------------------------------------------------------
def test_scenario_5_invalid_container_identifier_rejected():
    """Validates missing or invalid container number is blocked by Safety Gate."""
    bad_id_data = {
        "container_number": "INVALID123",  # 10 chars, not 11-char ISO format
        "weights": {"gross_weight_kg": 22000.0}
    }
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=bad_id_data,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert gate_res.status == SafetyGateStatus.BLOCKED.value
    assert any(r.category == "IDENTIFIER" for r in gate_res.reasons)


# -------------------------------------------------------------
# Scenario 6: Low OCR Confidence Routes to Review Required
# -------------------------------------------------------------
def test_scenario_6_low_ocr_confidence_routes_to_review():
    """Validates that low OCR confidence / validation failure pauses at REVIEW_REQUIRED."""
    dirty_slip = """
    CONTAINER SHIPPING ORDER
    CONTAINER NO: MSCU4920198
    GROSS: 26200 KG
    DESTINATION: ROTTERDAM
    """
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(dirty_slip)
    assert session.current_state == WorkflowState.REVIEW_REQUIRED


# -------------------------------------------------------------
# Scenario 7: No Available Slot Safe Handling
# -------------------------------------------------------------
def test_scenario_7_no_available_slot_safe_handling():
    """Validates fully packed vessel halts with clear error and preserves vessel state."""
    ship = state.get_current_ship()
    for bay in range(1, ship.num_bays + 1):
        for side in ["port", "starboard"]:
            for tier in range(1, 4):
                ship.add_container(Container(id=f"CNTR_{bay}_{side}_{tier}", weight=20.0, bay=bay, side=side, tier=tier))

    initial_count = len(ship.containers)
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)

    assert session.current_state == WorkflowState.FAILED
    assert "No available cargo slots" in (session.error_message or "")
    assert len(ship.containers) == initial_count


# -------------------------------------------------------------
# Scenario 8: Unsafe Placement Gate Blocking
# -------------------------------------------------------------
def test_scenario_8_unsafe_placement_gate_blocking():
    """Validates that attempting to load into an occupied slot is rejected by Safety Gate."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="OCCUPIED_SLOT", weight=22.0, bay=2, side="port", tier=1))

    load_req = ContainerLoadingConfirmRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 25000.0}},
        recommendation={"bay": 2, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    load_res = ContainerLoadingService.confirm_and_load(load_req, ship_instance=ship)
    assert load_res.success is False
    assert "already occupied" in load_res.error_message


# -------------------------------------------------------------
# Scenario 9: Operator Explicit Rejection
# -------------------------------------------------------------
def test_scenario_9_operator_explicit_rejection():
    """Validates explicit operator rejection marks operation FAILED without mutating ship."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    session = engine.reject_workflow(op_id, reason="Damaged corner casting observed.", operator_id="ChiefMate")
    assert session.current_state == WorkflowState.FAILED
    assert len(state.get_current_ship().containers) == 0


# -------------------------------------------------------------
# Scenario 10: Telemetry Disconnect Persistence & Alerts
# -------------------------------------------------------------
def test_scenario_10_telemetry_disconnect_alerts():
    """Validates disconnected telemetry preserves last known state and generates alert without fake data."""
    ship = state.get_current_ship()
    from telemetry.models import NormalizedTelemetry, VesselStateTelemetry, TelemetryMetadata

    mock_tel = NormalizedTelemetry(
        connection_status=ConnectionStatus.DISCONNECTED,
        vessel_state=VesselStateTelemetry(roll_deg=1.8, pitch_deg=0.3),
        metadata=TelemetryMetadata(data_quality=DataQuality.STALE, stale_seconds=15.0)
    )
    dt = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_tel)
    assert dt.connection_status == "DISCONNECTED"
    assert dt.roll_deg == 1.8
    assert any(a.alert_type == "TELEMETRY_DISCONNECTED" for a in dt.alerts)


# -------------------------------------------------------------
# Scenario 11: Stale Telemetry Handling
# -------------------------------------------------------------
def test_scenario_11_stale_telemetry_handling():
    """Validates stale telemetry (>5s) is labeled STALE with operational warning."""
    ship = state.get_current_ship()
    from telemetry.models import NormalizedTelemetry, VesselStateTelemetry, TelemetryMetadata

    mock_tel = NormalizedTelemetry(
        connection_status=ConnectionStatus.CONNECTED,
        vessel_state=VesselStateTelemetry(roll_deg=2.1, pitch_deg=0.4),
        metadata=TelemetryMetadata(data_quality=DataQuality.STALE, stale_seconds=9.0)
    )
    dt = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_tel)
    assert dt.telemetry_freshness == "STALE"
    assert any(a.alert_type == "STALE_TELEMETRY" for a in dt.alerts)


# -------------------------------------------------------------
# Scenario 12: Ballast Execution Failure Preservation & Attention
# -------------------------------------------------------------
def test_scenario_12_ballast_execution_failure_preservation():
    """
    Validates that ballast execution failure preserves actual known tank volumes,
    marks operation FAILED, and requires operator attention.
    """
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    from container_stability.models import BallastExecutionResponse
    with patch("container_stability.analyzer.ContainerBallastService.execute_compensation") as mock_exec:
        mock_exec.return_value = BallastExecutionResponse(
            success=False,
            status="error",
            actual_qty_t=0.0,
            actual_qty_kg=0.0,
            error_message="Flow valve jammed on Port Tank 1"
        )
        session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
        assert session.current_state == WorkflowState.FAILED

    # Live tanks preserved
    ship = state.get_current_ship()
    assert ship.tanks["port_1"].current_volume == 300.0


# -------------------------------------------------------------
# Scenario 13: Duplicate Operation Idempotency
# -------------------------------------------------------------
def test_scenario_13_duplicate_operation_idempotency():
    """Validates duplicate transition attempts on completed sessions are rejected."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    if session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION:
        session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    assert session.current_state == WorkflowState.COMPLETED

    with pytest.raises(WorkflowTransitionError):
        engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)


# -------------------------------------------------------------
# Scenario 14: Load-Cell Sensor Data Exclusion Enforcement
# -------------------------------------------------------------
def test_scenario_14_load_cell_exclusion_enforcement():
    """
    Validates strict rejection of load-cell sensor weight data.
    Weight MUST originate exclusively from validated [DOCUMENT AI].
    """
    payload = {
        "gate_type": "LOADING_CONFIRMATION",
        "container_data": {"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 25000.0}},
        "weight_source": "LOAD_CELL_WEIGHING_SCALE",
        "operator_confirmed": True,
        "operator_id": "ChiefOfficer"
    }
    res = client.post("/api/safety-gate/evaluate-loading", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["allowed"] is False
    assert data["status"] == "BLOCKED"
    assert data["reasons"][0]["category"] == "POLICY"
    assert "forbidden" in data["reasons"][0]["message"].lower()
