"""
Unit & Integration Tests for Phase 4A: Document AI Intelligence Hardening.
Tests all 12 scenarios: clear, blurred, rotated, missing weights/dimensions, invalid check digits,
VGM balance discrepancies, hazardous defaults, partial documents, low-confidence gates,
and full backward compatibility with Phase 2 (Stability Analysis) and Phase 3 (Loading & Ballast).
"""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
from container_ocr.service import process_container_slip, default_service
from container_ocr.models import (
    ContainerSlipResponse, DocumentQuality, ConfidenceScores,
    ContainerDetails, ValidationResult
)
from container_stability.models import (
    ContainerStabilityAnalysisRequest, ContainerLoadingConfirmRequest,
    BallastCompensationRequest
)
from reports.logs_db import clear_logs
import state

client = TestClient(app)
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    state.get_current_ship().containers.clear()
    yield
    clear_logs()
    state.get_current_ship().containers.clear()


# --- TEST 1: CLEAR DOCUMENT ---
def test_1_clear_document_full_intelligence():
    img_path = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
    res = process_container_slip(img_path)

    assert res.success is True
    assert res.document.processing_status == "success"
    # Document quality check
    assert res.document_quality.quality == "good"
    assert len(res.document_quality.issues) == 0
    assert res.document_quality.blur_score is not None and res.document_quality.blur_score > 35.0
    # Core fields
    assert res.container.container_number == "MSCU4920195"
    assert res.container.container_type == "40HC"
    assert res.container.iso_type == "45G1"
    assert res.container.weights.gross_weight_kg == 26200.0
    assert res.container.weights.tare_weight_kg == 3800.0
    assert res.container.weights.cargo_weight_kg == 22400.0
    assert res.container.weights.vgm_verified is True
    assert res.container.cargo.hazardous is True
    assert res.container.cargo.un_number == "UN 3480"
    assert res.container.cargo.imdg_class == "Class 9"
    assert res.container.destination.upper() == "SINGAPORE"
    assert res.container.seal_number == "ML-SG-987214"
    assert res.container.carrier == "Mediterranean Shipping Company"
    # Granular confidence
    assert res.confidence.overall >= 0.85
    assert res.confidence.container_number >= 0.90
    assert res.confidence.weights >= 0.90
    assert res.confidence.hazardous >= 0.90
    assert res.validation.valid is True


# --- TEST 2: BLURRED DOCUMENT (QUALITY ASSESSMENT & REVIEW GATE) ---
def test_2_blurred_document_detected():
    img_path = os.path.join(FIXTURES_DIR, "blurred_container_slip.jpg")
    res = process_container_slip(img_path)

    # Document quality must detect blur
    assert res.document_quality.blur_score is not None
    assert "blurred_image" in res.document_quality.issues or res.document_quality.quality in ["poor", "unusable", "fair"]
    # If blur is severe, processing status must trigger review_required
    assert res.document.processing_status == "review_required" or res.confidence.overall < 0.85


# --- TEST 3: ROTATED DOCUMENT (EXTREME SKEW DETECTION) ---
def test_3_rotated_document_detected():
    img_path = os.path.join(FIXTURES_DIR, "rotated_container_slip.jpg")
    res = process_container_slip(img_path)

    # Extreme rotation should be flagged or trigger review_required
    assert "extreme_rotation" in res.document_quality.issues or res.document.processing_status == "review_required" or res.confidence.overall < 0.85


# --- TEST 4: MISSING WEIGHT (NULL PRESERVATION & VALIDATION FAILURE) ---
def test_4_missing_weight_slip():
    img_path = os.path.join(FIXTURES_DIR, "missing_weight_slip.jpg")
    res = process_container_slip(img_path)

    # Gross weight must NOT be fabricated
    assert res.container.weights.gross_weight_kg is None
    # Validation must flag missing gross weight
    assert res.validation.valid is False or any("Gross weight" in w for w in res.validation.warnings)
    # Processing status must be review_required
    assert res.document.processing_status == "review_required"


# --- TEST 5: MISSING DIMENSIONS (GRACEFUL INFERENCE / NULL PRESERVATION) ---
def test_5_missing_dimensions_fallback():
    # Direct text test without explicit dimension strings
    raw_text = """
    CONTAINER NO: MSCU 492019 5
    TYPE: 40HC (45G1)
    GROSS WT: 24,000 KG
    TARE WT: 3,800 KG
    CARGO WT: 20,200 KG
    """
    res = default_service.process_raw_text(raw_text)
    assert res.container.container_type == "40HC"
    # Dimensions inferred standard 40x8x9.5
    assert res.container.dimensions.length_ft == 40.0
    assert res.container.dimensions.height_ft == 9.5
    assert res.validation.valid is True


# --- TEST 6: INVALID CONTAINER NUMBER CHECK DIGIT ---
def test_6_invalid_container_check_digit():
    img_path = os.path.join(FIXTURES_DIR, "invalid_container_num_slip.jpg")
    res = process_container_slip(img_path)

    # MSCU4920199 has check digit 9, but mathematically expected is 5
    assert res.validation.iso_6346_valid is False
    assert res.confidence.container_number <= 0.75
    # Warning or review required
    assert any("check digit" in w.lower() for w in res.validation.warnings + res.validation.errors)


# --- TEST 7: INVALID VGM BALANCE (WEIGHT DISCREPANCY BLOCKS VALIDATION) ---
def test_7_invalid_vgm_balance():
    img_path = os.path.join(FIXTURES_DIR, "inconsistent_weight_slip.jpg")
    res = process_container_slip(img_path)

    # Discrepancy > 14,000 kg
    assert res.validation.weight_balance_valid is False
    assert res.validation.valid is False
    assert res.document.processing_status == "review_required"


# --- TEST 8: MISSING HAZARDOUS FIELD (NULL DEFAULT WITHOUT CRASH) ---
def test_8_missing_hazardous_field_clean_default():
    raw_text = """
    CONTAINER NO: TCKU 778899 0
    TYPE: 20GP
    GROSS WT: 15,000 KG
    TARE WT: 2,200 KG
    CARGO WT: 12,800 KG
    COMMODITY: COTTON TEXTILES
    """
    res = default_service.process_raw_text(raw_text)
    # Hazardous should be None or False (non-hazardous cargo default)
    assert res.container.cargo.hazardous in [None, False]
    assert res.container.cargo.un_number is None
    assert res.confidence.hazardous >= 0.0


# --- TEST 9: PARTIAL DOCUMENT (GRACEFUL HANDLING OF FRAGMENTS) ---
def test_9_partial_document_fragment():
    raw_text = "PORT OF SINGAPORE ONLY FRAGMENT"
    res = default_service.process_raw_text(raw_text)

    assert res.success is True
    assert res.container.container_number is None
    assert res.container.weights.gross_weight_kg is None
    assert res.validation.valid is False
    assert res.document.processing_status == "review_required"


# --- TEST 10: LOW-CONFIDENCE EXTRACTION (SAFETY GATE LOCKED) ---
def test_10_low_confidence_gate_enforcement():
    img_path = os.path.join(FIXTURES_DIR, "low_confidence_slip.jpg")
    res = process_container_slip(img_path)

    # Must be gated for review
    assert res.document.processing_status == "review_required" or res.confidence.overall < 0.85
    assert res.validation.valid is False


# --- TEST 11: VALID DOCUMENT REMAINS COMPATIBLE WITH PHASE 2 STABILITY ---
def test_11_phase2_stability_compatibility():
    img_path = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
    with open(img_path, "rb") as img_file:
        extract_res = client.post("/api/container/extract", files={"image": ("sample.jpg", img_file, "image/jpeg")})
    assert extract_res.status_code == 200
    extract_data = extract_res.json()

    # Pass directly to Phase 2 Stability Analysis
    analysis_req = ContainerStabilityAnalysisRequest(
        container=extract_data["container"],
        document=extract_data["document"],
        validation=extract_data["validation"]
    )
    stab_res = client.post("/api/container/stability/analyze", json=analysis_req.model_dump())
    assert stab_res.status_code == 200
    stab_data = stab_res.json()
    assert stab_data["success"] is True
    assert stab_data["recommendation"] is not None
    assert stab_data["recommendation"]["bay"] in [1, 2, 3, 4]


# --- TEST 12: VALID DOCUMENT REMAINS COMPATIBLE WITH PHASE 3 LOADING & BALLAST ---
def test_12_phase3_loading_and_ballast_compatibility():
    img_path = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
    with open(img_path, "rb") as img_file:
        extract_res = client.post("/api/container/extract", files={"image": ("sample.jpg", img_file, "image/jpeg")})
    extract_data = extract_res.json()

    # Stability analysis
    stab_res = client.post("/api/container/stability/analyze", json={
        "container": extract_data["container"],
        "document": extract_data["document"],
        "validation": extract_data["validation"]
    })
    rec = stab_res.json()["recommendation"]

    # Phase 3B Loading Confirmation
    load_res = client.post("/api/container/load/confirm", json={
        "container": extract_data["container"],
        "document": extract_data["document"],
        "validation": extract_data["validation"],
        "recommendation": rec,
        "operator_confirmed": True
    })
    assert load_res.status_code == 200
    load_data = load_res.json()
    assert load_data["success"] is True
    assert load_data["status"] == "LOADED"

    # Phase 3C Ballast Compensation Calculation
    calc_res = client.post("/api/container/ballast/calculate", json={
        "container_number": load_data["container"]["container_number"],
        "gross_weight_t": load_data["container"]["gross_weight_t"],
        "bay": load_data["loaded_position"]["bay"],
        "side": load_data["loaded_position"]["side"]
    })
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["success"] is True
    assert calc_data["compensation_required"] is True

    # Phase 3C Ballast Execution
    exec_res = client.post("/api/container/ballast/execute", json={
        "tank_key": calc_data["tank_key"],
        "direction": calc_data["direction"],
        "qty_t": calc_data["required_qty_t"],
        "operator_confirmed": True,
        "stability_before_load": load_data["stability_before"]
    })
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "COMPLETED"
