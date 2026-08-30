"""
FastAPI REST Routes for MareTide Phase 5 Telemetry Subsystem.
Exposes real-time normalized telemetry, source switching, health metrics,
and simulation controls.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from telemetry.models import (
    NormalizedTelemetry,
    TelemetrySource,
    TelemetryHealthMetrics,
    TelemetryValidationResult
)
from telemetry.manager import TelemetryManager
from telemetry.validator import TelemetryValidator
from telemetry.adapters.hardware_adapter import HardwareSerialAdapter

router = APIRouter(prefix="/api/telemetry", tags=["Real-Time Telemetry Subsystem"])


class SourceSelectRequest(BaseModel):
    source: TelemetrySource = Field(..., description="'HARDWARE_SENSOR' or 'SIMULATED_TELEMETRY'")
    port: Optional[str] = Field(default=None, description="Optional serial COM port name (e.g. 'COM3', '/dev/ttyUSB0')")


class SimulationOverrideRequest(BaseModel):
    roll_deg: Optional[float] = Field(default=None, description="Simulated roll angle in degrees")
    pitch_deg: Optional[float] = Field(default=None, description="Simulated pitch angle in degrees")
    ballast_pct: Optional[float] = Field(default=None, description="Simulated ballast percentage (0-100)")


class TelemetryValidateRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="Raw or normalized telemetry dictionary to validate")
    strict_load_cell_check: bool = Field(default=True, description="Strictly reject any load-cell sensor measurements")


@router.get(
    "/live",
    response_model=NormalizedTelemetry,
    summary="Get Real-Time Normalized Telemetry",
    description="Returns the unified normalized vessel telemetry contract with source provenance, quality rating, and explicit load cell exclusion."
)
async def get_live_telemetry():
    mgr = TelemetryManager.get_instance()
    return mgr.get_latest_telemetry()


@router.get(
    "/health",
    response_model=TelemetryHealthMetrics,
    summary="Get Telemetry Subsystem Health Metrics",
    description="Returns packet statistics, connection freshness, drop counters, and quality diagnostics."
)
async def get_telemetry_health():
    mgr = TelemetryManager.get_instance()
    return mgr.get_health_metrics()


@router.get(
    "/sources",
    summary="List Available Telemetry Sources",
    description="Returns available telemetry adapters, active source, detected hardware COM ports, and provenance policy."
)
async def list_telemetry_sources():
    mgr = TelemetryManager.get_instance()
    active_adapter = mgr.get_active_adapter()
    available_ports = HardwareSerialAdapter.get_available_ports()

    return {
        "success": True,
        "active_source": active_adapter.source_type.value,
        "active_adapter_id": active_adapter.adapter_id,
        "is_simulated": active_adapter.is_simulated,
        "available_sources": [s.value for s in TelemetrySource],
        "detected_hardware_ports": available_ports,
        "authoritative_cargo_source": "DOCUMENT_AI",
        "load_cell_sensor_policy": "FORBIDDEN_FOR_CARGO_AND_STABILITY"
    }


@router.post(
    "/source/select",
    summary="Switch Telemetry Source",
    description="Switches the active telemetry collection engine between Hardware Serial UART and Simulator."
)
async def select_telemetry_source(req: SourceSelectRequest):
    mgr = TelemetryManager.get_instance()
    success = mgr.select_source(req.source, port=req.port)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to switch telemetry source.")

    return {
        "success": True,
        "message": f"Telemetry source switched to {req.source.value}",
        "active_source": req.source.value,
        "port": req.port
    }


@router.post(
    "/simulate/override",
    summary="Apply Simulator Overrides",
    description="Injects custom manual tilt (roll/pitch) and ballast levels into the simulated vessel engine."
)
async def apply_simulator_overrides(req: SimulationOverrideRequest):
    mgr = TelemetryManager.get_instance()
    mgr.set_simulator_overrides(
        roll=req.roll_deg,
        pitch=req.pitch_deg,
        ballast_pct=req.ballast_pct
    )
    return {
        "success": True,
        "message": "Simulator overrides applied.",
        "overrides": req.model_dump()
    }


@router.post(
    "/simulate/clear",
    summary="Clear Simulator Overrides",
    description="Restores automatic natural wave dynamics and standard ballast levels in the simulator."
)
async def clear_simulator_overrides():
    mgr = TelemetryManager.get_instance()
    mgr.clear_simulator_overrides()
    return {
        "success": True,
        "message": "Simulator overrides cleared. Natural wave dynamics restored."
    }


@router.post(
    "/validate",
    response_model=TelemetryValidationResult,
    summary="Validate Telemetry Packet",
    description="Validates a telemetry packet against physical limits, timestamp freshness, and load-cell exclusion criteria."
)
async def validate_telemetry_packet(req: TelemetryValidateRequest):
    result = TelemetryValidator.validate_raw_packet(
        raw_data=req.payload,
        strict_load_cell_check=req.strict_load_cell_check
    )
    return result
