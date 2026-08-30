"""
Phase 4C: Explainable Cargo Stowage Decision Engine Tests.
Verifies categorical structured explanations, zero-fabrication metric alignment,
data provenance attribution (OCR vs. Calculated vs. Operator-provided), and non-autonomous safety disclaimers.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Container, StabilityAnalyzer
import state
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ExplanationItem,
    DataProvenanceReport
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


# --- TEST 1: EXPLANATIONS CORRESPOND TO ACTUAL METRICS ---
def test_1_explanations_correspond_to_actual_metrics():
    """Verify that structured explanations exactly match computed stability metrics without drift."""
    req_payload = {
        "container": {
            "container_number": "MSCU7766554",
            "container_type": "40HC",
            "weights": {"gross_weight_kg": 24000.0},
            "cargo": {"hazardous": False}
        },
        "document": {"source": "test_manifest.jpg", "processing_status": "success"},
        "validation": {"valid": True, "iso_6346_valid": True, "weight_balance_valid": True}
    }

    res = client.post("/api/container/stability/analyze", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    exps = data.get("structured_explanations")
    assert exps is not None
    assert len(exps) >= 6

    # Find STABILITY explanation
    stab_exp = next((e for e in exps if e["category"] == "STABILITY"), None)
    assert stab_exp is not None
    ev = stab_exp["evidence"]

    # Verify exact numeric match with stability comparison
    assert ev["before_score"] == data["stability"]["before"]["stability_score"]
    assert ev["after_score"] == data["stability"]["after"]["stability_score"]
    assert ev["delta_score"] == data["stability"]["delta_score"]
    assert ev["before_list_t"] == data["stability"]["before"]["list_t"]
    assert ev["after_list_t"] == data["stability"]["after"]["list_t"]
    assert ev["risk_level"] == data["stability"]["after"]["risk_level"]


# --- TEST 2: ZERO VALUE FABRICATION ---
def test_2_zero_value_fabrication():
    """Verify that placement and ranking explanation evidence matches calculated candidate scores."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "TRHU9988112",
            "weights": {"gross_weight_kg": 26000.0},
            "cargo": {"hazardous": False}
        },
        document={"source": "slip_001.jpg", "processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True

    # Find PLACEMENT explanation
    place_exp = next((e for e in res.structured_explanations if e.category == "PLACEMENT"), None)
    assert place_exp is not None
    ev = place_exp.evidence

    assert ev["selected_bay"] == res.recommendation.bay
    assert ev["selected_side"] == res.recommendation.side
    assert ev["selected_tier"] == res.recommendation.tier
    assert ev["ranking_score"] == res.recommendation.ranking_score
    assert ev["stability_score"] == res.candidate_evaluations[0].score


# --- TEST 3: REJECTED CANDIDATE EXPLANATIONS ---
def test_3_rejected_candidate_explanations():
    """Verify that candidate evaluations contain explicit engineering reasons for lower ranks or ineligibility."""
    ship = state.get_current_ship()
    # Occupy Bay 1 Port, Bay 1 Starboard
    ship.containers.append(Container(id="OCC1", weight=20.0, bay=1, side="port", tier=1))

    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "MEDU3344556",
            "weights": {"gross_weight_kg": 28000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req, ship_instance=ship)
    assert res.success is True

    # Verify all candidates have explainable reasons
    for cand in res.candidate_evaluations:
        assert len(cand.reasons) > 0, f"Candidate {cand.bay}/{cand.side} must have explainable reasons"


# --- TEST 4: OCR PROVENANCE ATTRIBUTION ---
def test_4_ocr_provenance_attribution():
    """Verify that OCR-derived data is correctly categorized and attributed."""
    req_payload = {
        "container": {
            "container_number": "HLXU4455667",
            "container_type": "40GP",
            "weights": {"gross_weight_kg": 21500.0},
            "dimensions": {"length_ft": 40.0, "height_ft": 8.5},
            "cargo": {"hazardous": False},
            "destination": "ROTTERDAM",
            "seal_number": "SL-998822",
            "carrier": "HAPAG-LLOYD"
        },
        "document": {"source": "manifest_hl.jpg", "processing_status": "success"},
        "validation": {"valid": True}
    }

    res = client.post("/api/container/stability/analyze", json=req_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    prov = data.get("provenance")
    assert prov is not None
    ocr = prov["ocr_derived"]

    assert ocr["container_number"] == "HLXU4455667"
    assert ocr["container_type"] == "40GP"
    assert ocr["gross_weight_kg"] == 21500.0
    assert ocr["gross_weight_t"] == 21.5
    assert ocr["destination"] == "ROTTERDAM"
    assert ocr["seal_number"] == "SL-998822"
    assert ocr["carrier"] == "HAPAG-LLOYD"


# --- TEST 5: CALCULATED VALUE PROVENANCE ATTRIBUTION ---
def test_5_calculated_value_provenance_attribution():
    """Verify that stability and ranking metrics are strictly attributed to calculated provenance."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "CMAU8899001",
            "weights": {"gross_weight_kg": 25000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True

    prov = res.provenance
    assert prov is not None
    calc = prov.calculated

    assert "stability_score_before" in calc
    assert "stability_score_after" in calc
    assert "list_after_t" in calc
    assert "trim_after_t" in calc
    assert "multi_objective_ranking_score" in calc
    assert "recommended_bay" in calc
    assert "recommended_side" in calc
    assert "recommended_tier" in calc
    assert "candidate_rank" in calc
    assert calc["candidate_rank"] == 1


# --- TEST 6: OPERATOR ACTIONS ATTRIBUTION ---
def test_6_operator_actions_attribution():
    """Verify that human operator gates (authorization, override) are attributed to operator_provided provenance."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "OOCU1122334",
            "weights": {"gross_weight_kg": 19000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True

    prov = res.provenance
    assert prov is not None
    op = prov.operator_provided

    assert "stowage_confirmation" in op
    assert "position_override" in op
    assert "ballast_execution" in op


# --- TEST 7: COMPLETE CATEGORICAL COVERAGE ---
def test_7_complete_categorical_coverage():
    """Verify that hazardous container generates explanations covering all 7 categories."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "HAZMAT77889",
            "weights": {"gross_weight_kg": 18500.0},
            "cargo": {
                "hazardous": True,
                "un_number": "UN 1203",
                "imdg_class": "Class 3"
            }
        },
        document={"source": "dg_slip.jpg", "processing_status": "success"},
        validation={"valid": True, "iso_6346_valid": True, "weight_balance_valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True

    categories = {e.category for e in res.structured_explanations}
    expected_categories = {
        "DOCUMENT",
        "VALIDATION",
        "STABILITY",
        "PLACEMENT",
        "HAZARDOUS_CARGO",
        "BALLAST",
        "SAFETY"
    }
    assert expected_categories.issubset(categories), f"Missing categories: {expected_categories - categories}"


# --- TEST 8: SAFETY DISCLAIMER AND NON-AUTONOMOUS NOTICE ---
def test_8_safety_disclaimer_notice():
    """Verify that response explicitly communicates advisory decision-support and operator authority."""
    req = ContainerStabilityAnalysisRequest(
        container={
            "container_number": "SAFE001",
            "weights": {"gross_weight_kg": 15000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True}
    )

    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is True

    # Disclaimer field
    assert "AI-assisted decision support" in res.disclaimer
    assert "Final operational authority remains with the qualified operator" in res.disclaimer

    # SAFETY category explanation
    safety_exp = next((e for e in res.structured_explanations if e.category == "SAFETY"), None)
    assert safety_exp is not None
    assert "Final operational authority remains with the qualified operator" in safety_exp.message
