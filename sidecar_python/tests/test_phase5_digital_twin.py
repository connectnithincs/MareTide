"""
MareTide Phase 5 Test Suite: Upgraded Real-Time Digital Twin & Multi-Layer Provenance.

Validates:
1. Live telemetry refresh and timestamps
2. Stale data detection, retention of last known state, and alert generation
3. Disconnection handling without synthetic hardware data fabrication
4. Simulated telemetry provenance distinction ([SIMULATED TELEMETRY])
5. Hardware sensor telemetry provenance distinction ([HARDWARE SENSOR])
6. Multi-layer provenance map ([DOCUMENT AI], [CALCULATED], [HARDWARE SENSOR]/[SIMULATED TELEMETRY], [PREDICTED])
7. Strict load-cell exclusion (zero load-cell weight in Digital Twin)
8. Ballast tank refresh, pump operational state, and flow telemetry
9. Predicted vs Actual pre-load simulation comparison matrix
10. Four-stage lifecycle progression model
"""

import sys
import os
import copy
import time
import datetime
import pytest
from fastapi.testclient import TestClient

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ship import Ship, BallastTank, Container, StabilityAnalyzer
import state
from digital_twin import DigitalTwin
from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    ConnectionStatus,
    DataQuality,
    PumpState,
    VesselStateTelemetry,
    BallastTankTelemetry,
    PumpTelemetry,
    FlowTelemetry,
    OperationalTelemetry,
    TelemetryMetadata
)
from container_stability.models import DigitalTwinVesselState, FourStageLifecycle, PredictiveComparison
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    LOAD_CELL_POLICY,
    FORBIDDEN_WEIGHT_SOURCES
)
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_ship_state():
    """Ensure clean ship state for each test."""
    state.reset_state()


def _create_mock_telemetry(
    source: TelemetrySource = TelemetrySource.SIMULATED_TELEMETRY,
    connection_status: ConnectionStatus = ConnectionStatus.CONNECTED,
    data_quality: DataQuality = DataQuality.GOOD,
    roll_deg: float = 1.2,
    pitch_deg: float = 0.5,
    stale_seconds: float = 0.0,
    pump_state: PumpState = PumpState.IDLE,
    pump_flow: float = 0.0,
    active_valve: bool = False
) -> NormalizedTelemetry:
    """Helper to generate a structured NormalizedTelemetry instance for testing."""
    return NormalizedTelemetry(
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        timestamp_epoch=time.time(),
        source=source,
        connection_status=connection_status,
        vessel_state=VesselStateTelemetry(
            roll_deg=roll_deg,
            pitch_deg=pitch_deg,
            heave_m=0.0,
            heading_deg=180.0,
            draft_m=8.5,
            rate_of_turn_deg_s=0.0
        ),
        ballast_tanks={
            f"port_{i}": BallastTankTelemetry(
                tank_id=f"port_{i}",
                name=f"Port Tank {i}",
                level_pct=100.0,
                distance_cm=10.0,
                volume_t=300.0,
                capacity_t=300.0,
                fill_ratio=1.0,
                status="OK"
            ) for i in range(1, 5)
        },
        pumps={
            "PUMP_PRIMARY": PumpTelemetry(
                pump_id="PUMP_PRIMARY",
                state=pump_state,
                flow_rate_l_s=pump_flow,
                target_qty_t=0.0,
                active_valve_open=active_valve
            )
        },
        flow_info=FlowTelemetry(
            flow_rate_l_s=pump_flow,
            cumulative_volume_m3=0.0,
            direction="DISCHARGE",
            sensor_healthy=True
        ),
        operational_telemetry=OperationalTelemetry(
            status="IDLE",
            risk_level="SAFE"
        ),
        metadata=TelemetryMetadata(
            adapter_id="test_adapter",
            data_quality=data_quality,
            stale_seconds=stale_seconds,
            authoritative_weight_source=CONTAINER_WEIGHT_SOURCE,
            load_cell_policy=LOAD_CELL_POLICY
        )
    )


# 1. Live Telemetry Update
def test_digital_twin_live_telemetry_update():
    """Verify live snapshot integrates fresh normalized telemetry with timestamp and quality."""
    ship = state.get_current_ship()
    mock_tel = _create_mock_telemetry(
        source=TelemetrySource.SIMULATED_TELEMETRY,
        roll_deg=1.45,
        pitch_deg=-0.82,
        stale_seconds=0.2
    )

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_tel)

    assert snapshot.roll_deg == 1.45
    assert snapshot.pitch_deg == -0.82
    assert snapshot.telemetry_timestamp is not None
    assert snapshot.telemetry_freshness == "FRESH"
    assert snapshot.connection_status == "CONNECTED"
    assert snapshot.stale_seconds == 0.2
    assert snapshot.authoritative_weight_source == PROVENANCE_LABEL


# 2. Stale Data Handling
def test_digital_twin_stale_data_handling():
    """Verify snapshot preserves last known values, flags STALE, and adds alert when delay >= 5.0s."""
    ship = state.get_current_ship()
    mock_stale = _create_mock_telemetry(
        source=TelemetrySource.HARDWARE_SENSOR,
        roll_deg=2.1,
        pitch_deg=0.4,
        data_quality=DataQuality.STALE,
        stale_seconds=8.5
    )

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_stale)

    assert snapshot.roll_deg == 2.1  # Value preserved
    assert snapshot.pitch_deg == 0.4
    assert snapshot.telemetry_freshness == "STALE"
    assert snapshot.stale_seconds == 8.5

    # Check that a STALE_TELEMETRY alert is present
    alert_types = [a.alert_type for a in snapshot.alerts]
    assert "STALE_TELEMETRY" in alert_types


# 3. Disconnect Handling (Zero Data Fabrication)
def test_digital_twin_disconnect_handling():
    """Verify disconnected link preserves last values, sets DISCONNECTED, and does not synthesize fake data."""
    ship = state.get_current_ship()
    mock_disconnected = _create_mock_telemetry(
        source=TelemetrySource.HARDWARE_SENSOR,
        connection_status=ConnectionStatus.DISCONNECTED,
        roll_deg=1.8,
        pitch_deg=0.2,
        stale_seconds=15.0
    )

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_disconnected)

    assert snapshot.roll_deg == 1.8  # Preserved
    assert snapshot.connection_status == "DISCONNECTED"
    assert snapshot.telemetry_freshness == "DISCONNECTED"
    assert snapshot.telemetry_source == "HARDWARE_SENSOR"

    alert_types = [a.alert_type for a in snapshot.alerts]
    assert "TELEMETRY_DISCONNECTED" in alert_types


# 4. Simulated Telemetry Provenance
def test_digital_twin_simulated_telemetry_provenance():
    """Verify simulated telemetry is explicitly labeled [SIMULATED TELEMETRY]."""
    ship = state.get_current_ship()
    mock_sim = _create_mock_telemetry(source=TelemetrySource.SIMULATED_TELEMETRY)

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_sim)

    assert snapshot.is_simulated is True
    assert snapshot.telemetry_source == "SIMULATED_TELEMETRY"
    assert snapshot.provenance_map["telemetry"] == "[SIMULATED TELEMETRY]"


# 5. Hardware Sensor Provenance
def test_digital_twin_hardware_telemetry_provenance():
    """Verify physical hardware serial telemetry is explicitly labeled [HARDWARE SENSOR]."""
    ship = state.get_current_ship()
    mock_hw = _create_mock_telemetry(source=TelemetrySource.HARDWARE_SENSOR)

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_hw)

    assert snapshot.is_simulated is False
    assert snapshot.telemetry_source == "HARDWARE_SENSOR"
    assert snapshot.provenance_map["telemetry"] == "[HARDWARE SENSOR]"


# 6. Multi-Layer Provenance Map
def test_digital_twin_multi_layer_provenance_map():
    """Verify all 5 layers are distinctly tracked in provenance_map and stowed containers."""
    ship = state.get_current_ship()
    # Add a stowed container (simulating committed Document AI container)
    ship.add_container(Container(id="MSCU1234567", weight=24.5, bay=1, side="port", tier=1))

    mock_tel = _create_mock_telemetry(source=TelemetrySource.HARDWARE_SENSOR)
    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_tel)

    # Check multi-layer provenance mapping
    assert snapshot.provenance_map["cargo_weight"] == "[DOCUMENT AI]"
    assert snapshot.provenance_map["vessel_hydrostatics"] == "[CALCULATED]"
    assert snapshot.provenance_map["telemetry"] == "[HARDWARE SENSOR]"
    assert snapshot.provenance_map["predictions"] == "[PREDICTED]"

    # Check container provenance
    assert len(snapshot.containers) == 1
    assert snapshot.containers[0]["provenance"] == "[DOCUMENT AI]"
    assert snapshot.containers[0]["weight"] == 24.5


# 7. Strict Load-Cell Exclusion
def test_digital_twin_load_cell_exclusion():
    """Verify load-cell sensor measurements are strictly excluded from the Digital Twin cargo weight."""
    ship = state.get_current_ship()
    ship.add_container(Container(id="MSCU9999999", weight=28.0, bay=2, side="starboard", tier=1))

    # Pass dictionary that maliciously includes load-cell fields
    malicious_telemetry = {
        "roll": 0.5,
        "pitch": 0.1,
        "cargo_kg": 29500.0,  # Prohibited sensor weight
        "scale_kg": 29480.0,  # Prohibited
        "hx711_raw": 128490   # Prohibited
    }

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=malicious_telemetry)

    # Container weight must remain exactly 28.0 tonnes from the container model, unaffected by sensor
    assert snapshot.containers[0]["weight"] == 28.0
    assert snapshot.authoritative_weight_source in [PROVENANCE_LABEL, CONTAINER_WEIGHT_SOURCE, "[DOCUMENT AI]"]


# 8. Ballast Tank & Pump Refresh
def test_digital_twin_pump_state_and_flow_refresh():
    """Verify active pump state, transfer flow rate, and ballast tank levels are reflected."""
    ship = state.get_current_ship()
    mock_pump = _create_mock_telemetry(
        pump_state=PumpState.DRAINING,
        pump_flow=18.5,
        active_valve=True
    )

    snapshot = DigitalTwin.get_vessel_twin_snapshot(ship, telemetry=mock_pump)

    assert snapshot.pump_state == "DRAINING"
    assert snapshot.pump_flow_l_s == 18.5
    assert snapshot.pump_active is True
    assert len(snapshot.ballast_tanks) == 8


# 9. Predicted vs Actual Comparison Matrix
def test_digital_twin_predicted_vs_actual_matrix():
    """Verify side-by-side comparison between projected simulation and committed vessel state."""
    ship = state.get_current_ship()

    # Pre-load state: Projected
    comp_projected = DigitalTwin.get_predictive_comparison(
        current_ship=ship,
        container_id="MSCU7777777",
        gross_weight_t=25.0,
        bay=1,
        side="port",
        tier=1
    )

    assert comp_projected.status == "PROJECTED"
    assert comp_projected.actual_list_t is None

    # Post-load state: Committed
    ship.add_container(Container(id="MSCU7777777", weight=25.0, bay=1, side="port", tier=1))
    comp_committed = DigitalTwin.get_predictive_comparison(
        current_ship=ship,
        container_id="MSCU7777777",
        gross_weight_t=25.0,
        bay=1,
        side="port",
        tier=1
    )

    assert comp_committed.status == "COMMITTED"
    assert comp_committed.actual_list_t is not None
    assert comp_committed.projected_list_t == comp_committed.actual_list_t


# 10. Four-Stage Lifecycle Progression Model
def test_digital_twin_four_stage_lifecycle():
    """Verify four-stage lifecycle progression builds before, loaded, ballasted, and current snapshots."""
    ship_before = state.get_current_ship()
    
    ship_loaded = copy.deepcopy(ship_before)
    ship_loaded.add_container(Container(id="MSCU8888888", weight=26.0, bay=1, side="port", tier=1))

    ship_ballasted = copy.deepcopy(ship_loaded)
    ship_ballasted.tanks["port_1"].remove_water(26.0)

    lifecycle = DigitalTwin.get_four_stage_lifecycle(
        ship_before=ship_before,
        ship_loaded=ship_loaded,
        ship_ballasted=ship_ballasted,
        current_ship=ship_ballasted
    )

    assert lifecycle.vessel_before is not None
    assert lifecycle.vessel_before.operation_status == "BEFORE_CONTAINER"
    assert lifecycle.container_loaded is not None
    assert lifecycle.container_loaded.operation_status == "CONTAINER_LOADED"
    assert lifecycle.ballast_compensated is not None
    assert lifecycle.ballast_compensated.operation_status == "BALLAST_COMPENSATED"
    assert lifecycle.current_vessel_state.operation_status == "CURRENT_STATE"
