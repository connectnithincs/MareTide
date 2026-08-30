"""
Comprehensive Unit & Integration Test Suite for Phase 5 Event-Driven Container Document Intelligence Workflow.

Validates:
1. End-to-end automated progression from upload to completed audit.
2. Complete 15-state lifecycle model & state transition records.
3. Rejection of illegal / invalid state machine transitions.
4. Review-required branching on low OCR confidence or anomalies.
5. Live vessel state immutability during OCR, validation, simulation, and recommendation.
6. Explicit operator authorization required for container loading.
7. Explicit operator authorization required for ballast water discharge.
8. Strict zero load-cell sensor data exclusion ([DOCUMENT AI] authoritative provenance).
9. Session tracking, audit events, and transition logging.
10. FastAPI REST API endpoints compliance.
"""

import pytest
import io
import cv2
import numpy as np
from fastapi.testclient import TestClient

from main import app
import state
from container_ocr.workflow import (
    WorkflowState,
    WorkflowTransitionError,
    StateTransitionRecord,
    ContainerWorkflowSession,
    ContainerWorkflowEngine,
    VALID_TRANSITIONS
)
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    LOAD_CELL_POLICY
)

SAMPLE_SLIP_TEXT = """GLOBAL CONTAINER TERMINAL - INTERCHANGE RECEIPT
GATE-IN VERIFICATION & VGM CERTIFICATE
CONTAINER NO: MSCU 492019 5
TYPE / ISO CODE: 40HC (45G1)
DIMENSIONS: 40' x 8' x 9'6" (12.19m x 2.44m x 2.89m)
TARE WEIGHT: 3,800 KG / 8,377 LBS
NET CARGO WT: 22,400 KG
VERIFIED GROSS MASS (VGM): 26,200 KG [VERIFIED ACCURATE]
COMMODITY DESC: ELECTRONIC COMPONENTS & LITHIUM CELLS
HAZMAT STATUS: HAZARDOUS - UN 3480 CLASS 9 (LITHIUM ION BATTERIES)
PORT OF DISCHARGE: PORT OF SINGAPORE (SGSIN)
SEAL NUMBER: ML-SG-987214
CARRIER: MEDITERRANEAN SHIPPING COMPANY
PORT AUTHORITY GATE 04 - APPROVED FOR LOADING"""

SAMPLE_REVIEW_TEXT = """GLOBAL CONTAINER TERMINAL
CONTAINER NO: INVALID1234
TARE: 3800 KG
GROSS: 26000 KG"""

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_engine_and_ship():
    """Ensures a clean ship state and clean workflow engine for every test."""
    state.reset_state()
    engine = ContainerWorkflowEngine.get_instance()
    engine.reset()
    yield
    state.reset_state()
    engine.reset()


def test_1_full_end_to_end_event_driven_workflow():
    """Verify automated event-driven progression from upload to final verification and completion."""
    engine = ContainerWorkflowEngine.get_instance()
    ship = state.get_current_ship()
    assert len(ship.containers) == 0

    # Step 1: Upload slip text -> triggers OCR, Validation, Stability Analysis automatically
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT, source_name="test_gate_slip.txt")
    
    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    assert session.container_id == "MSCU4920195"
    assert session.extraction_response is not None
    assert session.extraction_response.container.weights.gross_weight_kg == 26200.0
    assert session.stability_response is not None
    assert session.stability_response.recommendation is not None

    # Verify ship state was NOT mutated during analysis
    assert len(ship.containers) == 0

    # Verify transition history records
    states_traversed = [r.next_state for r in session.transition_history]
    assert WorkflowState.DOCUMENT_RECEIVED in states_traversed
    assert WorkflowState.OCR_PROCESSING in states_traversed
    assert WorkflowState.VALIDATING in states_traversed
    assert WorkflowState.ANALYZING_STABILITY in states_traversed
    assert WorkflowState.RECOMMENDATION_READY in states_traversed
    assert WorkflowState.AWAITING_OPERATOR_CONFIRMATION in states_traversed

    # Step 2: Operator confirms container loading
    session = engine.confirm_load_step(
        operation_id=session.operation_id,
        operator_id="ChiefOfficer",
        operator_confirmed=True
    )
    
    assert session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION
    assert session.loaded_response is not None
    assert session.loaded_response.success is True
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "MSCU4920195"
    assert ship.containers[0].weight == 26.2

    # Step 3: Operator confirms ballast compensation execution
    session = engine.confirm_ballast_step(
        operation_id=session.operation_id,
        operator_id="ChiefOfficer",
        operator_confirmed=True
    )

    assert session.current_state == WorkflowState.COMPLETED
    assert session.ballast_execution is not None
    assert session.ballast_execution.success is True
    assert session.final_verification is not None
    assert session.final_verification["provenance"] in [CONTAINER_WEIGHT_SOURCE, "[DOCUMENT AI]", "DOCUMENT_AI"]


def test_2_illegal_state_transition_rejection():
    """Verify that jumping illegal steps raises WorkflowTransitionError."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION

    # Attempt to jump from AWAITING_OPERATOR_CONFIRMATION directly to COMPLETED
    with pytest.raises(WorkflowTransitionError) as exc_info:
        engine._record_transition(
            session,
            WorkflowState.COMPLETED,
            reason="Illegal shortcut attempt"
        )
    assert exc_info.value.previous_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    assert exc_info.value.attempted_state == WorkflowState.COMPLETED

    # Attempt to jump directly to BALLAST_EXECUTING without loading
    with pytest.raises(WorkflowTransitionError):
        engine.confirm_ballast_step(session.operation_id, "Operator", operator_confirmed=True)


def test_3_review_required_branching_on_low_confidence_or_invalid_data():
    """Verify workflow halts in REVIEW_REQUIRED state when document has invalid or missing ISO data."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_REVIEW_TEXT, source_name="invalid_slip.txt")
    
    assert session.current_state == WorkflowState.REVIEW_REQUIRED
    assert session.stability_response is None  # Stability simulation deferred until review approved

    # Operator explicitly approves review
    session = engine.approve_review_and_analyze(
        operation_id=session.operation_id,
        operator_id="DutyOfficer",
        operator_notes="Manually confirmed cargo manifest override"
    )
    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    assert session.stability_response is not None


def test_4_ship_live_state_immutability_during_ocr_and_simulation():
    """Guarantee that live ship containers and ballast tanks are never modified prior to explicit loading confirmation."""
    engine = ContainerWorkflowEngine.get_instance()
    ship = state.get_current_ship()
    
    initial_containers_count = len(ship.containers)
    initial_tank_vols = {k: t.current_volume for k, t in ship.tanks.items()}

    # Run OCR and stability analysis
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION

    # Live ship state must remain 100% untouched
    assert len(ship.containers) == initial_containers_count
    for k, t in ship.tanks.items():
        assert t.current_volume == initial_tank_vols[k]


def test_5_explicit_operator_confirmation_required_for_loading():
    """Verify that if operator rejects container, state transitions to FAILED and vessel remains untouched."""
    engine = ContainerWorkflowEngine.get_instance()
    ship = state.get_current_ship()

    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION

    # Operator rejects load
    session = engine.confirm_load_step(
        operation_id=session.operation_id,
        operator_id="ChiefOfficer",
        operator_confirmed=False
    )
    assert session.current_state == WorkflowState.FAILED
    assert len(ship.containers) == 0


def test_6_explicit_operator_confirmation_required_for_ballast():
    """Verify operator can skip ballast compensation, cleanly transitioning to VERIFYING and COMPLETED."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    session = engine.confirm_load_step(session.operation_id, "ChiefOfficer", operator_confirmed=True)
    assert session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION

    # Operator skips ballast
    session = engine.confirm_ballast_step(session.operation_id, "ChiefOfficer", operator_confirmed=False)
    assert session.current_state == WorkflowState.COMPLETED
    assert session.ballast_execution is None  # Skipped execution


def test_7_prohibited_load_cell_cannot_influence_workflow():
    """Verify load-cell data is never used or required to drive the workflow."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    
    # Check that provenance is strictly Document AI
    for record in session.transition_history:
        assert record.provenance in ["[DOCUMENT AI]", "DOCUMENT_AI", CONTAINER_WEIGHT_SOURCE]
        assert record.provenance != "LOAD_CELL_SENSOR"
        assert record.provenance != "HARDWARE_SENSOR"


def test_8_complete_audit_trail_recorded():
    """Verify transition history contains timestamps, operation ID, container ID, reasons, and metadata."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    session = engine.confirm_load_step(session.operation_id, "ChiefOfficer", operator_confirmed=True)
    session = engine.confirm_ballast_step(session.operation_id, "ChiefOfficer", operator_confirmed=True)

    assert len(session.transition_history) >= 8
    for record in session.transition_history:
        assert record.operation_id == session.operation_id
        assert record.timestamp is not None
        assert record.reason is not None
        assert record.previous_state is not None
        assert record.next_state is not None


def test_9_operator_explicit_rejection_method():
    """Verify reject_workflow marks session FAILED with reason."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
    
    session = engine.reject_workflow(
        operation_id=session.operation_id,
        reason="Port congestion cancelled loading schedule",
        operator_id="HarborMaster"
    )
    assert session.current_state == WorkflowState.FAILED
    assert session.is_active is False
    last_record = session.transition_history[-1]
    assert "Port congestion cancelled" in last_record.reason


def test_10_rest_api_workflow_initiate_text():
    """Test POST /api/container/workflow/initiate-text."""
    response = client.post(
        "/api/container/workflow/initiate-text",
        json={"raw_text": SAMPLE_SLIP_TEXT, "source_name": "api_test_slip.txt"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["current_state"] == "AWAITING_OPERATOR_CONFIRMATION"
    assert data["container_id"] == "MSCU4920195"
    assert data["extraction_response"]["container"]["weights"]["gross_weight_kg"] == 26200.0


def test_11_rest_api_confirm_load_and_ballast():
    """Test full REST API lifecycle: initiate -> confirm-load -> confirm-ballast -> get session."""
    # 1. Initiate
    init_res = client.post(
        "/api/container/workflow/initiate-text",
        json={"raw_text": SAMPLE_SLIP_TEXT}
    )
    assert init_res.status_code == 200
    op_id = init_res.json()["operation_id"]

    # 2. Confirm Load
    load_res = client.post(
        "/api/container/workflow/confirm-load",
        json={"operation_id": op_id, "operator_id": "ChiefOfficer", "operator_confirmed": True}
    )
    assert load_res.status_code == 200
    assert load_res.json()["current_state"] == "AWAITING_BALLAST_CONFIRMATION"

    # 3. Confirm Ballast
    ballast_res = client.post(
        "/api/container/workflow/confirm-ballast",
        json={"operation_id": op_id, "operator_id": "ChiefOfficer", "operator_confirmed": True}
    )
    assert ballast_res.status_code == 200
    assert ballast_res.json()["current_state"] == "COMPLETED"

    # 4. Get Session
    get_res = client.get(f"/api/container/workflow/session/{op_id}")
    assert get_res.status_code == 200
    assert get_res.json()["current_state"] == "COMPLETED"
    assert len(get_res.json()["transition_history"]) >= 8


def test_12_rest_api_invalid_transition_error_code():
    """Test that invalid transition via REST API returns 409 Conflict."""
    init_res = client.post(
        "/api/container/workflow/initiate-text",
        json={"raw_text": SAMPLE_SLIP_TEXT}
    )
    op_id = init_res.json()["operation_id"]

    # Attempt to confirm ballast when session is awaiting load confirmation
    ballast_res = client.post(
        "/api/container/workflow/confirm-ballast",
        json={"operation_id": op_id, "operator_id": "ChiefOfficer", "operator_confirmed": True}
    )
    assert ballast_res.status_code == 409
    assert "Invalid state transition" in ballast_res.json()["detail"]


def test_13_rest_api_workflow_history_and_active():
    """Test GET /api/container/workflow/history and GET /api/container/workflow/active."""
    client.post(
        "/api/container/workflow/initiate-text",
        json={"raw_text": SAMPLE_SLIP_TEXT}
    )
    hist_res = client.get("/api/container/workflow/history?limit=10")
    assert hist_res.status_code == 200
    assert len(hist_res.json()) >= 1

    active_res = client.get("/api/container/workflow/active")
    assert active_res.status_code == 200
    assert active_res.json() is not None
