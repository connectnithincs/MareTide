"""
Phase 6A: Real-Time Integration Hardening & Zero-Load-Cell Enforcement Test Suite.
Verifies that load-cell / scale sensor telemetry has zero influence on cargo mass,
stowage optimization, hydrostatic stability, ballast calculation, and audit logging.
"""

import pytest
import copy
from fastapi.testclient import TestClient

from main import app
from ship import Ship, Container, BallastTank, StabilityAnalyzer, RecommendationEngine
import state
from container_ocr.models import CargoMassMetadata, ContainerWeights, ContainerDetails
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    MultiContainerPlanRequest,
    SafetyGateStatus
)
from container_stability.policy import (
    DOCUMENT_AI_CARGO_MASS,
    LOAD_CELL_CARGO_MASS,
    HARDWARE_TELEMETRY_LABEL,
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    ALLOWED_WEIGHT_SOURCES,
    FORBIDDEN_WEIGHT_SOURCES,
    assert_authoritative_source,
    validate_cargo_mass_provenance
)
from container_stability.analyzer import (
    ContainerStabilityService,
    ContainerLoadingService,
    ContainerBallastService,
    MultiContainerPlanner
)
from container_stability.safety_gate import RealTimeSafetyGate
from reports.logs_db import _sanitize_metrics, log_operation_audit_event, get_operation_timeline


client = TestClient(app)


def _create_test_ship(name: str = "Test Ship") -> Ship:
    s = Ship(name=name, num_bays=4)
    for i in range(1, 5):
        s.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
        s.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)
    return s


# -----------------------------------------------------------------------------
# 1. Centralized Provenance Rule & Constants Validation
# -----------------------------------------------------------------------------

def test_phase6a_centralized_policy_constants():
    """Verify that centralized provenance constants strictly enforce Document AI and bar Load Cells."""
    assert DOCUMENT_AI_CARGO_MASS == "authoritative"
    assert LOAD_CELL_CARGO_MASS == "forbidden"
    assert HARDWARE_TELEMETRY_LABEL == "[HARDWARE TELEMETRY — NON-AUTHORITATIVE]"
    assert CONTAINER_WEIGHT_SOURCE == "DOCUMENT_AI"
    assert PROVENANCE_LABEL == "[DOCUMENT AI]"
    
    # Verify forbidden sources contains all relevant keywords
    for kw in ["LOAD_CELL", "LOADCELL", "SCALE", "HX711", "WEIGHING_SENSOR", "SENSOR_DERIVED_WEIGHT"]:
        assert any(kw in src for src in FORBIDDEN_WEIGHT_SOURCES)


def test_cargo_mass_metadata_structure():
    """Verify CargoMassMetadata Pydantic model contract and defaults."""
    meta = CargoMassMetadata(value=24500.0)
    assert meta.value == 24500.0
    assert meta.unit == "kg"
    assert meta.source == "DOCUMENT_AI"
    assert meta.authoritative is True
    
    # Serialized dump
    d = meta.model_dump()
    assert d["source"] == "DOCUMENT_AI"
    assert d["authoritative"] is True


def test_validate_cargo_mass_provenance_helper():
    """Verify the centralized provenance validator accepts Document AI and rejects load cells."""
    # Valid sources
    validate_cargo_mass_provenance("DOCUMENT_AI", authoritative=True)
    validate_cargo_mass_provenance("VALIDATED_OCR_DOCUMENT_JSON", authoritative=True)
    validate_cargo_mass_provenance("[DOCUMENT AI]", authoritative=True)

    
    # Non-authoritative flag must raise
    with pytest.raises(ValueError, match="Non-authoritative"):
        validate_cargo_mass_provenance("DOCUMENT_AI", authoritative=False)
        
    # Forbidden sources must raise
    for forbidden in ["LOAD_CELL", "LOADCELL", "ACTIVE_SCALE", "HX711_SENSOR", "SENSOR_DERIVED_WEIGHT"]:
        with pytest.raises(ValueError, match="Policy Violation"):
            validate_cargo_mass_provenance(forbidden, authoritative=True)


# -----------------------------------------------------------------------------
# 2. Invariance Proof: Varying Load-Cell Telemetry Has Zero Effect on Physics
# -----------------------------------------------------------------------------

def test_load_cell_zero_effect_on_stability_and_stowage_recommendation():
    """
    Changing load-cell sensor telemetry (from 0 kg to 5,000 kg to 25,000 kg)
    must have ZERO effect on:
    1. Recommended Bay
    2. Recommended Side
    3. Recommended Tier
    4. Initial List
    5. Initial Trim
    6. Projected Stability Score
    7. Post-load List and Trim
    """
    doc_ai_container = {
        "container_number": "MSCU7829104",
        "container_type": "40HC",
        "weights": {
            "gross_weight_kg": 24500.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 20700.0
        },
        "cargo": {"hazardous": False},
        "weight_source": "DOCUMENT_AI",
        "authoritative": True
    }
    
    analysis_results = []
    
    # Test across multiple simulated load-cell values
    for simulated_load_cell_kg in [0.0, 5000.0, 15000.0, 30000.0, 99999.0]:
        # Inject load cell reading into telemetry state
        state.latest_telemetry["cargo_kg"] = simulated_load_cell_kg
        
        req = ContainerStabilityAnalysisRequest(
            container=doc_ai_container,
            document={"processing_status": "success", "confidence": {"overall": 0.98, "weights": 0.95}},
            validation={"valid": True, "errors": []}
        )
        
        # Isolated test ship
        test_ship = _create_test_ship("MareTide Zero-LoadCell Test")
        resp = ContainerStabilityService.analyze_container_placement(req, ship_instance=test_ship)
        
        assert resp.success is True
        analysis_results.append(resp)
        
    # Baseline is first run
    baseline = analysis_results[0]
    for idx, run in enumerate(analysis_results[1:], start=1):
        assert run.recommendation.bay == baseline.recommendation.bay, f"Bay differed at run {idx}"
        assert run.recommendation.side == baseline.recommendation.side, f"Side differed at run {idx}"
        assert run.recommendation.tier == baseline.recommendation.tier, f"Tier differed at run {idx}"
        assert run.stability.before.list_t == baseline.stability.before.list_t, f"Before list differed at run {idx}"
        assert run.stability.before.trim_t == baseline.stability.before.trim_t, f"Before trim differed at run {idx}"
        assert run.stability.after.list_t == baseline.stability.after.list_t, f"After list differed at run {idx}"
        assert run.stability.after.trim_t == baseline.stability.after.trim_t, f"After trim differed at run {idx}"
        assert run.stability.after.stability_score == baseline.stability.after.stability_score, f"Score differed at run {idx}"
        assert run.cargo_mass.value == 24500.0
        assert run.cargo_mass.source == "DOCUMENT_AI"
        assert run.cargo_mass.authoritative is True


def test_load_cell_zero_effect_on_ballast_compensation_requirement():
    """
    Varying load-cell sensor readings must have ZERO effect on ballast calculation requirements.
    """
    ballast_results = []
    
    for simulated_load_cell_kg in [0.0, 2500.0, 10000.0, 50000.0]:
        state.latest_telemetry["cargo_kg"] = simulated_load_cell_kg
        
        # Test ship with 24.5t loaded container stowed in starboard Bay 2
        test_ship = _create_test_ship("Ballast Test Ship")
        test_ship.add_container(Container(id="C1", weight=24.5, bay=2, side="starboard", tier=1))
        
        req = BallastCompensationRequest(
            container_number="C1",
            gross_weight_t=24.5,
            bay=2,
            side="STARBOARD",
            tier=1
        )
        
        resp = ContainerBallastService.calculate_compensation(req, ship_instance=test_ship)
        assert resp.success is True
        ballast_results.append(resp)
        
    baseline = ballast_results[0]
    for idx, run in enumerate(ballast_results[1:], start=1):
        assert run.compensation_required == baseline.compensation_required
        assert run.affected_tank == baseline.affected_tank
        assert run.required_qty_t == baseline.required_qty_t
        assert run.projected_stability.stability_score == baseline.projected_stability.stability_score


def test_load_cell_zero_effect_on_multi_container_manifest_optimization():
    """
    Varying load-cell readings must have ZERO effect on MultiContainerPlanner sequence optimization.
    """
    manifest_containers = [
        {
            "container_number": "MEDU1001",
            "weights": {"gross_weight_kg": 28000.0},
            "cargo": {"hazardous": False},
            "weight_source": "DOCUMENT_AI"
        },
        {
            "container_number": "MEDU1002",
            "weights": {"gross_weight_kg": 14000.0},
            "cargo": {"hazardous": True},
            "weight_source": "DOCUMENT_AI"
        },
        {
            "container_number": "MEDU1003",
            "weights": {"gross_weight_kg": 22000.0},
            "cargo": {"hazardous": False},
            "weight_source": "DOCUMENT_AI"
        }
    ]
    
    plans = []
    for simulated_load_cell_kg in [0.0, 8000.0, 35000.0]:
        state.latest_telemetry["cargo_kg"] = simulated_load_cell_kg
        
        plan_req = MultiContainerPlanRequest(containers=manifest_containers)
        test_ship = _create_test_ship("Multi Manifest Test")
        plan_resp = MultiContainerPlanner.plan_multi_container_stowage(plan_req, ship_instance=test_ship)
        
        assert plan_resp.success is True
        plans.append(plan_resp)
        
    baseline_plan = plans[0]
    for plan in plans[1:]:
        assert len(plan.loading_sequence) == len(baseline_plan.loading_sequence)
        for s1, s2 in zip(baseline_plan.loading_sequence, plan.loading_sequence):
            assert s1.container.container_number == s2.container.container_number
            assert s1.recommended_position.bay == s2.recommended_position.bay
            assert s1.recommended_position.side == s2.recommended_position.side
            assert s1.recommended_position.tier == s2.recommended_position.tier
            assert s1.cargo_mass.value == s2.cargo_mass.value
            assert s1.cargo_mass.source == "DOCUMENT_AI"


# -----------------------------------------------------------------------------
# 3. Security & Regression: Forbidden Weight Injection Rejection Tests
# -----------------------------------------------------------------------------

def test_security_rejection_of_load_cell_in_stability_analysis():
    """Attempting to inject sensor/load-cell weight into stability analysis must be rejected."""
    forbidden_payloads = [
        {"container_number": "INJ01", "weights": {"gross_weight_kg": 20000.0}, "weight_source": "LOAD_CELL"},
        {"container_number": "INJ02", "weights": {"gross_weight_kg": 20000.0}, "weight_source": "HX711_WEIGHING_SENSOR"},
        {"container_number": "INJ03", "weights": {"gross_weight_kg": 20000.0}, "weight_source": "ACTIVE_SCALE"},
        {"container_number": "INJ04", "weights": {"gross_weight_kg": 20000.0}, "authoritative": False}
    ]
    
    test_ship = _create_test_ship("Security Test")
    for c_data in forbidden_payloads:
        req = ContainerStabilityAnalysisRequest(container=c_data)
        resp = ContainerStabilityService.analyze_container_placement(req, ship_instance=test_ship)
        assert resp.success is False
        assert resp.status == "rejected"
        assert "Policy Violation" in resp.error_message or "Non-authoritative" in resp.error_message


def test_security_rejection_of_load_cell_in_loading_confirmation():
    """Attempting to commit a container with sensor/load-cell provenance must be rejected."""
    forbidden_req = ContainerLoadingConfirmRequest(
        container={
            "container_number": "INJ_LOAD",
            "weights": {"gross_weight_kg": 18000.0},
            "weight_source": "LOAD_CELL_SENSOR"
        },
        recommendation={"bay": 1, "side": "PORT", "tier": 1},
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )
    
    test_ship = _create_test_ship("Commit Security Test")
    resp = ContainerLoadingService.confirm_and_load(forbidden_req, ship_instance=test_ship)
    assert resp.success is False
    assert resp.status == "rejected"
    assert "Policy Violation" in resp.error_message
    # Live vessel state must NOT be modified
    assert len(test_ship.containers) == 0



def test_security_rejection_of_load_cell_in_safety_gate():
    """RealTimeSafetyGate Rule 8 must strictly block any payload with forbidden sensor keywords."""
    gate_result = RealTimeSafetyGate.evaluate_loading_gate(
        container={
            "container_number": "GATE_TEST",
            "weights": {"gross_weight_kg": 22000.0},
            "weight_source": "HARDWARE_LOAD_CELL"
        },
        operator_confirmed=True,
        operator_id="ChiefOfficer"
    )

    assert gate_result.allowed is False
    assert gate_result.status == SafetyGateStatus.BLOCKED.value
    assert any("Security Policy Violation" in r.message for r in gate_result.reasons)


def test_security_rejection_of_load_cell_in_multi_container_manifest():
    """Any manifest container claiming load-cell weight must be isolated into rejected_containers."""
    manifest_req = MultiContainerPlanRequest(
        containers=[
            {
                "container_number": "VALID_01",
                "weights": {"gross_weight_kg": 20000.0},
                "weight_source": "DOCUMENT_AI"
            },
            {
                "container_number": "FORBIDDEN_02",
                "weights": {"gross_weight_kg": 15000.0},
                "weight_source": "LOAD_CELL_TELEMETRY"
            }
        ]
    )
    test_ship = Ship(name="Manifest Security", num_bays=4)
    resp = MultiContainerPlanner.plan_multi_container_stowage(manifest_req, ship_instance=test_ship)
    
    assert resp.success is True
    assert resp.valid_count == 1
    assert resp.rejected_count == 1
    assert resp.rejected_containers[0].container_number == "FORBIDDEN_02"
    assert "Security Policy Violation" in resp.rejected_containers[0].reason


# -----------------------------------------------------------------------------
# 4. Database Audit Sanitization & REST Endpoints
# -----------------------------------------------------------------------------

def test_database_audit_metric_sanitization():
    """_sanitize_metrics must strip all load-cell and scale keys before database persistence."""
    dirty_metrics = {
        "gross_weight_kg": 24500.0,
        "gross_weight_t": 24.5,
        "cargo_kg": 24500.0,
        "scale_kg": 24500.0,
        "hx711": 1024.5,
        "load_cell": 24500.0,
        "sensor_derived_weight": 24500.0,
        "target_slot": "Bay 1 PORT Tier 1"
    }
    
    clean = _sanitize_metrics(dirty_metrics)
    assert "gross_weight_kg" in clean
    assert "gross_weight_t" in clean
    assert "target_slot" in clean
    
    for forbidden_key in ["cargo_kg", "scale_kg", "hx711", "load_cell", "sensor_derived_weight"]:
        assert forbidden_key not in clean


def test_api_operations_policy_endpoint():
    """REST endpoint /api/operations/policy must return Phase 6A policy constants."""
    response = client.get("/api/operations/policy")
    assert response.status_code == 200
    data = response.json()
    assert data["document_ai_cargo_mass"] == "authoritative"
    assert data["load_cell_cargo_mass"] == "forbidden"
    assert data["hardware_telemetry_label"] == "[HARDWARE TELEMETRY — NON-AUTHORITATIVE]"
    assert "LOAD_CELL" in data["forbidden_sources"]


def test_api_ballast_calculate_compensation_decoupled_from_telemetry():
    """REST endpoint /api/ballast/calculate-compensation must use request body weight and reject sensor overrides."""
    # Ensure telemetry is non-zero to prove it is ignored
    state.latest_telemetry["cargo_kg"] = 999.0
    
    # 1. Valid Document AI request
    valid_resp = client.post("/api/ballast/calculate-compensation", json={
        "id": "API_TEST_C1",
        "bay": 2,
        "side": "port",
        "tier": 1,
        "gross_weight_t": 20.0,
        "weight_source": "DOCUMENT_AI"
    })
    assert valid_resp.status_code == 200
    assert state.planned_container["weight"] == 20.0  # From Document AI, not 999.0 * 10
    
    # 2. Forbidden sensor source rejected
    invalid_resp = client.post("/api/ballast/calculate-compensation", json={
        "id": "API_TEST_FORBIDDEN",
        "bay": 2,
        "side": "port",
        "tier": 1,
        "gross_weight_t": 20.0,
        "weight_source": "LOAD_CELL_SENSOR"
    })
    assert invalid_resp.status_code == 400
    assert "Security Policy Violation" in invalid_resp.json()["detail"]


def test_api_recommendations_decoupled_from_telemetry():
    """REST endpoint /api/recommendations must use planned container weight, not load-cell telemetry."""
    state.planned_container = {"weight": 18.0}
    state.latest_telemetry["cargo_kg"] = 9999.0
    
    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert "best_bay" in data
    assert "best_side" in data
    assert "explainable_recs" in data
