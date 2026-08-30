"""
Phase 4G: Performance Benchmarking Script.
Measures real runtime in milliseconds across all pipeline stages:
1. OCR & Document Preprocessing
2. Validation & Anomaly Detection
3. Multi-Objective Stowage Optimization
4. Operator Confirmation & State Commit
5. Ballast Compensation Calculation & Execution
6. Digital Twin State Snapshot & Alert Generation
7. Total End-to-End Workflow Latency
"""

import os
import sys
import time
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Ship, Container, StabilityAnalyzer
import state
from container_ocr.service import process_container_slip
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
from digital_twin import DigitalTwin
from reports.logs_db import clear_logs

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "fixtures")


def run_benchmark():
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0

    sample_slip_path = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")
    with open(sample_slip_path, "rb") as f:
        image_bytes = f.read()

    measurements = {}

    # 1. OCR & Document Intelligence Extraction
    t0 = time.perf_counter()
    extracted_res = process_container_slip(image_bytes, source_name="sample_container_slip.jpg")
    t1 = time.perf_counter()
    ocr_ms = (t1 - t0) * 1000.0
    measurements["ocr_and_document_ai_ms"] = round(ocr_ms, 2)

    # 2. Validation & Anomaly Detection
    t0 = time.perf_counter()
    validation_data = extracted_res.validation.model_dump()
    anomalies = extracted_res.validation.anomalies
    t1 = time.perf_counter()
    val_ms = (t1 - t0) * 1000.0
    measurements["validation_and_anomaly_detection_ms"] = round(val_ms, 2)

    # 3. Multi-Objective Stowage Optimization
    analysis_req = ContainerStabilityAnalysisRequest(
        container=extracted_res.container.model_dump(),
        document=extracted_res.document.model_dump(),
        validation=validation_data
    )
    t0 = time.perf_counter()
    stab_res = ContainerStabilityService.analyze_container_placement(analysis_req, ship_instance=ship)
    t1 = time.perf_counter()
    opt_ms = (t1 - t0) * 1000.0
    measurements["stowage_optimization_ms"] = round(opt_ms, 2)

    # 4. Operator Loading Confirmation & State Commit
    confirm_req = ContainerLoadingConfirmRequest(
        container=extracted_res.container.model_dump(),
        document=extracted_res.document.model_dump(),
        validation=validation_data,
        recommendation=stab_res.recommendation.model_dump(),
        operator_confirmed=True
    )
    t0 = time.perf_counter()
    confirm_res = ContainerLoadingService.confirm_and_load(confirm_req, ship_instance=ship)
    t1 = time.perf_counter()
    load_ms = (t1 - t0) * 1000.0
    measurements["loading_commit_and_audit_ms"] = round(load_ms, 2)

    # 5. Ballast Compensation Calculation & Execution
    ballast_req = BallastCompensationRequest(
        container_number=confirm_res.container.container_number if confirm_res.container else "MSCU4920195",
        gross_weight_t=confirm_res.container.gross_weight_t if confirm_res.container else 24.0,
        bay=confirm_res.loaded_position.bay if confirm_res.loaded_position else 2,
        side=confirm_res.loaded_position.side if confirm_res.loaded_position else "PORT",
        tier=confirm_res.loaded_position.tier if confirm_res.loaded_position else 1
    )
    t0 = time.perf_counter()
    ballast_calc = ContainerBallastService.calculate_compensation(ballast_req, ship_instance=ship)
    t1 = time.perf_counter()
    ballast_calc_ms = (t1 - t0) * 1000.0
    measurements["ballast_calculation_ms"] = round(ballast_calc_ms, 2)

    exec_req = BallastExecutionRequest(
        container_number=ballast_req.container_number,
        tank_key=ballast_calc.tank_key or "port_2",
        direction=ballast_calc.direction or "DRAIN",
        qty_t=ballast_calc.required_qty_t,
        operator_confirmed=True
    )
    t0 = time.perf_counter()
    ballast_exec = ContainerBallastService.execute_compensation(exec_req, ship_instance=ship)
    t1 = time.perf_counter()
    ballast_exec_ms = (t1 - t0) * 1000.0
    measurements["ballast_execution_ms"] = round(ballast_exec_ms, 2)

    # 6. Digital Twin State Snapshot & Alert Generation
    t0 = time.perf_counter()
    twin_snap = DigitalTwin.get_vessel_twin_snapshot(ship)
    t1 = time.perf_counter()
    dt_ms = (t1 - t0) * 1000.0
    measurements["digital_twin_snapshot_ms"] = round(dt_ms, 2)

    # Total Workflow Time
    total_ms = (
        ocr_ms + val_ms + opt_ms + load_ms + ballast_calc_ms + ballast_exec_ms + dt_ms
    )
    measurements["total_workflow_ms"] = round(total_ms, 2)

    print("===== MARETIDE PIPELINE BENCHMARK RESULTS =====")
    for k, v in measurements.items():
        print(f"{k:<45}: {v:>8.2f} ms")
    print("===============================================")
    return measurements


if __name__ == "__main__":
    run_benchmark()
