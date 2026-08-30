"""
Phase 6B: Full End-to-End Operational Reliability Verification Suite.

Tests the complete MareTide workflow from Image Upload to Final SQLite Audit:
IMAGE
  ↓
OCR Extraction
  ↓
Normalized Container JSON
  ↓
ISO 6346 & VGM Validation
  ↓
Anomaly Detection
  ↓
Stability Optimization
  ↓
Explainable Recommendation
  ↓
Operator Authorization Gate
  ↓
Live Vessel Atomic Commit
  ↓
Ballast Calculation
  ↓
Ballast Authorization Gate
  ↓
Ballast Execution
  ↓
Four-Stage Hydrostatic Verification
  ↓
SQLite Audit & Provenance Certification

Strictly enforces ZERO LOAD-CELL SENSOR DATA USE across all phases.
"""

import os
import sys
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from main import app
import state
from ship import Ship, Container, BallastTank, StabilityAnalyzer, RecommendationEngine
from container_ocr.workflow import (
    WorkflowState,
    WorkflowTransitionError,
    ContainerWorkflowEngine,
    ContainerWorkflowSession
)
from container_ocr.service import default_service
from container_ocr.validator import DomainValidator
from container_ocr.anomaly_detector import CargoAnomalyDetector
from container_ocr.normalizer import DataNormalizer
from container_ocr.models import ContainerSlipResponse, CargoMassMetadata, ContainerWeights
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest,
    SafetyGateStatus
)

from container_stability.analyzer import (
    ContainerStabilityService,
    ContainerLoadingService,
    ContainerBallastService,
    MultiContainerPlanner
)
from container_stability.safety_gate import RealTimeSafetyGate
from container_stability.policy import (
    DOCUMENT_AI_CARGO_MASS,
    LOAD_CELL_CARGO_MASS,
    HARDWARE_TELEMETRY_LABEL,
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    validate_cargo_mass_provenance
)
from reports.logs_db import (
    clear_logs,
    get_operation_timeline,
    get_all_audit_events,
    get_cargo_operations,
    get_ballast_operations,
    _sanitize_metrics
)

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMPLE_SLIP_PATH = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
HEAVY_SLIP_PATH = os.path.join(FIXTURES_DIR, "heavy_container_slip.jpg")
INCONSISTENT_SLIP_PATH = os.path.join(FIXTURES_DIR, "inconsistent_weight_slip.jpg")
INVALID_NUM_SLIP_PATH = os.path.join(FIXTURES_DIR, "invalid_container_num_slip.jpg")
MISSING_WEIGHT_SLIP_PATH = os.path.join(FIXTURES_DIR, "missing_weight_slip.jpg")


@pytest.fixture(autouse=True)
def reset_all_state():
    """Reset singleton state, database logs, and workflow engine before and after every test."""
    state.reset_state()
    clear_logs()
    engine = ContainerWorkflowEngine.get_instance()
    engine.reset()
    yield
    state.reset_state()
    clear_logs()
    engine.reset()


# =============================================================================
# PART 1: CANONICAL GOLDEN PATH TEST (IMAGE -> OCR -> LOAD -> BALLAST -> AUDIT)
# =============================================================================

def test_phase6b_canonical_golden_path_image_to_audit():
    """
    CANONICAL GOLDEN PATH:
    Executes the entire uncompromised workflow starting from a real slip image file:
    1. Image Input: sample_container_slip.jpg
    2. Document AI OCR: Extracts all fields
    3. Normalization: Metric KG, standard dimensions, ISO 6346
    4. Validation: ISO 6346 check digit and VGM consistency valid
    5. Anomaly Detection: Evaluated clean
    6. Stability Simulation: Computes 8 candidate slots without mutating live ship
    7. Recommendation: Generates explainable recommendation (Bay, Side, Tier)
    8. Operator Authorization Gate 1: Mandatory human-in-the-loop authorization
    9. Live Vessel Commit: Atomic commitment of container to vessel state
    10. Ballast Calculation: Calculates post-load moment compensation on live vessel
    11. Operator Authorization Gate 2: Mandatory ballast discharge confirmation
    12. Ballast Execution: Discharges water, modifies tank volume, triggers hardware command
    13. Four-Stage Verification: Certifies hydrostatic equilibrium
    14. SQLite Audit: Verifies complete chronological timeline with provenance
    """
    assert os.path.exists(SAMPLE_SLIP_PATH), f"Fixture not found at {SAMPLE_SLIP_PATH}"
    
    engine = ContainerWorkflowEngine.get_instance()
    ship = state.get_current_ship()
    assert len(ship.containers) == 0
    initial_port_ballast = ship.ballast_port()
    initial_stbd_ballast = ship.ballast_starboard()
    
    # -------------------------------------------------------------------------
    # STEP 1: Image Upload & Automated Document Intelligence Progression
    # -------------------------------------------------------------------------
    img = Image.open(SAMPLE_SLIP_PATH)
    session = engine.initiate_workflow_from_image(img, source_name="sample_container_slip.jpg")
    
    # Verify session automatically advanced to AWAITING_OPERATOR_CONFIRMATION
    assert session.current_state == WorkflowState.AWAITING_OPERATOR_CONFIRMATION
    assert session.container_id == "MSCU4920195"
    assert session.extraction_response is not None
    
    # -------------------------------------------------------------------------
    # STEP 2 & 3: Extraction & Normalization Verification
    # -------------------------------------------------------------------------
    ext = session.extraction_response
    cntr = ext.container
    assert cntr.container_number == "MSCU4920195"
    assert cntr.container_type == "40HC"
    assert cntr.iso_type == "45G1"
    assert cntr.dimensions.length_ft == 40.0
    assert cntr.dimensions.height_ft == 9.5
    assert cntr.weights.tare_weight_kg == 3800.0
    assert cntr.weights.cargo_weight_kg == 22400.0
    assert cntr.weights.gross_weight_kg == 26200.0
    assert cntr.weights.vgm_kg == 26200.0
    assert cntr.weights.vgm_verified is True
    assert cntr.cargo.hazardous is True
    assert "3480" in cntr.cargo.un_number
    assert "9" in str(cntr.cargo.imdg_class)
    assert "SINGAPORE" in cntr.destination or "SGSIN" in cntr.destination
    assert cntr.seal_number == "ML-SG-987214"
    assert "MEDITERRANEAN SHIPPING COMPANY" in cntr.carrier.upper()


    
    # Verify Provenance Metadata
    assert cntr.cargo_mass is not None
    assert cntr.cargo_mass.value == 26200.0
    assert cntr.cargo_mass.unit == "kg"
    assert cntr.cargo_mass.source == "DOCUMENT_AI"
    assert cntr.cargo_mass.authoritative is True

    
    # -------------------------------------------------------------------------
    # STEP 4 & 5: Validation & Anomaly Detection Verification
    # -------------------------------------------------------------------------
    assert ext.validation.valid is True
    assert ext.validation.iso_6346_valid is True
    assert ext.validation.weight_balance_valid is True
    assert len(ext.validation.errors) == 0

    # No critical anomalies
    assert not any(a.severity == "CRITICAL" for a in (ext.anomalies or []))
    
    # -------------------------------------------------------------------------
    # STEP 6 & 7: Stability Optimization & Explainability Verification
    # -------------------------------------------------------------------------
    stab = session.stability_response
    assert stab is not None
    assert stab.success is True
    assert stab.recommendation is not None
    rec = stab.recommendation
    assert rec.bay in [1, 2, 3, 4]
    assert rec.side in ["PORT", "STARBOARD"]
    assert rec.tier == 1  # Hazardous cargo prioritized for deck level (tier 1)
    assert len(stab.reason) > 0
    assert len(stab.structured_explanations) > 0
    
    # Verify live vessel state has NOT been modified during simulation
    assert len(ship.containers) == 0
    
    # -------------------------------------------------------------------------
    # STEP 8 & 9: Operator Authorization Gate & Live Vessel Commit
    # -------------------------------------------------------------------------
    session = engine.confirm_load_step(
        operation_id=session.operation_id,
        operator_id="ChiefOfficer_Sarah",
        operator_confirmed=True
    )
    
    # Verify progression
    assert session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION
    assert session.loaded_response is not None
    assert session.loaded_response.success is True
    assert session.loaded_response.status == "LOADED"
    
    # Verify container is now atomically committed to live vessel state
    assert len(ship.containers) == 1
    committed_c = ship.containers[0]
    assert committed_c.id == "MSCU4920195"
    assert committed_c.weight == 26.2  # 26,200 kg -> 26.2 tonnes
    assert committed_c.bay == rec.bay
    assert committed_c.side.upper() == rec.side.upper()
    assert committed_c.tier == rec.tier
    
    # -------------------------------------------------------------------------
    # STEP 10: Ballast Calculation Verification
    # -------------------------------------------------------------------------
    ballast_comp = session.ballast_compensation
    assert ballast_comp is not None
    assert ballast_comp.success is True
    assert ballast_comp.compensation_required is True
    assert ballast_comp.required_qty_t > 0.0
    assert ballast_comp.tank_key is not None
    assert ballast_comp.affected_tank is not None
    assert ballast_comp.direction == "DRAIN"
    
    # -------------------------------------------------------------------------
    # STEP 11 & 12: Operator Ballast Confirmation & Execution
    # -------------------------------------------------------------------------
    target_tank = ship.tanks[ballast_comp.tank_key]
    vol_before_drain = target_tank.current_volume
    
    session = engine.confirm_ballast_step(
        operation_id=session.operation_id,
        operator_id="ChiefOfficer_Sarah",
        operator_confirmed=True
    )
    
    # Verify completion
    assert session.current_state == WorkflowState.COMPLETED
    assert session.ballast_execution is not None
    assert session.ballast_execution.success is True
    assert session.ballast_execution.status == "COMPLETED"
    
    # Verify tank volume was modified by the exact calculated compensation
    expected_volume = round(vol_before_drain - ballast_comp.required_qty_t, 2)
    assert abs(target_tank.current_volume - expected_volume) < 0.05
    
    # -------------------------------------------------------------------------
    # STEP 13: Four-Stage Verification Snapshot
    # -------------------------------------------------------------------------
    assert session.final_verification is not None
    fv = session.final_verification
    assert "stage_1_before" in fv
    assert "stage_2_loaded" in fv
    assert "stage_3_ballasted" in fv
    assert "stage_4_current" in fv
    assert fv["container_id"] == "MSCU4920195"
    assert "DOCUMENT AI" in fv["provenance"] or "DOCUMENT_AI" in fv["provenance"]
    
    # -------------------------------------------------------------------------
    # STEP 14: SQLite Audit Trail Verification
    # -------------------------------------------------------------------------
    timeline = get_operation_timeline(session.operation_id)
    assert len(timeline) >= 8  # Full lifecycle transitions recorded
    
    event_types = [e["event_type"] for e in timeline]
    assert "DOCUMENT_RECEIVED" in event_types
    assert "OCR_PROCESSING" in event_types
    assert "VALIDATING" in event_types
    assert "ANALYZING_STABILITY" in event_types
    assert "RECOMMENDATION_READY" in event_types
    assert "AWAITING_OPERATOR_CONFIRMATION" in event_types
    assert "LOADED" in event_types
    assert "BALLAST_CALCULATED" in event_types
    assert "BALLAST_EXECUTING" in event_types
    assert "COMPLETED" in event_types
    
    # Verify provenance across all events
    for event in timeline:
        assert event["source"] in ["DOCUMENT_AI", "CALCULATED", "OPERATOR"]
        assert event["success"] is True
        # Verify no forbidden keys exist in metrics
        metrics = event.get("relevant_metrics", {})
        for forbidden in ["cargo_kg", "scale_kg", "hx711", "load_cell", "sensor_derived_weight"]:
            assert forbidden not in metrics


# =============================================================================
# PART 2: CANONICAL GOLDEN FAILURE PATH (UNVALIDATED OCR STOPS BEFORE LOADING)
# =============================================================================

def test_phase6b_canonical_golden_failure_path_invalid_ocr_stops():
    """
    CANONICAL GOLDEN FAILURE PATH:
    Uploads a defective container slip image (invalid container number / missing check digit).
    Verifies that:
    1. OCR detects the issue and validation fails (iso_6346_valid is False).
    2. Workflow stops safely at REVIEW_REQUIRED.
    3. Stability simulation is not automatically cleared.
    4. Attempting to bypass and load without operator review clearance is blocked.
    5. Live vessel state remains completely untouched (0 containers).
    6. Audit trail records the validation failure accurately.
    """
    assert os.path.exists(INVALID_NUM_SLIP_PATH), f"Fixture not found at {INVALID_NUM_SLIP_PATH}"
    
    engine = ContainerWorkflowEngine.get_instance()
    ship = state.get_current_ship()
    assert len(ship.containers) == 0
    
    img = Image.open(INVALID_NUM_SLIP_PATH)
    session = engine.initiate_workflow_from_image(img, source_name="invalid_container_num_slip.jpg")
    
    # Must stop at REVIEW_REQUIRED
    assert session.current_state == WorkflowState.REVIEW_REQUIRED
    assert session.extraction_response is not None
    assert session.extraction_response.validation.iso_6346_valid is False
    assert session.extraction_response.document.processing_status == "review_required"
    
    # Verify stability simulation was NOT automatically run
    assert session.stability_response is None
    
    # Verify attempting to confirm loading from REVIEW_REQUIRED raises WorkflowTransitionError
    with pytest.raises(WorkflowTransitionError):
        engine.confirm_load_step(
            operation_id=session.operation_id,
            operator_id="UnauthorizedOperator",
            operator_confirmed=True
        )
        
    # Verify live ship containers count is STILL 0
    assert len(ship.containers) == 0
    
    # Verify audit event logged REVIEW_REQUIRED
    timeline = get_operation_timeline(session.operation_id)
    event_types = [e["event_type"] for e in timeline]
    assert "REVIEW_REQUIRED" in event_types
    assert "LOADED" not in event_types


# =============================================================================
# PART 3: 20-POINT OPERATIONAL RELIABILITY VERIFICATIONS
# =============================================================================

def test_point_01_ocr_field_extraction():
    """Point 1: OCR successfully extracts all 10 essential maritime fields from gate slip."""
    img = Image.open(SAMPLE_SLIP_PATH)
    res: ContainerSlipResponse = default_service.process_image(img, source_name="sample_container_slip.jpg")
    
    c = res.container
    assert c.container_number == "MSCU4920195"
    assert c.container_type == "40HC"
    assert c.dimensions.length_ft == 40.0
    assert c.dimensions.height_ft == 9.5
    assert c.weights.tare_weight_kg == 3800.0
    assert c.weights.cargo_weight_kg == 22400.0
    assert c.weights.gross_weight_kg == 26200.0
    assert c.cargo.description is not None
    assert c.cargo.hazardous is True
    assert "SINGAPORE" in c.destination or "SGSIN" in c.destination
    assert c.seal_number is not None
    assert c.carrier is not None



def test_point_02_container_json_normalization():
    """Point 2: Container JSON is normalized into standard SI units and standardized fields."""
    raw_candidates = {
        "container_number": {"value": "mscu 492019 5", "confidence": 0.95},
        "container_type": {"value": "40 high cube", "confidence": 0.90},
        "dimensions": {"raw_length": "40", "raw_width": "8", "raw_height": "9'6\"", "confidence": 0.90},
        "weights": {
            "tare": {"raw_value": "8377", "unit": "LBS", "confidence": 0.92},
            "cargo": {"raw_value": "22.4", "unit": "TONNES", "confidence": 0.95},
            "gross": {"raw_value": "26200", "unit": "KG", "confidence": 0.95},
            "vgm": {"raw_value": "26200", "unit": "KG", "verified": True}
        }
    }
    
    details, confidences = DataNormalizer.normalize_all(raw_candidates)
    assert details.container_number == "MSCU4920195"
    assert "40" in details.container_type
    assert abs(details.weights.tare_weight_kg - 3800.0) < 5.0  # 8377 lbs -> ~3800 kg
    assert details.weights.cargo_weight_kg == 22400.0          # 22.4 tonnes -> 22,400 kg
    assert details.weights.gross_weight_kg == 26200.0
    assert details.weights.cargo_mass.value == 26200.0
    assert details.weights.cargo_mass.source == "DOCUMENT_AI"



def test_point_03_iso_6346_check_digit_validation():
    """Point 3: ISO 6346 validation succeeds for valid documents and fails for corrupted serials."""
    # MSCU 492019 [5] is a valid ISO 6346 number
    is_valid, _ = DomainValidator.validate_iso_6346("MSCU4920195")
    assert is_valid is True
    # Corrupted check digit (9 instead of 5)
    is_invalid, _ = DomainValidator.validate_iso_6346("MSCU4920199")
    assert is_invalid is False
    # Corrupted owner code
    is_invalid_owner, _ = DomainValidator.validate_iso_6346("12344920195")
    assert is_invalid_owner is False


def test_point_04_vgm_validation_accuracy():
    """Point 4: VGM validation succeeds when Gross == Tare + Cargo within tolerance."""
    # Consistent: 3800 + 22400 = 26200 (Diff = 0)
    w_valid = ContainerWeights(tare_weight_kg=3800.0, cargo_weight_kg=22400.0, gross_weight_kg=26200.0)
    valid, _, errors = DomainValidator.validate_weights(w_valid)
    assert valid is True
    assert len(errors) == 0

    # Inconsistent: 3800 + 10000 = 13800, but Gross claims 28000 (Diff = 14200 kg)
    w_invalid = ContainerWeights(tare_weight_kg=3800.0, cargo_weight_kg=10000.0, gross_weight_kg=28000.0)
    invalid, _, errors = DomainValidator.validate_weights(w_invalid)
    assert invalid is False
    assert len(errors) > 0
    assert "GROSS_WEIGHT_INCONSISTENT" in errors[0]



def test_point_05_invalid_documents_stop_before_loading():
    """Point 5: Invalid documents (unweighted or missing VGM) stop at REVIEW_REQUIRED before loading."""
    engine = ContainerWorkflowEngine.get_instance()
    img = Image.open(MISSING_WEIGHT_SLIP_PATH)
    session = engine.initiate_workflow_from_image(img, source_name="missing_weight_slip.jpg")
    
    assert session.current_state == WorkflowState.REVIEW_REQUIRED
    assert session.loaded_response is None
    assert len(state.get_current_ship().containers) == 0


def test_point_06_anomalous_documents_cannot_bypass_safety_gates():
    """Point 6: Anomalous documents with critical discrepancies are blocked by RealTimeSafetyGate."""
    critical_anomaly_container = {
        "container_number": "ANOM9999999",
        "weights": {
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 10000.0,
            "gross_weight_kg": 35000.0  # Critical > 20,000 kg discrepancy
        },
        "weight_source": "DOCUMENT_AI"
    }
    
    gate_res = RealTimeSafetyGate.evaluate_loading_gate(
        container=critical_anomaly_container,
        document={"processing_status": "review_required"},
        validation={"valid": False, "errors": ["Severe VGM weight mismatch"]},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    assert gate_res.allowed is False
    assert gate_res.status in [SafetyGateStatus.BLOCKED.value, SafetyGateStatus.REVIEW_REQUIRED.value]


def test_point_07_stability_optimization_returns_valid_candidate():
    """Point 7: Stability optimization returns a valid candidate placement with ranked alternatives."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "MSCU4920195",
            "weights": {"gross_weight_kg": 26200.0},
            "cargo": {"hazardous": False},
            "weight_source": "DOCUMENT_AI"
        }
    )
    resp = ContainerStabilityService.analyze_container_placement(req)
    assert resp.success is True
    assert resp.recommendation.bay in range(1, 5)
    assert resp.recommendation.side in ["PORT", "STARBOARD"]
    assert resp.recommendation.tier in [1, 2, 3]
    assert len(resp.alternatives) > 0


def test_point_08_recommendation_is_explainable():
    """Point 8: Placement recommendation includes explainable multi-objective reasons."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "MSCU4920195",
            "weights": {"gross_weight_kg": 26200.0},
            "cargo": {"hazardous": True},
            "weight_source": "DOCUMENT_AI"
        }
    )
    resp = ContainerStabilityService.analyze_container_placement(req)
    assert resp.success is True
    assert len(resp.reason) >= 3
    # Check for engineering explanation categories
    categories = [item.category for item in resp.structured_explanations]
    assert "STABILITY" in categories
    assert "PLACEMENT" in categories
    assert "HAZARDOUS_CARGO" in categories


def test_point_09_operator_confirmation_is_mandatory():
    """Point 9: Loading confirmation fails if operator_confirmed is False."""
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 26200.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=False,  # Unconfirmed
        operator_id="Operator"
    )
    resp = ContainerLoadingService.confirm_and_load(req)
    assert resp.success is False
    assert resp.status == "rejected"
    assert "operator confirmation" in resp.error_message.lower()


def test_point_10_vessel_state_changes_only_after_explicit_confirmation():
    """Point 10: Vessel state changes ONLY after explicit operator confirmation."""
    ship = state.get_current_ship()
    assert len(ship.containers) == 0

    # Step 1: Stability analysis does NOT mutate vessel state
    req = ContainerStabilityAnalysisRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 26200.0}}
    )
    ContainerStabilityService.analyze_container_placement(req)
    assert len(ship.containers) == 0

    # Step 2: Unconfirmed load does NOT mutate vessel state
    unconfirmed_req = ContainerLoadingConfirmRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 26200.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=False
    )
    ContainerLoadingService.confirm_and_load(unconfirmed_req)
    assert len(ship.containers) == 0

    # Step 3: Explicit confirmation mutates vessel state
    confirmed_req = ContainerLoadingConfirmRequest(
        container={"container_number": "MSCU4920195", "weights": {"gross_weight_kg": 26200.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerLoadingService.confirm_and_load(confirmed_req)
    assert resp.success is True
    assert len(ship.containers) == 1


def test_point_11_ballast_calculation_uses_committed_vessel_state():
    """Point 11: Ballast calculation computes required moment based on actual committed container weight."""
    ship = state.get_current_ship()
    # Add container directly to starboard Bay 2
    ship.add_container(Container(id="MSCU4920195", weight=26.2, bay=2, side="starboard", tier=1))

    req = BallastCompensationRequest(
        container_number="MSCU4920195",
        gross_weight_t=26.2,
        bay=2,
        side="STARBOARD",
        tier=1
    )
    resp = ContainerBallastService.calculate_compensation(req)
    assert resp.success is True
    assert resp.compensation_required is True
    assert resp.tank_key == "starboard_2"
    assert resp.required_qty_t == 26.2


def test_point_12_ballast_execution_requires_explicit_authorization():
    """Point 12: Ballast discharge execution is blocked if operator_confirmed is False."""
    req = BallastExecutionRequest(
        tank_key="starboard_2",
        direction="DRAIN",
        qty_t=26.2,
        operator_confirmed=False  # Blocked
    )
    resp = ContainerBallastService.execute_compensation(req)
    assert resp.success is False
    assert resp.status == "rejected"


def test_point_13_failed_ballast_execution_preserves_tank_state():
    """Point 13: Attempted invalid ballast operation (non-existent tank) does not corrupt vessel state."""
    ship = state.get_current_ship()
    total_ballast_before = ship.total_ballast_weight()

    req = BallastExecutionRequest(
        tank_key="invalid_tank_99",
        direction="DRAIN",
        qty_t=50.0,
        operator_confirmed=True
    )
    resp = ContainerBallastService.execute_compensation(req)
    assert resp.success is False
    assert ship.total_ballast_weight() == total_ballast_before


def test_point_14_final_stability_recalculated_after_ballast():
    """Point 14: Final 3-stage stability report recalculates list, trim, and score after ballast movement."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="C1", weight=25.0, bay=1, side="port", tier=1))

    req = BallastExecutionRequest(
        container_number="C1",
        tank_key="port_1",
        direction="DRAIN",
        qty_t=25.0,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerBallastService.execute_compensation(req)
    assert resp.success is True
    assert resp.three_stage_stability is not None
    ts = resp.three_stage_stability
    assert ts.before_load is not None
    assert ts.after_container is not None
    assert ts.after_ballast is not None
    # Ballasting restores score towards equilibrium
    assert ts.after_ballast.stability_score <= ts.after_container.stability_score


def test_point_15_sqlite_audit_records_generated():
    """Point 15: Loading and ballast operations are recorded in SQLite audit logs."""
    ship = state.get_current_ship()
    load_req = ContainerLoadingConfirmRequest(
        container={"container_number": "AUDIT_TEST_01", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="Auditor"
    )
    load_resp = ContainerLoadingService.confirm_and_load(load_req)
    assert load_resp.success is True
    assert load_resp.audit_id is not None

    cargo_logs = get_cargo_operations()
    assert any(log["container"] == "AUDIT_TEST_01" for log in cargo_logs)


def test_point_16_audit_records_contain_provenance():
    """Point 16: Operation audit events contain standardized provenance tags."""
    engine = ContainerWorkflowEngine.get_instance()
    img = Image.open(SAMPLE_SLIP_PATH)
    session = engine.initiate_workflow_from_image(img, source_name="sample_container_slip.jpg")
    
    events = get_operation_timeline(session.operation_id)
    assert len(events) > 0
    for e in events:
        assert e["source"] in ["DOCUMENT_AI", "CALCULATED", "OPERATOR"]


def test_point_17_load_cell_zero_involvement_across_all_steps():
    """Point 17: Varying load-cell sensor readings across all workflow stages produces zero effect."""
    for fake_sensor_kg in [0.0, 12345.0, 88888.0]:
        state.latest_telemetry["cargo_kg"] = fake_sensor_kg
        
        req = ContainerStabilityAnalysisRequest(
            container={
                "container_number": "INVAR_TEST",
                "weights": {"gross_weight_kg": 20000.0},
                "weight_source": "DOCUMENT_AI"
            }
        )
        resp = ContainerStabilityService.analyze_container_placement(req)
        assert resp.success is True
        assert resp.cargo_mass.value == 20000.0
        assert resp.cargo_mass.source == "DOCUMENT_AI"


def test_point_18_duplicate_container_idempotency():
    """Point 18: Loading the same container twice is blocked by slot occupancy and duplicate detection."""
    ship = state.get_current_ship()
    load_req = ContainerLoadingConfirmRequest(
        container={"container_number": "DUP_TEST_01", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="Operator"
    )
    # First load succeeds
    resp1 = ContainerLoadingService.confirm_and_load(load_req)
    assert resp1.success is True

    # Second load to same slot fails
    resp2 = ContainerLoadingService.confirm_and_load(load_req)
    assert resp2.success is False
    assert "already occupied" in resp2.error_message.lower() or "already stowed" in resp2.error_message.lower()
    assert len(ship.containers) == 1


def test_point_19_frontend_refresh_statelessness():
    """Point 19: Calling REST read endpoints repeatedly does not mutate backend vessel state."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="PERSIST_01", weight=20.0, bay=1, side="port", tier=1))

    # Simulate repeated frontend poll / page refresh calls
    for _ in range(5):
        r1 = client.get("/api/operations/status")
        assert r1.status_code == 200
        r2 = client.get("/api/deck-plan")
        assert r2.status_code == 200
        r3 = client.get("/api/operations/policy")
        assert r3.status_code == 200
        r4 = client.get("/api/reports/ops-log")
        assert r4.status_code == 200

    # Vessel state remains precisely 1 container
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "PERSIST_01"



def test_point_20_backend_restart_and_state_integrity():
    """Point 20: Resetting state cleans up in-flight workflows without corrupting vessel tanks."""
    state.reset_state()
    ship = state.get_current_ship()
    assert len(ship.containers) == 0
    assert len(ship.tanks) == 8
    # 4 Port tanks and 4 Starboard tanks exist with 300t capacity each
    for i in range(1, 5):
        assert f"port_{i}" in ship.tanks
        assert f"starboard_{i}" in ship.tanks
        assert ship.tanks[f"port_{i}"].capacity == 300.0
        assert ship.tanks[f"starboard_{i}"].capacity == 300.0
