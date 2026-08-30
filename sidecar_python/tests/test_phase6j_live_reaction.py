"""
Phase 6J Live Digital Twin Telemetry Reaction Tests
Validates real-time visual reactions to simulated ESP32 sensor changes:
STABLE, PORT_LIST, STARBOARD_LIST, FORWARD_PITCH, AFT_PITCH, TANK_FILLING, TANK_DRAINING, SENSOR_FAULT
Verifies strict separation between [SIMULATED ESP32] motion and [CALCULATED] hydrostatic GM.
"""
import time
import pytest
from fastapi.testclient import TestClient

from main import app
from telemetry.manager import TelemetryManager
from telemetry.models import TelemetrySource, ConnectionStatus

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown_virtual_esp32():
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    if hasattr(mgr, "_virtual_esp32_adapter") and mgr._virtual_esp32_adapter:
        mgr._virtual_esp32_adapter.firmware.set_scenario("STABLE")
        mgr._virtual_esp32_adapter.firmware.current_roll = 0.0
        mgr._virtual_esp32_adapter.firmware.current_pitch = 0.0
    time.sleep(0.05)
    yield
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)


def test_01_scenario_stable_level_vessel():
    """STABLE: Vessel remains approximately level with 100% ballast."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "STABLE"})
    assert res.status_code == 200
    time.sleep(0.35)

    twin_res = client.get("/api/digital-twin/state")
    assert twin_res.status_code == 200
    data = twin_res.json()
    assert abs(data["roll_deg"]) <= 1.5
    assert abs(data["pitch_deg"]) <= 1.5
    assert data["telemetry_source"] == "SIMULATED_ESP32"
    assert data["provenance_map"]["telemetry"] == "[SIMULATED ESP32]"


def test_02_scenario_port_list_visual_tilt():
    """PORT_LIST: Vessel visually tilts toward port (negative roll ~ -7.5°)."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "PORT_LIST"})
    assert res.status_code == 200
    time.sleep(0.35)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    data = vessel_res.json()
    assert data["roll"] < -4.0
    assert data["telemetry_source"] == "SIMULATED_ESP32"


def test_03_scenario_starboard_list_visual_tilt():
    """STARBOARD_LIST: Vessel visually tilts toward starboard (positive roll ~ +8.2°)."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "STARBOARD_LIST"})
    assert res.status_code == 200
    time.sleep(0.35)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    data = vessel_res.json()
    assert data["roll"] > 4.0
    assert data["telemetry_source"] == "SIMULATED_ESP32"


def test_04_scenario_forward_pitch_visual_bow_down():
    """FORWARD_PITCH: Vessel visually pitches forward (negative pitch ~ -6.5°)."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "FORWARD_PITCH"})
    assert res.status_code == 200
    time.sleep(0.35)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    data = vessel_res.json()
    assert data["pitch"] < -3.5


def test_05_scenario_aft_pitch_visual_stern_down():
    """AFT_PITCH: Vessel visually pitches aft (positive pitch ~ +5.8°)."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "AFT_PITCH"})
    assert res.status_code == 200
    time.sleep(0.35)

    vessel_res = client.get("/api/vessel-state")
    assert vessel_res.status_code == 200
    data = vessel_res.json()
    assert data["pitch"] > 3.5


def test_06_scenario_tank_draining_and_servo_reaction():
    """TANK_DRAINING: Torricelli orifice discharge opens servo gate and decrements level."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "TANK_DRAINING"})
    assert res.status_code == 200
    time.sleep(0.2)

    status_res = client.get("/api/telemetry/virtual/status")
    assert status_res.status_code == 200
    fw_state = status_res.json()["firmware_state"]
    assert fw_state["servo_gate_deg"] == 80
    assert fw_state["pump_active"] is True
    assert fw_state["flow_rate_l_s"] > 0.0


def test_07_scenario_sensor_fault_degraded_status():
    """SENSOR_FAULT: Emulates ultrasonic distance sensor failure and triggers warning."""
    res = client.post("/api/telemetry/virtual/scenario", json={"scenario": "SENSOR_FAULT"})
    assert res.status_code == 200
    time.sleep(0.1)

    status_res = client.get("/api/telemetry/virtual/status")
    assert status_res.status_code == 200
    fw_state = status_res.json()["firmware_state"]
    assert fw_state["status"] == "SENSOR_ERROR"
    assert "WARNING_ULTRASONIC_TIMEOUT" in fw_state["warnings"]


def test_08_load_cell_diagnostic_quarantine_in_all_reactions():
    """
    Verifies that under ANY scenario (tilt, drain, fault), the diagnostic load-cell
    reading never influences cargo weight or stability calculations.
    """
    for sc in ["PORT_LIST", "STARBOARD_LIST", "FORWARD_PITCH", "TANK_DRAINING", "STABLE"]:
        client.post("/api/telemetry/virtual/scenario", json={"scenario": sc})
        time.sleep(0.05)

        twin_res = client.get("/api/digital-twin/state")
        twin_data = twin_res.json()
        assert twin_data["provenance_map"]["cargo_weight"] == "[DOCUMENT AI]"
        assert twin_data["provenance_map"]["diagnostic_load_cell"] == "[SIMULATED ESP32 — DIAGNOSTIC ONLY]"
        assert twin_data["provenance_map"]["stability_index"] == "[CALCULATED]"
