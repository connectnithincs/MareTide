"""
Phase 5 Comprehensive Performance Benchmarking Harness for MareTide.

Measures latency across all key subsystems:
1. Document Upload & Direct Text Parsing
2. Image OCR Preprocessing & Extraction (Synthesized clean slip)
3. Container Data Extraction & Normalization
4. ISO 6346 & VGM Validation
5. Cargo Anomaly Detection
6. Multi-Objective Stability Optimization
7. Ballast Water Compensation Calculation
8. Telemetry Normalization, Validation, & Quality Check
9. Digital Twin Snapshot & Refresh
10. SQLite Audit Event Logging & Retrieval
11. Complete End-to-End Workflow Execution
12. FastAPI HTTP Request/Response Latency
"""

import sys
import os
import time
import json
import statistics
import cv2
import numpy as np
from typing import Dict, List, Any

# Ensure path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import state
from ship import Ship, BallastTank, Container, StabilityAnalyzer
from container_ocr.models import ContainerSlipResponse
from container_ocr.service import default_service
from container_ocr.workflow import ContainerWorkflowEngine, WorkflowState
from container_stability.models import (
    ContainerStabilityAnalysisRequest,
    ContainerLoadingConfirmRequest,
    BallastCompensationRequest,
    BallastExecutionRequest
)
from container_stability.analyzer import (
    ContainerStabilityService,
    ContainerLoadingService,
    ContainerBallastService,
    CargoAnomalyDetector
)
from container_stability.safety_gate import RealTimeSafetyGate
from telemetry.manager import TelemetryManager
from telemetry.models import TelemetrySource, ConnectionStatus, NormalizedTelemetry
from digital_twin import DigitalTwin
from reports.logs_db import (
    init_db,
    clear_logs,
    log_operation_audit_event,
    get_operation_timeline,
    get_recent_operation_summaries
)
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_SLIP_TEXT = """
CONTAINER SHIPPING ORDER
CONTAINER NO: MSCU4920195
TYPE: 40HC
MAX GROSS: 32500 KG
TARE: 3800 KG
CARGO: 22400 KG
GROSS: 26200 KG
DESTINATION: ROTTERDAM
VGM DECLARED: YES
HAZARDOUS: NO
"""


def generate_synthetic_slip_image() -> np.ndarray:
    """Generates an in-memory synthetic container slip image for OCR profiling."""
    img = np.ones((600, 800, 3), dtype=np.uint8) * 255
    cv2.putText(img, "CONTAINER SHIPPING ORDER", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
    cv2.putText(img, "CONTAINER NO: MSCU4920195", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "TYPE: 40HC", (50, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "GROSS: 26200 KG", (50, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "TARE: 3800 KG", (50, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "CARGO: 22400 KG", (50, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "DESTINATION: ROTTERDAM", (50, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return img


def benchmark_subsystems(iterations: int = 50) -> Dict[str, Dict[str, float]]:
    """Runs high-precision micro-benchmarks across all Phase 5 modules."""
    results: Dict[str, List[float]] = {
        "text_parsing_extraction": [],
        "image_ocr_processing": [],
        "anomaly_detection": [],
        "safety_gate_evaluation": [],
        "stability_optimization": [],
        "ballast_calculation": [],
        "telemetry_normalization": [],
        "digital_twin_refresh": [],
        "audit_event_logging": [],
        "audit_timeline_query": [],
        "complete_workflow_e2e": [],
        "api_workflow_initiate": [],
        "api_confirm_loading": [],
        "api_confirm_ballast": []
    }

    synthetic_img = generate_synthetic_slip_image()

    print(f"[*] Starting Phase 5 benchmarking harness ({iterations} iterations per subsystem)...")

    # 1. Text Parsing & Extraction
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = default_service.process_raw_text(SAMPLE_SLIP_TEXT)
        t1 = time.perf_counter()
        results["text_parsing_extraction"].append((t1 - t0) * 1000.0)

    # 2. Image OCR Processing
    for _ in range(min(iterations, 20)):  # OCR is computationally intensive
        t0 = time.perf_counter()
        res = default_service.process_image(synthetic_img)
        t1 = time.perf_counter()
        results["image_ocr_processing"].append((t1 - t0) * 1000.0)

    # 3. Anomaly Detection
    cntr_data = {
        "container_number": "MSCU4920195",
        "container_type": "40HC",
        "weights": {"gross_weight_kg": 26200.0, "tare_weight_kg": 3800.0, "cargo_weight_kg": 22400.0},
        "dimensions": {"length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5}
    }
    ship = state.get_current_ship()
    for _ in range(iterations):
        t0 = time.perf_counter()
        anomalies = CargoAnomalyDetector.detect_anomalies(cntr_data, existing_containers=ship.containers)
        t1 = time.perf_counter()
        results["anomaly_detection"].append((t1 - t0) * 1000.0)

    # 4. Safety Gate Evaluation
    for _ in range(iterations):
        t0 = time.perf_counter()
        gate = RealTimeSafetyGate.evaluate_loading_gate(
            container=cntr_data,
            operator_confirmed=True,
            operator_id="ChiefOfficer"
        )
        t1 = time.perf_counter()
        results["safety_gate_evaluation"].append((t1 - t0) * 1000.0)

    # 5. Stability Optimization
    stab_req = ContainerStabilityAnalysisRequest(
        container=cntr_data,
        document={"processing_status": "success"},
        validation={"valid": True}
    )
    for _ in range(iterations):
        t0 = time.perf_counter()
        stab = ContainerStabilityService.analyze_container_placement(stab_req, ship_instance=ship)
        t1 = time.perf_counter()
        results["stability_optimization"].append((t1 - t0) * 1000.0)

    # 6. Ballast Calculation
    ballast_req = BallastCompensationRequest(
        container_number="MSCU4920195",
        gross_weight_t=26.2,
        bay=2,
        side="PORT",
        tier=1
    )
    for _ in range(iterations):
        t0 = time.perf_counter()
        bal = ContainerBallastService.calculate_compensation(ballast_req, ship_instance=ship)
        t1 = time.perf_counter()
        results["ballast_calculation"].append((t1 - t0) * 1000.0)

    # 7. Telemetry Normalization & Quality Check
    raw_packet = {
        "roll_deg": 1.25,
        "pitch_deg": 0.42,
        "timestamp": time.time(),
        "tanks": {"port_1": {"volume_m3": 300.0, "fill_pct": 60.0}}
    }
    mgr = TelemetryManager.get_instance()
    for _ in range(iterations):
        t0 = time.perf_counter()
        norm = mgr.get_latest_telemetry()
        t1 = time.perf_counter()
        results["telemetry_normalization"].append((t1 - t0) * 1000.0)

    # 8. Digital Twin Refresh
    for _ in range(iterations):
        t0 = time.perf_counter()
        dt_snap = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=norm)
        t1 = time.perf_counter()
        results["digital_twin_refresh"].append((t1 - t0) * 1000.0)

    # 9. Audit Event Logging & Querying
    clear_logs()
    for i in range(iterations):
        t0 = time.perf_counter()
        log_operation_audit_event(
            operation_id="OP-BENCHMARK-001",
            event_type="LOADING",
            container_id="MSCU4920195",
            actor="ChiefOfficer",
            source="OPERATOR",
            relevant_metrics={"gross_weight_t": 26.2, "bay": 2, "side": "PORT"},
            reason="Benchmark test event."
        )
        t1 = time.perf_counter()
        results["audit_event_logging"].append((t1 - t0) * 1000.0)

    for _ in range(iterations):
        t0 = time.perf_counter()
        tl = get_operation_timeline("OP-BENCHMARK-001")
        t1 = time.perf_counter()
        results["audit_timeline_query"].append((t1 - t0) * 1000.0)

    # 10. Complete End-to-End Workflow Execution
    engine = ContainerWorkflowEngine.get_instance()
    for _ in range(iterations):
        state.reset_state()
        engine.reset()
        t0 = time.perf_counter()
        session = engine.initiate_workflow_from_text(SAMPLE_SLIP_TEXT)
        op_id = session.operation_id
        session = engine.confirm_load_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
        if session.current_state == WorkflowState.AWAITING_BALLAST_CONFIRMATION:
            session = engine.confirm_ballast_step(op_id, operator_id="ChiefOfficer", operator_confirmed=True)
        t1 = time.perf_counter()
        results["complete_workflow_e2e"].append((t1 - t0) * 1000.0)

    # 11. REST API Endpoints Latency
    for _ in range(iterations):
        state.reset_state()
        engine.reset()
        
        t0 = time.perf_counter()
        res_init = client.post("/api/container/workflow/initiate-text", json={"raw_text": SAMPLE_SLIP_TEXT})
        t1 = time.perf_counter()
        results["api_workflow_initiate"].append((t1 - t0) * 1000.0)
        
        op_id = res_init.json()["operation_id"]
        
        t0 = time.perf_counter()
        res_load = client.post(
            "/api/container/workflow/confirm-load",
            json={"operation_id": op_id, "operator_id": "ChiefOfficer", "operator_confirmed": True}
        )
        t1 = time.perf_counter()
        results["api_confirm_loading"].append((t1 - t0) * 1000.0)

        t0 = time.perf_counter()
        res_bal = client.post(
            "/api/container/workflow/confirm-ballast",
            json={"operation_id": op_id, "operator_id": "ChiefOfficer", "operator_confirmed": True}
        )
        t1 = time.perf_counter()
        results["api_confirm_ballast"].append((t1 - t0) * 1000.0)

    # Compile Summary Statistics
    summary: Dict[str, Dict[str, float]] = {}
    for k, v in results.items():
        if v:
            summary[k] = {
                "mean_ms": round(statistics.mean(v), 3),
                "median_ms": round(statistics.median(v), 3),
                "p95_ms": round(np.percentile(v, 95), 3),
                "min_ms": round(min(v), 3),
                "max_ms": round(max(v), 3),
                "samples": len(v)
            }

    return summary


if __name__ == "__main__":
    report = benchmark_subsystems(iterations=50)
    print("\n" + "=" * 80)
    print("PHASE 5 PERFORMANCE BENCHMARK REPORT (BASELINE)")
    print("=" * 80)
    print(f"{'Subsystem / Operation':<35} | {'Mean (ms)':<10} | {'Median (ms)':<11} | {'P95 (ms)':<10} | {'Min (ms)':<9} | {'Max (ms)':<9}")
    print("-" * 80)
    for k, v in report.items():
        print(f"{k:<35} | {v['mean_ms']:<10.3f} | {v['median_ms']:<11.3f} | {v['p95_ms']:<10.3f} | {v['min_ms']:<9.3f} | {v['max_ms']:<9.3f}")
    print("=" * 80)

    # Save to json file
    with open("benchmark_results.json", "w") as f:
        json.dump(report, f, indent=2)
    print("[+] Benchmark results saved to benchmark_results.json")
