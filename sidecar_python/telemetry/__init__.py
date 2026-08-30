"""
MareTide Telemetry Subsystem Package.
Provides unified normalized telemetry, source-awareness, and sensor decoupling.
"""

from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    ConnectionStatus,
    DataQuality,
    VesselStateTelemetry,
    BallastTankTelemetry,
    PumpTelemetry,
    PumpState,
    FlowTelemetry,
    OperationalTelemetry,
    TelemetryMetadata,
    TelemetryValidationResult,
    TelemetryHealthMetrics
)
from telemetry.adapters.base import BaseTelemetryAdapter
from telemetry.adapters.hardware_adapter import HardwareSerialAdapter
from telemetry.adapters.simulator_adapter import SimulatorTelemetryAdapter
from telemetry.normalizer import TelemetryNormalizer
from telemetry.validator import TelemetryValidator
from telemetry.quality_monitor import TelemetryQualityMonitor
from telemetry.manager import TelemetryManager
from telemetry.routes import router as telemetry_router

__all__ = [
    "NormalizedTelemetry",
    "TelemetrySource",
    "ConnectionStatus",
    "DataQuality",
    "VesselStateTelemetry",
    "BallastTankTelemetry",
    "PumpTelemetry",
    "PumpState",
    "FlowTelemetry",
    "OperationalTelemetry",
    "TelemetryMetadata",
    "TelemetryValidationResult",
    "TelemetryHealthMetrics",
    "BaseTelemetryAdapter",
    "HardwareSerialAdapter",
    "SimulatorTelemetryAdapter",
    "TelemetryNormalizer",
    "TelemetryValidator",
    "TelemetryQualityMonitor",
    "TelemetryManager",
    "telemetry_router"
]
