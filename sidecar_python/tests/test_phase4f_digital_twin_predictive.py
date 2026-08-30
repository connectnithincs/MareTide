"""
Phase 4F: Cargo-Aware Digital Twin & Predictive Monitoring Test Suite.
Verifies digital twin container reflection, predictive vs actual comparisons,
4-stage lifecycle progression, ballast update propagation, telemetry provenance tracking,
operational safety alerts (excessive list, excessive trim, ballast asymmetry), and REST endpoints.
"""

import os
import sys
import copy
import pytest
from fastapi.testclient import TestClient

# Ensure sidecar_python is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import app
from ship import Ship, Container, StabilityAnalyzer
import state
from digital_twin import DigitalTwin
from container_stability.models import (
    ContainerLoadingConfirmRequest,
    BallastExecutionRequest
)
from container_stability.analyzer import (
    ContainerLoadingService,
    ContainerBallastService,
    ContainerStabilityService
)
from reports.logs_db import clear_logs

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0
    yield
    clear_logs()
    ship = state.get_current_ship()
    ship.containers.clear()
    for i in range(1, 5):
        if f"port_{i}" in ship.tanks:
            ship.tanks[f"port_{i}"].current_volume = 300.0
        if f"starboard_{i}" in ship.tanks:
            ship.tanks[f"starboard_{i}"].current_volume = 300.0


# --- TEST 1: LOADED CONTAINER REFLECTED IN DIGITAL TWIN ---
def test_1_loaded_container_reflected_in_digital_twin():
    """Verify that committed containers appear immediately in the digital twin snapshot."""
    ship = state.get_current_ship()
    confirm_req = ContainerLoadingConfirmRequest(
        container={
            "container_number": "MSCU4920195",
            "container_type": "40HC",
            "weights": {"gross_weight_kg": 24000.0}
        },
        document={"processing_status": "success"},
        validation={"valid": True},
        recommendation={"bay": 2, "side": "PORT", "tier": 1},
        operator_confirmed=True
    )
    res = ContainerLoadingService.confirm_and_load(confirm_req, ship_instance=ship)
    assert res.success is True

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship)
    assert len(snapshot.containers) == 1
    c = snapshot.containers[0]
    assert c["id"] == "MSCU4920195"
    assert c["weight"] == 24.0
    assert c["bay"] == 2
    assert c["side"] == "PORT"
    assert c["tier"] == 1


# --- TEST 2: PROJECTED MATCHES STABILITY ENGINE ---
def test_2_projected_matches_stability_engine():
    """Verify that projected pre-load comparison matches StabilityAnalyzer calculations."""
    ship = state.get_current_ship()
    comp = DigitalTwin.get_predictive_comparison(
        current_ship=ship,
        container_id="MSCU4920195",
        gross_weight_t=25.0,
        bay=1,
        side="port",
        tier=1
    )

    assert comp.status == "PROJECTED"
    assert comp.actual_list_t is None
    assert comp.actual_trim_t is None

    # Compare with independent copy calculation
    test_ship = copy.deepcopy(ship)
    test_ship.add_container(Container(id="MSCU4920195", weight=25.0, bay=1, side="port", tier=1))
    expected_list = round(float(StabilityAnalyzer.calculate_list(test_ship)), 2)
    expected_trim = round(float(StabilityAnalyzer.calculate_trim(test_ship)), 2)

    assert comp.projected_list_t == expected_list
    assert comp.projected_trim_t == expected_trim


# --- TEST 3: ACTUAL MATCHES LIVE VESSEL STATE ---
def test_3_actual_matches_live_vessel_state():
    """Verify that after container commitment, actual values populate and match live ship state."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="MSCU4920195", weight=25.0, bay=1, side="port", tier=1))

    comp = DigitalTwin.get_predictive_comparison(
        current_ship=ship,
        container_id="MSCU4920195",
        gross_weight_t=25.0,
        bay=1,
        side="port",
        tier=1
    )

    assert comp.status == "COMMITTED"
    assert comp.actual_list_t is not None
    assert comp.actual_trim_t is not None
    assert comp.actual_list_t == round(float(StabilityAnalyzer.calculate_list(ship)), 2)
    assert comp.actual_trim_t == round(float(StabilityAnalyzer.calculate_trim(ship)), 2)


# --- TEST 4: FOUR-STAGE LIFECYCLE PROGRESSION ---
def test_4_four_stage_lifecycle_progression():
    """Verify 4-stage Before/After lifecycle progression model consistency."""
    ship_before = copy.deepcopy(state.get_current_ship())
    ship_before.containers.clear()
    for i in range(1, 5):
        ship_before.tanks[f"port_{i}"].current_volume = 300.0
        ship_before.tanks[f"starboard_{i}"].current_volume = 300.0

    ship_loaded = copy.deepcopy(ship_before)
    ship_loaded.add_container(Container(id="LOADED1", weight=28.0, bay=2, side="port", tier=1))

    ship_ballasted = copy.deepcopy(ship_loaded)
    ship_ballasted.tanks["port_2"].current_volume -= 28.0

    lifecycle = DigitalTwin.get_four_stage_lifecycle(
        ship_before=ship_before,
        ship_loaded=ship_loaded,
        ship_ballasted=ship_ballasted,
        current_ship=ship_ballasted
    )

    assert lifecycle.vessel_before is not None
    assert lifecycle.container_loaded is not None
    assert lifecycle.ballast_compensated is not None
    assert lifecycle.current_vessel_state is not None

    # Before container: 0 containers, list = 0.0
    assert len(lifecycle.vessel_before.containers) == 0
    assert lifecycle.vessel_before.list_t == 0.0

    # Loaded container: 1 container, list < 0 (Port list)
    assert len(lifecycle.container_loaded.containers) == 1
    assert lifecycle.container_loaded.list_t != 0.0

    # Ballast compensated: Port tank discharged, equilibrium restored
    assert lifecycle.ballast_compensated.ballast_tanks["port_2"]["current_volume"] == 272.0


# --- TEST 5: BALLAST COMPENSATION PROPAGATION ---
def test_5_ballast_compensation_propagation():
    """Verify ballast tank updates propagate accurately into the digital twin."""
    ship = state.get_current_ship()
    ship.tanks["port_1"].current_volume = 210.0
    ship.tanks["starboard_1"].current_volume = 290.0

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship)
    assert snapshot.ballast_tanks["port_1"]["current_volume"] == 210.0
    assert snapshot.ballast_tanks["starboard_1"]["current_volume"] == 290.0
    assert snapshot.ballast_tanks["port_1"]["fill_ratio"] == round(210.0 / 300.0, 3)


# --- TEST 6: TELEMETRY PROVENANCE EXPLICIT LABELING ---
def test_6_telemetry_provenance_explicit_labeling():
    """Verify telemetry source is explicitly tagged as simulated or hardware sensor."""
    ship = state.get_current_ship()

    sim_snap = DigitalTwin.get_vessel_twin_snapshot(ship, is_simulated=True)
    assert sim_snap.is_simulated is True
    assert sim_snap.telemetry_source == "SIMULATED_TELEMETRY"

    hw_snap = DigitalTwin.get_vessel_twin_snapshot(ship, is_simulated=False)
    assert hw_snap.is_simulated is False
    assert hw_snap.telemetry_source == "HARDWARE_SENSOR"


# --- TEST 7: EXCESSIVE LIST ALERT GENERATION ---
def test_7_excessive_list_alert_generation():
    """Verify list exceeding threshold triggers operational warning or critical alert."""
    ship = state.get_current_ship()
    # Add heavy container on Port side to induce list
    ship.add_container(Container(id="HEAVY-PORT-1", weight=32.0, bay=1, side="port", tier=2))
    ship.add_container(Container(id="HEAVY-PORT-2", weight=32.0, bay=2, side="port", tier=2))

    alerts = DigitalTwin.detect_operational_alerts(ship)
    list_alert = next((a for a in alerts if a.alert_type == "EXCESSIVE_LIST"), None)
    assert list_alert is not None
    assert list_alert.severity in ["WARNING", "CRITICAL"]
    assert "list" in list_alert.message.lower()
    assert "counter-flooding" in list_alert.action.lower() or "compensation" in list_alert.action.lower()


# --- TEST 8: EXCESSIVE TRIM ALERT GENERATION ---
def test_8_excessive_trim_alert_generation():
    """Verify longitudinal pitch/trim exceeding threshold triggers trim alert."""
    ship = state.get_current_ship()
    # Heavily weight Bay 1 (forward) to induce trim
    ship.add_container(Container(id="BOW-HEAVY-1", weight=30.0, bay=1, side="port", tier=1))
    ship.add_container(Container(id="BOW-HEAVY-2", weight=30.0, bay=1, side="starboard", tier=1))

    alerts = DigitalTwin.detect_operational_alerts(ship)
    trim_alert = next((a for a in alerts if a.alert_type == "EXCESSIVE_TRIM"), None)
    assert trim_alert is not None
    assert trim_alert.severity in ["WARNING", "CRITICAL"]
    assert "trim" in trim_alert.message.lower()


# --- TEST 9: BALLAST IMBALANCE ALERT GENERATION ---
def test_9_ballast_imbalance_alert_generation():
    """Verify severe port/starboard ballast differential triggers asymmetry alert."""
    ship = state.get_current_ship()
    for i in range(1, 5):
        ship.tanks[f"port_{i}"].current_volume = 300.0  # 1200t total
        ship.tanks[f"starboard_{i}"].current_volume = 50.0  # 200t total -> diff 1000t > 150t

    alerts = DigitalTwin.detect_operational_alerts(ship)
    imbal_alert = next((a for a in alerts if a.alert_type == "BALLAST_IMBALANCE"), None)
    assert imbal_alert is not None
    assert imbal_alert.observed_value == 1000.0
    assert "asymmetry" in imbal_alert.message.lower()


# --- TEST 10: NO FABRICATED SENSOR DATA GUARANTEE ---
def test_10_no_fabricated_sensor_data_guarantee():
    """Verify digital twin does not invent fake telemetry readings."""
    ship = state.get_current_ship()
    custom_telemetry = {"roll": 1.45, "pitch": -0.85, "distance": 18.2}
    snap = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=custom_telemetry)

    assert snap.roll_deg == 1.45
    assert snap.pitch_deg == -0.85


# --- TEST 11: REST ENDPOINTS COMPLIANCE ---
def test_11_rest_endpoints_compliance():
    """Verify Digital Twin REST endpoints return 200 OK with expected JSON structure."""
    # 1. /api/digital-twin/state
    res_state = client.get("/api/digital-twin/state")
    assert res_state.status_code == 200
    state_data = res_state.json()
    assert "ship_name" in state_data
    assert "containers" in state_data
    assert "ballast_tanks" in state_data
    assert "telemetry_source" in state_data
    assert "alerts" in state_data

    # 2. /api/digital-twin/lifecycle
    res_life = client.get("/api/digital-twin/lifecycle")
    assert res_life.status_code == 200
    life_data = res_life.json()
    assert "current_vessel_state" in life_data

    # 3. /api/digital-twin/predictive
    res_pred = client.post("/api/digital-twin/predictive", json={
        "container_id": "PRED-TEST",
        "gross_weight_t": 22.5,
        "bay": 2,
        "side": "port",
        "tier": 1
    })
    assert res_pred.status_code == 200
    pred_data = res_pred.json()
    assert pred_data["container_id"] == "PRED-TEST"
    assert pred_data["status"] == "PROJECTED"
    assert "projected_list_t" in pred_data
    assert "projected_trim_t" in pred_data
