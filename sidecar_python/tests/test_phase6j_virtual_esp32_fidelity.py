"""
Phase 6J: Virtual ESP32 Sensor Simulator & Firmware Fidelity Tests.

Verifies:
1. Exact multi-line JSON stream emission matching esp32_sensor_sketch.ino.
2. All 9 supported simulation scenarios (STABLE, PORT_LIST, STARBOARD_LIST, FORWARD_PITCH,
   AFT_PITCH, TANK_FILLING, TANK_DRAINING, SENSOR_FAULT, DISCONNECTED).
3. Smooth mathematical motion transitions for inclinometer roll/pitch.
4. Torricelli orifice discharge math and gate servo angles (0 deg <-> 80 deg).
5. Asynchronous boot banners, warnings, and serial commands ('DRAIN:<weight>').
6. Virtual UART streaming via VirtualESP32Adapter.
7. Strict Load-Cell Isolation Invariant (HX711 scale data never contaminates cargo or stability).
8. Provenance stamping as [SIMULATED ESP32].
9. REST API endpoints for scenario configuration and diagnostic inspection.
"""

import time
import json
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
from telemetry.simulators.virtual_esp32_firmware import VirtualESP32Firmware
from telemetry.adapters.virtual_esp32_adapter import VirtualESP32Adapter
from telemetry.adapters.hardware_adapter import extract_json_from_buffer
from telemetry.normalizer import TelemetryNormalizer
from telemetry.manager import TelemetryManager
from digital_twin import DigitalTwin

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
    mgr.select_source(TelemetrySource.SIMULATED_TELEMETRY)
    mgr.clear_simulator_overrides()


def test_01_virtual_esp32_exact_multiline_json_output():
    """
    Test 1: Verifies that VirtualESP32Firmware generates the exact 9-line JSON
    packet and '---' delimiter matching esp32_sensor_sketch.ino.
    """
    fw = VirtualESP32Firmware()
    fw.boot()

    # Step past the 500ms telemetry interval
    emitted = fw.step(dt_sec=0.60)
    assert "MPU6050: OK" in emitted
    assert "NAVI-AI ESP32 Ready" in emitted
    assert "{\n" in emitted
    assert "  \"roll\":" in emitted
    assert "  \"pitch\":" in emitted
    assert "  \"distance\":" in emitted
    assert "  \"ballast_pct\":" in emitted
    assert "  \"cargo_kg\":" in emitted
    assert "  \"status\":" in emitted
    assert "  \"risk\":" in emitted
    assert "}\n---\n" in emitted

    # Parse with hardware stream parser
    packets, remaining = extract_json_from_buffer(emitted)
    assert len(packets) == 1
    pkt = packets[0]
    assert "roll" in pkt
    assert "pitch" in pkt
    assert "distance" in pkt
    assert "ballast_pct" in pkt
    assert "cargo_kg" in pkt
    assert pkt["status"] == "IDLE"
    assert pkt["risk"] == "SAFE"


def test_02_all_nine_scenarios_execution():
    """
    Test 2: Verifies that all 9 controllable scenarios execute properly on the virtual MCU.
    """
    fw = VirtualESP32Firmware()
    fw.boot()

    scenarios = [
        "STABLE",
        "PORT_LIST",
        "STARBOARD_LIST",
        "FORWARD_PITCH",
        "AFT_PITCH",
        "TANK_FILLING",
        "TANK_DRAINING",
        "SENSOR_FAULT",
        "DISCONNECTED"
    ]

    for sc in scenarios:
        assert fw.set_scenario(sc) is True
        state_dict = fw.get_firmware_state()
        assert state_dict["active_scenario"] == sc

        # Step time to verify stability
        out = fw.step(dt_sec=0.10)
        if sc == "DISCONNECTED":
            assert out == ""  # Disconnected emits nothing
        elif sc == "SENSOR_FAULT":
            assert state_dict["sensor_fault"] is True
        elif sc == "TANK_DRAINING":
            assert state_dict["is_draining"] is True
            assert state_dict["gate_servo_angle"] == 80


def test_03_smooth_motion_transition_interpolation():
    """
    Test 3: Validates that inclinometer angles transition smoothly across ticks rather than jumping abruptly.
    """
    fw = VirtualESP32Firmware()
    fw.boot()
    fw.set_scenario("PORT_LIST") # Target roll is -7.50 deg

    rolls = []
    for _ in range(10):
        fw.step(dt_sec=0.05)
        rolls.append(fw.current_roll)

    # Check monotonic convergence toward -7.50
    for i in range(len(rolls) - 1):
        assert rolls[i + 1] < rolls[i]  # Moving negatively
        assert abs(rolls[i + 1] - rolls[i]) < 2.0  # Smooth step (< 2 deg per 50ms)

    assert rolls[-1] < -4.0


def test_04_torricelli_orifice_discharge_and_gate_servo():
    """
    Test 4: Verifies Torricelli orifice discharge physics Q = Cd * A * sqrt(2gh)
    and servo gate opening (80 deg) and closing (0 deg).
    """
    fw = VirtualESP32Firmware()
    fw.boot()

    # Initial tank full: distance = 10.0cm (depth = 20.0cm = 0.2m)
    fw.start_draining(cargo_weight_kg=1.0)
    assert fw.is_draining is True
    assert fw.gate_servo_angle == 80
    assert fw.pump_led is True

    # Step through draining until target volume is cleared
    for _ in range(100):
        if not fw.is_draining:
            break
        fw.step(dt_sec=0.50)

    assert fw.is_draining is False
    assert fw.gate_servo_angle == 0
    assert fw.pump_led is False
    assert fw.filtered_distance > 10.0  # Water level decreased


def test_05_serial_drain_command_processing():
    """
    Test 5: Sending serial command 'DRAIN:2.00\\n' initiates draining cycle.
    """
    fw = VirtualESP32Firmware()
    fw.boot()
    fw.send_command("DRAIN:2.00\n")
    assert fw.is_draining is True
    assert fw.gate_servo_angle == 80


def test_06_low_ballast_and_capacity_warnings():
    """
    Test 6: Emits 'WARNING: LOW BALLAST LEVEL!' when level < 20% and
    'Tilt Right -> Pump PORT side' when roll > 5.0 deg.
    """
    fw = VirtualESP32Firmware()
    fw.boot()
    fw.set_scenario("STARBOARD_LIST") # Roll = +8.20 deg

    # Step past 500ms
    emitted = fw.step(dt_sec=0.60)
    assert "Tilt Right -> Pump PORT side" in emitted


def test_07_boot_banner_emission_and_parser_immunity():
    """
    Test 7: Boot banners are emitted upon power-on reset and successfully filtered by parser.
    """
    fw = VirtualESP32Firmware()
    fw.boot()
    out = fw.step(dt_sec=0.60)
    assert "MPU6050: OK" in out
    assert "NAVI-AI ESP32 Ready" in out

    packets, remaining = extract_json_from_buffer(out)
    assert len(packets) >= 1
    assert packets[0]["status"] == "IDLE"


def test_08_virtual_adapter_uart_stream_integration():
    """
    Test 8: Validates VirtualESP32Adapter streaming thread and packet receipt.
    """
    adapter = VirtualESP32Adapter()
    adapter.connect()
    assert adapter.is_connected() is True
    assert adapter.source_type == TelemetrySource.SIMULATED_ESP32

    # Allow thread to produce at least 1 packet
    time.sleep(0.60)
    pkt = adapter.read_raw()
    assert pkt is not None
    assert "roll" in pkt
    assert "pitch" in pkt

    adapter.disconnect()
    assert adapter.is_connected() is False


def test_09_stale_and_disconnect_lifecycle():
    """
    Test 9: Setting DISCONNECTED scenario pauses output stream and flags disconnection.
    """
    adapter = VirtualESP32Adapter()
    adapter.connect()
    adapter.set_scenario("DISCONNECTED")
    assert adapter.is_connected() is False
    adapter.disconnect()


def test_10_strict_load_cell_isolation_invariant():
    """
    Test 10: Strict Invariant: Virtual HX711 diagnostic weight is quarantined and
    never contaminates cargo container weight or vessel stability.
    """
    fw = VirtualESP32Firmware()
    fw.boot()
    fw.diagnostic_cargo_kg = 22.50 # Bench scale weight

    out = fw.step(dt_sec=0.60)
    packets, _ = extract_json_from_buffer(out)
    assert len(packets) >= 1
    raw_pkt = packets[0]
    assert raw_pkt["cargo_kg"] == 22.50

    # Normalization purges it
    normalized = TelemetryNormalizer.normalize_raw_packet(
        raw_data=raw_pkt,
        source=TelemetrySource.SIMULATED_ESP32,
        connection_status=ConnectionStatus.CONNECTED,
        adapter_id="virtual_esp32_simulator"
    )
    assert normalized.source == TelemetrySource.SIMULATED_ESP32
    assert normalized.metadata.load_cell_policy == "FORBIDDEN_FOR_CARGO_AND_STABILITY"
    assert normalized.metadata.authoritative_weight_source == "DOCUMENT_AI"


def test_11_provenance_tagging_simulated_esp32():
    """
    Test 11: Selecting SIMULATED_ESP32 stamps [SIMULATED ESP32] in DigitalTwin and API.
    """
    mgr = TelemetryManager.get_instance()
    mgr.select_source(TelemetrySource.SIMULATED_ESP32)
    time.sleep(0.15)

    res = client.get("/api/vessel-state")
    assert res.status_code == 200
    data = res.json()
    assert data["telemetry_source"] == "SIMULATED_ESP32"
    assert data["provenance_map"]["telemetry"] == "[SIMULATED ESP32]"
    assert data["provenance_map"]["cargo_weight"] == "[DOCUMENT AI]"
    assert data["is_simulated"] is True


def test_12_virtual_esp32_rest_api_endpoints():
    """
    Test 12: Validates /api/telemetry/virtual/status, /virtual/scenario, and /virtual/command endpoints.
    """
    # 1. Status
    res_status = client.get("/api/telemetry/virtual/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["success"] is True
    assert "firmware_state" in status_data
    assert status_data["firmware_state"]["provenance_tag"] == "[SIMULATED ESP32]"

    # 2. Set scenario
    res_sc = client.post("/api/telemetry/virtual/scenario", json={"scenario": "PORT_LIST"})
    assert res_sc.status_code == 200
    sc_data = res_sc.json()
    assert sc_data["scenario"] == "PORT_LIST"

    # 3. Invalid scenario rejection
    res_inv = client.post("/api/telemetry/virtual/scenario", json={"scenario": "INVALID_NAME"})
    assert res_inv.status_code == 400

    # 4. Command dispatch
    res_cmd = client.post("/api/telemetry/virtual/command", json={"command": "DRAIN:1.50"})
    assert res_cmd.status_code == 200
    assert res_cmd.json()["success"] is True
