"""
Telemetry Validation Layer for MareTide.
Enforces physical plausibility limits, timestamp validity, malformed packet rejection,
and strict load-cell sensor exclusion policy.
"""

import time
import datetime
import math
import logging
from typing import Dict, Any, Optional, List, Tuple

from telemetry.models import (
    NormalizedTelemetry,
    TelemetryValidationResult,
    TelemetrySource
)
from telemetry.normalizer import PROHIBITED_LOAD_CELL_KEYS, TelemetryNormalizer

logger = logging.getLogger("telemetry.validator")


class TelemetryValidator:
    """
    Validates physical constraints, timing semantics, data formats, and exclusion policies.
    """

    # Physical plausibility threshold boundaries
    MAX_ROLL_DEG = 45.0
    MIN_ROLL_DEG = -45.0
    MAX_PITCH_DEG = 25.0
    MIN_PITCH_DEG = -25.0
    MAX_BALLAST_PCT = 100.0
    MIN_BALLAST_PCT = 0.0
    MAX_DISTANCE_CM = 500.0
    MIN_DISTANCE_CM = 0.0
    MAX_FLOW_RATE_L_S = 1000.0
    MIN_FLOW_RATE_L_S = 0.0
    
    # Timing limits (seconds)
    MAX_FUTURE_TOLERANCE_SEC = 5.0
    MAX_STALE_TOLERANCE_SEC = 60.0

    @classmethod
    def validate_raw_packet(
        cls,
        raw_data: Any,
        source: TelemetrySource = TelemetrySource.SIMULATED_TELEMETRY,
        strict_load_cell_check: bool = False
    ) -> TelemetryValidationResult:
        """
        Validates a raw dictionary packet before normalization.
        """
        errors: List[str] = []
        warnings: List[str] = []
        prohibited_detected: List[str] = []

        if not isinstance(raw_data, dict):
            return TelemetryValidationResult(
                is_valid=False,
                errors=["Malformed packet: Payload is not a valid key-value dictionary."],
                warnings=[],
                prohibited_fields_detected=[],
                sanitized_telemetry=TelemetryNormalizer.get_safe_fallback_telemetry(source=source)
            )

        # 1. Check for Prohibited Load-Cell Fields
        for key in PROHIBITED_LOAD_CELL_KEYS:
            if key in raw_data:
                prohibited_detected.append(key)
                msg = f"Prohibited load-cell sensor field '{key}' detected in telemetry payload."
                if strict_load_cell_check:
                    errors.append(f"Security/Policy Violation: {msg} Load cell sensor data is FORBIDDEN for stability and cargo operations.")
                else:
                    warnings.append(f"Policy Warning: {msg} Field safely ignored and dropped.")

        # 2. Timestamp Validation
        now = time.time()
        raw_epoch = raw_data.get("timestamp_epoch")
        raw_ts = raw_data.get("timestamp")

        parsed_epoch: Optional[float] = None
        if raw_epoch is not None:
            try:
                parsed_epoch = float(raw_epoch)
            except (ValueError, TypeError):
                errors.append(f"Invalid timestamp_epoch value '{raw_epoch}': must be numeric.")

        if raw_ts is not None and isinstance(raw_ts, str):
            try:
                # Validate ISO format
                dt = datetime.datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if parsed_epoch is None:
                    parsed_epoch = dt.timestamp()
            except Exception:
                warnings.append(f"Timestamp '{raw_ts}' does not conform to strict ISO-8601 format.")

        if parsed_epoch is not None:
            # Check future clock skew
            if parsed_epoch - now > cls.MAX_FUTURE_TOLERANCE_SEC:
                errors.append(
                    f"Timestamp is in the future ({parsed_epoch - now:.1f}s ahead of local clock). Possible clock desynchronization."
                )
            # Check excessive age
            elif now - parsed_epoch > cls.MAX_STALE_TOLERANCE_SEC:
                warnings.append(
                    f"Timestamp is stale ({now - parsed_epoch:.1f}s old, exceeding {cls.MAX_STALE_TOLERANCE_SEC}s threshold)."
                )

        # 3. Physical Boundary Validation
        cls._validate_numeric_field(raw_data, "roll", cls.MIN_ROLL_DEG, cls.MAX_ROLL_DEG, errors, warnings)
        cls._validate_numeric_field(raw_data, "pitch", cls.MIN_PITCH_DEG, cls.MAX_PITCH_DEG, errors, warnings)
        cls._validate_numeric_field(raw_data, "ballast_pct", cls.MIN_BALLAST_PCT, cls.MAX_BALLAST_PCT, errors, warnings)
        cls._validate_numeric_field(raw_data, "distance", cls.MIN_DISTANCE_CM, cls.MAX_DISTANCE_CM, errors, warnings)
        cls._validate_numeric_field(raw_data, "flow_rate_l_s", cls.MIN_FLOW_RATE_L_S, cls.MAX_FLOW_RATE_L_S, errors, warnings)

        is_valid = (len(errors) == 0)
        
        # Build sanitized normalized telemetry
        sanitized = TelemetryNormalizer.normalize_raw_packet(
            raw_data=raw_data if is_valid or not strict_load_cell_check else None,
            source=source
        )

        return TelemetryValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            prohibited_fields_detected=prohibited_detected,
            sanitized_telemetry=sanitized
        )

    @classmethod
    def validate_normalized_telemetry(cls, telemetry: NormalizedTelemetry) -> TelemetryValidationResult:
        """
        Validates an existing NormalizedTelemetry instance against physical and data invariants.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Vessel attitude checks
        roll = telemetry.vessel_state.roll_deg
        pitch = telemetry.vessel_state.pitch_deg
        if not (cls.MIN_ROLL_DEG <= roll <= cls.MAX_ROLL_DEG):
            errors.append(f"Roll angle {roll}° exceeds physical boundaries [{cls.MIN_ROLL_DEG}, {cls.MAX_ROLL_DEG}].")
        if not (cls.MIN_PITCH_DEG <= pitch <= cls.MAX_PITCH_DEG):
            errors.append(f"Pitch angle {pitch}° exceeds physical boundaries [{cls.MIN_PITCH_DEG}, {cls.MAX_PITCH_DEG}].")

        # 2. Ballast tank checks
        for tid, tank in telemetry.ballast_tanks.items():
            if not (0.0 <= tank.level_pct <= 100.0):
                errors.append(f"Tank '{tid}' level_pct {tank.level_pct}% out of range [0, 100].")
            if not (0.0 <= tank.fill_ratio <= 1.0):
                errors.append(f"Tank '{tid}' fill_ratio {tank.fill_ratio} out of range [0, 1].")

        # 3. Source check
        if telemetry.source not in [TelemetrySource.HARDWARE_SENSOR, TelemetrySource.SIMULATED_TELEMETRY, TelemetrySource.SYSTEM_DERIVED]:
            errors.append(f"Invalid telemetry source '{telemetry.source}'.")

        # 4. Provenance assertion check
        if telemetry.metadata.authoritative_weight_source != "DOCUMENT_AI":
            errors.append(
                f"Policy Violation: Authoritative weight source is '{telemetry.metadata.authoritative_weight_source}', expected 'DOCUMENT_AI'."
            )

        return TelemetryValidationResult(
            is_valid=(len(errors) == 0),
            errors=errors,
            warnings=warnings,
            prohibited_fields_detected=[],
            sanitized_telemetry=telemetry
        )

    @classmethod
    def _validate_numeric_field(
        cls,
        data: Dict[str, Any],
        key: str,
        min_val: float,
        max_val: float,
        errors: List[str],
        warnings: List[str]
    ):
        if key in data and data[key] is not None:
            try:
                v = float(data[key])
                if math.isnan(v) or math.isinf(v):
                    errors.append(f"Field '{key}' has non-finite numeric value (NaN or Inf).")
                elif not (min_val <= v <= max_val):
                    errors.append(f"Field '{key}' value {v} exceeds allowable range [{min_val}, {max_val}].")
            except (ValueError, TypeError):
                errors.append(f"Field '{key}' value '{data[key]}' cannot be parsed as numeric float.")
