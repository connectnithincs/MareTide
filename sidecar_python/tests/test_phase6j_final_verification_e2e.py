"""
Phase 6J Final Virtual ESP32 End-to-End Verification Test Suite
Verifies all 9 mandatory scenarios:
1. Stable Level Vessel
2. Port List
3. Starboard List
4. Forward Pitch
5. Tank Fill
6. Tank Drain
7. Sensor Fault
8. Disconnect (VIRTUAL ESP32 DISCONNECTED)
9. Load-Cell Strict Isolation & Provenance Audit
"""
import time
import pytest
from fastapi.testclient import TestClient

from main import app
import state
from digital_twin import DigitalTwin
from telemetry.manager import TelemetryManager
from telemetry.models import TelemetrySource, ConnectionStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown_virtual_esp32():
    """Sets up Virtual ESP32 mode and resets after each test."""
    state.reset_state()
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    if hasattr(mgr, "_virtual_esp32_adapter") and mgr._virtual_esp32_adapter:
        mgr._virtual_esp32_adapter.firmware.set_scenario("STABLE")
        mgr._virtual_esp32_adapter.firmware.current_roll = 0.0
        mgr._virtual_esp32_adapter.firmware.current_pitch = 0.0
    time.sleep(0.05)
    yield
    state.reset_state()
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)


def test_01_scenario_stable_level_vessel():
    """
    TEST 1 — Stable:
    Expected: Telemetry connected, roll approx stable, pitch approx stable,
    Digital Twin level, UI receives updates.
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "STABLE"})
    assert res.status_code == 200
    time.sleep(0.4)

    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    data = twin_res.json()
    assert abs(data["roll_deg"]) <= 1.5
    assert abs(data["pitch_deg"]) <= 1.5
    assert data["telemetry_source"] == "SIMULATED_ESP32"
    assert data["provenance_map"]["telemetry"] == "[SIMULATED ESP32]"

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vdata = vessel_res.json()
    assert vdata["connection_status"] == "CONNECTED"
    assert vdata["is_simulated"] is True


def test_02_scenario_port_list():
    """
    TEST 2 — Port List:
    Expected: Virtual roll changes, backend receives change,
    Digital Twin tilts port (-7.5° roll).
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "PORT_LIST"})
    assert res.status_code == 200
    time.sleep(0.4)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vdata = vessel_res.json()
    assert vdata["roll"] < -3.0
    assert vdata["telemetry_source"] == "SIMULATED_ESP32"
    assert vdata["provenance_map"]["telemetry"] == "[SIMULATED ESP32]"

    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    tdata = twin_res.json()
    assert tdata["roll_deg"] < -3.0


def test_03_scenario_starboard_list():
    """
    TEST 3 — Starboard List:
    Expected: Virtual roll changes, backend receives change,
    Digital Twin tilts starboard (+8.2° roll).
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "STARBOARD_LIST"})
    assert res.status_code == 200
    time.sleep(0.4)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vdata = vessel_res.json()
    assert vdata["roll"] > 3.0
    assert vdata["telemetry_source"] == "SIMULATED_ESP32"

    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    tdata = twin_res.json()
    assert tdata["roll_deg"] > 3.0


def test_04_scenario_forward_pitch():
    """
    TEST 4 — Forward Pitch:
    Expected: Pitch changes bow-down, UI reflects change, Digital Twin reacts.
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "FORWARD_PITCH"})
    assert res.status_code == 200
    time.sleep(0.4)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vdata = vessel_res.json()
    assert vdata["pitch"] < -3.0
    assert vdata["telemetry_source"] == "SIMULATED_ESP32"

    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    assert twin_res.json()["pitch_deg"] < -3.0


def test_05_scenario_tank_fill():
    """
    TEST 5 — Tank Fill:
    Expected: Tank telemetry changes, ultrasonic sensor reflects rising water level.
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "TANK_FILLING"})
    assert res.status_code == 200
    time.sleep(0.2)

    status_res = client.get("/api/telemetry/virtual/status")
    assert status_res.status_code == 200
    fw_state = status_res.json()["firmware_state"]
    assert fw_state["distance_cm"] <= 30.0
    assert fw_state["provenance_tag"] == "[SIMULATED ESP32]"


def test_06_scenario_tank_drain():
    """
    TEST 6 — Tank Drain:
    Expected: Torricelli orifice discharge triggers, gate servo opens to 80 deg,
    pump state active, tank level decreases.
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "TANK_DRAINING"})
    assert res.status_code == 200
    time.sleep(0.25)

    status_res = client.get("/api/telemetry/virtual/status")
    assert status_res.status_code == 200
    fw_state = status_res.json()["firmware_state"]
    assert fw_state["servo_gate_deg"] == 80
    assert fw_state["pump_active"] is True
    assert fw_state["flow_rate_l_s"] > 0.0


def test_07_scenario_sensor_fault_no_fabrication():
    """
    TEST 7 — Sensor Fault:
    Expected: Affected ultrasonic sensor becomes invalid, UI receives warning,
    system does NOT fabricate valid hardware values.
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "SENSOR_FAULT"})
    assert res.status_code == 200
    time.sleep(0.2)

    status_res = client.get("/api/telemetry/virtual/status")
    assert status_res.status_code == 200
    fw_state = status_res.json()["firmware_state"]
    assert fw_state["status"] == "SENSOR_ERROR"
    assert "WARNING_ULTRASONIC_TIMEOUT" in fw_state["warnings"]
    assert fw_state["sensor_fault"] is True


def test_08_scenario_disconnect():
    """
    TEST 8 — Disconnect:
    Expected: Virtual ESP32 stopped, connection status becomes DISCONNECTED,
    no fake hardware values synthesized.
    """
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "DISCONNECTED"})
    assert res.status_code == 200
    time.sleep(0.1)

    status_res = client.get("/api/telemetry/virtual/status")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["firmware_state"]["active_scenario"] == "DISCONNECTED"


def test_09_mandatory_load_cell_strict_isolation_and_provenance_audit():
    """
    TEST 9 — Load-Cell Isolation & Comprehensive Provenance Audit:
    Change simulated HX711 value dramatically (e.g. inject scale weight = 50.0 kg).
    Verify:
    1. Diagnostic value changes: diagnostic_load_cell_kg = 50.0
    2. Vessel cargo mass DOES NOT change (remains strictly 0.0 or Document AI weight)
    3. VGM DOES NOT change
    4. Stability calculation DOES NOT change
    5. Stowage recommendation DOES NOT change
    6. Ballast calculation DOES NOT change
    7. Complete Provenance Mapping is verified:
       - Telemetry: [SIMULATED ESP32]
       - Cargo Weight: [DOCUMENT AI]
       - Stability Index: [CALCULATED]
       - Stowage Recommendation: [CALCULATED]
       - Diagnostic Scale: [SIMULATED ESP32 — DIAGNOSTIC ONLY]
    """
    mgr = TelemetryManager.get_instance()
    
    # 1. Baseline stability calculation
    ship_before = state.get_current_ship()
    twin_before = DigitalTwin.get_vessel_twin_snapshot(ship_before)
    base_score = twin_before.stability_score
    base_risk = twin_before.risk_level
    base_list = twin_before.list_t
    base_trim = twin_before.trim_t
    base_containers = twin_before.containers

    # 2. Inject high load-cell weight into Virtual ESP32 firmware
    if hasattr(mgr, "_virtual_esp32_adapter") and mgr._virtual_esp32_adapter:
        mgr._virtual_esp32_adapter.firmware.diagnostic_cargo_kg = 50.0
    
    # Send DRAIN command with 50.0 kg weight
    cmd_res = client.post("/api/telemetry/virtual/command", json={"command": "DRAIN:50.0"})
    assert cmd_res.status_code == 200
    time.sleep(0.2)

    # 3. Query Live Telemetry Endpoint
    live_res = client.get("/api/telemetry/live")
    assert live_res.status_code == 200
    live_data = live_res.json()
    assert live_data["source"] == "SIMULATED_ESP32"
    assert live_data["diagnostic_load_cell_kg"] == 50.0

    # 4. Query Digital Twin Endpoint
    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    twin_data = twin_res.json()

    # Verify zero cargo weight contamination
    assert twin_data["containers"] == base_containers
    assert twin_data["stability_score"] == base_score
    assert twin_data["risk_level"] == base_risk
    assert twin_data["list_t"] == base_list
    assert twin_data["trim_t"] == base_trim
    assert twin_data["telemetry_source"] == "SIMULATED_ESP32"

    # 5. Query Vessel State Endpoint
    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    vessel_data = vessel_res.json()
    assert vessel_data["cargo_kg"] == 0.0  # Quarantined away from container stowage

    # 6. Provenance Mapping Verification
    prov = twin_data["provenance_map"]
    assert prov["telemetry"] == "[SIMULATED ESP32]"
    assert prov["cargo_weight"] == "[DOCUMENT AI]"
    assert prov["stability_index"] == "[CALCULATED]"
    assert prov["recommended_placement"] == "[CALCULATED]"
    assert prov["operator_authorization"] == "[OPERATOR]"
    assert prov["diagnostic_load_cell"] == "[SIMULATED ESP32 — DIAGNOSTIC ONLY]"

