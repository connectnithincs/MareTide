"""
Phase 5 Comprehensive Test Suite: Operational Traceability and Audit Logging.

Validates:
1. Unique operation ID per workflow session.
2. Complete chronological ordering of audit events in SQLite (maretide.db).
3. Full lifecycle tracking across all 10+ operational stages.
4. Five-tier provenance source labeling (DOCUMENT_AI, CALCULATED, OPERATOR, HARDWARE_SENSOR, SIMULATED_TELEMETRY).
5. Zero load-cell data recorded in audit storage.
6. Operator human-in-the-loop authorization audit capture.
7. Explicit operational rejection and failure audit logging.
8. REST API timeline endpoints compliance.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ship import Ship, BallastTank, Container
import state
from reports.logs_db import (
    init_db,
    clear_logs,
    log_operation_audit_event,
    get_operation_timeline,
    get_all_audit_events,
    get_recent_operation_summaries
)
from container_ocr.workflow import ContainerWorkflowEngine, WorkflowState
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


@pytest.fixture(autouse=True)
def reset_system_and_db():
    """Ensure clean ship state and clear audit database for each test."""
    state.reset_state()
    ContainerWorkflowEngine.get_instance().reset()
    clear_logs()


# 1. Unique Operation ID
def test_audit_unique_operation_id():
    """Verify each workflow session receives a unique, non-empty operation ID."""
    engine = ContainerWorkflowEngine.get_instance()
    
    session1 = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    session2 = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)

    assert session1.operation_id.startswith("OP-")
    assert session2.operation_id.startswith("OP-")
    assert session1.operation_id != session2.operation_id


# 2. Chronological Ordering of Events in SQLite
def test_audit_complete_chronological_ordering():
    """Verify all events for an operation are saved to SQLite in strict ascending chronological order."""
    engine = ContainerWorkflowEngine.get_instance()
    
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    # Confirm loading step
    session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    # Confirm ballast step if needed
    if session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION:
        session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)

    assert session.current_state == WorkflowState.COMPLETED

    # Query timeline from SQLite
    timeline = get_operation_timeline(op_id)
    assert len(timeline) >= 6

    # Verify ID monotonicity and timestamp ascending order
    for i in range(len(timeline) - 1):
        assert timeline[i]["id"] < timeline[i + 1]["id"]
        assert timeline[i]["timestamp"] <= timeline[i + 1]["timestamp"]


# 3. Full Lifecycle Tracking
def test_audit_full_lifecycle_event_coverage():
    """Verify key lifecycle states are recorded as events in SQLite."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    session = engine.confirm_load_step(op_id, operator_id="DutyOfficer", operator_confirmed=True)
    if session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION:
        session = engine.confirm_ballast_step(op_id, operator_id="DutyOfficer", operator_confirmed=True)

    timeline = get_operation_timeline(op_id)
    event_types = [e["event_type"] for e in timeline]

    assert "DOCUMENT_RECEIVED" in event_types
    assert "OCR_PROCESSING" in event_types
    assert "VALIDATING" in event_types
    assert "ANALYZING_STABILITY" in event_types
    assert "RECOMMENDATION_READY" in event_types
    assert "AWAITING_OPERATOR_CONFIRMATION" in event_types
    assert "LOADING" in event_types
    assert "LOADED" in event_types
    assert "COMPLETED" in event_types


# 4. Five-Tier Provenance Labels
def test_audit_provenance_labels_strict_compliance():
    """Verify all audit events conform to the 5 allowed provenance tiers."""
    allowed_tiers = {
        "DOCUMENT_AI",
        "CALCULATED",
        "OPERATOR",
        "HARDWARE_SENSOR",
        "SIMULATED_TELEMETRY"
    }

    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
    timeline = get_operation_timeline(op_id)

    for event in timeline:
        assert event["source"] in allowed_tiers, f"Unexpected source: {event['source']}"


# 5. Zero Load-Cell Guarantee in Audit Storage
def test_audit_zero_load_cell_guarantee():
    """Verify load-cell measurements are purged and never saved in audit logs."""
    # Attempt logging event with malicious/prohibited sensor fields
    event_id = log_operation_audit_event(
        operation_id="OP-TEST-001",
        event_type="TEST_EVENT",
        container_id="MSCU4920195",
        actor="SENSOR_ADAPTER",
        source="HARDWARE_SENSOR",
        relevant_metrics={
            "roll_deg": 1.2,
            "cargo_kg": 26200.0,      # FORBIDDEN
            "scale_kg": 26180.0,      # FORBIDDEN
            "hx711_raw": 891230,      # FORBIDDEN
            "valid_metric_displacement_t": 8250.0
        },
        reason="Sanitization verification test."
    )

    timeline = get_operation_timeline("OP-TEST-001")
    assert len(timeline) == 1
    metrics = timeline[0]["relevant_metrics"]

    assert "cargo_kg" not in metrics
    assert "scale_kg" not in metrics
    assert "hx711_raw" not in metrics
    assert metrics.get("valid_metric_displacement_t") == 8250.0
    assert metrics.get("roll_deg") == 1.2


# 6. Operator Action Capture
def test_audit_operator_action_capture():
    """Verify operator load and ballast authorization actions are logged with operator ID."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    session = engine.confirm_load_step(op_id, operator_id="CaptReynolds", operator_confirmed=True)
    timeline = get_operation_timeline(op_id)

    load_event = next((e for e in timeline if e["event_type"] == "LOADING"), None)
    assert load_event is not None
    assert "LOAD_AUTHORIZED" in load_event["actor"]
    assert load_event["source"] == "OPERATOR"


# 7. Explicit Rejection / Failure Audit Logging
def test_audit_rejection_and_failure_logging():
    """Verify explicit rejection records a FAILED event with reason and actor."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    session = engine.reject_workflow(
        operation_id=op_id,
        reason="Damaged corner casting detected during quay inspection.",
        operator_id="ChiefMate"
    )

    assert session.current_state == WorkflowState.FAILED
    timeline = get_operation_timeline(op_id)

    fail_event = timeline[-1]
    assert fail_event["event_type"] == "FAILED"
    assert fail_event["success"] is False
    assert "Damaged corner casting" in fail_event["reason"]
    assert "EXPLICIT_REJECTION" in fail_event["actor"]


# 8. REST API Timeline Endpoints
def test_audit_rest_api_timeline_endpoints():
    """Verify REST API endpoints /timeline/{operation_id}, /timeline, /events."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_text(SAMPLE_CLEAN_SLIP)
    op_id = session.operation_id

    # 1. Query timeline for op_id
    res_tl = client.get(f"/api/container/workflow/timeline/{op_id}")
    assert res_tl.status_code == 200
    data_tl = res_tl.json()
    assert data_tl["operation_id"] == op_id
    assert len(data_tl["timeline"]) >= 1

    # 2. Query summary list
    res_sums = client.get("/api/container/workflow/timeline")
    assert res_sums.status_code == 200
    ops = res_sums.json()["operations"]
    assert any(o["operation_id"] == op_id for o in ops)

    # 3. Query all audit events
    res_evts = client.get("/api/container/workflow/events")
    assert res_evts.status_code == 200
    assert len(res_evts.json()["events"]) >= 1
