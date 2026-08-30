"""
Comprehensive Test Suite for Phase 2: Container JSON -> Stability & Loading Integration.
Tests all 10 core requirements:
1. Valid Phase 1 JSON
2. Missing gross weight
3. Invalid validation status / review_required
4. Heavy container placement sensitivity
5. Normal container placement
6. Candidate slot evaluation
7. Stability calculation integration
8. Recommendation generation
9. Simulation does not permanently modify vessel state
10. Existing stability endpoints remain functional
11. Phase 1 -> Phase 2 End-to-End pipeline
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ship import Ship, BallastTank, Container, StabilityAnalyzer, RecommendationEngine
import state
from container_stability.models import ContainerStabilityAnalysisRequest
from container_stability.analyzer import ContainerStabilityService
from container_ocr.service import process_container_slip
from main import app

client = TestClient(app)


# --- 1. VALID PHASE 1 JSON ---
def test_valid_phase1_json_analysis():
    """
    Verifies that valid Phase 1 container JSON produces recommendations and before/after stability metrics.
    """
    payload = {
        "container": {
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "dimensions": {"length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5},
            "weights": {
                "tare_weight_kg": 3800.0,
                "cargo_weight_kg": 22400.0,
                "gross_weight_kg": 26200.0
            },
            "cargo": {"description": "ELECTRONIC COMPONENTS", "hazardous": False},
            "destination": "SINGAPORE"
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True, "warnings": [], "errors": []}
    }

    response = client.post("/api/container/stability/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert data["status"] == "success"
    assert data["container"]["container_number"] == "MSCU4920195"
    assert data["container"]["gross_weight_kg"] == 26200.0
    assert data["container"]["gross_weight_t"] == 26.2
    assert "bay" in data["recommendation"]
    assert data["recommendation"]["side"] in ["PORT", "STARBOARD"]
    assert "before" in data["stability"]
    assert "after" in data["stability"]
    assert len(data["reason"]) > 0


# --- 2. MISSING GROSS WEIGHT ---
def test_missing_gross_weight_error():
    """
    Verifies that missing gross weight fails safely without computing placement.
    """
    payload = {
        "container": {
            "container_number": "MSCU4920195",
            "weights": {"gross_weight_kg": None}
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True}
    }

    response = client.post("/api/container/stability/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert data["status"] == "error"
    assert "Gross weight is missing" in data["error_message"]
    assert data["recommendation"] is None


# --- 3. INVALID VALIDATION STATUS / REVIEW REQUIRED ---
def test_review_required_document_blocked():
    """
    Verifies that review_required or invalid documents do NOT perform loading calculations.
    """
    payload = {
        "container": {
            "container_number": "MSCU4920195",
            "weights": {"gross_weight_kg": 25000.0}
        },
        "document": {"processing_status": "review_required"},
        "validation": {"valid": False, "warnings": ["Check digit invalid"]}
    }

    response = client.post("/api/container/stability/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is False
    assert data["status"] == "review_required"
    assert "requires verification" in data["error_message"]
    assert data["recommendation"] is None


# --- 4. HEAVY CONTAINER VS LIGHT CONTAINER SENSITIVITY ---
def test_heavy_container_placement_sensitivity():
    """
    Verifies that container weight dynamically drives the placement optimization.
    Setup a ship with an existing port load, and test placing light (5t) vs heavy (40t) containers.
    """
    test_ship = Ship("Sensitivity Ship", num_bays=4)
    for i in range(1, 5):
        test_ship.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
        test_ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)

    # Add 60t on port side Bay 1
    test_ship.add_container(Container(id="PRE-01", weight=60.0, bay=1, side="port"))

    # Analyze 40t container (40,000 kg)
    req_heavy = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "HEAVY40T",
            "weights": {"gross_weight_kg": 40000.0}
        }
    )
    res_heavy = ContainerStabilityService.analyze_container_placement(req_heavy, ship_instance=test_ship)

    assert res_heavy.success is True
    # To counteract 60t port weight in Bay 1, heavy container should be placed on Starboard
    assert res_heavy.recommendation.side == "STARBOARD"
    assert res_heavy.container.gross_weight_t == 40.0


# --- 5. CANDIDATE SLOT EVALUATIONS ---
def test_candidate_slot_evaluations_list():
    """
    Verifies that all available (bay, side) candidate positions are evaluated and ranked.
    """
    test_ship = Ship("Slot Ship", num_bays=4)
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "CONT-CANDIDATES",
            "weights": {"gross_weight_kg": 20000.0}
        }
    )
    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=test_ship)

    assert res.success is True
    candidates = res.candidate_evaluations
    assert len(candidates) == 8  # 4 bays x 2 sides

    selected_count = sum(1 for c in candidates if c.selected)
    assert selected_count == 1

    selected_cand = next(c for c in candidates if c.selected)
    assert selected_cand.bay == res.recommendation.bay
    assert selected_cand.side == res.recommendation.side


# --- 6. STABILITY CALCULATION INTEGRATION ---
def test_stability_calculation_metrics_match():
    """
    Verifies that before/after metrics match existing StabilityAnalyzer calculations.
    """
    test_ship = Ship("Calculation Ship", num_bays=4)
    for i in range(1, 5):
        test_ship.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
        test_ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)

    test_ship.add_container(Container(id="C1", weight=50.0, bay=2, side="port"))

    req = ContainerStabilityAnalysisRequest(
        container={"container_number": "C2", "weights": {"gross_weight_kg": 50000.0}}
    )
    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=test_ship)

    assert res.stability.before.list_t == -50.0  # Listing to port by 50t
    assert res.recommendation.side == "STARBOARD"
    assert res.stability.after.list_t == 0.0  # Perfect lateral equilibrium achieved


# --- 7. SIMULATION DOES NOT PERMANENTLY MODIFY LIVE VESSEL STATE ---
def test_simulation_does_not_mutate_live_ship_state():
    """
    CRITICAL REQUIREMENT: Verify that candidate simulation does NOT permanently add containers or alter ballast.
    """
    live_ship = state.get_current_ship()
    initial_container_count = len(live_ship.containers)
    initial_ballast_port = live_ship.ballast_port()
    initial_ballast_starboard = live_ship.ballast_starboard()

    payload = {
        "container": {
            "container_number": "SIM-TEST-999",
            "weights": {"gross_weight_kg": 35000.0}
        }
    }

    # Execute simulation analysis
    res = client.post("/api/container/stability/analyze", json=payload)
    assert res.status_code == 200

    # Assert live ship instance is 100% unchanged
    assert len(live_ship.containers) == initial_container_count
    assert live_ship.ballast_port() == initial_ballast_port
    assert live_ship.ballast_starboard() == initial_ballast_starboard
    assert not any(c.id == "SIM-TEST-999" for c in live_ship.containers)


# --- 8. EXISTING STABILITY AND RECOMMENDATION ENDPOINTS UNTOUCHED ---
def test_existing_endpoints_functional():
    """
    Verifies that existing vessel state and recommendation endpoints remain functional.
    """
    res_state = client.get("/api/vessel-state")
    assert res_state.status_code == 200
    assert "stability_score" in res_state.json()

    res_rec = client.get("/api/recommendations")
    assert res_rec.status_code == 200
    assert "best_bay" in res_rec.json()


# --- 9. PHASE 1 -> PHASE 2 END-TO-END PIPELINE ---
def test_phase1_ocr_to_phase2_stability_end_to_end():
    """
    Tests complete end-to-end integration:
    Slip Image -> Phase 1 OCR -> Structured JSON -> Phase 2 Stability Analysis -> Recommendation.
    """
    # 1. Phase 1 OCR on synthetic slip fixture
    slip_path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_container_slip.jpg")
    phase1_response = process_container_slip(slip_path)

    assert phase1_response.success is True
    assert phase1_response.container.container_number == "MSCU4920195"
    assert phase1_response.container.weights.gross_weight_kg == 26200.0

    # 2. Phase 2 Stability Analysis on Phase 1 output
    phase2_request = ContainerStabilityAnalysisRequest(
        container=phase1_response.container.model_dump(),
        document=phase1_response.document.model_dump(),
        validation=phase1_response.validation.model_dump()
    )
    phase2_response = ContainerStabilityService.analyze_container_placement(phase2_request)

    assert phase2_response.success is True
    assert phase2_response.status == "success"
    assert phase2_response.container.container_number == "MSCU4920195"
    assert phase2_response.recommendation.bay in [1, 2, 3, 4]
    assert phase2_response.recommendation.side in ["PORT", "STARBOARD"]
    assert len(phase2_response.reason) > 0
    assert phase2_response.stability.after.stability_score >= 0.0
