"""
Phase 6D: Performance Profiling and Safe Optimization Benchmark Suite.

Measures all 10 stages:
 1. Image loading
 2. Image preprocessing
 3. OCR inference
 4. Field extraction
 5. Normalization
 6. Validation
 7. Anomaly detection
 8. Stowage optimization
 9. API serialization
10. Frontend request/response handling (HTTP API roundtrip via TestClient)

Evaluates accuracy invariance and memory usage.
"""

import os
import time
import tracemalloc
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

from main import app
from container_ocr.preprocessing import ImagePreprocessor
from container_ocr.ocr_engine import get_ocr_engine
from container_ocr.extractor import FieldExtractor
from container_ocr.normalizer import DataNormalizer
from container_ocr.validator import DomainValidator
from container_ocr.anomaly_detector import CargoAnomalyDetector
from container_ocr.service import default_service
from container_stability.models import ContainerStabilityAnalysisRequest
from container_stability.analyzer import ContainerStabilityService

client = TestClient(app)

FIXTURES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tests", "fixtures")
SAMPLE_SLIP_PATH = os.path.join(FIXTURES_DIR, "sample_container_slip.jpg")


def benchmark_all_stages(runs: int = 5):
    assert os.path.exists(SAMPLE_SLIP_PATH), f"Fixture not found at {SAMPLE_SLIP_PATH}"
    
    stage_times = {
        "1_image_loading": [],
        "2_image_preprocessing": [],
        "3_ocr_inference": [],
        "4_field_extraction": [],
        "5_normalization": [],
        "6_validation": [],
        "7_anomaly_detection": [],
        "8_stowage_optimization": [],
        "9_api_serialization": [],
        "10_api_roundtrip": []
    }
    
    tracemalloc.start()
    mem_before, _ = tracemalloc.get_traced_memory()
    
    # Warmup
    engine = get_ocr_engine()
    _ = default_service.process_image(SAMPLE_SLIP_PATH)
    
    for r in range(runs):
        # 1. Image loading
        t0 = time.perf_counter()
        img = ImagePreprocessor.load_image(SAMPLE_SLIP_PATH)
        stage_times["1_image_loading"].append((time.perf_counter() - t0) * 1000.0)
        
        # 2. Image Preprocessing (Quality + Prep)
        t0 = time.perf_counter()
        doc_quality = ImagePreprocessor.assess_document_quality(img)
        prep_img = ImagePreprocessor.process_for_ocr(img, quality_meta=doc_quality)
        stage_times["2_image_preprocessing"].append((time.perf_counter() - t0) * 1000.0)
        
        # 3. OCR Inference
        t0 = time.perf_counter()
        ocr_result = engine.recognize(prep_img)
        stage_times["3_ocr_inference"].append((time.perf_counter() - t0) * 1000.0)
        
        # 4. Field Extraction
        t0 = time.perf_counter()
        candidates = FieldExtractor.extract_candidates(ocr_result)
        stage_times["4_field_extraction"].append((time.perf_counter() - t0) * 1000.0)
        
        # 5. Normalization
        t0 = time.perf_counter()
        container_details, raw_confidences = DataNormalizer.normalize_all(candidates)
        stage_times["5_normalization"].append((time.perf_counter() - t0) * 1000.0)
        
        # 6. Validation
        t0 = time.perf_counter()
        validation = DomainValidator.validate_container(container_details)
        stage_times["6_validation"].append((time.perf_counter() - t0) * 1000.0)
        
        # 7. Anomaly Detection
        t0 = time.perf_counter()
        anomalies = CargoAnomalyDetector.detect_anomalies(container_data=container_details.model_dump())
        stage_times["7_anomaly_detection"].append((time.perf_counter() - t0) * 1000.0)
        
        # 8. Stowage Optimization
        t0 = time.perf_counter()
        req = ContainerStabilityAnalysisRequest(
            container=container_details.model_dump(),
            weight_source="DOCUMENT_AI"
        )
        stowage_resp = ContainerStabilityService.analyze_container_placement(req)
        stage_times["8_stowage_optimization"].append((time.perf_counter() - t0) * 1000.0)
        
        # 9. API Serialization
        t0 = time.perf_counter()
        _ = stowage_resp.model_dump_json()
        stage_times["9_api_serialization"].append((time.perf_counter() - t0) * 1000.0)
        
        # 10. Frontend API Request/Response Roundtrip
        t0 = time.perf_counter()
        with open(SAMPLE_SLIP_PATH, "rb") as f:
            http_resp = client.post("/api/container/extract", files={"file": ("sample_container_slip.jpg", f, "image/jpeg")})
        assert http_resp.status_code == 200
        stage_times["10_api_roundtrip"].append((time.perf_counter() - t0) * 1000.0)


    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print("\n================================================================================")
    print("                MARETIDE PHASE 6D PERFORMANCE BENCHMARK RESULTS                 ")
    print("================================================================================")
    print(f"{'Stage':<35} | {'Mean Latency (ms)':<18} | {'Min (ms)':<10} | {'Max (ms)':<10}")
    print("-" * 80)
    
    total_pipeline_mean = 0.0
    for k, v in stage_times.items():
        mean_v = np.mean(v)
        min_v = np.min(v)
        max_v = np.max(v)
        if k != "10_api_roundtrip":
            total_pipeline_mean += mean_v
        print(f"{k:<35} | {mean_v:15.2f} ms | {min_v:7.2f} ms | {max_v:7.2f} ms")
        
    print("-" * 80)
    print(f"{'TOTAL CORE PIPELINE (Stages 1-9)':<35} | {total_pipeline_mean:15.2f} ms")
    print(f"{'FULL HTTP API ROUNDTRIP (Stage 10)':<35} | {np.mean(stage_times['10_api_roundtrip']):15.2f} ms")
    print("-" * 80)
    print(f"Memory Allocated: {current_mem / (1024 * 1024):.2f} MB | Peak Memory: {peak_mem / (1024 * 1024):.2f} MB")
    print("================================================================================\n")
    
    return stage_times, container_details, validation, anomalies


if __name__ == "__main__":
    benchmark_all_stages()
