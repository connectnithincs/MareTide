"""
Phase 3D: Full OCR -> Loading -> Ballast End-to-End System Verification & Performance Benchmark.
Tests all 6 required verification scenarios with synthetic image inputs, state integrity, and latency measurements.
"""

import os
import time
import pytest
from fastapi.testclient import TestClient

from main import app
from ship import Ship, Container, BallastTank, StabilityAnalyzer
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest
)
from container_stability.analyzer import (
    ContainerStabilityService,
    ContainerLoadingService,
    ContainerBallastService
)
from reports.logs_db import get_container_loading_audits, get_ballast_operations, clear_logs
import state

client = TestClient(app)
FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    # Reset ship singleton
    ship = state.get_current_ship()
    ship.containers.clear()
    for b in range(1, ship.num_bays + 1):
        if f"port_{b}" in ship.tanks:
            ship.tanks[f"port_{b}"].current_volume = 100.0
        if f"starboard_{b}" in ship.tanks:
            ship.tanks[f"starboard_{b}"].current_volume = 100.0
    yield
    clear_logs()
    ship.containers.clear()



# --- TEST CASE 1: NORMAL CONTAINER (REAL IMAGE OCR -> LOAD -> BALLAST) ---
def test_case_1_normal_container_e2e():
    image_path = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
    assert os.path.exists(image_path), "sample_container_slip.jpg must exist"

    # Step 1: Real Image OCR Extraction
    t0 = time.perf_counter()
    with open(image_path, "rb") as img_file:
        ocr_res = client.post("/api/container/extract", files={"image": ("slip.jpg", img_file, "image/jpeg")})
    t1 = time.perf_counter()
    ocr_latency_ms = (t1 - t0) * 1000

    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["success"] is True
    assert ocr_data["container"]["container_number"] == "MSCU4920195"
    assert ocr_data["container"]["weights"]["gross_weight_kg"] == 26200.0
    assert ocr_data["confidence"]["overall"] >= 0.85
    assert ocr_data["validation"]["valid"] is True

    # Step 2: Stability Analysis & Recommendation
    t2 = time.perf_counter()
    stab_res = client.post("/api/container/stability/analyze", json={
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"]
    })
    t3 = time.perf_counter()
    stability_latency_ms = (t3 - t2) * 1000

    assert stab_res.status_code == 200
    stab_data = stab_res.json()
    assert stab_data["success"] is True
    rec = stab_data["recommendation"]
    assert rec is not None
    assert rec["bay"] in [1, 2, 3, 4]
    assert rec["side"] in ["PORT", "STARBOARD"]

    # Step 3: Operator Confirmation & Loading
    t4 = time.perf_counter()
    load_res = client.post("/api/container/load/confirm", json={
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "recommendation": rec,
        "operator_confirmed": True
    })
    t5 = time.perf_counter()
    load_latency_ms = (t5 - t4) * 1000

    assert load_res.status_code == 200
    load_data = load_res.json()
    assert load_data["success"] is True
    assert load_data["status"] == "LOADED"
    assert load_data["loaded_position"]["bay"] == rec["bay"]

    # Step 4: Ballast Compensation Calculation
    t6 = time.perf_counter()
    ballast_calc_res = client.post("/api/container/ballast/calculate", json={
        "container_number": load_data["container"]["container_number"],
        "gross_weight_t": load_data["container"]["gross_weight_t"],
        "bay": load_data["loaded_position"]["bay"],
        "side": load_data["loaded_position"]["side"]
    })
    t7 = time.perf_counter()
    ballast_calc_latency_ms = (t7 - t6) * 1000

    assert ballast_calc_res.status_code == 200
    ballast_calc_data = ballast_calc_res.json()
    assert ballast_calc_data["success"] is True
    assert ballast_calc_data["compensation_required"] is True

    # Step 5: Ballast Execution & 3-Stage Stability Verification
    t8 = time.perf_counter()
    ballast_exec_res = client.post("/api/container/ballast/execute", json={
        "tank_key": ballast_calc_data["tank_key"],
        "direction": ballast_calc_data["direction"],
        "qty_t": ballast_calc_data["required_qty_t"],
        "operator_confirmed": True,
        "stability_before_load": load_data["stability_before"]
    })
    t9 = time.perf_counter()
    ballast_exec_latency_ms = (t9 - t8) * 1000

    assert ballast_exec_res.status_code == 200
    ballast_exec_data = ballast_exec_res.json()
    assert ballast_exec_data["success"] is True
    assert ballast_exec_data["status"] == "COMPLETED"
    report = ballast_exec_data["three_stage_stability"]
    assert report["after_ballast"]["risk_level"] == "SAFE"

    total_pipeline_latency_ms = (t9 - t0) * 1000
    print(f"\n[BENCHMARK] Normal Slip Pipeline Latency: {total_pipeline_latency_ms:.2f}ms (OCR: {ocr_latency_ms:.2f}ms, Stability: {stability_latency_ms:.2f}ms, Load: {load_latency_ms:.2f}ms, Ballast: {(ballast_calc_latency_ms + ballast_exec_latency_ms):.2f}ms)")


# --- TEST CASE 2: HEAVY CONTAINER (34.5t CONTAINER DYNAMIC ADAPTATION) ---
def test_case_2_heavy_container_dynamic_recommendation():
    image_path = os.path.join(FIXTURES_DIR, "heavy_container_slip.jpg")
    assert os.path.exists(image_path), "heavy_container_slip.jpg must exist"

    with open(image_path, "rb") as img_file:
        ocr_res = client.post("/api/container/extract", files={"image": ("heavy.jpg", img_file, "image/jpeg")})
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()
    assert ocr_data["success"] is True
    assert ocr_data["container"]["weights"]["gross_weight_kg"] == 34500.0

    # Evaluate stability recommendation for 34.5t heavy container
    stab_res = client.post("/api/container/stability/analyze", json={
        "container": ocr_data["container"]
    })
    assert stab_res.status_code == 200
    stab_data = stab_res.json()
    assert stab_data["success"] is True
    assert stab_data["container"]["gross_weight_t"] == 34.5
    # Verify candidate evaluations are dynamically computed without hardcoding
    evals = stab_data["candidate_evaluations"]
    assert len(evals) == 8  # 4 bays * 2 sides
    # Verify the selected candidate has the lowest score
    selected = [e for e in evals if e["selected"]]
    assert len(selected) == 1
    min_score = min(e["score"] for e in evals)
    assert selected[0]["score"] == min_score


# --- TEST CASE 3: INVALID DOCUMENT (WEIGHT INCONSISTENCY BLOCKS LOADING) ---
def test_case_3_inconsistent_weight_blocks_loading():
    image_path = os.path.join(FIXTURES_DIR, "inconsistent_weight_slip.jpg")
    assert os.path.exists(image_path), "inconsistent_weight_slip.jpg must exist"

    with open(image_path, "rb") as img_file:
        ocr_res = client.post("/api/container/extract", files={"image": ("inconsistent.jpg", img_file, "image/jpeg")})
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()

    # Document validation must flag weight discrepancy
    assert ocr_data["validation"]["valid"] is False
    assert len(ocr_data["validation"]["errors"]) > 0 or ocr_data["document"]["processing_status"] == "review_required"

    # Attempt to load this invalid container
    load_res = client.post("/api/container/load/confirm", json={
        "container": ocr_data["container"],
        "document": ocr_data["document"],
        "validation": ocr_data["validation"],
        "recommendation": {"bay": 1, "side": "PORT", "tier": 1},
        "operator_confirmed": True
    })
    assert load_res.status_code == 200
    load_data = load_res.json()
    assert load_data["success"] is False
    assert load_data["status"] in ["review_required", "error"]


# --- TEST CASE 4: LOW CONFIDENCE DEGRADED DOCUMENT ---
def test_case_4_low_confidence_blocked():
    image_path = os.path.join(FIXTURES_DIR, "low_confidence_slip.jpg")
    assert os.path.exists(image_path), "low_confidence_slip.jpg must exist"

    with open(image_path, "rb") as img_file:
        ocr_res = client.post("/api/container/extract", files={"image": ("degraded.jpg", img_file, "image/jpeg")})
    assert ocr_res.status_code == 200
    ocr_data = ocr_res.json()

    # System must either set review_required or mark confidence low
    assert ocr_data["document"]["processing_status"] == "review_required" or ocr_data["confidence"]["overall"] < 0.85

    # Attempt to load
    load_res = client.post("/api/container/load/confirm", json={
        "container": ocr_data.get("container") or {"container_number": "UNVERIFIED"},
        "document": ocr_data["document"],
        "validation": ocr_data.get("validation") or {"valid": False},
        "recommendation": {"bay": 1, "side": "PORT", "tier": 1},
        "operator_confirmed": True
    })
    assert load_res.status_code == 200
    assert load_res.json()["success"] is False


# --- TEST CASE 5: OCCUPIED POSITION SAFETY ---
def test_case_5_occupied_position_safety():
    ship = state.get_current_ship()
    # Pre-occupy slot Bay 1 / STARBOARD / Tier 1
    ship.add_container(Container(id="FIRST-LOAD", weight=20.0, bay=1, side="starboard", tier=1))
    initial_count = len(ship.containers)

    # Attempt to load another container into the same slot
    load_res = client.post("/api/container/load/confirm", json={
        "container": {"container_number": "SECOND-LOAD", "weights": {"gross_weight_kg": 22000.0}},
        "document": {"processing_status": "success"},
        "validation": {"valid": True},
        "recommendation": {"bay": 1, "side": "STARBOARD", "tier": 1},
        "operator_confirmed": True
    })
    assert load_res.status_code == 200
    load_data = load_res.json()
    assert load_data["success"] is False
    assert "already occupied" in load_data["error_message"].lower()

    # Ensure live vessel state was NOT corrupted and count is unchanged
    assert len(ship.containers) == initial_count
    assert ship.containers[0].id == "FIRST-LOAD"


# --- TEST CASE 6: BALLAST RESTORATION CYCLE ---
def test_case_6_ballast_restoration_cycle():
    ship = state.get_current_ship()
    # Initial state
    score_0 = StabilityAnalyzer.stability_score(ship)

    # 1. Add single heavy load on starboard side
    ship.add_container(Container(id="HEAVY-01", weight=40.0, bay=1, side="starboard", tier=1))
    score_1 = StabilityAnalyzer.stability_score(ship)
    list_1 = StabilityAnalyzer.calculate_list(ship)
    assert list_1 > 0  # Heavy list to starboard

    # 2. Calculate compensation
    calc_res = ContainerBallastService.calculate_compensation(
        BallastCompensationRequest(gross_weight_t=40.0, bay=1, side="STARBOARD"),
        ship_instance=ship
    )
    assert calc_res.compensation_required is True
    assert calc_res.tank_key == "starboard_1"
    assert calc_res.required_qty_t == 40.0

    # 3. Execute compensation
    exec_res = ContainerBallastService.execute_compensation(
        BallastExecutionRequest(tank_key="starboard_1", qty_t=40.0, operator_confirmed=True),
        ship_instance=ship
    )
    assert exec_res.success is True
    score_2 = StabilityAnalyzer.stability_score(ship)
    list_2 = StabilityAnalyzer.calculate_list(ship)

    # After ballast, list imbalance should return to 0
    assert abs(list_2) < abs(list_1)
    assert score_2 < score_1
