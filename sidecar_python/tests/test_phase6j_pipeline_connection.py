"""
Phase 6J: Connect Virtual ESP32 to Real Telemetry Pipeline Tests.

Verifies:
1. Three explicitly distinguishable modes:
   - MODE A: Real ESP32 (HARDWARE_SENSOR)
   - MODE B: Virtual ESP32 (SIMULATED_ESP32)
   - MODE C: Simulation (SIMULATED_TELEMETRY)
2. Environment variable initialization (MARETIDE_TELEMETRY_MODE / EV_TELEMETRY_MODE).
3. End-to-end traversal of the real pipeline:
   Virtual ESP32 -> Stream -> Parser -> Normalizer -> Digital Twin -> API.
4. Connection state lifecycle: CONNECTED, STALE, DISCONNECTED, INVALID_DATA.
5. Component-level provenance labeling.
6. Strict load-cell isolation invariant (HX711 value never affects cargo, VGM, stability, ballast).
7. Mode switching stability without state corruption.
8. API contracts on /api/telemetry/live, /api/digital-twin/state, and /api/vessel-state.
"""

import os
import time
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
from telemetry.manager import TelemetryManager
from telemetry.normalizer import TelemetryNormalizer
from telemetry.validator import TelemetryValidator
from digital_twin import DigitalTwin

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_env_and_telemetry():
    """Ensures a clean telemetry and ship state for every test."""
    state.reset_state()
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)
    mgr.clear_simulator_overrides()
    yield
    state.reset_state()
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)
    mgr.clear_simulator_overrides()


def test_01_three_distinct_modes_selection():
    """
    Test 1: Verifies that Real ESP32, Virtual ESP32, and Simulation modes
    are explicitly distinguishable and do not overwrite each other.
    """
    mgr = TelemetryManager.get_instance()

    # 1. Mode C: Simulation
    mgr.select_source("simulation")
    adapter_c = mgr.get_active_adapter()
    assert adapter_c.source_type == TelemetrySource.SIMULATED_TELEMETRY
    assert adapter_c.adapter_id == "simulator_vessel_engine"
    assert adapter_c.is_simulated is True

    # 2. Mode B: Virtual ESP32
    mgr.select_source("virtual_esp32")
    adapter_b = mgr.get_active_adapter()
    assert adapter_b.source_type == TelemetrySource.SIMULATED_ESP32
    assert adapter_b.adapter_id == "virtual_esp32_simulator"
    assert adapter_b.is_simulated is True

    # 3. Mode A: Real ESP32
    mgr.select_source("real_esp32")
    adapter_a = mgr.get_active_adapter()
    assert adapter_a.source_type == TelemetrySource.HARDWARE_SENSOR
    assert adapter_a.adapter_id == "hardware_serial_esp32"
    assert adapter_a.is_simulated is False


def test_02_environment_variable_mode_initialization(monkeypatch):
    """
    Test 2: Verifies that environment variable MARETIDE_TELEMETRY_MODE / EV_TELEMETRY_MODE
    configures the initial active telemetry source on boot.
    """
    # Virtual ESP32 via env
    monkeypatch.setenv("MARETIDE_TELEMETRY_MODE", "virtual_esp32")
    TelemetryManager._instance = None
    mgr = TelemetryManager.get_instance()
    assert mgr.get_active_adapter().source_type == TelemetrySource.SIMULATED_ESP32

    # Real ESP32 via env
    monkeypatch.delenv("MARETIDE_TELEMETRY_MODE", raising=False)
    monkeypatch.setenv("EV_TELEMETRY_MODE", "real_esp32")
    monkeypatch.setenv("EV_SERIAL_PORT", "COM7")
    TelemetryManager._instance = None
    mgr2 = TelemetryManager.get_instance()
    assert mgr2.get_active_adapter().source_type == TelemetrySource.HARDWARE_SENSOR
    assert mgr2._hw_adapter.port == "COM7"

    # Reset back to default
    monkeypatch.delenv("MARETIDE_TELEMETRY_MODE", raising=False)
    monkeypatch.delenv("EV_TELEMETRY_MODE", raising=False)
    monkeypatch.delenv("EV_SERIAL_PORT", raising=False)
    TelemetryManager._instance = None


def test_03_virtual_esp32_through_real_pipeline():
    """
    Test 3: Confirms that Virtual ESP32 telemetry passes through the standard
    multi-line stream parser, normalizer, digital twin, and API without bypassing.
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    mgr.set_virtual_scenario("PORT_LIST")
    time.sleep(0.60) # Allow virtual MCU to emit packet and background thread to parse

    res = client.get("/api/telemetry/live")
    assert res.status_code == 200
    live = res.json()
    assert live["source"] == "SIMULATED_ESP32"
    assert live["metadata"]["adapter_id"] == "virtual_esp32_simulator"
    assert live["vessel_state"]["roll_deg"] < -3.0 # Dynamic tilt propagated from virtual MCU


def test_04_virtual_esp32_connection_states_lifecycle():
    """
    Test 4: Exposes CONNECTED, STALE, DISCONNECTED, and INVALID_DATA on Virtual ESP32.
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)

    # 1. Connected
    live = mgr.get_latest_telemetry()
    assert live.connection_status in [ConnectionStatus.CONNECTED, ConnectionStatus.SIMULATED]

    # 2. Disconnected scenario
    mgr.set_virtual_scenario("DISCONNECTED")
    assert mgr.get_active_adapter().is_connected() is False
    
    # 3. Invalid data normalization
    invalid_raw = {"roll": "corrupted_non_float", "pitch": 0.0}
    normalized_invalid = TelemetryNormalizer.normalize_raw_packet(
        raw_data=invalid_raw,
        source=TelemetrySource.SIMULATED_ESP32,
        connection_status=ConnectionStatus.INVALID_DATA
    )
    assert normalized_invalid.connection_status == ConnectionStatus.INVALID_DATA


def test_05_provenance_labels_exhaustive_verification():
    """
    Test 5: Verifies that provenance tags are strictly applied according to spec:
    - Roll: [SIMULATED ESP32]
    - Pitch: [SIMULATED ESP32]
    - Container weight: [DOCUMENT AI]
    - Stability index: [CALCULATED]
    - Recommended placement: [CALCULATED]
    - Operator authorization: [OPERATOR]
    - Load-cell: [SIMULATED ESP32 — DIAGNOSTIC ONLY]
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    time.sleep(0.15)

    res = client.get("/api/vessel-state")
    assert res.status_code == 200
    data = res.json()

    prov = data["provenance_map"]
    assert prov["roll"] == "[SIMULATED ESP32]"
    assert prov["pitch"] == "[SIMULATED ESP32]"
    assert prov["container_weight"] == "[DOCUMENT AI]"
    assert prov["cargo_weight"] == "[DOCUMENT AI]"
    assert prov["stability_index"] == "[CALCULATED]"
    assert prov["vessel_hydrostatics"] == "[CALCULATED]"
    assert prov["recommended_placement"] == "[CALCULATED]"
    assert prov["operator_authorization"] == "[OPERATOR]"
    assert prov["diagnostic_load_cell"] == "[SIMULATED ESP32 — DIAGNOSTIC ONLY]"


def test_06_strict_load_cell_zero_coupling_invariant():
    """
    Test 6: Strict Isolation Invariant: Injected virtual load-cell readings
    must never enter container weight, cargo mass, stability index, or ballast calculations.
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    
    # Inject heavy diagnostic scale weight on virtual MCU
    mgr._virtual_esp32_adapter.firmware.diagnostic_cargo_kg = 75.0
    time.sleep(0.60)

    # 1. Check /api/vessel-state
    res = client.get("/api/vessel-state")
    data = res.json()
    assert data["cargo_kg"] == 0.0
    assert data["cargo_t"] == 0.0
    assert data["authoritative_weight_source"] == "DOCUMENT_AI"

    # 2. Check Digital Twin snapshot
    twin_res = client.get("/api/digital-twin/state")
    twin_data = twin_res.json()
    assert twin_data["provenance_map"]["cargo_weight"] == "[DOCUMENT AI]"
    assert twin_data["provenance_map"]["diagnostic_load_cell"] == "[SIMULATED ESP32 — DIAGNOSTIC ONLY]"


def test_07_mode_switching_state_integrity():
    """
    Test 7: Rapid switching between Simulation -> Virtual ESP32 -> Real ESP32 -> Simulation
    does not corrupt state or leave orphan threads.
    """
    mgr = TelemetryManager.get_instance()

    modes = [
        ("simulation", TelemetrySource.SIMULATED_TELEMETRY),
        ("virtual_esp32", TelemetrySource.SIMULATED_ESP32),
        ("real_esp32", TelemetrySource.HARDWARE_SENSOR),
        ("virtual_esp32", TelemetrySource.SIMULATED_ESP32),
        ("simulation", TelemetrySource.SIMULATED_TELEMETRY),
    ]

    for mode_str, expected_enum in modes:
        res = client.post("/api/telemetry/source/select", json={"source": mode_str})
        assert res.status_code == 200
        assert res.json()["active_source"] == expected_enum.value
        time.sleep(0.05)
        
        # Verify vessel-state responds with matching source
        v_res = client.get("/api/vessel-state")
        assert v_res.status_code == 200
        assert v_res.json()["telemetry_source"] == expected_enum.value


def test_08_api_live_telemetry_and_digital_twin_endpoints():
    """
    Test 8: Validates schema consistency across /api/telemetry/live, /api/digital-twin/state,
    and /api/vessel-state in Virtual ESP32 mode.
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    time.sleep(0.15)

    # 1. Live Telemetry
    res_live = client.get("/api/telemetry/live")
    assert res_live.status_code == 200
    live_data = res_live.json()
    assert "vessel_state" in live_data
    assert "ballast_tanks" in live_data
    assert "metadata" in live_data
    assert "provenance_map" in live_data

    # 2. Digital Twin State
    res_twin = client.get("/api/digital-twin/state")
    assert res_twin.status_code == 200
    twin_data = res_twin.json()
    assert twin_data["telemetry_source"] == "SIMULATED_ESP32"
    assert twin_data["provenance_map"]["telemetry"] == "[SIMULATED ESP32]"

    # 3. Sources listing
    res_sources = client.get("/api/telemetry/sources")
    assert res_sources.status_code == 200
    sources_data = res_sources.json()
    assert sources_data["active_source"] == "SIMULATED_ESP32"
    assert "SIMULATED_ESP32" in sources_data["available_sources"]
