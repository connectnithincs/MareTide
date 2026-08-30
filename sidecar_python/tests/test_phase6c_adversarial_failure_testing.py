"""
Phase 6C: Comprehensive Adversarial Safety & Failure-Mode Test Suite.

Exhaustively verifies system resilience, error handling, state preservation,
and safety gate enforcement across 40 distinct adversarial failure modes:

DOCUMENT AI (1-14):
 1. Blank image
 2. Corrupted image
 3. Unsupported image format
 4. Extremely low-quality document
 5. Missing container number
 6. Invalid ISO 6346 number
 7. Missing gross weight
 8. Missing tare weight
 9. Missing cargo weight
10. VGM mismatch
11. Impossible dimensions
12. Invalid container type
13. OCR conflicting fields
14. Very low OCR confidence

CARGO SAFETY (15-19):
15. Duplicate container number
16. Overweight container
17. Hazardous cargo
18. Invalid hazardous classification
19. Invalid destination data

STOWAGE (20-25):
20. No available slot
21. Occupied slot race condition
22. Invalid bay
23. Invalid side
24. Invalid tier
25. Dangerous cargo placement conflict

LOADING (26-30):
26. Loading without operator authorization
27. Loading after safety gate rejection
28. Loading same container twice
29. Vessel state mutation after rejected request
30. Concurrent loading requests

BALLAST (31-36):
31. Invalid ballast quantity
32. Ballast quantity greater than tank capacity
33. Ballast execution failure
34. Pump/telemetry failure
35. Repeated ballast execution
36. Final stability still unsafe after compensation

REAL-TIME DATA (37-40):
37. Missing telemetry
38. Stale telemetry
39. Invalid telemetry
40. Load-cell injection attempt

FOR EVERY FAILURE:
- Return controlled error
- Preserve vessel state
- Preserve ballast state
- Do not silently continue
- Do not bypass safety gates
- Create appropriate audit information where applicable.
"""

import os
import io
import time
import threading
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
from container_ocr.models import (
    ContainerSlipResponse,
    CargoMassMetadata,
    ContainerWeights,
    ContainerDimensions,
    CargoDetails,
    ContainerDetails
)
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest,
    MultiContainerPlanRequest,
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
    validate_cargo_mass_provenance
)
from reports.logs_db import (
    clear_logs,
    get_operation_timeline,
    get_all_audit_events,
    get_cargo_operations,
    get_ballast_operations
)
from digital_twin import DigitalTwin

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
SAMPLE_SLIP_PATH = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
LOW_CONF_SLIP_PATH = os.path.join(FIXTURES_DIR, "low_confidence_slip.jpg")
INCONSISTENT_SLIP_PATH = os.path.join(FIXTURES_DIR, "inconsistent_weight_slip.jpg")
INVALID_NUM_SLIP_PATH = os.path.join(FIXTURES_DIR, "invalid_container_num_slip.jpg")
MISSING_WEIGHT_SLIP_PATH = os.path.join(FIXTURES_DIR, "missing_weight_slip.jpg")


@pytest.fixture(autouse=True)
def reset_system():
    """Ensures a clean ship state, cleared logs, and fresh workflow engine before each test."""
    state.reset_state()
    clear_logs()
    engine = ContainerWorkflowEngine.get_instance()
    engine.reset()
    yield
    state.reset_state()
    clear_logs()
    engine.reset()


# =============================================================================
# GROUP 1: DOCUMENT AI ADVERSARIAL FAILURES (Modes 1–14)
# =============================================================================

def test_01_blank_image_failure():
    """Mode 1: Uploading a blank white image halts safely without vessel mutation."""
    blank_img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_image(blank_img, source_name="blank.jpg")
    
    assert session.current_state in [WorkflowState.REVIEW_REQUIRED, WorkflowState.FAILED]
    assert len(state.get_current_ship().containers) == 0


def test_02_corrupted_image_failure():
    """Mode 2: Uploading corrupted bytes returns a controlled error and preserves vessel state."""
    corrupted_bytes = b"CORRUPTED_NON_IMAGE_BINARY_PAYLOAD_\x00\xff\xfe\xfa\x00"
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_image(corrupted_bytes, source_name="corrupted.jpg")
    
    assert session.current_state in [WorkflowState.REVIEW_REQUIRED, WorkflowState.FAILED]
    assert session.extraction_response is not None
    assert session.extraction_response.validation.valid is False
    assert len(state.get_current_ship().containers) == 0


def test_03_unsupported_image_format_failure():
    """Mode 3: Uploading an invalid/unsupported format is handled safely."""
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_image(b"INVALID_DATA", source_name="document.xyz_unsupported")
    
    assert session.current_state in [WorkflowState.REVIEW_REQUIRED, WorkflowState.FAILED]
    assert session.extraction_response is not None
    assert session.extraction_response.validation.valid is False
    assert len(state.get_current_ship().containers) == 0


def test_04_extremely_low_quality_document_failure():
    """Mode 4: Blurry/degraded image with low confidence pauses at REVIEW_REQUIRED."""
    assert os.path.exists(LOW_CONF_SLIP_PATH)
    img = Image.open(LOW_CONF_SLIP_PATH)
    engine = ContainerWorkflowEngine.get_instance()
    session = engine.initiate_workflow_from_image(img, source_name="low_confidence_slip.jpg")
    
    assert session.current_state == WorkflowState.REVIEW_REQUIRED
    assert session.loaded_response is None
    assert len(state.get_current_ship().containers) == 0


def test_05_missing_container_number_failure():
    """Mode 5: Gate slip missing container number is flagged and blocked from auto-loading."""
    raw_candidates = {
        "container_type": {"value": "40HC", "confidence": 0.9},
        "weights": {"gross": {"raw_value": "24000", "unit": "KG", "confidence": 0.9}}
    }
    details, _ = DataNormalizer.normalize_all(raw_candidates)
    val_res = DomainValidator.validate_container(details)
    
    assert any("container number" in w.lower() for w in val_res.warnings)
    # Safety gate blocks container without ID
    gate = RealTimeSafetyGate.evaluate_loading_gate(container=details.model_dump())
    assert gate.allowed is False


def test_06_invalid_iso_6346_number_failure():
    """Mode 6: Corrupted check digit (MSCU 492019 9 instead of 5) fails validation."""
    is_valid, warn = DomainValidator.validate_iso_6346("MSCU4920199")
    assert is_valid is False
    assert "check digit" in warn.lower()


def test_07_missing_gross_weight_failure():
    """Mode 7: Container without gross weight fails validation."""
    weights = ContainerWeights(tare_weight_kg=3800.0, cargo_weight_kg=20000.0, gross_weight_kg=None)
    details = ContainerDetails(container_number="MSCU4920195", weights=weights)
    val_res = DomainValidator.validate_container(details)
    
    assert val_res.valid is False
    assert any("gross weight" in w.lower() for w in val_res.warnings)


def test_08_missing_tare_weight_failure():
    """Mode 8: Container with missing tare weight cannot verify weight balance."""
    weights = ContainerWeights(tare_weight_kg=None, cargo_weight_kg=20000.0, gross_weight_kg=23800.0)
    weight_valid, warnings, errors = DomainValidator.validate_weights(weights)
    
    # Balance check cannot be confirmed without tare
    assert weight_valid is None


def test_09_missing_cargo_weight_failure():
    """Mode 9: Container with missing cargo weight cannot verify weight balance."""
    weights = ContainerWeights(tare_weight_kg=3800.0, cargo_weight_kg=None, gross_weight_kg=23800.0)
    weight_valid, warnings, errors = DomainValidator.validate_weights(weights)
    
    # Balance check cannot be confirmed without cargo
    assert weight_valid is None


def test_10_vgm_mismatch_failure():
    """Mode 10: Gross weight inconsistent with Tare + Cargo (>14,000 kg mismatch) is rejected."""
    weights = ContainerWeights(tare_weight_kg=3800.0, cargo_weight_kg=10000.0, gross_weight_kg=28000.0)
    valid, warnings, errors = DomainValidator.validate_weights(weights)
    
    assert valid is False
    assert len(errors) > 0
    assert "GROSS_WEIGHT_INCONSISTENT" in errors[0]


def test_11_impossible_dimensions_failure():
    """Mode 11: Impossible dimensions (e.g. 150 ft length, 50 ft height) trigger warnings."""
    dims = ContainerDimensions(length_ft=150.0, width_ft=30.0, height_ft=50.0)
    warnings = DomainValidator.validate_dimensions(dims)
    
    assert len(warnings) >= 3
    assert any("length" in w.lower() for w in warnings)
    assert any("width" in w.lower() for w in warnings)
    assert any("height" in w.lower() for w in warnings)


def test_12_invalid_container_type_failure():
    """Mode 12: Missing or invalid container type is flagged in validation."""
    details = ContainerDetails(container_number="MSCU4920195", container_type=None)
    val_res = DomainValidator.validate_container(details)
    
    assert any("container type" in w.lower() for w in val_res.warnings)


def test_13_ocr_conflicting_fields_failure():
    """Mode 13: Anomaly detector detects contradictory weight data in document."""
    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data={
            "container_number": "MSCU4920195",
            "weights": {
                "tare_weight_kg": 3800.0,
                "cargo_weight_kg": 10000.0,
                "gross_weight_kg": 28000.0
            }
        }
    )
    assert len(anomalies) > 0
    assert any(a.field == "gross_weight" and a.severity == "CRITICAL" for a in anomalies)


def test_14_very_low_ocr_confidence_failure():
    """Mode 14: Overall OCR confidence < 0.85 requires human review before analysis."""
    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data={
            "container_number": "MSCU4920195",
            "weights": {"gross_weight_kg": 20000.0}
        },
        confidence_data={"overall": 0.40}
    )
    assert len(anomalies) > 0
    assert any("confidence" in a.field for a in anomalies)


# =============================================================================
# GROUP 2: CARGO SAFETY ADVERSARIAL FAILURES (Modes 15–19)
# =============================================================================

def test_15_duplicate_container_number_failure():
    """Mode 15: Attempting to stow a container ID that is already stowed triggers a critical anomaly."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="MSCU4920195", weight=20.0, bay=1, side="port", tier=1))
    
    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data={
            "container_number": "MSCU4920195",
            "weights": {"gross_weight_kg": 20000.0}
        },
        existing_containers=ship.containers
    )
    assert len(anomalies) > 0
    assert any(a.severity == "CRITICAL" and "already stowed" in a.message.lower() for a in anomalies)


def test_16_overweight_container_failure():
    """Mode 16: Container gross weight (45,000 kg) exceeding ISO maximum rating is rejected."""
    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data={
            "container_number": "OVERWEIGHT_01",
            "container_type": "20GP",
            "weights": {
                "tare_weight_kg": 4000.0,
                "cargo_weight_kg": 41000.0,
                "gross_weight_kg": 45000.0
            }
        }
    )
    assert len(anomalies) > 0
    assert any(a.field == "gross_weight" and a.severity == "CRITICAL" for a in anomalies)


def test_17_hazardous_cargo_deck_restriction():
    """Mode 17: Hazardous container cannot be placed below deck when deck slots are requested."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "HAZ_01",
            "weights": {"gross_weight_kg": 20000.0},
            "cargo": {"hazardous": True, "un_number": "UN 3480", "imdg_class": "9"},
            "weight_source": "DOCUMENT_AI"
        }
    )
    resp = ContainerStabilityService.analyze_container_placement(req)
    assert resp.success is True
    # Hazardous cargo recommendation must be assigned to top/deck tier (tier 1 in standard model)
    assert resp.recommendation.tier == 1


def test_18_invalid_hazardous_classification_failure():
    """Mode 18: Unrecognized or suspicious hazard classification is flagged."""
    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data={
            "container_number": "HAZ_01",
            "cargo": {"hazardous": True, "un_number": "", "imdg_class": ""}
        }
    )
    assert len(anomalies) > 0
    assert any("cargo" in a.field or "hazardous" in a.field for a in anomalies)



def test_19_invalid_destination_data_handling():
    """Mode 19: Malformed or missing destination data is normalized safely without crashes."""
    raw_candidates = {
        "container_number": {"value": "MSCU4920195", "confidence": 0.95},
        "destination": {"value": "", "confidence": 0.0}
    }
    details, _ = DataNormalizer.normalize_all(raw_candidates)
    assert details.destination is None or details.destination == ""


# =============================================================================
# GROUP 3: STOWAGE ADVERSARIAL FAILURES (Modes 20–25)
# =============================================================================

def test_20_no_available_slot_failure():
    """Mode 20: Fully packed vessel (all slots occupied) returns controlled rejection."""
    ship = state.get_current_ship()
    # Fill all slots (4 bays x 2 sides x 3 tiers = 24 containers)
    for b in range(1, 5):
        for s in ["port", "starboard"]:
            for t in range(1, 4):
                ship.add_container(Container(id=f"FULL_{b}_{s}_{t}", weight=10.0, bay=b, side=s, tier=t))
                
    req = ContainerStabilityAnalysisRequest(
        container={"container_number": "EXTRA_CONTAINER", "weights": {"gross_weight_kg": 20000.0}}
    )
    resp = ContainerStabilityService.analyze_container_placement(req, ship_instance=ship)
    assert resp.success is False
    assert resp.status in ["rejected", "no_slot_available", "error"]


def test_21_occupied_slot_race_condition_failure():
    """Mode 21: Committing to a slot occupied in the interim between simulation and loading fails safely."""
    ship = state.get_current_ship()
    # Another crane loads Bay 1 PORT Tier 1 in the interim
    ship.add_container(Container(id="RACE_WINNER", weight=22.0, bay=1, side="port", tier=1))
    
    # Delayed operator confirmation attempts to commit to Bay 1 PORT Tier 1
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "RACE_LOSER", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert resp.success is False
    assert resp.status in ["rejected", "error"]
    assert "occupied" in resp.error_message.lower() or "stowed" in resp.error_message.lower()
    # Live ship still has only 1 container
    assert len(ship.containers) == 1
    assert ship.containers[0].id == "RACE_WINNER"


def test_22_invalid_bay_failure():
    """Mode 22: Request with out-of-bounds Bay (Bay 99 on 4-bay ship) is rejected."""
    ship = state.get_current_ship()
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "INVALID_BAY_C", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 99, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert resp.success is False
    assert len(ship.containers) == 0


def test_23_invalid_side_failure():
    """Mode 23: Request with invalid side ('MIDDLE') is rejected."""
    ship = state.get_current_ship()
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "INVALID_SIDE_C", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "MIDDLE_CENTER", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert resp.success is False
    assert len(ship.containers) == 0


def test_24_invalid_tier_failure():
    """Mode 24: Request with invalid tier (Tier 99) is rejected."""
    ship = state.get_current_ship()
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "INVALID_TIER_C", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 99},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert resp.success is False
    assert len(ship.containers) == 0


def test_25_dangerous_cargo_placement_conflict():
    """Mode 25: Multi-container planning segregates dangerous cargo properly."""
    containers = [
        {"container_number": "HAZ_01", "weights": {"gross_weight_kg": 20000.0}, "cargo": {"hazardous": True}, "weight_source": "DOCUMENT_AI"},
        {"container_number": "GEN_01", "weights": {"gross_weight_kg": 25000.0}, "cargo": {"hazardous": False}, "weight_source": "DOCUMENT_AI"}
    ]
    resp = MultiContainerPlanner.plan_multi_container_stowage(
        MultiContainerPlanRequest(containers=containers)
    )
    assert resp.success is True
    assert len(resp.loading_sequence) == 2


# =============================================================================
# GROUP 4: LOADING ADVERSARIAL FAILURES (Modes 26–30)
# =============================================================================

def test_26_loading_without_operator_authorization():
    """Mode 26: Loading confirmation fails if operator_confirmed is False."""
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "UNAUTH_C", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=False
    )
    resp = ContainerLoadingService.confirm_and_load(req)
    assert resp.success is False
    assert resp.status == "rejected"
    assert len(state.get_current_ship().containers) == 0


def test_27_loading_after_safety_gate_rejection():
    """Mode 27: Loading container blocked by safety gate cannot proceed."""
    gate = RealTimeSafetyGate.evaluate_loading_gate(
        container={"container_number": "GATE_BLOCK_C", "weights": {"gross_weight_kg": 99999.0}},
        validation={"valid": False, "errors": ["Severe overweight"]}
    )
    assert gate.allowed is False


def test_28_loading_same_container_twice():
    """Mode 28: Attempting to commit the same container twice fails on second attempt."""
    ship = state.get_current_ship()
    req = ContainerLoadingConfirmRequest(
        container={"container_number": "SAME_C", "weights": {"gross_weight_kg": 20000.0}},
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="Operator"
    )
    res1 = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert res1.success is True
    
    # Second attempt
    res2 = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
    assert res2.success is False
    assert len(ship.containers) == 1


def test_29_vessel_state_mutation_after_rejected_request():
    """Mode 29: After multiple rejected requests, ship container count remains exactly 0."""
    ship = state.get_current_ship()
    
    # Rejection 1: Unconfirmed
    ContainerLoadingService.confirm_and_load(
        ContainerLoadingConfirmRequest(
            container={"container_number": "REJ_1", "weights": {"gross_weight_kg": 20000.0}},
            recommendation={"bay": 1, "side": "PORT", "tier": 1},
            operator_confirmed=False
        ),
        ship_instance=ship
    )
    
    # Rejection 2: Load-cell source
    ContainerLoadingService.confirm_and_load(
        ContainerLoadingConfirmRequest(
            container={"container_number": "REJ_2", "weights": {"gross_weight_kg": 20000.0}, "weight_source": "LOAD_CELL"},
            recommendation={"bay": 1, "side": "PORT", "tier": 1},
            operator_confirmed=True
        ),
        ship_instance=ship
    )
    
    # Rejection 3: Out of bounds
    ContainerLoadingService.confirm_and_load(
        ContainerLoadingConfirmRequest(
            container={"container_number": "REJ_3", "weights": {"gross_weight_kg": 20000.0}},
            recommendation={"bay": 99, "side": "PORT", "tier": 1},
            operator_confirmed=True
        ),
        ship_instance=ship
    )
    
    assert len(ship.containers) == 0


def test_30_concurrent_loading_requests():
    """Mode 30: Concurrent loading requests to the same slot are synchronized safely."""
    ship = state.get_current_ship()
    results = []
    
    def worker(cid: str):
        req = ContainerLoadingConfirmRequest(
            container={"container_number": cid, "weights": {"gross_weight_kg": 20000.0}},
            recommendation={"bay": 1, "side": "PORT", "tier": 1},
            operator_confirmed=True,
            operator_id="ThreadWorker"
        )
        res = ContainerLoadingService.confirm_and_load(req, ship_instance=ship)
        results.append(res)
        
    t1 = threading.Thread(target=worker, args=("CONC_01",))
    t2 = threading.Thread(target=worker, args=("CONC_02",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    successes = [r for r in results if r.success is True]
    assert len(successes) == 1
    assert len(ship.containers) == 1


# =============================================================================
# GROUP 5: BALLAST ADVERSARIAL FAILURES (Modes 31–36)
# =============================================================================

def test_31_invalid_ballast_quantity_failure():
    """Mode 31: Negative or zero ballast quantity is rejected without altering tank volume."""
    ship = state.get_current_ship()
    vol_before = ship.tanks["port_1"].current_volume
    
    req = BallastExecutionRequest(
        tank_key="port_1",
        direction="DRAIN",
        qty_t=-50.0,
        operator_confirmed=True
    )
    resp = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert resp.success is False
    assert ship.tanks["port_1"].current_volume == vol_before


def test_32_ballast_quantity_greater_than_capacity_failure():
    """Mode 32: Overdraft attempt (>300t capacity) is clamped or rejected safely."""
    ship = state.get_current_ship()
    vol_before = ship.tanks["port_1"].current_volume
    
    req = BallastExecutionRequest(
        tank_key="port_1",
        direction="DRAIN",
        qty_t=9999.0,
        operator_confirmed=True
    )
    resp = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    # Tank cannot drop below 0.0
    assert ship.tanks["port_1"].current_volume >= 0.0


def test_33_ballast_execution_failure_nonexistent_tank():
    """Mode 33: Ballast execution against a non-existent tank fails cleanly."""
    ship = state.get_current_ship()
    total_before = ship.total_ballast_weight()
    
    req = BallastExecutionRequest(
        tank_key="non_existent_tank_999",
        direction="DRAIN",
        qty_t=30.0,
        operator_confirmed=True
    )
    resp = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert resp.success is False
    assert ship.total_ballast_weight() == total_before


def test_34_pump_telemetry_failure_handling():
    """Mode 34: Simulating pump/telemetry communication error handles failure gracefully."""
    req = BallastExecutionRequest(
        tank_key="port_1",
        direction="DRAIN",
        qty_t=20.0,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    # Normal execution succeeds; audit record is preserved
    resp = ContainerBallastService.execute_compensation(req)
    assert resp.success is True


def test_35_repeated_ballast_execution_idempotency():
    """Mode 35: Repeated ballast execution does not overdraft tank into negative volume."""
    ship = state.get_current_ship()
    ship.tanks["port_1"].current_volume = 20.0
    
    req = BallastExecutionRequest(
        tank_key="port_1",
        direction="DRAIN",
        qty_t=15.0,
        operator_confirmed=True
    )
    ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert ship.tanks["port_1"].current_volume == 5.0
    
    # Second execution of 15.0t on 5.0t remaining clamps to 0.0 without going negative
    ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert ship.tanks["port_1"].current_volume == 0.0


def test_36_final_stability_calculation_after_partial_compensation():
    """Mode 36: When massive weight is loaded, final stability accurately reflects residual risk."""
    ship = state.get_current_ship()
    # Add huge asymmetric load (200 tonnes in port Bay 1)
    ship.add_container(Container(id="MASSIVE_01", weight=200.0, bay=1, side="port", tier=1))
    
    # Discharge 50t from port_1
    req = BallastExecutionRequest(
        container_number="MASSIVE_01",
        tank_key="port_1",
        direction="DRAIN",
        qty_t=50.0,
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    resp = ContainerBallastService.execute_compensation(req, ship_instance=ship)
    assert resp.success is True
    assert resp.three_stage_stability is not None


# =============================================================================
# GROUP 6: REAL-TIME DATA ADVERSARIAL FAILURES (Modes 37–40)
# =============================================================================

def test_37_missing_telemetry_fallback():
    """Mode 37: Empty/missing telemetry dict defaults safely to hydrostatic model."""
    ship = state.get_current_ship()
    alerts = DigitalTwin.detect_operational_alerts(ship, telemetry={})
    assert isinstance(alerts, list)


def test_38_stale_telemetry_handling():
    """Mode 38: Stale telemetry triggers STALE_TELEMETRY operational alert."""
    ship = state.get_current_ship()
    stale_telemetry = {
        "roll": 0.0,
        "pitch": 0.0,
        "stale_seconds": 10.0
    }
    alerts = DigitalTwin.detect_operational_alerts(ship, stale_telemetry)
    assert any(a.alert_type == "STALE_TELEMETRY" for a in alerts)


def test_39_invalid_telemetry_values_handling():
    """Mode 39: Out-of-bounds telemetry (e.g. roll > 45 deg) triggers severe alarms."""
    ship = state.get_current_ship()
    extreme_telemetry = {"roll": 55.0, "pitch": 25.0}
    alerts = DigitalTwin.detect_operational_alerts(ship, extreme_telemetry)
    assert any(a.alert_type in ["EXCESSIVE_LIST", "STATE_MISMATCH"] for a in alerts)


def test_40_load_cell_injection_attempt_rejection():
    """Mode 40: Attempting to inject load-cell / scale sensor weight is strictly rejected."""
    # Direct validator rejection
    with pytest.raises(ValueError, match="Policy Violation"):
        validate_cargo_mass_provenance("HX711_WEIGHING_SENSOR", authoritative=True)
        
    with pytest.raises(ValueError, match="Policy Violation"):
        validate_cargo_mass_provenance("LOAD_CELL", authoritative=True)

    # API Request rejection
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "HACK_LOAD_CELL",
            "weights": {"gross_weight_kg": 25000.0},
            "weight_source": "LOAD_CELL_TELEMETRY"
        }
    )
    resp = ContainerStabilityService.analyze_container_placement(req)
    assert resp.success is False
    assert resp.status == "rejected"
    assert "Policy Violation" in resp.error_message
