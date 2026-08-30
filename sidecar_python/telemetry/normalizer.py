"""
Telemetry Normalization Layer for MareTide.
Converts heterogeneous raw telemetry dictionaries and packets into the canonical
NormalizedTelemetry model with explicit provenance, source-awareness, and strict
enforcement of the Load-Cell Sensor Exclusion Policy.
"""

import time
import datetime
import hashlib
import json
import logging
from typing import Dict, Any, Optional, Tuple, List

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
    TelemetryMetadata
)

logger = logging.getLogger("telemetry.normalizer")

# Explicit Prohibited Load-Cell Sensor Keys
PROHIBITED_LOAD_CELL_KEYS = [
    "cargo_kg",
    "scale_kg",
    "load_cell",
    "hx711",
    "hx711_raw",
    "load_cell_mv",
    "sensor_cargo_weight",
    "scale_weight",
    "weighing_sensor"
]


class TelemetryNormalizer:
    """
    Transforms raw incoming telemetry packets into the standardized NormalizedTelemetry schema.
    Strictly purges any sensor-based cargo weights.
    """

    @classmethod
    def normalize_raw_packet(
        cls,
        raw_data: Optional[Dict[str, Any]],
        source: TelemetrySource,
        connection_status: ConnectionStatus = ConnectionStatus.CONNECTED,
        adapter_id: str = "generic_adapter",
        sequence_num: int = 0
    ) -> NormalizedTelemetry:
        """
        Normalizes a raw packet. If raw_data is None or empty, returns a safe default state.
        """
        if not raw_data:
            return cls.get_safe_fallback_telemetry(source=source, connection_status=connection_status)

        warnings: List[str] = []
        errors: List[str] = []
        now_epoch = time.time()

        # 1. Prohibited Load-Cell Detection & Stripping
        prohibited_detected = []
        for key in PROHIBITED_LOAD_CELL_KEYS:
            if key in raw_data:
                prohibited_detected.append(key)
                warnings.append(
                    f"Load-cell exclusion policy: Prohibited sensor field '{key}' detected and safely ignored."
                )

        # 2. Extract Timestamp
        raw_ts = raw_data.get("timestamp")
        raw_epoch = raw_data.get("timestamp_epoch")
        
        if raw_epoch is not None:
            try:
                epoch_val = float(raw_epoch)
            except (ValueError, TypeError):
                epoch_val = now_epoch
                errors.append("Invalid timestamp_epoch format; defaulted to current time.")
        else:
            epoch_val = now_epoch

        if raw_ts and isinstance(raw_ts, str):
            ts_str = raw_ts
        else:
            ts_str = datetime.datetime.fromtimestamp(epoch_val, datetime.timezone.utc).isoformat()

        # 3. Extract Vessel State
        roll = cls._safe_float(raw_data.get("roll", raw_data.get("roll_deg", 0.0)))
        pitch = cls._safe_float(raw_data.get("pitch", raw_data.get("pitch_deg", 0.0)))
        heave = cls._safe_float(raw_data.get("heave", raw_data.get("heave_m", 0.0)))
        heading = cls._safe_float(raw_data.get("heading", raw_data.get("heading_deg", 0.0)))
        draft = cls._safe_float(raw_data.get("draft", raw_data.get("draft_m", 8.5)))
        rot = cls._safe_float(raw_data.get("rot", raw_data.get("rate_of_turn_deg_s", 0.0)))

        vessel_state = VesselStateTelemetry(
            roll_deg=roll,
            pitch_deg=pitch,
            heave_m=heave,
            heading_deg=heading,
            draft_m=draft,
            rate_of_turn_deg_s=rot
        )

        # 4. Extract Ballast Tanks State
        distance = cls._safe_float(raw_data.get("distance", raw_data.get("distance_cm", 10.0)))
        ballast_pct = cls._safe_float(raw_data.get("ballast_pct", raw_data.get("ballast_level_pct", 100.0)))
        
        # Build structured tanks dictionary across standard 4 bays
        ballast_tanks: Dict[str, BallastTankTelemetry] = {}
        if "tanks" in raw_data and isinstance(raw_data["tanks"], dict):
            for k, t_data in raw_data["tanks"].items():
                if isinstance(t_data, dict):
                    ballast_tanks[k] = BallastTankTelemetry(
                        tank_id=k,
                        name=t_data.get("name", k.replace("_", " ").title()),
                        level_pct=cls._safe_float(t_data.get("level_pct", ballast_pct)),
                        distance_cm=cls._safe_float(t_data.get("distance_cm", distance)),
                        volume_t=cls._safe_float(t_data.get("volume_t", 300.0)),
                        capacity_t=cls._safe_float(t_data.get("capacity_t", 300.0)),
                        fill_ratio=cls._safe_float(t_data.get("fill_ratio", ballast_pct / 100.0)),
                        status=t_data.get("status", "OK")
                    )
        else:
            # Generate default representation based on active distance/pct
            for i in range(1, 5):
                p_key = f"port_{i}"
                s_key = f"starboard_{i}"
                ballast_tanks[p_key] = BallastTankTelemetry(
                    tank_id=p_key,
                    name=f"Port Tank {i}",
                    level_pct=ballast_pct,
                    distance_cm=distance,
                    volume_t=round((ballast_pct / 100.0) * 300.0, 1),
                    capacity_t=300.0,
                    fill_ratio=round(ballast_pct / 100.0, 3),
                    status="OK"
                )
                ballast_tanks[s_key] = BallastTankTelemetry(
                    tank_id=s_key,
                    name=f"Starboard Tank {i}",
                    level_pct=ballast_pct,
                    distance_cm=distance,
                    volume_t=round((ballast_pct / 100.0) * 300.0, 1),
                    capacity_t=300.0,
                    fill_ratio=round(ballast_pct / 100.0, 3),
                    status="OK"
                )

        # 5. Extract Pumps State
        status_str = str(raw_data.get("status", "IDLE")).upper()
        flow_rate = cls._safe_float(raw_data.get("flow_rate_l_s", raw_data.get("flow_l_s", 0.0)))
        cum_flow = cls._safe_float(raw_data.get("cumulative_flow_m3", 0.0))

        if "DRAIN" in status_str:
            pump_state = PumpState.DRAINING
            valve_open = True
            if flow_rate == 0.0:
                flow_rate = 0.85
        elif "FILL" in status_str:
            pump_state = PumpState.FILLING
            valve_open = True
            if flow_rate == 0.0:
                flow_rate = 0.85
        elif "TRANSFER" in status_str:
            pump_state = PumpState.TRANSFERRING
            valve_open = True
        else:
            pump_state = PumpState.IDLE
            valve_open = False

        pumps: Dict[str, PumpTelemetry] = {
            "PUMP_MAIN": PumpTelemetry(
                pump_id="PUMP_MAIN",
                state=pump_state,
                flow_rate_l_s=flow_rate,
                target_qty_t=cls._safe_float(raw_data.get("target_qty_t", 0.0)),
                active_valve_open=valve_open,
                last_command=raw_data.get("last_command")
            )
        }

        # 6. Extract Flow Telemetry
        flow_info = FlowTelemetry(
            flow_rate_l_s=flow_rate,
            cumulative_volume_m3=cum_flow,
            direction="DISCHARGE" if pump_state == PumpState.DRAINING else ("INTAKE" if pump_state == PumpState.FILLING else "INTERNAL"),
            sensor_healthy=True
        )

        # 7. Extract Operational Telemetry
        risk_str = str(raw_data.get("risk", raw_data.get("risk_level", "SAFE"))).upper()
        if risk_str not in ["SAFE", "WARNING", "CRITICAL"]:
            risk_str = "SAFE"

        operational_telemetry = OperationalTelemetry(
            status=status_str,
            risk_level=risk_str,
            is_emergency_stop=bool(raw_data.get("is_emergency_stop", False)),
            power_status="NORMAL"
        )

        # 8. Compute Checksum and Quality
        raw_str = json.dumps(raw_data, sort_keys=True, default=str)
        checksum = hashlib.md5(raw_str.encode("utf-8")).hexdigest()

        quality = DataQuality.GOOD
        if errors:
            quality = DataQuality.DEGRADED
        if connection_status == ConnectionStatus.STALE:
            quality = DataQuality.STALE
        elif connection_status == ConnectionStatus.DISCONNECTED:
            quality = DataQuality.DEGRADED

        metadata = TelemetryMetadata(
            adapter_id=adapter_id,
            latency_ms=round((now_epoch - epoch_val) * 1000.0, 2) if now_epoch >= epoch_val else 0.0,
            sequence_number=sequence_num,
            data_quality=quality,
            stale_seconds=max(0.0, round(now_epoch - epoch_val, 2)),
            raw_payload_checksum=checksum,
            authoritative_weight_source="DOCUMENT_AI",
            load_cell_policy="FORBIDDEN_FOR_CARGO_AND_STABILITY",
            validation_status="VALID" if not errors else "DEGRADED",
            warnings=warnings,
            errors=errors
        )

        # Determine telemetry provenance labels
        if source == TelemetrySource.HARDWARE_SENSOR:
            tel_label = "[HARDWARE SENSOR]"
            diag_load_label = "[HARDWARE SENSOR — DIAGNOSTIC ONLY]"
        elif source == TelemetrySource.SIMULATED_ESP32:
            tel_label = "[SIMULATED ESP32]"
            diag_load_label = "[SIMULATED ESP32 — DIAGNOSTIC ONLY]"
        else:
            tel_label = "[SIMULATED TELEMETRY]"
            diag_load_label = "[SIMULATED — DIAGNOSTIC ONLY]"

        provenance_map = {
            "roll": tel_label,
            "pitch": tel_label,
            "telemetry": tel_label,
            "container_weight": "[DOCUMENT AI]",
            "cargo_weight": "[DOCUMENT AI]",
            "stability_index": "[CALCULATED]",
            "vessel_hydrostatics": "[CALCULATED]",
            "recommended_placement": "[CALCULATED]",
            "operator_authorization": "[OPERATOR]",
            "diagnostic_load_cell": diag_load_label,
            "predictions": "[PREDICTED]"
        }

        # Extract isolated diagnostic load-cell value if provided in raw stream
        diag_load_kg = None
        for key in ["cargo_kg", "scale_kg", "load_cell", "hx711"]:
            if key in raw_data and raw_data[key] is not None:
                diag_load_kg = cls._safe_float(raw_data[key])
                break

        return NormalizedTelemetry(
            timestamp=ts_str,
            timestamp_epoch=epoch_val,
            source=source,
            connection_status=connection_status,
            vessel_state=vessel_state,
            ballast_tanks=ballast_tanks,
            pumps=pumps,
            flow_info=flow_info,
            operational_telemetry=operational_telemetry,
            metadata=metadata,
            provenance_map=provenance_map,
            diagnostic_load_cell_kg=diag_load_kg
        )

    @classmethod
    def get_safe_fallback_telemetry(
        cls,
        source: TelemetrySource = TelemetrySource.SYSTEM_DERIVED,
        connection_status: ConnectionStatus = ConnectionStatus.DISCONNECTED,
        reason: str = "Fallback to safe default vessel state"
    ) -> NormalizedTelemetry:
        """Constructs a deterministic, safe fallback telemetry state."""
        now = time.time()
        ts_str = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat()

        ballast_tanks: Dict[str, BallastTankTelemetry] = {}
        for i in range(1, 5):
            for side in ["port", "starboard"]:
                k = f"{side}_{i}"
                ballast_tanks[k] = BallastTankTelemetry(
                    tank_id=k,
                    name=f"{side.title()} Tank {i}",
                    level_pct=100.0,
                    distance_cm=10.0,
                    volume_t=300.0,
                    capacity_t=300.0,
                    fill_ratio=1.0,
                    status="SAFE_FALLBACK"
                )

        metadata = TelemetryMetadata(
            adapter_id="fallback_engine",
            latency_ms=0.0,
            sequence_number=0,
            data_quality=DataQuality.DEGRADED,
            stale_seconds=0.0,
            authoritative_weight_source="DOCUMENT_AI",
            load_cell_policy="FORBIDDEN_FOR_CARGO_AND_STABILITY",
            validation_status="DEGRADED",
            warnings=[reason],
            errors=[]
        )

        if source == TelemetrySource.HARDWARE_SENSOR:
            tel_label = "[HARDWARE SENSOR]"
            diag_load_label = "[HARDWARE SENSOR — DIAGNOSTIC ONLY]"
        elif source == TelemetrySource.SIMULATED_ESP32:
            tel_label = "[SIMULATED ESP32]"
            diag_load_label = "[SIMULATED ESP32 — DIAGNOSTIC ONLY]"
        else:
            tel_label = "[SIMULATED TELEMETRY]"
            diag_load_label = "[SIMULATED — DIAGNOSTIC ONLY]"

        provenance_map = {
            "roll": tel_label,
            "pitch": tel_label,
            "telemetry": tel_label,
            "container_weight": "[DOCUMENT AI]",
            "cargo_weight": "[DOCUMENT AI]",
            "stability_index": "[CALCULATED]",
            "vessel_hydrostatics": "[CALCULATED]",
            "recommended_placement": "[CALCULATED]",
            "operator_authorization": "[OPERATOR]",
            "diagnostic_load_cell": diag_load_label,
            "predictions": "[PREDICTED]"
        }

        return NormalizedTelemetry(
            timestamp=ts_str,
            timestamp_epoch=now,
            source=source,
            connection_status=connection_status,
            vessel_state=VesselStateTelemetry(),
            ballast_tanks=ballast_tanks,
            pumps={"PUMP_MAIN": PumpTelemetry(pump_id="PUMP_MAIN", state=PumpState.IDLE)},
            flow_info=FlowTelemetry(),
            operational_telemetry=OperationalTelemetry(status="IDLE", risk_level="SAFE"),
            metadata=metadata,
            provenance_map=provenance_map,
            diagnostic_load_cell_kg=None
        )

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default
