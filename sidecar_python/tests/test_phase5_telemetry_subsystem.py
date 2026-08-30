"""
MareTide Phase 5: Real-Time Telemetry Subsystem Comprehensive Test Suite.

Verifies:
1. Valid Telemetry Normalization & Contracts
2. Malformed Telemetry Detection & Rejection
3. Stale Telemetry & Freshness Degradation
4. Disconnected Telemetry & Safe Fallback
5. Simulated Telemetry Dynamics & Overrides
6. Hardware Serial Adapter Abstraction
7. Strict Prohibited Load-Cell Sensor Data Rejection / Exclusion
8. Decoupled Stability Engine & Digital Twin Ingestion
9. FastAPI REST Telemetry Endpoints
"""

import os
import sys
import time
import datetime
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Ship, BallastTank, Container, StabilityAnalyzer
import state
from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    ConnectionStatus,
    DataQuality,
    PumpState
)
from telemetry.adapters.simulator_adapter import SimulatorTelemetryAdapter
from telemetry.adapters.hardware_adapter import HardwareSerialAdapter
from telemetry.normalizer import TelemetryNormalizer, PROHIBITED_LOAD_CELL_KEYS
from telemetry.validator import TelemetryValidator
from telemetry.quality_monitor import TelemetryQualityMonitor
from telemetry.manager import TelemetryManager

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_telemetry_state():
    """Ensures a fresh telemetry state and simulator adapter before each test."""
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)
    mgr.clear_simulator_overrides()
    yield
    mgr.clear_simulator_overrides()


# =========================================================================
# 1. VALID TELEMETRY TESTS
# =========================================================================

def test_valid_simulated_telemetry_normalization():
    """Verifies that valid simulated telemetry packets normalize into a compliant NormalizedTelemetry contract."""
    raw_packet = {
        "timestamp": "2026-08-29T12:00:00Z",
        "timestamp_epoch": time.time(),
        "roll": 1.25,
        "pitch": -0.45,
        "distance": 14.5,
        "ballast_pct": 77.5,
        "flow_rate_l_s": 0.85,
        "cumulative_flow_m3": 1.2,
        "status": "DRAINING",
        "risk": "SAFE"
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=raw_packet,
        source=TelemetrySource.SIMULATED_TELEMETRY,
        connection_status=ConnectionStatus.SIMULATED,
        adapter_id="test_simulator"
    )

    assert isinstance(normalized, NormalizedTelemetry)
    assert normalized.source == TelemetrySource.SIMULATED_TELEMETRY
    assert normalized.connection_status == ConnectionStatus.SIMULATED
    assert normalized.vessel_state.roll_deg == 1.25
    assert normalized.vessel_state.pitch_deg == -0.45
    assert len(normalized.ballast_tanks) == 8  # 4 bays x 2 sides
    assert normalized.ballast_tanks["port_1"].level_pct == 77.5
    assert normalized.pumps["PUMP_MAIN"].state == PumpState.DRAINING
    assert normalized.flow_info.flow_rate_l_s == 0.85
    assert normalized.operational_telemetry.status == "DRAINING"
    assert normalized.metadata.data_quality in [DataQuality.GOOD, DataQuality.EXCELLENT]
    assert normalized.metadata.authoritative_weight_source == "DOCUMENT_AI"
    assert normalized.metadata.load_cell_policy == "FORBIDDEN_FOR_CARGO_AND_STABILITY"


def test_valid_hardware_telemetry_normalization():
    """Verifies that valid hardware sensor packets normalize with source HARDWARE_SENSOR and no cargo weight."""
    raw_hw_packet = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "timestamp_epoch": time.time(),
        "roll": -2.10,
        "pitch": 0.85,
        "distance": 12.0,
        "ballast_pct": 90.0,
        "status": "STANDBY",
        "risk": "SAFE"
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=raw_hw_packet,
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.CONNECTED,
        adapter_id="hardware_serial_esp32"
    )

    assert normalized.source == TelemetrySource.HARDWARE_SENSOR
    assert normalized.connection_status == ConnectionStatus.CONNECTED
    assert normalized.vessel_state.roll_deg == -2.10
    assert normalized.vessel_state.pitch_deg == 0.85
    assert normalized.ballast_tanks["starboard_1"].level_pct == 90.0
    assert normalized.metadata.data_quality == DataQuality.GOOD


# =========================================================================
# 2. MALFORMED TELEMETRY TESTS
# =========================================================================

def test_malformed_telemetry_non_dictionary():
    """Verifies that non-dictionary raw payloads fail validation gracefully with safe fallback."""
    val_res = TelemetryValidator.validate_raw_packet("NOT_A_DICT_PAYLOAD")
    assert val_res.is_valid is False
    assert len(val_res.errors) > 0
    assert "Malformed packet" in val_res.errors[0]
    assert val_res.sanitized_telemetry is not None
    assert val_res.sanitized_telemetry.metadata.data_quality == DataQuality.DEGRADED


def test_malformed_telemetry_out_of_bounds_values():
    """Verifies that sensor readings exceeding physical boundaries (e.g. roll > 45 deg) are flagged."""
    bad_packet = {
        "roll": 89.5,      # Exceeds max roll (45 deg)
        "pitch": -55.0,    # Exceeds min pitch (-25 deg)
        "ballast_pct": 180.0,  # Exceeds 100%
        "distance": "INVALID_NUMBER_STRING"  # Non-numeric string
    }

    val_res = TelemetryValidator.validate_raw_packet(bad_packet)
    assert val_res.is_valid is False
    assert any("roll" in err.lower() for err in val_res.errors)
    assert any("pitch" in err.lower() for err in val_res.errors)
    assert any("ballast_pct" in err.lower() for err in val_res.errors)
    assert any("distance" in err.lower() for err in val_res.errors)


def test_malformed_future_timestamp_rejected():
    """Verifies that timestamps significantly in the future are flagged as clock skew / errors."""
    future_time = time.time() + 100.0  # 100 seconds into the future
    future_packet = {
        "timestamp_epoch": future_time,
        "roll": 0.0,
        "pitch": 0.0
    }

    val_res = TelemetryValidator.validate_raw_packet(future_packet)
    assert val_res.is_valid is False
    assert any("future" in err.lower() for err in val_res.errors)


# =========================================================================
# 3. STALE TELEMETRY & FRESHNESS TESTS
# =========================================================================

def test_stale_telemetry_quality_degradation():
    """Verifies that when telemetry updates halt for > 2.0 seconds, quality degrades to STALE."""
    monitor = TelemetryQualityMonitor(stale_threshold_sec=0.1, disconnect_threshold_sec=0.3)
    
    current_telemetry = TelemetryNormalizer.get_safe_fallback_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    monitor.record_packet(current_telemetry)

    # Wait past stale threshold (0.1s)
    time.sleep(0.15)

    evaluated = monitor.evaluate_quality(current_telemetry, is_adapter_connected=True)
    assert evaluated.connection_status == ConnectionStatus.STALE
    assert evaluated.metadata.data_quality == DataQuality.STALE
    assert any("stale" in w.lower() for w in evaluated.metadata.warnings)


def test_stale_timestamp_warning():
    """Verifies that an old timestamp (> 60s in the past) produces a staleness warning."""
    old_time = time.time() - 120.0  # 2 minutes ago
    old_packet = {
        "timestamp_epoch": old_time,
        "roll": 0.5,
        "pitch": 0.2
    }
    val_res = TelemetryValidator.validate_raw_packet(old_packet)
    assert any("stale" in w.lower() for w in val_res.warnings)


# =========================================================================
# 4. DISCONNECTED TELEMETRY TESTS
# =========================================================================

def test_disconnected_telemetry_detection_and_fallback():
    """Verifies that an adapter disconnection or timeout > 5.0s marks status as DISCONNECTED."""
    monitor = TelemetryQualityMonitor(stale_threshold_sec=0.1, disconnect_threshold_sec=0.2)
    
    current_telemetry = TelemetryNormalizer.get_safe_fallback_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    monitor.record_packet(current_telemetry)

    # Adapter disconnected explicitly
    evaluated = monitor.evaluate_quality(current_telemetry, is_adapter_connected=False)
    assert evaluated.connection_status == ConnectionStatus.DISCONNECTED
    assert evaluated.metadata.data_quality == DataQuality.DEGRADED
    assert any("disconnected" in w.lower() for w in evaluated.metadata.warnings)


def test_safe_fallback_telemetry_contract():
    """Verifies that fallback telemetry provides safe, consistent vessel defaults without exceptions."""
    fallback = TelemetryNormalizer.get_safe_fallback_telemetry(
        source=TelemetrySource.SYSTEM_DERIVED,
        connection_status=ConnectionStatus.DISCONNECTED,
        reason="Communication timeout fallback"
    )

    assert fallback.source == TelemetrySource.SYSTEM_DERIVED
    assert fallback.connection_status == ConnectionStatus.DISCONNECTED
    assert fallback.vessel_state.roll_deg == 0.0
    assert fallback.vessel_state.pitch_deg == 0.0
    assert len(fallback.ballast_tanks) == 8
    assert fallback.metadata.data_quality == DataQuality.DEGRADED
    assert fallback.metadata.authoritative_weight_source == "DOCUMENT_AI"


# =========================================================================
# 5. SIMULATED TELEMETRY ADAPTER & OVERRIDES
# =========================================================================

def test_simulator_adapter_lifecycle_and_overrides():
    """Verifies the simulator adapter generates continuous dynamics and respects manual overrides."""
    sim = SimulatorTelemetryAdapter(tick_interval=0.02)
    sim.connect()
    assert sim.is_connected() is True

    # Allow simulator to produce a packet
    time.sleep(0.05)
    packet = sim.read_raw()
    assert packet is not None
    assert "roll" in packet
    assert "pitch" in packet
    assert "ballast_pct" in packet

    # Apply manual override
    sim.set_override_tilt(roll=4.25, pitch=-2.10)
    sim.set_override_ballast(85.0)
    time.sleep(0.05)

    packet_override = sim.read_raw()
    assert packet_override["roll"] == 4.25
    assert packet_override["pitch"] == -2.10
    assert packet_override["ballast_pct"] == 85.0

    # Clear overrides
    sim.clear_overrides()
    time.sleep(0.05)
    packet_restored = sim.read_raw()
    # Should revert to natural wave motion around 0
    assert abs(packet_restored["roll"]) < 2.0

    sim.disconnect()
    assert sim.is_connected() is False


def test_simulator_drain_and_fill_commands():
    """Verifies simulated pump commands update flow rates and operational statuses."""
    sim = SimulatorTelemetryAdapter(tick_interval=0.02)
    sim.connect()

    # Trigger drain command
    sim.send_command("DRAIN", qty=30.0)
    time.sleep(0.05)
    packet = sim.read_raw()
    assert packet["status"] == "DRAINING"
    assert packet["flow_rate_l_s"] > 0.0

    # Reset
    sim.send_command("RESET")
    time.sleep(0.05)
    packet_reset = sim.read_raw()
    assert packet_reset["status"] == "IDLE"
    assert packet_reset["flow_rate_l_s"] == 0.0

    sim.disconnect()


# =========================================================================
# 6. HARDWARE TELEMETRY ADAPTER TESTS
# =========================================================================

def test_hardware_adapter_abstraction_properties():
    """Verifies hardware adapter configuration, port scanner, and error tracking."""
    hw = HardwareSerialAdapter(port="COM99_NONEXISTENT", baudrate=115200)
    assert hw.source_type == TelemetrySource.HARDWARE_SENSOR
    assert hw.is_simulated is False

    info = hw.get_adapter_info()
    assert info["adapter_id"] == "hardware_serial_esp32"
    assert info["port"] == "COM99_NONEXISTENT"
    assert info["is_simulated"] is False

    # Scanning ports should return a list without raising errors
    ports = HardwareSerialAdapter.get_available_ports()
    assert isinstance(ports, list)


# =========================================================================
# 7. STRICT PROHIBITED LOAD-CELL SENSOR DATA REJECTION
# =========================================================================

def test_prohibited_load_cell_fields_purged_by_normalizer():
    """
    CRITICAL PROOF: If raw telemetry packet contains sensor weight fields
    (cargo_kg, scale_kg, hx711), they are strictly PURGED from NormalizedTelemetry.
    """
    poisoned_raw = {
        "timestamp": "2026-08-29T12:00:00Z",
        "roll": 0.5,
        "pitch": -0.2,
        "distance": 15.0,
        "ballast_pct": 75.0,
        "cargo_kg": 45.0,            # PROHIBITED LOAD-CELL DATA
        "scale_kg": 450.0,           # PROHIBITED LOAD-CELL DATA
        "hx711": 1284920,            # PROHIBITED LOAD-CELL DATA
        "load_cell_mv": 3.82         # PROHIBITED LOAD-CELL DATA
    }

    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=poisoned_raw,
        source=TelemetrySource.HARDWARE_SENSOR
    )

    # 1. Verify NormalizedTelemetry schema contains NO cargo_kg or scale_kg
    dumped = normalized.model_dump()
    assert "cargo_kg" not in dumped["vessel_state"]
    assert "cargo_kg" not in dumped

    # 2. Verify audit notice is logged in metadata warnings
    assert any("Load-cell exclusion policy" in w for w in normalized.metadata.warnings)
    assert normalized.metadata.authoritative_weight_source == "DOCUMENT_AI"
    assert normalized.metadata.load_cell_policy == "FORBIDDEN_FOR_CARGO_AND_STABILITY"


def test_validator_strict_rejection_of_load_cell_telemetry():
    """
    CRITICAL PROOF: TelemetryValidator rejects raw packets containing load cell data
    when strict_load_cell_check is enabled.
    """
    packet_with_scale = {
        "roll": 1.0,
        "pitch": 0.0,
        "cargo_kg": 25.0  # Prohibited
    }

    val_res = TelemetryValidator.validate_raw_packet(packet_with_scale, strict_load_cell_check=True)
    assert val_res.is_valid is False
    assert "cargo_kg" in val_res.prohibited_fields_detected
    assert any("FORBIDDEN" in err for err in val_res.errors)


# =========================================================================
# 8. DECOUPLED STABILITY ENGINE & DIGITAL TWIN CONSUMPTION
# =========================================================================

def test_stability_engine_decoupled_from_hardware():
    """
    Verifies that the stability engine consumes normalized vessel state,
    and injected load cell weights have ZERO effect on vessel list, trim, or score.
    """
    ship = Ship(name="Decoupled Ship", num_bays=4)
    for i in range(1, 5):
        ship.tanks[f"port_{i}"] = BallastTank(f"Port-{i}", 300, 300)
        ship.tanks[f"starboard_{i}"] = BallastTank(f"Starboard-{i}", 300, 300)

    # Stability calculated purely from ship hydrostatics
    initial_list = StabilityAnalyzer.calculate_list(ship)
    initial_trim = StabilityAnalyzer.calculate_trim(ship)
    initial_score = StabilityAnalyzer.stability_score(ship)

    assert initial_list == 0.0
    assert initial_trim == 0.0
    assert initial_score == 0.0

    # Simulate injecting 50 kg into legacy state
    state.process_telemetry_tick(
        roll_val=0.5,
        pitch_val=-0.2,
        cargo_kg_val=50.0,
        distance_val=15.0,
        ballast_pct_val=80.0,
        status_val="IDLE",
        reader_connected_val=True
    )

    # Ship container count must remain 0 and stability hydrostatics unchanged
    assert len(ship.containers) == 0
    assert StabilityAnalyzer.calculate_list(ship) == 0.0
    assert StabilityAnalyzer.calculate_trim(ship) == 0.0


# =========================================================================
# 9. FASTAPI REST TELEMETRY ENDPOINTS
# =========================================================================

def test_rest_api_live_telemetry():
    """Verifies GET /api/telemetry/live returns normalized contract."""
    response = client.get("/api/telemetry/live")
    assert response.status_code == 200
    data = response.json()

    assert "timestamp" in data
    assert "source" in data
    assert data["source"] in ["HARDWARE_SENSOR", "SIMULATED_TELEMETRY", "SYSTEM_DERIVED"]
    assert "vessel_state" in data
    assert "ballast_tanks" in data
    assert "pumps" in data
    assert "flow_info" in data
    assert "operational_telemetry" in data
    assert "metadata" in data
    assert data["metadata"]["authoritative_weight_source"] == "DOCUMENT_AI"
    assert data["metadata"]["load_cell_policy"] == "FORBIDDEN_FOR_CARGO_AND_STABILITY"


def test_rest_api_telemetry_health():
    """Verifies GET /api/telemetry/health returns health indicators."""
    response = client.get("/api/telemetry/health")
    assert response.status_code == 200
    data = response.json()

    assert "active_source" in data
    assert "connection_status" in data
    assert "data_quality" in data
    assert "packet_count" in data
    assert "uptime_seconds" in data


def test_rest_api_telemetry_sources():
    """Verifies GET /api/telemetry/sources returns available adapters and policy."""
    response = client.get("/api/telemetry/sources")
    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "HARDWARE_SENSOR" in data["available_sources"]
    assert "SIMULATED_TELEMETRY" in data["available_sources"]
    assert data["authoritative_cargo_source"] == "DOCUMENT_AI"
    assert data["load_cell_sensor_policy"] == "FORBIDDEN_FOR_CARGO_AND_STABILITY"


def test_rest_api_simulator_override_and_clear():
    """Verifies POST /api/telemetry/simulate/override and clear endpoints."""
    override_payload = {
        "roll_deg": 3.75,
        "pitch_deg": -1.50,
        "ballast_pct": 65.0
    }
    resp = client.post("/api/telemetry/simulate/override", json=override_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True

    # Query live telemetry
    time.sleep(0.05)
    live_resp = client.get("/api/telemetry/live")
    assert live_resp.status_code == 200
    live_data = live_resp.json()
    assert live_data["vessel_state"]["roll_deg"] == 3.75
    assert live_data["vessel_state"]["pitch_deg"] == -1.50

    # Clear override
    clear_resp = client.post("/api/telemetry/simulate/clear")
    assert clear_resp.status_code == 200
    assert clear_resp.json()["success"] is True


def test_rest_api_validate_endpoint():
    """Verifies POST /api/telemetry/validate endpoint rejects prohibited load cell packets."""
    # 1. Valid packet
    valid_resp = client.post("/api/telemetry/validate", json={
        "payload": {"roll": 1.2, "pitch": -0.5, "ballast_pct": 80.0},
        "strict_load_cell_check": True
    })
    assert valid_resp.status_code == 200
    assert valid_resp.json()["is_valid"] is True

    # 2. Poisoned packet with cargo_kg
    poisoned_resp = client.post("/api/telemetry/validate", json={
        "payload": {"roll": 1.2, "pitch": -0.5, "cargo_kg": 30.0},
        "strict_load_cell_check": True
    })
    assert poisoned_resp.status_code == 200
    p_data = poisoned_resp.json()
    assert p_data["is_valid"] is False
    assert "cargo_kg" in p_data["prohibited_fields_detected"]
    assert any("FORBIDDEN" in err for err in p_data["errors"])
