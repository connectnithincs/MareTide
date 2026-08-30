"""
Phase 4E: Cargo Data Anomaly & Safety Intelligence Tests.
Verifies VGM mismatch detection, impossible dimensions, invalid ISO checksums,
duplicate container detection, degraded confidence alerts, missing weight blocks,
conflicting value resolution, and clean document handling.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Container
import state
from container_ocr.models import ContainerDetails, ContainerWeights, ContainerDimensions, CargoDetails
from container_ocr.validator import DomainValidator
from container_ocr.anomaly_detector import CargoAnomalyDetector, CargoAnomaly
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest
)
from container_stability.analyzer import ContainerStabilityService, ContainerLoadingService
from reports.logs_db import clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0
    yield
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0


# --- TEST 1: VGM MISMATCH (tare + cargo != gross) ---
def test_1_vgm_mismatch_detected_and_blocks_loading():
    """Verify that gross != tare + cargo generates a CRITICAL anomaly and blocks loading."""
    container_dict = {
        "container_number": "MSCU4920194",
        "container_type": "40HC",
        "weights": {
            "gross_weight_kg": 31000.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 22000.0  # 3800 + 22000 = 25800 != 31000
        }
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(container_dict)
    vgm_anomaly = next((a for a in anomalies if a.field == "gross_weight" and a.severity == "CRITICAL"), None)
    
    assert vgm_anomaly is not None, "Must trigger CRITICAL anomaly for VGM mismatch"
    assert vgm_anomaly.observed == 31000.0
    assert "tare" in vgm_anomaly.expected
    assert "does not equal tare plus cargo" in vgm_anomaly.message

    # Verify that DomainValidator marks valid=False due to critical anomaly
    cntr_obj = ContainerDetails(**container_dict)
    val_res = DomainValidator.validate_container(cntr_obj)
    assert val_res.valid is False
    assert any(a.severity == "CRITICAL" for a in val_res.anomalies)

    # Verify that ContainerLoadingService blocks loading
    load_req = ContainerLoadingConfirmRequest(
        container=container_dict,
        validation=val_res.model_dump(),
        recommendation={"bay": 2, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )
    confirm_res = ContainerLoadingService.confirm_and_load(load_req)
    assert confirm_res.success is False
    assert confirm_res.status in ["rejected", "error"]


# --- TEST 2: IMPOSSIBLE DIMENSIONS ---
def test_2_impossible_dimensions():
    """Verify extreme or negative dimensions trigger CRITICAL anomalies."""
    container_dict = {
        "container_number": "MSCU4920194",
        "container_type": "40HC",
        "weights": {"gross_weight_kg": 22000.0},
        "dimensions": {
            "length_ft": 65.0,  # Impossible length > 53ft
            "width_ft": 8.0,
            "height_ft": 9.5
        }
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(container_dict)
    dim_anomaly = next((a for a in anomalies if "length" in a.field and a.severity == "CRITICAL"), None)
    assert dim_anomaly is not None
    assert "exceeds allowable vessel cell guide envelope" in dim_anomaly.message


# --- TEST 3: INVALID ISO NUMBER & CHECK DIGIT ---
def test_3_invalid_iso_number():
    """Verify invalid check digit or corrupted length generates structured anomaly."""
    # 1. Invalid length (10 chars instead of 11)
    short_dict = {
        "container_number": "MSCU123456",
        "weights": {"gross_weight_kg": 20000.0}
    }
    short_anomalies = CargoAnomalyDetector.detect_anomalies(short_dict)
    short_crit = next((a for a in short_anomalies if a.field == "container_number" and a.severity == "WARNING"), None)
    assert short_crit is not None

    # 2. Check digit mismatch (MSCU4920199 instead of correct check digit 4)
    bad_check_dict = {
        "container_number": "MSCU4920199",
        "weights": {"gross_weight_kg": 20000.0}
    }
    bad_anomalies = CargoAnomalyDetector.detect_anomalies(bad_check_dict)
    bad_warn = next((a for a in bad_anomalies if a.field == "container_number" and a.severity == "WARNING"), None)
    assert bad_warn is not None
    assert "check digit verification failed" in bad_warn.message


# --- TEST 4: DUPLICATE CONTAINER ON VESSEL ---
def test_4_duplicate_container_on_vessel():
    """Verify that attempting to plan or load an already-stowed container triggers CRITICAL anomaly."""
    ship = state.get_current_ship()
    ship.containers.append(Container(id="MSCU8877112", weight=22.0, bay=2, side="port", tier=1))

    incoming_dict = {
        "container_number": "MSCU8877112",
        "weights": {"gross_weight_kg": 22000.0}
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data=incoming_dict,
        existing_containers=ship.containers
    )
    dup_anomaly = next((a for a in anomalies if a.field == "container_number" and a.severity == "CRITICAL"), None)
    assert dup_anomaly is not None
    assert "already stowed in an active slot" in dup_anomaly.message


# --- TEST 5: LOW EXTRACTION CONFIDENCE ---
def test_5_low_extraction_confidence():
    """Verify degraded OCR confidence score generates WARNING anomaly."""
    container_dict = {
        "container_number": "MSCU4920194",
        "weights": {"gross_weight_kg": 24000.0}
    }
    confidence_dict = {
        "overall": 0.65,
        "weights": 0.55
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(
        container_data=container_dict,
        confidence_data=confidence_dict
    )
    conf_anomaly = next((a for a in anomalies if a.field == "confidence.overall" and a.severity == "WARNING"), None)
    assert conf_anomaly is not None
    assert conf_anomaly.observed == 0.65


# --- TEST 6: MISSING REQUIRED GROSS WEIGHT ---
def test_6_missing_required_gross_weight():
    """Verify missing gross weight produces CRITICAL anomaly and cannot proceed to stability analysis."""
    container_dict = {
        "container_number": "MSCU4920194",
        "weights": {}  # Missing gross weight
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(container_dict)
    weight_anomaly = next((a for a in anomalies if a.field == "gross_weight" and a.severity == "CRITICAL"), None)
    assert weight_anomaly is not None
    assert "Mandatory Verified Gross Mass" in weight_anomaly.message

    # Test via API
    req = ContainerStabilityAnalysisRequest(container=container_dict)
    res = ContainerStabilityService.analyze_container_placement(req)
    assert res.success is False
    assert res.status == "error"


# --- TEST 7: CONFLICTING VALUES (UN NUMBER WITHOUT HAZARDOUS FLAG) ---
def test_7_conflicting_values_hazardous_mismatch():
    """Verify dangerous goods UN number with hazardous=False triggers CRITICAL classification anomaly."""
    container_dict = {
        "container_number": "MSCU4920194",
        "weights": {"gross_weight_kg": 21000.0},
        "cargo": {
            "hazardous": False,
            "un_number": "UN 1203"  # Flammable Gasoline
        }
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(container_dict)
    haz_anomaly = next((a for a in anomalies if a.field == "cargo.hazardous" and a.severity == "CRITICAL"), None)
    assert haz_anomaly is not None
    assert "Conflicting cargo classification" in haz_anomaly.message


# --- TEST 8: CLEAN DOCUMENT COMPLIANCE ---
def test_8_clean_document_compliance():
    """Verify clean document produces INFO verified item and passes validation."""
    clean_dict = {
        "container_number": "MSCU4920195",
        "container_type": "40HC",
        "weights": {
            "gross_weight_kg": 24000.0,
            "tare_weight_kg": 3900.0,
            "cargo_weight_kg": 20100.0
        },
        "dimensions": {
            "length_ft": 40.0,
            "width_ft": 8.0,
            "height_ft": 9.5
        },
        "cargo": {
            "hazardous": False,
            "description": "General Auto Parts"
        }
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(clean_dict)
    assert len(anomalies) == 1
    assert anomalies[0].severity == "INFO"
    assert "passed all ISO, VGM, dimensional" in anomalies[0].message


# --- TEST 9: SUSPICIOUS OVERWEIGHT CONTAINER (> 36t) ---
def test_9_suspicious_overweight_container():
    """Verify containers exceeding 36t trigger CRITICAL overload safety anomaly."""
    heavy_dict = {
        "container_number": "MSCU4920194",
        "weights": {"gross_weight_kg": 42000.0}  # Over 36t ISO rating
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(heavy_dict)
    over_anomaly = next((a for a in anomalies if a.field == "gross_weight" and a.severity == "CRITICAL"), None)
    assert over_anomaly is not None
    assert "exceeds maximum ISO structural rating" in over_anomaly.message


# --- TEST 10: INCONSISTENT CONTAINER TYPE VS LENGTH ---
def test_10_inconsistent_container_type_vs_length():
    """Verify 20ft container type with 40ft length triggers CRITICAL type inconsistency."""
    inconsistent_dict = {
        "container_number": "MSCU4920194",
        "container_type": "20GP",
        "dimensions": {"length_ft": 40.0},
        "weights": {"gross_weight_kg": 20000.0}
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(inconsistent_dict)
    type_anomaly = next((a for a in anomalies if a.field == "container_type" and a.severity == "CRITICAL"), None)
    assert type_anomaly is not None
    assert "indicates a 20ft unit, but extracted length is 40.0 ft" in type_anomaly.message


# --- TEST 11: NON-SILENT CORRECTION SAFETY INTEGRITY ---
def test_11_non_silent_correction_safety_integrity():
    """Verify raw extracted values are never silently mutated or falsified."""
    raw_dict = {
        "container_number": "MSCU4920194",
        "weights": {
            "gross_weight_kg": 31000.0,
            "tare_weight_kg": 3800.0,
            "cargo_weight_kg": 22000.0
        }
    }

    anomalies = CargoAnomalyDetector.detect_anomalies(raw_dict)
    # Assert raw_dict remains completely untouched
    assert raw_dict["weights"]["gross_weight_kg"] == 31000.0
    assert raw_dict["weights"]["cargo_weight_kg"] == 22000.0
    assert len(anomalies) > 0
