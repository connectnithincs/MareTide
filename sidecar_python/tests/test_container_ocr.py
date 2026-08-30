"""
Comprehensive Unit and Integration Test Suite for Container Document Intelligence (Phase 1).
Validates all 12 core requirements:
1. Valid container number
2. Invalid container number
3. Missing gross weight
4. Gross weight mismatch
5. Missing dimensions
6. Unknown container type
7. Weight unit conversion
8. Dimension unit conversion
9. Hazardous YES
10. Hazardous NO
11. Low confidence extraction (review_required)
12. Completely unreadable document (ocr_failed / review_required)
"""

import io
import sys
import os
import pytest
import numpy as np
from PIL import Image, ImageDraw

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from container_ocr.validator import DomainValidator
from container_ocr.normalizer import DataNormalizer
from container_ocr.extractor import FieldExtractor
from container_ocr.confidence import ConfidenceScorer
from container_ocr.ocr_engine import OCRResult, OCRTextBlock, MockOCREngine
from container_ocr.preprocessing import ImagePreprocessor
from container_ocr.service import ContainerSlipService, process_container_slip
from container_ocr.models import ContainerDetails, ContainerWeights, ContainerDimensions, CargoDetails
from container_ocr.config import EXTRACTION_REVIEW_THRESHOLD
from main import app
from fastapi.testclient import TestClient


# --- REQUIREMENT 1: VALID CONTAINER NUMBER ---
def test_case_1_valid_container_number():
    """
    Validates ISO 6346 compliant container numbers across major shipping lines.
    """
    valid_numbers = [
        "MSCU4920195",  # MSC (check digit 5)
        "CSQU3054383",  # China Shipping (check digit 3)
        "HLXU1234561",  # Hapag-Lloyd (check digit 1)
    ]
    for num in valid_numbers:
        is_valid, warn = DomainValidator.validate_iso_6346(num)
        assert is_valid is True, f"Expected {num} to be valid, got {warn}"
        assert warn is None


# --- REQUIREMENT 2: INVALID CONTAINER NUMBER ---
def test_case_2_invalid_container_number():
    """
    Verifies that invalid check digits return a warning and do NOT discard the value.
    """
    num_invalid = "MSCU4920198"  # Check digit should be 5, but is 8
    is_valid, warn = DomainValidator.validate_iso_6346(num_invalid)
    assert is_valid is False
    assert "check digit appears invalid" in warn.lower()

    # Full extraction check: container_number is retained and warning is added
    res = ContainerSlipService().process_raw_text(f"CONTAINER: {num_invalid}\nGROSS: 25000 KG")
    assert res.container.container_number == num_invalid
    assert any("check digit appears invalid" in w.lower() for w in res.validation.warnings)


# --- REQUIREMENT 3: MISSING GROSS WEIGHT ---
def test_case_3_missing_gross_weight():
    """
    Verifies that missing gross weight returns null, adds a warning, and lowers confidence.
    """
    text = (
        "CONTAINER NO: MSCU 492019 5\n"
        "TYPE: 40HC\n"
        "DESTINATION: SINGAPORE\n"
    )
    res = ContainerSlipService().process_raw_text(text)
    assert res.container.weights.gross_weight_kg is None
    assert any("Gross weight could not be extracted" in w for w in res.validation.warnings)
    assert res.confidence.weights == 0.0
    assert res.document.processing_status == "review_required"


# --- REQUIREMENT 4: GROSS WEIGHT MISMATCH ---
def test_case_4_gross_weight_mismatch():
    """
    Verifies GROSS_WEIGHT_INCONSISTENT warning with diagnostic details when Gross != Tare + Cargo.
    """
    weights = ContainerWeights(
        tare_weight_kg=3800.0,
        cargo_weight_kg=20000.0,
        gross_weight_kg=26000.0  # Expected 23800, difference of 2200 kg
    )
    is_valid, warns, errs = DomainValidator.validate_weights(weights)
    assert is_valid is False
    assert any("GROSS_WEIGHT_INCONSISTENT" in w for w in warns)
    assert any("Expected gross 23800.0 kg" in w for w in warns)
    assert any("extracted gross 26000.0 kg" in w for w in warns)
    assert any("difference: 2200.0 kg" in w for w in warns)


# --- REQUIREMENT 5: MISSING DIMENSIONS ---
def test_case_5_missing_dimensions():
    """
    Verifies that missing dimensions remain null without fabrication.
    """
    text = (
        "CONTAINER NO: MSCU 492019 5\n"
        "GROSS WEIGHT: 25000 KG\n"
    )
    res = ContainerSlipService().process_raw_text(text)
    assert res.container.dimensions.length_ft is None
    assert res.container.dimensions.width_ft is None
    assert res.container.dimensions.height_ft is None


# --- REQUIREMENT 6: UNKNOWN CONTAINER TYPE ---
def test_case_6_unknown_container_type():
    """
    Verifies warning when container type is absent or unknown.
    """
    text = (
        "CONTAINER NO: MSCU 492019 5\n"
        "TYPE: UNKNOWN-BOX-99\n"
        "GROSS: 25000 KG\n"
    )
    res = ContainerSlipService().process_raw_text(text)
    assert any("Container type could not be confidently identified" in w for w in res.validation.warnings)


# --- REQUIREMENT 7: WEIGHT UNIT CONVERSION ---
def test_case_7_weight_unit_conversion():
    """
    Tests converting LBS (8,377 lbs -> 3,800 kg) and Tonnes (28.5 T -> 28,500 kg).
    """
    text = (
        "CONTAINER: MSCU4920195\n"
        "GROSS WT: 28.5 TONNES\n"
        "TARE WT: 8377.56 LBS\n"
    )
    res = ContainerSlipService().process_raw_text(text)
    assert res.container.weights.gross_weight_kg == 28500.0
    assert res.container.weights.tare_weight_kg == 3800.0
    assert res.container.weights.cargo_weight_kg == 24700.0  # Derived via balance


# --- REQUIREMENT 8: DIMENSION UNIT CONVERSION ---
def test_case_8_dimension_unit_conversion():
    """
    Tests converting metric dimensions (12.19m x 2.44m x 2.89m) to feet.
    """
    text = (
        "CONTAINER: MSCU4920195\n"
        "DIMENSIONS: 12.19m x 2.44m x 2.89m\n"
        "GROSS: 25000 KG\n"
    )
    res = ContainerSlipService().process_raw_text(text)
    assert res.container.dimensions.length_ft == 40.0
    assert res.container.dimensions.width_ft == 8.0
    assert res.container.dimensions.height_ft == 9.5


# --- REQUIREMENT 9: HAZARDOUS YES ---
def test_case_9_hazardous_yes():
    """
    Tests normalization of hazardous indicators (YES, DG, UN numbers) to true.
    """
    indicators = [
        "HAZMAT: YES",
        "DG: TRUE",
        "DANGEROUS GOODS: UN 3480 CLASS 9",
        "HAZARDOUS CARGO DETECTED"
    ]
    for ind in indicators:
        text = f"CONTAINER: MSCU4920195\n{ind}\nGROSS: 25000 KG"
        res = ContainerSlipService().process_raw_text(text)
        assert res.container.cargo.hazardous is True, f"Failed for indicator: {ind}"


# --- REQUIREMENT 10: HAZARDOUS NO ---
def test_case_10_hazardous_no():
    """
    Tests normalization of non-hazardous indicators (NO, NON-HAZARDOUS) to false.
    """
    indicators = [
        "HAZMAT: NO",
        "NON-HAZARDOUS GENERAL CARGO",
        "DG: FALSE",
        "NO DG"
    ]
    for ind in indicators:
        text = f"CONTAINER: MSCU4920195\n{ind}\nGROSS: 25000 KG"
        res = ContainerSlipService().process_raw_text(text)
        assert res.container.cargo.hazardous is False, f"Failed for indicator: {ind}"


# --- REQUIREMENT 11: LOW CONFIDENCE EXTRACTION ---
def test_case_11_low_confidence_review_required():
    """
    Verifies that low confidence extractions are marked as 'review_required'.
    """
    # A partial slip missing critical weights and container type
    partial_text = "CONTAINER: MSCU4920195\n"
    res = ContainerSlipService().process_raw_text(partial_text)
    assert res.confidence.overall < EXTRACTION_REVIEW_THRESHOLD
    assert res.document.processing_status == "review_required"
    assert res.success is True  # Returns extracted data safely


# --- REQUIREMENT 12: COMPLETELY UNREADABLE DOCUMENT ---
def test_case_12_completely_unreadable_document():
    """
    Verifies safe failure behavior on corrupt binary input.
    """
    garbage_bytes = b"MALFORMED_GARBAGE_BINARY_IMAGE_DATA_0000"
    res = ContainerSlipService().process_image(garbage_bytes, source_name="corrupted.png")
    assert res.success is False
    assert res.document.processing_status == "ocr_failed"
    assert len(res.validation.errors) > 0


# --- ADDITIONAL: IMAGE PREPROCESSING & FASTAPI ENDPOINTS ---

def test_image_preprocessing_pipeline():
    """
    Tests OpenCV deskew and contrast enhancement on synthetic generated slip.
    """
    img = Image.new("RGB", (800, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(20, 20), (780, 580)], outline=(0, 0, 0), width=2)
    draw.text((40, 40), "CONTAINER INTERCHANGE RECEIPT", fill=(0, 0, 0))
    draw.text((40, 80), "CONTAINER NO: MSCU 492019 5", fill=(0, 0, 0))
    draw.text((40, 120), "TYPE: 40HC", fill=(0, 0, 0))
    draw.text((40, 160), "TARE: 3,800 KG", fill=(0, 0, 0))
    draw.text((40, 200), "CARGO: 22,400 KG", fill=(0, 0, 0))
    draw.text((40, 240), "VGM: 26,200 KG", fill=(0, 0, 0))
    draw.text((40, 280), "DESTINATION: SINGAPORE", fill=(0, 0, 0))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    raw_bytes = img_bytes.getvalue()

    res = process_container_slip(raw_bytes, source_name="synthetic_slip.jpg")
    assert res.success is True
    assert res.document.source == "synthetic_slip.jpg"
    assert "MSCU" in (res.container.container_number or "")
    assert res.container.destination == "SINGAPORE"
    assert res.document.processing_status == "success"


client = TestClient(app)

def test_api_health_endpoint():
    response = client.get("/api/container/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "rapidocr" in data["supported_engines"]
    assert data["endpoint"] == "POST /api/container/extract"


def test_api_extract_valid_image():
    """
    Tests POST /api/container/extract with valid image file using 'image' form field.
    """
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "CONTAINER: MSCU4920195", fill=(0, 0, 0))
    draw.text((20, 60), "TYPE: 40HC", fill=(0, 0, 0))
    draw.text((20, 100), "VGM GROSS: 28000 KG", fill=(0, 0, 0))

    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/api/container/extract",
        files={"image": ("container_slip.png", img_bytes, "image/png")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["document"]["source"] == "container_slip.png"
    assert data["container"]["container_number"] == "MSCU4920195"
    assert data["container"]["container_type"] == "40HC"
    assert data["container"]["weights"]["gross_weight_kg"] == 28000.0


def test_api_extract_missing_image():
    """
    Tests POST /api/container/extract with no image supplied -> 400 Bad Request.
    """
    response = client.post("/api/container/extract")
    assert response.status_code == 400
    assert "No image file provided" in response.json()["detail"]


def test_api_extract_invalid_extension():
    """
    Tests POST /api/container/extract with unsupported extension (.pdf) -> 400 Bad Request.
    """
    dummy_file = io.BytesIO(b"%PDF-1.4...")
    response = client.post(
        "/api/container/extract",
        files={"image": ("slip.pdf", dummy_file, "application/pdf")}
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_api_extract_empty_file():
    """
    Tests POST /api/container/extract with 0-byte file -> 400 Bad Request.
    """
    empty_file = io.BytesIO(b"")
    response = client.post(
        "/api/container/extract",
        files={"image": ("empty.png", empty_file, "image/png")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_api_extract_corrupted_image():
    """
    Tests POST /api/container/extract with corrupted image data -> 400 Bad Request.
    """
    corrupt_file = io.BytesIO(b"NOT_A_VALID_IMAGE_BINARY_HEADER")
    response = client.post(
        "/api/container/extract",
        files={"image": ("corrupted.png", corrupt_file, "image/png")}
    )
    assert response.status_code == 400
    assert "Corrupted or invalid image" in response.json()["detail"]


def test_api_process_raw_text():
    payload = {
        "raw_text": (
            "CONTAINER NO: MSCU 492019 5\n"
            "TYPE: 40HC\n"
            "TARE: 3,800 KG\n"
            "VGM: 26,200 KG\n"
            "PORT: SINGAPORE"
        ),
        "source_name": "test_text_api.txt"
    }
    response = client.post("/api/container/ocr/process-raw", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["container"]["container_number"] == "MSCU4920195"
    assert data["container"]["container_type"] == "40HC"
    assert data["container"]["weights"]["tare_weight_kg"] == 3800.0
    assert data["container"]["weights"]["gross_weight_kg"] == 26200.0
    assert data["document"]["processing_status"] == "success"


def test_existing_vessel_state_endpoint_untouched():
    """
    Verifies that the existing vessel state endpoint operates normally without disruption.
    """
    response = client.get("/api/vessel-state")
    assert response.status_code == 200
    data = response.json()
    assert "ship_name" in data
    assert "stability_score" in data
    assert "ballast_tanks" in data


def test_existing_recommendations_endpoint_untouched():
    """
    Verifies that existing advisory/recommendations endpoint operates normally.
    """
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert "best_bay" in data
    assert "best_side" in data
