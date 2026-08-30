"""
MareTide Phase 5: Normalized Telemetry & Source-Aware Abstraction Contract.

CRITICAL POLICY REQUIREMENT:
Load-cell sensor data (HX711 / scale cargo_kg / weighing sensors) MUST NOT be included
in the normalized vessel telemetry contract or used for cargo weight or stability calculations.
Container cargo weight is strictly sourced from DOCUMENT_AI.
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import time
import datetime


class TelemetrySource(str, Enum):
    """Permitted telemetry provenance sources."""
    HARDWARE_SENSOR = "HARDWARE_SENSOR"
    SIMULATED_TELEMETRY = "SIMULATED_TELEMETRY"
    SYSTEM_DERIVED = "SYSTEM_DERIVED"


class ConnectionStatus(str, Enum):
    """Real-time link status."""
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    SIMULATED = "SIMULATED"


class DataQuality(str, Enum):
    """Telemetry data quality rating."""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    INVALID = "INVALID"


class PumpState(str, Enum):
    """Ballast pump operational states."""
    IDLE = "IDLE"
    DRAINING = "DRAINING"
    FILLING = "FILLING"
    TRANSFERRING = "TRANSFERRING"
    OFF = "OFF"


class VesselStateTelemetry(BaseModel):
    """Dynamic vessel motion and attitude telemetry."""
    roll_deg: float = Field(0.0, description="Transverse roll / heel angle in degrees (-45.0 to +45.0)")
    pitch_deg: float = Field(0.0, description="Longitudinal pitch / trim angle in degrees (-25.0 to +25.0)")
    heave_m: float = Field(0.0, description="Vertical heave displacement in meters")
    heading_deg: float = Field(0.0, description="Compass heading in degrees (0.0 to 360.0)")
    draft_m: float = Field(8.5, description="Mean vessel draft in meters")
    rate_of_turn_deg_s: float = Field(0.0, description="Yaw rate of turn in degrees per second")


class BallastTankTelemetry(BaseModel):
    """Telemetry reading for an individual ballast tank."""
    tank_id: str = Field(..., description="Unique tank identifier, e.g. 'port_1', 'starboard_2'")
    name: str = Field(..., description="Human-readable tank name, e.g. 'Port Tank 1'")
    level_pct: float = Field(100.0, description="Tank fill percentage (0.0 to 100.0%)")
    distance_cm: float = Field(10.0, description="Ultrasonic sensor distance measurement in cm")
    volume_t: float = Field(300.0, description="Current ballast fluid volume in metric tonnes")
    capacity_t: float = Field(300.0, description="Total tank capacity in metric tonnes")
    fill_ratio: float = Field(1.0, description="Ratio of current volume to capacity (0.0 to 1.0)")
    status: str = Field("OK", description="Tank sensor status: 'OK', 'ALARM_HIGH', 'ALARM_LOW', 'SENSOR_FAULT'")


class PumpTelemetry(BaseModel):
    """Telemetry for ballast pump and valve subsystems."""
    pump_id: str = Field("PUMP_PRIMARY", description="Pump identifier")
    state: PumpState = Field(PumpState.IDLE, description="Current pump operational state")
    flow_rate_l_s: float = Field(0.0, description="Real-time flow rate in litres per second")
    target_qty_t: float = Field(0.0, description="Target ballast transfer quantity in metric tonnes")
    active_valve_open: bool = Field(False, description="Physical/servo gate valve state")
    last_command: Optional[str] = Field(None, description="Last command sent to pump controller")


class FlowTelemetry(BaseModel):
    """Ballast fluid line flow telemetry."""
    flow_rate_l_s: float = Field(0.0, description="Active line flow rate in litres per second")
    cumulative_volume_m3: float = Field(0.0, description="Cumulative volume transferred in cubic meters")
    direction: str = Field("DISCHARGE", description="Flow direction: 'DISCHARGE', 'INTAKE', 'INTERNAL'")
    sensor_healthy: bool = Field(True, description="Flow meter hardware integrity indicator")


class OperationalTelemetry(BaseModel):
    """Vessel operational stage and safety status."""
    status: str = Field("IDLE", description="Operational workflow status: 'IDLE', 'STANDBY', 'DRAINING', 'READY', 'ALARM'")
    risk_level: str = Field("SAFE", description="Stability risk level: 'SAFE', 'WARNING', 'CRITICAL'")
    is_emergency_stop: bool = Field(False, description="Emergency stop status")
    power_status: str = Field("NORMAL", description="Subsystem electrical power health: 'NORMAL', 'BACKUP', 'FAULT'")


class TelemetryMetadata(BaseModel):
    """Provenance, quality, and timing metadata."""
    adapter_id: str = Field("simulator_adapter", description="Active telemetry adapter identifier")
    latency_ms: float = Field(0.0, description="Processing and transport latency in milliseconds")
    sequence_number: int = Field(0, description="Monotonically increasing sequence packet counter")
    data_quality: DataQuality = Field(DataQuality.GOOD, description="Evaluated quality of the telemetry")
    stale_seconds: float = Field(0.0, description="Seconds elapsed since last valid packet update")
    raw_payload_checksum: Optional[str] = Field(None, description="Integrity checksum of raw packet")
    authoritative_weight_source: str = Field("DOCUMENT_AI", description="Authoritative cargo weight source policy")
    load_cell_policy: str = Field("FORBIDDEN_FOR_CARGO_AND_STABILITY", description="Exclusion policy flag")
    validation_status: str = Field("VALID", description="'VALID', 'CORRECTED', 'DEGRADED', 'INVALID'")
    warnings: List[str] = Field(default_factory=list, description="Validation or operational warnings")
    errors: List[str] = Field(default_factory=list, description="Validation or parsing errors")


class NormalizedTelemetry(BaseModel):
    """
    Unified, source-aware Normalized Telemetry Contract for MareTide.
    Contains ONLY permitted real-time vessel telemetry.
    DOES NOT contain cargo container weights from sensors.
    """
    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO-8601 UTC timestamp of normalized packet"
    )
    timestamp_epoch: float = Field(
        default_factory=time.time,
        description="Unix epoch float timestamp"
    )
    source: TelemetrySource = Field(
        TelemetrySource.SIMULATED_TELEMETRY,
        description="Source provenance: HARDWARE_SENSOR, SIMULATED_TELEMETRY, SYSTEM_DERIVED"
    )
    connection_status: ConnectionStatus = Field(
        ConnectionStatus.SIMULATED,
        description="Link connection status: CONNECTED, DISCONNECTED, STALE, DEGRADED, SIMULATED"
    )
    vessel_state: VesselStateTelemetry = Field(
        default_factory=VesselStateTelemetry,
        description="Vessel attitude and motion telemetry"
    )
    ballast_tanks: Dict[str, BallastTankTelemetry] = Field(
        default_factory=dict,
        description="Ballast tank level and distance telemetry"
    )
    pumps: Dict[str, PumpTelemetry] = Field(
        default_factory=dict,
        description="Ballast pump and valve states"
    )
    flow_info: FlowTelemetry = Field(
        default_factory=FlowTelemetry,
        description="Fluid flow measurement information"
    )
    operational_telemetry: OperationalTelemetry = Field(
        default_factory=OperationalTelemetry,
        description="Vessel operational and risk telemetry"
    )
    metadata: TelemetryMetadata = Field(
        default_factory=TelemetryMetadata,
        description="Provenance and data quality metadata"
    )


class TelemetryValidationResult(BaseModel):
    """Result of running validation checks on incoming raw or normalized telemetry."""
    is_valid: bool = True
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    prohibited_fields_detected: List[str] = Field(default_factory=list)
    sanitized_telemetry: Optional[NormalizedTelemetry] = None


class TelemetryHealthMetrics(BaseModel):
    """Subsystem performance, uptime, and quality statistics."""
    active_source: TelemetrySource
    active_adapter: str
    connection_status: ConnectionStatus
    data_quality: DataQuality
    packet_count: int = 0
    packets_per_second: float = 0.0
    stale_count: int = 0
    disconnect_count: int = 0
    malformed_count: int = 0
    prohibited_load_cell_attempts: int = 0
    uptime_seconds: float = 0.0
    last_packet_age_seconds: float = 0.0
    is_simulated: bool = True
