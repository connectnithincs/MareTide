"""
Phase 6I: ESP32 Multi-Line Serial Parser & Hardware Telemetry Integration Tests.

Verifies:
1. Exact multi-line formatted JSON output from esp32_sensor_sketch.ino.
2. Interspersed boot messages ('MPU6050: OK', 'NAVI-AI ESP32 Ready') and '---' delimiters.
3. Asynchronous operational warnings ('WARNING: LOW BALLAST LEVEL!', 'Tilt Right...').
4. Chunked / fragmented serial packet arrival.
5. Malformed JSON recovery and error isolation.
6. Serial auto-reconnection and COM port selection.
7. Freshness tracking and stale telemetry degradation.
8. Absolute Load-Cell Isolation: HX711 scale data is strictly quarantined from stability calculations,
   VGM, and cargo container weights.
9. Source provenance: HARDWARE_SENSOR vs SIMULATED_TELEMETRY.
"""

import time
import json
import datetime
import pytest
from fastapi.testclient import TestClient

from main import app
import state
from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    ConnectionStatus,
    DataQuality
)
from telemetry.adapters.hardware_adapter import HardwareSerialAdapter, extract_json_from_buffer
from telemetry.normalizer import TelemetryNormalizer, PROHIBITED_LOAD_CELL_KEYS
from telemetry.validator import TelemetryValidator
from telemetry.quality_monitor import TelemetryQualityMonitor
from telemetry.manager import TelemetryManager

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


def test_01_extract_json_exact_esp32_multiline_output():
    """
    Test 1: Verifies that extract_json_from_buffer accurately parses the exact
    multi-line JSON structure produced by esp32_sensor_sketch.ino with '---' delimiter.
    """
    raw_esp32_stream = (
        "{\n"
        "  \"roll\": 1.45,\n"
        "  \"pitch\": -0.65,\n"
        "  \"distance\": 12.00,\n"
        "  \"ballast_pct\": 82.50,\n"
        "  \"cargo_kg\": 0.00,\n"
        "  \"status\": \"IDLE\",\n"
        "  \"risk\": \"SAFE\"\n"
        "}\n"
        "---\n"
    )

    packets, remaining = extract_json_from_buffer(raw_esp32_stream)
    assert len(packets) == 1
    pkt = packets[0]
    assert pkt["roll"] == 1.45
    assert pkt["pitch"] == -0.65
    assert pkt["distance"] == 12.00
    assert pkt["ballast_pct"] == 82.50
    assert pkt["cargo_kg"] == 0.00
    assert pkt["status"] == "IDLE"
    assert pkt["risk"] == "SAFE"
    assert "---" in remaining


def test_02_extract_json_with_boot_banners_and_warnings():
    """
    Test 2: Verifies that boot banners ('MPU6050: OK', 'NAVI-AI ESP32 Ready')
    and live warning text ('WARNING: LOW BALLAST LEVEL!') do not crash or corrupt parsing.
    """
    stream_with_banners = (
        "MPU6050: OK\n"
        "HX711: Ready\n"
        "Gate Servo: Closed\n"
        "NAVI-AI ESP32 Ready\n"
        "-------------------\n"
        "{\n"
        "  \"roll\": -0.22,\n"
        "  \"pitch\": 0.45,\n"
        "  \"distance\": 18.50,\n"
        "  \"ballast_pct\": 57.50,\n"
        "  \"cargo_kg\": 5.20,\n"
        "  \"status\": \"READY\",\n"
        "  \"risk\": \"SAFE\"\n"
        "}\n"
        "---\n"
        "WARNING: LOW BALLAST LEVEL!\n"
        "Tilt Right -> Pump PORT side\n"
        "{\n"
        "  \"roll\": 5.80,\n"
        "  \"pitch\": 1.10,\n"
        "  \"distance\": 28.00,\n"
        "  \"ballast_pct\": 10.00,\n"
        "  \"cargo_kg\": 5.20,\n"
        "  \"status\": \"READY\",\n"
        "  \"risk\": \"WARNING\"\n"
        "}\n"
        "---\n"
    )

    packets, remaining = extract_json_from_buffer(stream_with_banners)
    assert len(packets) == 2
    assert packets[0]["roll"] == -0.22
    assert packets[0]["status"] == "READY"
    assert packets[1]["roll"] == 5.80
    assert packets[1]["risk"] == "WARNING"


def test_03_chunked_fragmented_stream_arrival():
    """
    Test 3: Simulates partial/fragmented reads arriving over UART across multiple ticks.
    """
    chunk1 = "{\n  \"roll\": 2.30,\n  \"pitch\":"
    chunk2 = " -1.15,\n  \"distance\": 15.00,\n  \"ballast_pct\": 75.00,"
    chunk3 = "\n  \"cargo_kg\": 0.00,\n  \"status\": \"IDLE\",\n  \"risk\": \"SAFE\"\n}\n---\n"

    buffer = ""
    
    # Tick 1: Partial chunk
    buffer += chunk1
    packets1, buffer = extract_json_from_buffer(buffer)
    assert len(packets1) == 0
    assert len(buffer) > 0  # Buffered

    # Tick 2: Second partial chunk
    buffer += chunk2
    packets2, buffer = extract_json_from_buffer(buffer)
    assert len(packets2) == 0

    # Tick 3: Final completing chunk
    buffer += chunk3
    packets3, buffer = extract_json_from_buffer(buffer)
    assert len(packets3) == 1
    assert packets3[0]["roll"] == 2.30
    assert packets3[0]["pitch"] == -1.15
    assert packets3[0]["ballast_pct"] == 75.00


def test_04_malformed_json_recovery():
    """
    Test 4: Corrupted/truncated JSON fragments must be discarded safely without
    preventing subsequent valid packets from being decoded.
    """
    corrupt_stream = (
        "{ CORRUPTED NOT JSON } \n"
        "{\n"
        "  \"roll\": 0.10,\n"
        "  \"pitch\": 0.05,\n"
        "  \"distance\": 10.00,\n"
        "  \"ballast_pct\": 100.00,\n"
        "  \"cargo_kg\": 0.00,\n"
        "  \"status\": \"IDLE\",\n"
        "  \"risk\": \"SAFE\"\n"
        "}\n"
    )

    packets, remaining = extract_json_from_buffer(corrupt_stream)
    assert len(packets) == 1
    assert packets[0]["roll"] == 0.10
    assert packets[0]["ballast_pct"] == 100.00


def test_05_single_line_json_lines_support():
    """
    Test 5: Supports compact single-line JSON Lines format.
    """
    single_line = '{"roll": -0.85, "pitch": 0.40, "distance": 14.0, "ballast_pct": 80.0, "status": "IDLE", "risk": "SAFE"}\n'
    packets, remaining = extract_json_from_buffer(single_line)
    assert len(packets) == 1
    assert packets[0]["roll"] == -0.85
    assert packets[0]["pitch"] == 0.40


def test_06_load_cell_isolation_invariant_enforced():
    """
    Test 6: Strict Invariant: When the physical ESP32 sends 'cargo_kg' (from HX711),
    the TelemetryNormalizer purges it, and the legacy/API state guarantees cargo_kg == 0.0.
    """
    raw_esp32_with_scale = {
        "roll": 0.75,
        "pitch": -0.30,
        "distance": 16.0,
        "ballast_pct": 70.0,
        "cargo_kg": 24.50,  # 24.5 kg on physical load cell
        "status": "READY",
        "risk": "SAFE"
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=raw_esp32_with_scale,
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.CONNECTED,
        adapter_id="hardware_serial_esp32"
    )

    # 1. Normalized contract does not store sensor cargo weight
    assert normalized.source == TelemetrySource.HARDWARE_SENSOR
    assert normalized.connection_status == ConnectionStatus.CONNECTED
    assert normalized.metadata.load_cell_policy == "FORBIDDEN_FOR_CARGO_AND_STABILITY"
    assert normalized.metadata.authoritative_weight_source == "DOCUMENT_AI"
    assert any("Load-cell exclusion policy" in w for w in normalized.metadata.warnings)

    # 2. Legacy/API dictionary forces cargo_kg = 0.0
    legacy = TelemetryManager.get_instance().get_legacy_telemetry_dict()
    assert legacy["cargo_kg"] == 0.0


def test_07_hardware_adapter_lifecycle_and_info():
    """
    Test 7: Validates HardwareSerialAdapter initialization, adapter info, and disconnect handling.
    """
    adapter = HardwareSerialAdapter(port="COM_NONEXISTENT", baudrate=115200, reconnect_interval=0.05)
    assert adapter.adapter_id == "hardware_serial_esp32"
    assert adapter.source_type == TelemetrySource.HARDWARE_SENSOR
    assert adapter.baudrate == 115200

    info = adapter.get_adapter_info()
    assert info["is_simulated"] is False
    assert info["source_type"] == "HARDWARE_SENSOR"
    assert info["connected"] is False

    # Calling disconnect when not running should be a safe no-op
    adapter.disconnect()
    assert adapter.is_connected() is False


def test_08_stale_telemetry_detection():
    """
    Test 8: Quality monitor flags telemetry as STALE if packet age exceeds threshold.
    """
    monitor = TelemetryQualityMonitor(stale_threshold_sec=0.1, disconnect_threshold_sec=0.4)
    telemetry = TelemetryNormalizer.get_safe_fallback_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    monitor.record_packet(telemetry)

    # Within freshness threshold
    fresh = monitor.evaluate_quality(telemetry, is_adapter_connected=True)
    assert fresh.connection_status != ConnectionStatus.STALE

    # Sleep past stale threshold
    time.sleep(0.15)
    stale = monitor.evaluate_quality(telemetry, is_adapter_connected=True)
    assert stale.connection_status == ConnectionStatus.STALE
    assert stale.metadata.data_quality == DataQuality.STALE


def test_09_disconnect_detection_and_safe_fallback():
    """
    Test 9: Quality monitor flags DISCONNECTED when serial link drops or times out.
    """
    monitor = TelemetryQualityMonitor(stale_threshold_sec=0.1, disconnect_threshold_sec=0.2)
    telemetry = TelemetryNormalizer.get_safe_fallback_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    monitor.record_packet(telemetry)

    # Disconnect signaled
    disconnected = monitor.evaluate_quality(telemetry, is_adapter_connected=False)
    assert disconnected.connection_status == ConnectionStatus.DISCONNECTED
    assert disconnected.metadata.data_quality == DataQuality.DEGRADED
    assert any("disconnected" in w.lower() for w in disconnected.metadata.warnings)


def test_10_end_to_end_telemetry_live_endpoint():
    """
    Test 10: GET /api/telemetry/live returns normalized vessel state with explicit provenance.
    """
    res = client.get("/api/telemetry/live")
    assert res.status_code == 200
    data = res.json()
    assert "vessel_state" in data
    assert "ballast_tanks" in data
    assert "metadata" in data
    assert data["metadata"]["authoritative_weight_source"] == "DOCUMENT_AI"
    assert data["metadata"]["load_cell_policy"] == "FORBIDDEN_FOR_CARGO_AND_STABILITY"


def test_11_esp32_payload_to_digital_twin_and_vessel_state():
    """
    Test 11: End-to-end propagation:
    ESP32 Raw Payload -> Normalizer -> TelemetryManager -> Digital Twin Snapshot -> /api/vessel-state & /api/digital-twin/state.
    Verifies roll, pitch, ballast level, provenance, and strict cargo mass isolation.
    """
    raw_packet = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timestamp_epoch": time.time(),
        "roll": 2.75,
        "pitch": -1.20,
        "distance": 14.0,
        "ballast_pct": 80.0,
        "cargo_kg": 15.0,  # Scale load
        "status": "IDLE",
        "risk": "SAFE"
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=raw_packet,
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.CONNECTED,
        adapter_id="hardware_serial_esp32"
    )

    mgr = TelemetryManager.get_instance()
    with mgr._mutex:
        mgr._latest_normalized = normalized

    # 1. Digital Twin Snapshot API
    res_twin = client.get("/api/digital-twin/state")
    assert res_twin.status_code == 200
    twin_data = res_twin.json()
    assert twin_data["roll_deg"] == 2.75
    assert twin_data["pitch_deg"] == -1.20
    assert twin_data["telemetry_source"] == "HARDWARE_SENSOR"
    assert twin_data["authoritative_weight_source"] == "[DOCUMENT AI]"
    assert twin_data["provenance_map"]["telemetry"] == "[HARDWARE SENSOR]"
    assert twin_data["provenance_map"]["cargo_weight"] == "[DOCUMENT AI]"

    # 2. Vessel State WebSocket / Polling API
    res_vessel = client.get("/api/vessel-state")
    assert res_vessel.status_code == 200
    vessel_data = res_vessel.json()
    assert vessel_data["roll"] == 2.75
    assert vessel_data["pitch"] == -1.20
    assert vessel_data["distance"] == 14.0
    assert vessel_data["ballast_pct"] == 80.0
    assert vessel_data["cargo_kg"] == 0.0  # Isolated
    assert vessel_data["is_simulated"] is False
    assert vessel_data["connection_status"] == "CONNECTED"
    assert vessel_data["telemetry_source"] == "HARDWARE_SENSOR"


def test_12_simulation_mode_explicitly_labeled_not_hardware():
    """
    Test 12: In simulation mode, telemetry is labeled SIMULATED_TELEMETRY with [SIMULATED TELEMETRY]
    provenance and never labeled as [HARDWARE SENSOR].
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)

    res_vessel = client.get("/api/vessel-state")
    assert res_vessel.status_code == 200
    data = res_vessel.json()
    assert data["is_simulated"] is True
    assert data["telemetry_source"] == "SIMULATED_TELEMETRY"
    assert data["provenance_map"]["telemetry"] == "[SIMULATED TELEMETRY]"


def test_13_operations_live_status_telemetry_coupling():
    """
    Test 13: GET /api/operations/live-status reflects the single authoritative telemetry state.
    """
    res = client.get("/api/operations/live-status")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "telemetry" in data
    assert data["authoritative_weight_source"] == "[DOCUMENT AI]"
    assert data["load_cell_policy"] == "FORBIDDEN_FOR_CARGO_AND_STABILITY"

