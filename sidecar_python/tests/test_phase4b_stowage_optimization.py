"""
Phase 4B: Automated Multi-Objective Stowage Optimization Tests.
Verifies multi-criteria evaluation, hard constraint filtering, soft objective penalties,
top 3 (BEST + ALTERNATIVE) recommendations, explainable engineering reasons, and live-state immutability.
"""

import os
import sys
import copy
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Ship, Container, StabilityAnalyzer
import state
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    SlotCandidateEvaluation,
    RecommendedPosition
)
from container_stability.analyzer import ContainerStabilityService
from reports.logs_db import clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    state.get_current_ship().containers.clear()
    yield
    clear_logs()
    state.get_current_ship().containers.clear()


# --- TEST 1: MULTI-OBJECTIVE CANDIDATE RANKING ---
def test_1_candidate_ranking():
    """Verify that eligible candidates receive composite ranking scores and ranks (1, 2, 3...)."""
    req_payload = {
        "container": {
            "container_number": "MSCU1234567",
            "container_type": "40HC",
            "weights": {
                "gross_weight_kg": 22000.0
            },
            "cargo": {
                "hazardous": False
            }
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True}
    }

    res = client.post("/api/container/stability/analyze", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["recommendation"]["label"] == "BEST"
    assert data["recommendation"]["ranking_score"] is not None

    candidates = data["candidate_evaluations"]
    assert len(candidates) > 0

    eligible = [c for c in candidates if c["eligible"]]
    assert len(eligible) >= 4

    # Ranks should be sorted ascending by ranking_score
    scores = [c["ranking_score"] for c in eligible]
    assert scores == sorted(scores), "Eligible candidates must be sorted in ascending order of ranking_score"

    # Best candidate is rank 1
    assert eligible[0]["rank"] == 1
    assert eligible[0]["selected"] is True
    assert eligible[0]["label"] == "BEST"


# --- TEST 2: OCCUPIED SLOTS HARD CONSTRAINT REJECTION ---
def test_2_occupied_slots_rejection():
    """Verify that occupied slots advance to next tier, full columns are marked INELIGIBLE, and occupied slot loads are rejected."""
    ship = state.get_current_ship()
    # Pre-occupy Bay 2 Port Tier 1
    ship.containers.append(Container(id="OCCUPIED-B2P", weight=15.0, bay=2, side="port", tier=1))

    # Pre-occupy Bay 3 Starboard completely (Tiers 1, 2, 3)
    ship.containers.append(Container(id="FULL-B3S-T1", weight=10.0, bay=3, side="starboard", tier=1))
    ship.containers.append(Container(id="FULL-B3S-T2", weight=10.0, bay=3, side="starboard", tier=2))
    ship.containers.append(Container(id="FULL-B3S-T3", weight=10.0, bay=3, side="starboard", tier=3))

    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "TGHU8829104",
            "weights": {"gross_weight_kg": 18000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=ship)
    assert res.success is True

    # 1. Bay 2 Port advanced to Tier 2 and is eligible
    b2p = next((c for c in res.candidate_evaluations if c.bay == 2 and c.side == "PORT"), None)
    assert b2p is not None
    assert b2p.tier == 2
    assert b2p.eligible is True

    # 2. Bay 3 Starboard is completely full and is marked INELIGIBLE
    b3s = next((c for c in res.candidate_evaluations if c.bay == 3 and c.side == "STARBOARD"), None)
    assert b3s is not None
    assert b3s.eligible is False
    assert b3s.label == "INELIGIBLE"
    assert any("occupied" in r.lower() for r in b3s.reasons)


# --- TEST 3: HEAVY CONTAINER TIER & VCG PREFERENCE ---
def test_3_heavy_container_tier_preference():
    """Verify that heavy containers (>20t) receive VCG tier penalties on Tier 2 and Tier 3."""
    ship = state.get_current_ship()
    # Populate deck tier at Bay 2 to allow tier 2 stacking
    ship.containers.append(Container(id="BASE-B2P", weight=20.0, bay=2, side="port", tier=1))
    ship.containers.append(Container(id="BASE-B2S", weight=20.0, bay=2, side="starboard", tier=1))

    # Test placing heavy 28t container
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "HEAVY8899001",
            "weights": {"gross_weight_kg": 28000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=ship)
    assert res.success is True

    # Check Tier 2 evaluation at Bay 2 Port
    b2p_t2 = next((c for c in res.candidate_evaluations if c.bay == 2 and c.side == "PORT" and c.tier == 2), None)
    assert b2p_t2 is not None
    assert b2p_t2.eligible is True
    assert "tier_vcg" in b2p_t2.penalties
    assert b2p_t2.penalties["tier_vcg"] > 0
    assert b2p_t2.ranking_score > b2p_t2.score  # Penalized ranking score is higher than pure stability score


# --- TEST 4: HAZARDOUS CONTAINER DECK PLACEMENT ---
def test_4_hazardous_container_placement():
    """Verify hazardous container gets deck accessibility bonus and explainable safety reasons."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "HAZMAT12345",
            "weights": {"gross_weight_kg": 18000.0},
            "cargo": {
                "hazardous": True,
                "un_number": "UN 3480",
                "imdg_class": "Class 9"
            }
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True
    assert res.recommendation.tier == 1
    assert any("Hazardous cargo" in r for r in res.reason)

    best_eval = next((c for c in res.candidate_evaluations if c.selected), None)
    assert best_eval is not None
    assert "hazardous_deck_bonus" in best_eval.penalties
    assert best_eval.penalties["hazardous_deck_bonus"] < 0  # Bonus reduces composite penalty score


# --- TEST 5: TOP 3 RECOMMENDATIONS (BEST + ALTERNATIVES) ---
def test_5_multiple_valid_candidates_alternatives():
    """Verify that the engine returns Rank 1 (BEST) and top alternatives (Rank 2 and Rank 3)."""
    req_payload = {
        "container": {
            "container_number": "MSCU9988776",
            "weights": {"gross_weight_kg": 24000.0}
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True}
    }

    res = client.post("/api/container/stability/analyze", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Recommendation
    assert data["recommendation"]["label"] == "BEST"

    # Alternatives
    alts = data["alternatives"]
    assert alts is not None
    assert len(alts) == 2  # Top 2nd and 3rd alternatives
    assert alts[0]["rank"] == 2
    assert alts[0]["label"] == "ALTERNATIVE"
    assert alts[1]["rank"] == 3
    assert alts[1]["label"] == "ALTERNATIVE"
    assert alts[0]["ranking_score"] <= alts[1]["ranking_score"]


# --- TEST 6: NO VALID CANDIDATE HANDLING ---
def test_6_no_valid_candidate_when_full():
    """Verify system handles completely full vessel where all slots are occupied."""
    ship = state.get_current_ship()
    # Fill every tier 1, 2, 3 across all bays and sides
    for bay in range(1, 5):
        for side in ("port", "starboard"):
            for tier in range(1, 4):
                ship.containers.append(Container(id=f"FULL-B{bay}{side}T{tier}", weight=10.0, bay=bay, side=side, tier=tier))

    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "OVERFLOW001",
            "weights": {"gross_weight_kg": 15000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=ship)
    assert res.success is False
    assert res.status == "error"
    assert "No available cargo slots" in res.error_message


# --- TEST 7: RANKING CONSISTENCY & DETERMINISM ---
def test_7_ranking_consistency():
    """Verify repeated evaluations on identical state produce deterministic ranking scores and positions."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "DETERM12345",
            "weights": {"gross_weight_kg": 21500.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res1 = ContainerStabilityService.analyze_container_placement(req)
    res2 = ContainerStabilityService.analyze_container_placement(req)

    assert res1.recommendation.bay == res2.recommendation.bay
    assert res1.recommendation.side == res2.recommendation.side
    assert res1.recommendation.tier == res2.recommendation.tier
    assert res1.recommendation.ranking_score == res2.recommendation.ranking_score
    assert len(res1.candidate_evaluations) == len(res2.candidate_evaluations)


# --- TEST 8: LIVE STATE COPY-ON-WRITE IMMUTABILITY ---
def test_8_live_state_immutability():
    """Verify that simulating candidate slots leaves the live vessel state completely untouched."""
    ship = state.get_current_ship()
    initial_count = len(ship.containers)
    initial_list = StabilityAnalyzer.calculate_list(ship)
    initial_trim = StabilityAnalyzer.calculate_trim(ship)

    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "IMMUTABLE99",
            "weights": {"gross_weight_kg": 30000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True

    # Assert live ship was not mutated during simulation
    assert len(ship.containers) == initial_count
    assert StabilityAnalyzer.calculate_list(ship) == initial_list
    assert StabilityAnalyzer.calculate_trim(ship) == initial_trim


# --- TEST 9: PHASE 2 & 3 REGRESSION COMPATIBILITY ---
def test_9_phase2_and_3_regression_compatibility():
    """Verify that all Phase 2 response contracts (stability comparison, delta score, reasons) remain intact."""
    req_payload = {
        "container": {
            "container_number": "REGRESS001",
            "container_type": "40HC",
            "gross_weight_kg": 26200.0
        },
        "document": {"processing_status": "success"},
        "validation": {"valid": True}
    }

    res = client.post("/api/container/stability/analyze", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "recommendation" in data
    assert "stability" in data
    assert "before" in data["stability"]
    assert "after" in data["stability"]
    assert "delta_score" in data["stability"]
    assert len(data["reason"]) > 0
    assert len(data["candidate_evaluations"]) > 0
