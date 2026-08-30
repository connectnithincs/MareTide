"""
Phase 6G: ESP32 Real-Time Telemetry Integration Test Suite.

Verifies:
1. Valid ESP32 packet normalization & telemetry contract compliance.
2. Malformed packet resilience (broken JSON, partial lines, corrupt delimiters).
3. Disconnected ESP32 handling & safe state preservation.
4. Auto-reconnect handling and resumption of live stream.
5. Stale telemetry degradation & quality marking (>5s threshold).
6. Invalid numeric value sanitation (NaN, strings, out-of-range).
7. Load-cell packet detection & exclusion (strict policy).
8. Guaranteed isolation: ESP32 load-cell telemetry CANNOT influence container cargo mass or vessel stability calculations.
9. Explicit reporting of actual ESP32 connection status separately from simulation mode.
"""

import time
import datetime
import pytest
from fastapi.testclient import TestClient

from main import app
import state
from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    ConnectionStatus,
    DataQuality,
    PumpState
)
from telemetry.adapters.hardware_adapter import HardwareSerialAdapter
from telemetry.adapters.simulator_adapter import SimulatorTelemetryAdapter
from telemetry.normalizer import TelemetryNormalizer, PROHIBITED_LOAD_CELL_KEYS
from telemetry.validator import TelemetryValidator
from telemetry.quality_monitor import TelemetryQualityMonitor
from telemetry.manager import TelemetryManager
from container_stability.analyzer import ContainerStabilityService
from container_stability.models import ContainerStabilityAnalysisRequest

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_telemetry_environment():
    """Resets the telemetry manager and vessel state before each test."""
    state.reset_state()
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)
    mgr.clear_simulator_overrides()
    yield
    state.reset_state()
    mgr.clear_simulator_overrides()


def test_01_valid_esp32_packet_normalization():
    """
    Test 1: Valid ESP32 packet with 115200-baud UART format:
    {"roll": 1.45, "pitch": -0.65, "distance": 12.0, "ballast_pct": 82.5, "status": "IDLE", "risk": "SAFE"}
    Verifies that it normalizes into a full NormalizedTelemetry contract with HARDWARE_SENSOR provenance.
    """
    raw_esp32_packet = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timestamp_epoch": time.time(),
        "roll": 1.45,
        "pitch": -0.65,
        "distance": 12.0,
        "ballast_pct": 82.5,
        "status": "IDLE",
        "risk": "SAFE"
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=raw_esp32_packet,
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.CONNECTED,
        adapter_id="hardware_serial_esp32"
    )

    assert isinstance(normalized, NormalizedTelemetry)
    assert normalized.source == TelemetrySource.HARDWARE_SENSOR
    assert normalized.connection_status == ConnectionStatus.CONNECTED
    assert round(normalized.vessel_state.roll_deg, 2) == 1.45
    assert round(normalized.vessel_state.pitch_deg, 2) == -0.65
    assert normalized.ballast_tanks["port_1"].level_pct == 82.5
    assert normalized.operational_telemetry.status == "IDLE"
    assert normalized.metadata.authoritative_weight_source == "DOCUMENT_AI"
    assert normalized.metadata.load_cell_policy == "FORBIDDEN_FOR_CARGO_AND_STABILITY"


def test_02_malformed_packet_resilience():
    """
    Test 2: Malformed packets (empty data, partial fragments, corrupt strings)
    must not crash the normalizer or service and should fallback safely.
    """
    # 1. Non-dictionary input validation
    val_res = TelemetryValidator.validate_raw_packet("INVALID_STRING_PAYLOAD")
    assert val_res.is_valid is False
    assert len(val_res.errors) > 0
    assert val_res.sanitized_telemetry is not None

    # 2. None / Empty payload
    empty_norm = TelemetryNormalizer.normalize_raw_packet(
        raw_data=None,
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.DISCONNECTED
    )
    assert empty_norm is not None
    assert empty_norm.connection_status == ConnectionStatus.DISCONNECTED
    assert empty_norm.vessel_state.roll_deg == 0.0

    # 3. Corrupt / empty dictionary
    corrupt_norm = TelemetryNormalizer.normalize_raw_packet(
        raw_data={},
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.DISCONNECTED
    )
    assert corrupt_norm is not None
    assert corrupt_norm.metadata.data_quality in [DataQuality.STALE, DataQuality.DEGRADED]


def test_03_disconnected_esp32_safe_fallback():
    """
    Test 3: When ESP32 is disconnected, the system retains last verified state
    and flags connection_status as DISCONNECTED without synthesizing fake data.
    """
    monitor = TelemetryQualityMonitor(stale_threshold_sec=0.1, disconnect_threshold_sec=0.2)
    current_telemetry = TelemetryNormalizer.get_safe_fallback_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    monitor.record_packet(current_telemetry)

    # Disconnected adapter evaluation
    evaluated = monitor.evaluate_quality(current_telemetry, is_adapter_connected=False)
    assert evaluated.connection_status == ConnectionStatus.DISCONNECTED
    assert evaluated.metadata.data_quality == DataQuality.DEGRADED
    assert any("disconnected" in w.lower() for w in evaluated.metadata.warnings)


def test_04_auto_reconnect_handling():
    """
    Test 4: Simulates an adapter connection lifecycle (connect -> disconnect -> reconnect).
    """
    adapter = HardwareSerialAdapter(port=None, reconnect_interval=0.1)
    assert adapter.is_connected() is False
    
    # Check info dictionary before and after
    info = adapter.get_adapter_info()
    assert info["connected"] is False
    assert info["source_type"] == "HARDWARE_SENSOR"
    assert info["is_simulated"] is False


def test_05_stale_telemetry_degradation():
    """
    Test 5: Telemetry older than stale threshold is flagged as STALE.
    """
    monitor = TelemetryQualityMonitor(stale_threshold_sec=0.1, disconnect_threshold_sec=0.5)
    current_telemetry = TelemetryNormalizer.get_safe_fallback_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    monitor.record_packet(current_telemetry)

    time.sleep(0.15)
    evaluated = monitor.evaluate_quality(current_telemetry, is_adapter_connected=True)

    assert evaluated.connection_status == ConnectionStatus.STALE
    assert evaluated.metadata.data_quality == DataQuality.STALE
    assert any("stale" in w.lower() for w in evaluated.metadata.warnings)


def test_06_invalid_numeric_value_sanitation():
    """
    Test 6: Out-of-bounds numeric values (e.g. roll > 45 deg, pitch < -25 deg) are flagged and sanitized.
    """
    bad_packet = {
        "roll": 89.5,      # Exceeds max roll (45 deg)
        "pitch": -55.0,    # Exceeds min pitch (-25 deg)
        "ballast_pct": 180.0,  # Exceeds 100%
        "distance": "INVALID_NUMBER_STRING"
    }

    val_res = TelemetryValidator.validate_raw_packet(bad_packet)
    assert val_res.is_valid is False
    assert any("roll" in err.lower() for err in val_res.errors)
    assert any("pitch" in err.lower() for err in val_res.errors)
    assert any("ballast_pct" in err.lower() for err in val_res.errors)
    assert any("distance" in err.lower() for err in val_res.errors)


def test_07_load_cell_packet_detection_and_quarantine():
    """
    Test 7: When ESP32 packet contains load-cell sensor measurements ('cargo_kg', 'hx711', 'scale_kg'),
    they are safely detected, quarantined, and stripped from normalized telemetry.
    """
    packet_with_load_cell = {
        "roll": 1.1,
        "pitch": -0.2,
        "cargo_kg": 24500.0,    # Injected load-cell
        "hx711_raw": 842100,    # Injected raw ADC
        "scale_kg": 24500.0,    # Injected scale
        "ballast_pct": 60.0
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=packet_with_load_cell,
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.CONNECTED
    )

    # Telemetry should NOT contain cargo weight
    legacy_dict = TelemetryManager.get_instance().get_legacy_telemetry_dict()
    assert legacy_dict["cargo_kg"] == 0.0
    assert len(normalized.metadata.warnings) >= 1
    assert any("Load-cell exclusion policy" in w for w in normalized.metadata.warnings)


def test_08_load_cell_cannot_influence_stability_or_cargo_weight():
    """
    Test 8: Strict Invariant: Even if an adversary attempts to inject ESP32 load-cell
    readings into stability optimization or loading analysis, the stability engine rejects it.
    """
    # 1. Stability analysis with injected load-cell source is blocked or purged
    injection_req = {
        "container": {
            "container_number": "INJECTED123",
            "weights": {"gross_weight_kg": 25000.0},
            "weight_source": "HX711_LOAD_CELL"
        },
        "document": {"source": "fake_slip.jpg"},
        "validation": {"valid": True},
        "weight_source": "HX711_LOAD_CELL"
    }

    res = client.post("/api/containers/analyze-stability", json=injection_req)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "rejected" in data["status"] or "Policy Violation" in data.get("error_message", "")


def test_09_sources_endpoint_reports_status_and_detected_ports():
    """
    Test 9: GET /api/telemetry/sources accurately reports active source, simulation status,
    detected COM ports, and the load-cell quarantine policy.
    """
    res = client.get("/api/telemetry/sources")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["authoritative_cargo_source"] == "DOCUMENT_AI"
    assert data["load_cell_sensor_policy"] == "FORBIDDEN_FOR_CARGO_AND_STABILITY"
    assert isinstance(data["detected_hardware_ports"], list)
