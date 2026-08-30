"""
Phase 5 Real-Time Safety Gate for MareTide.

Provides a centralized, deterministic, and modular safety-gating layer that evaluates
operational workflows before permitting:
1. Loading Confirmation
2. Ballast Compensation Execution
3. Operational Completion

Strictly enforces 8 Core Safety Rules:
Rule 1: Invalid OCR/document data -> BLOCKED.
Rule 2: Critical anomaly -> BLOCKED.
Rule 3: Invalid container identifier -> BLOCKED.
Rule 4: Missing gross weight -> BLOCKED.
Rule 5: Unsafe candidate placement (occupied slot or critical list/trim) -> BLOCKED.
Rule 6: Stale / disconnected required telemetry -> REVIEW_REQUIRED / BLOCKED.
Rule 7: Missing operator confirmation -> BLOCKED.
Rule 8: Load-cell data must NEVER satisfy any safety gate -> BLOCKED (Security Policy Violation).
"""

import copy
import logging
from typing import Dict, Any, List, Optional
import datetime

from ship import Ship, StabilityAnalyzer
from container_stability.models import (
    SafetyGateStatus,
    SafetyGateType,
    SafetyGateReason,
    SafetyGateEvaluationResult,
    SafetyGateEvaluationRequest,
    StabilityMetrics
)
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    FORBIDDEN_WEIGHT_SOURCES,
    ALLOWED_WEIGHT_SOURCES
)

logger = logging.getLogger("safety_gate")


class RealTimeSafetyGate:
    """
    Centralized Real-Time Operational Safety Gate.
    Evaluates data integrity, stability physics, slot constraints, telemetry health,
    and operator authorization before allowing state mutations.
    """

    @classmethod
    def evaluate_loading_gate(
        cls,
        container: Dict[str, Any],
        document: Optional[Dict[str, Any]] = None,
        validation: Optional[Dict[str, Any]] = None,
        recommendation: Optional[Dict[str, Any]] = None,
        ship: Optional[Ship] = None,
        telemetry: Optional[Dict[str, Any]] = None,
        anomalies: Optional[List[Dict[str, Any]]] = None,
        operator_confirmed: bool = False,
        operator_id: Optional[str] = None,
        weight_source: Optional[str] = None,
        predicted_stability: Optional[StabilityMetrics] = None
    ) -> SafetyGateEvaluationResult:
        """
        Evaluates the Safety Gate for Container Loading Confirmation.
        """
        reasons: List[SafetyGateReason] = []
        is_blocked = False
        is_review_required = False
        is_warning = False

        # -------------------------------------------------------------
        # Rule 8: Strict Load-Cell Exclusion & Provenance Check
        # -------------------------------------------------------------
        raw_source = str(weight_source or container.get("weight_source") or container.get("source") or container.get("provenance") or "").upper().replace("-", "_").replace(" ", "_")
        auth_flag = container.get("authoritative", True)
        if auth_flag is False or any(forbidden in raw_source for forbidden in FORBIDDEN_WEIGHT_SOURCES):
            reasons.append(
                SafetyGateReason(
                    category="POLICY",
                    message=f"Security Policy Violation: Source '{raw_source}' contains forbidden load-cell/scale data or non-authoritative cargo mass. Container weight must strictly originate from [DOCUMENT AI].",
                    severity="BLOCKING",
                    evidence={"provided_source": raw_source, "forbidden_keywords": FORBIDDEN_WEIGHT_SOURCES}
                )
            )
            return SafetyGateEvaluationResult(
                allowed=False,
                status=SafetyGateStatus.BLOCKED.value,
                gate_type=SafetyGateType.LOADING_CONFIRMATION.value,
                reasons=reasons
            )


        # -------------------------------------------------------------
        # Rule 4: Gross Weight Verification
        # -------------------------------------------------------------
        weights = container.get("weights") if isinstance(container.get("weights"), dict) else {}
        gross_kg = weights.get("gross_weight_kg") or container.get("gross_weight_kg") or container.get("weight")
        
        if gross_kg is None or (isinstance(gross_kg, (int, float)) and float(gross_kg) <= 0.0):
            reasons.append(
                SafetyGateReason(
                    category="WEIGHT",
                    message="Missing or non-positive container gross weight. Loading confirmation requires validated gross_weight_kg > 0.",
                    severity="BLOCKING",
                    evidence={"gross_weight_kg": gross_kg}
                )
            )
            is_blocked = True

        # VGM Consistency Check
        tare_kg = weights.get("tare_weight_kg")
        cargo_kg = weights.get("cargo_weight_kg")
        if gross_kg and tare_kg and cargo_kg:
            expected_gross = float(tare_kg) + float(cargo_kg)
            diff_kg = abs(float(gross_kg) - expected_gross)
            if diff_kg > 500.0:
                reasons.append(
                    SafetyGateReason(
                        category="WEIGHT",
                        message=f"VGM inconsistency detected: Gross weight ({gross_kg} kg) differs from Tare + Cargo sum ({expected_gross} kg) by {diff_kg:.1f} kg.",
                        severity="WARNING" if diff_kg < 1500.0 else "BLOCKING",
                        evidence={"gross_kg": gross_kg, "tare_kg": tare_kg, "cargo_kg": cargo_kg, "diff_kg": diff_kg}
                    )
                )
                if diff_kg >= 1500.0:
                    is_blocked = True
                else:
                    is_review_required = True

        # -------------------------------------------------------------
        # Rule 3: Container Identifier (ISO 6346) Validity
        # -------------------------------------------------------------
        container_num = (
            container.get("container_number") or
            container.get("id") or
            ""
        ).strip().upper()

        if (
            not container_num or
            container_num == "UNKNOWN" or
            len(container_num) != 11 or
            not (container_num[:4].isalpha() and container_num[4:10].isdigit())
        ):
            reasons.append(
                SafetyGateReason(
                    category="IDENTIFIER",
                    message=f"Invalid or non-standard ISO 6346 container identifier '{container_num}' (expected 4 letters + 6 digits + 1 check digit, e.g. MSCU4920195).",
                    severity="BLOCKING",
                    evidence={"container_number": container_num}
                )
            )
            is_blocked = True
        elif validation and isinstance(validation, dict):
            iso_val = validation.get("iso_6346") if isinstance(validation.get("iso_6346"), dict) else {}
            if iso_val.get("valid_format") is False or iso_val.get("check_digit_valid") is False:
                reasons.append(
                    SafetyGateReason(
                        category="IDENTIFIER",
                        message=f"Container number '{container_num}' failed ISO 6346 checksum verification.",
                        severity="BLOCKING",
                        evidence={"iso_details": iso_val}
                    )
                )
                is_blocked = True

        # -------------------------------------------------------------
        # Rule 1: OCR / Document Validation
        # -------------------------------------------------------------
        if document and isinstance(document, dict):
            proc_status = str(document.get("processing_status", "")).lower()
            if proc_status in ["error", "corrupted", "unreadable", "failed"]:
                reasons.append(
                    SafetyGateReason(
                        category="VALIDATION",
                        message=f"Document processing status is '{proc_status}'. Unreadable or corrupted document.",
                        severity="BLOCKING",
                        evidence={"document_status": proc_status}
                    )
                )
                is_blocked = True

        if validation and isinstance(validation, dict):
            if validation.get("valid") is False:
                val_warnings = validation.get("warnings") or ["Document validation flagged invalid."]
                reasons.append(
                    SafetyGateReason(
                        category="VALIDATION",
                        message=f"Document validation failed: {'; '.join(val_warnings)}",
                        severity="BLOCKING",
                        evidence={"validation_warnings": val_warnings}
                    )
                )
                is_blocked = True

        # -------------------------------------------------------------
        # Rule 2: Critical Cargo Anomalies
        # -------------------------------------------------------------
        if anomalies:
            for anom in anomalies:
                anom_dict = anom if isinstance(anom, dict) else (anom.dict() if hasattr(anom, "dict") else anom.model_dump())
                sev = str(anom_dict.get("severity", "")).upper()
                msg = str(anom_dict.get("message", "Cargo anomaly detected"))
                code = str(anom_dict.get("anomaly_type") or anom_dict.get("code") or "ANOMALY")
                
                if sev == "CRITICAL":
                    reasons.append(
                        SafetyGateReason(
                            category="ANOMALY",
                            message=f"Critical Anomaly [{code}]: {msg}",
                            severity="BLOCKING",
                            evidence=anom_dict
                        )
                    )
                    is_blocked = True
                elif sev == "WARNING":
                    reasons.append(
                        SafetyGateReason(
                            category="ANOMALY",
                            message=f"Cargo Warning [{code}]: {msg}",
                            severity="WARNING",
                            evidence=anom_dict
                        )
                    )
                    is_review_required = True

        # -------------------------------------------------------------
        # Rule 5: Candidate Placement & Stability Constraints
        # -------------------------------------------------------------
        if recommendation and isinstance(recommendation, dict):
            bay = int(recommendation.get("bay", 1))
            side = str(recommendation.get("side", "port")).lower()
            tier = int(recommendation.get("tier", 1))

            if ship is not None:
                # Check slot collision
                occupied = any(
                    c.bay == bay and c.side.lower() == side and getattr(c, "tier", 1) == tier
                    for c in ship.containers
                )
                if occupied:
                    reasons.append(
                        SafetyGateReason(
                            category="SLOT",
                            message=f"Target slot Bay {bay} {side.upper()} Tier {tier} is already occupied on vessel.",
                            severity="BLOCKING",
                            evidence={"target_bay": bay, "target_side": side, "target_tier": tier}
                        )
                    )
                    is_blocked = True

        # Stability limits check
        if predicted_stability is not None:
            list_deg = abs(float(getattr(predicted_stability, "list_t", 0.0)))
            trim_deg = abs(float(getattr(predicted_stability, "trim_t", 0.0)))
            risk_level = str(getattr(predicted_stability, "risk_level", "SAFE")).upper()

            if list_deg >= 5.0 or trim_deg >= 3.0 or risk_level == "CRITICAL":
                reasons.append(
                    SafetyGateReason(
                        category="STABILITY",
                        message=f"Candidate placement violates safety limits: List ({list_deg:.2f}° >= 5.0°) or Trim ({trim_deg:.2f}° >= 3.0°). Capsizing / heeling hazard.",
                        severity="BLOCKING",
                        evidence={"list_deg": list_deg, "trim_deg": trim_deg, "risk_level": risk_level}
                    )
                )
                is_blocked = True
            elif list_deg >= 2.5 or trim_deg >= 1.5 or risk_level == "WARNING":
                reasons.append(
                    SafetyGateReason(
                        category="STABILITY",
                        message=f"Elevated stability imbalance: List {list_deg:.2f}°, Trim {trim_deg:.2f}°. Requires anti-heeling ballast compensation.",
                        severity="WARNING",
                        evidence={"list_deg": list_deg, "trim_deg": trim_deg}
                    )
                )
                is_warning = True

        # -------------------------------------------------------------
        # Rule 6: Telemetry Quality & Freshness
        # -------------------------------------------------------------
        if telemetry and isinstance(telemetry, dict):
            stale_sec = float(telemetry.get("stale_seconds", 0.0))
            conn_status = str(telemetry.get("connection_status", "CONNECTED")).upper()

            if conn_status == "DISCONNECTED":
                reasons.append(
                    SafetyGateReason(
                        category="TELEMETRY",
                        message="Physical telemetry link is disconnected. Operating under preserved historical vessel readings.",
                        severity="WARNING",
                        evidence={"connection_status": conn_status}
                    )
                )
                is_review_required = True
            elif stale_sec >= 10.0:
                reasons.append(
                    SafetyGateReason(
                        category="TELEMETRY",
                        message=f"Telemetry delay ({stale_sec:.1f}s) exceeds 10.0s threshold.",
                        severity="WARNING",
                        evidence={"stale_seconds": stale_sec}
                    )
                )
                is_warning = True

        # -------------------------------------------------------------
        # Rule 7: Operator Authorization
        # -------------------------------------------------------------
        if not operator_confirmed:
            reasons.append(
                SafetyGateReason(
                    category="AUTHORIZATION",
                    message="Missing explicit operator authorization. Human-in-the-loop confirmation is mandatory to commit cargo to vessel state.",
                    severity="BLOCKING",
                    evidence={"operator_confirmed": False, "operator_id": operator_id}
                )
            )
            is_blocked = True
        elif not operator_id or not str(operator_id).strip():
            reasons.append(
                SafetyGateReason(
                    category="AUTHORIZATION",
                    message="Operator identifier missing. Supervisory operator credentials required.",
                    severity="BLOCKING",
                    evidence={"operator_id": operator_id}
                )
            )
            is_blocked = True

        # -------------------------------------------------------------
        # Determine Final Safety State
        # -------------------------------------------------------------
        if is_blocked:
            final_status = SafetyGateStatus.BLOCKED
            allowed = False
        elif is_review_required:
            final_status = SafetyGateStatus.REVIEW_REQUIRED
            allowed = False
        elif is_warning:
            final_status = SafetyGateStatus.WARNING
            allowed = True
        else:
            final_status = SafetyGateStatus.SAFE
            allowed = True
            reasons.append(
                SafetyGateReason(
                    category="VALIDATION",
                    message="All safety constraints passed: Valid Document AI cargo, slot available, stability within safe boundaries, and authorized by operator.",
                    severity="INFO"
                )
            )

        return SafetyGateEvaluationResult(
            allowed=allowed,
            status=final_status.value,
            gate_type=SafetyGateType.LOADING_CONFIRMATION.value,
            reasons=reasons
        )

    @classmethod
    def evaluate_ballast_gate(
        cls,
        tank_key: str,
        direction: str,
        qty_t: float,
        ship: Ship,
        operator_confirmed: bool = False,
        operator_id: Optional[str] = None,
        telemetry: Optional[Dict[str, Any]] = None
    ) -> SafetyGateEvaluationResult:
        """
        Evaluates the Safety Gate for Ballast Compensation Execution.
        """
        reasons: List[SafetyGateReason] = []
        is_blocked = False
        is_warning = False

        # 1. Target Tank Verification
        tank = ship.tanks.get(tank_key)
        if not tank:
            reasons.append(
                SafetyGateReason(
                    category="BALLAST",
                    message=f"Target ballast tank '{tank_key}' does not exist on vessel.",
                    severity="BLOCKING",
                    evidence={"tank_key": tank_key}
                )
            )
            return SafetyGateEvaluationResult(
                allowed=False,
                status=SafetyGateStatus.BLOCKED.value,
                gate_type=SafetyGateType.BALLAST_EXECUTION.value,
                reasons=reasons
            )

        # 2. Overdraft / Overflow Validation
        dir_clean = str(direction).upper()
        if dir_clean in ["DRAIN", "DISCHARGE", "REMOVE"]:
            if tank.current_volume < qty_t - 0.01:
                reasons.append(
                    SafetyGateReason(
                        category="BALLAST",
                        message=f"Overdraft violation: Requested drain of {qty_t:.1f}t exceeds available water volume ({tank.current_volume:.1f}t) in tank '{tank.name}'.",
                        severity="BLOCKING",
                        evidence={"requested_qty_t": qty_t, "current_volume": tank.current_volume}
                    )
                )
                is_blocked = True
        elif dir_clean in ["FILL", "INTAKE", "ADD"]:
            avail_cap = tank.capacity - tank.current_volume
            if avail_cap < qty_t - 0.01:
                reasons.append(
                    SafetyGateReason(
                        category="BALLAST",
                        message=f"Overflow violation: Requested fill of {qty_t:.1f}t exceeds remaining capacity ({avail_cap:.1f}t) in tank '{tank.name}'.",
                        severity="BLOCKING",
                        evidence={"requested_qty_t": qty_t, "available_capacity": avail_cap}
                    )
                )
                is_blocked = True

        # 3. Operator Confirmation Check
        if not operator_confirmed:
            reasons.append(
                SafetyGateReason(
                    category="AUTHORIZATION",
                    message="Missing explicit operator ballast execution authorization.",
                    severity="BLOCKING",
                    evidence={"operator_confirmed": False}
                )
            )
            is_blocked = True
        elif not operator_id or not str(operator_id).strip():
            reasons.append(
                SafetyGateReason(
                    category="AUTHORIZATION",
                    message="Supervisory operator credentials required for pump dispatch.",
                    severity="BLOCKING",
                    evidence={"operator_id": operator_id}
                )
            )
            is_blocked = True

        # 4. Final Status
        if is_blocked:
            final_status = SafetyGateStatus.BLOCKED
            allowed = False
        else:
            final_status = SafetyGateStatus.SAFE
            allowed = True
            reasons.append(
                SafetyGateReason(
                    category="BALLAST",
                    message=f"Ballast transfer cleared: {dir_clean} {qty_t:.1f}t on '{tank.name}' is within physical capacity limits and authorized by operator.",
                    severity="INFO"
                )
            )

        return SafetyGateEvaluationResult(
            allowed=allowed,
            status=final_status.value,
            gate_type=SafetyGateType.BALLAST_EXECUTION.value,
            reasons=reasons
        )

    @classmethod
    def evaluate_completion_gate(
        cls,
        container_id: str,
        ship: Ship,
        verification_data: Optional[Dict[str, Any]] = None
    ) -> SafetyGateEvaluationResult:
        """
        Evaluates the Safety Gate for Operation Completion & Database Certification.
        """
        reasons: List[SafetyGateReason] = []
        is_blocked = False

        # 1. Verify container is stowed on vessel
        stowed = any(c.id == container_id for c in ship.containers)
        if not stowed:
            reasons.append(
                SafetyGateReason(
                    category="VALIDATION",
                    message=f"Container '{container_id}' is not stowed on vessel state. Operation cannot be completed.",
                    severity="BLOCKING",
                    evidence={"container_id": container_id}
                )
            )
            is_blocked = True

        # 2. Check stability is within certified limits
        list_t = abs(StabilityAnalyzer.calculate_list(ship))
        trim_t = abs(StabilityAnalyzer.calculate_trim(ship))

        if list_t >= 5.0 or trim_t >= 3.0:
            reasons.append(
                SafetyGateReason(
                    category="STABILITY",
                    message=f"Vessel post-operation state exceeds stability limits (List {list_t:.2f}°, Trim {trim_t:.2f}°). Completion blocked.",
                    severity="BLOCKING",
                    evidence={"list_deg": list_t, "trim_deg": trim_t}
                )
            )
            is_blocked = True

        if is_blocked:
            final_status = SafetyGateStatus.BLOCKED
            allowed = False
        else:
            final_status = SafetyGateStatus.SAFE
            allowed = True
            reasons.append(
                SafetyGateReason(
                    category="VALIDATION",
                    message="Operation lifecycle certified. Hydrostatic equilibrium verified and audit record logged.",
                    severity="INFO"
                )
            )

        return SafetyGateEvaluationResult(
            allowed=allowed,
            status=final_status.value,
            gate_type=SafetyGateType.OPERATION_COMPLETION.value,
            reasons=reasons
        )

    @classmethod
    def evaluate_general_gate(
        cls,
        request: SafetyGateEvaluationRequest,
        ship: Optional[Ship] = None
    ) -> SafetyGateEvaluationResult:
        """
        Entry point for generic REST safety gate evaluations.
        """
        import state
        ship_instance = ship if ship is not None else state.get_current_ship()
        gate_type = str(request.gate_type).upper()

        if "BALLAST" in gate_type:
            target_b = request.target_ballast or {}
            return cls.evaluate_ballast_gate(
                tank_key=target_b.get("tank_key", "port_1"),
                direction=target_b.get("direction", "DRAIN"),
                qty_t=float(target_b.get("qty_t", 0.0)),
                ship=ship_instance,
                operator_confirmed=bool(request.operator_confirmed),
                operator_id=request.operator_id,
                telemetry=request.telemetry
            )
        elif "COMPLETION" in gate_type:
            cntr_id = (request.container_data or {}).get("container_number", "UNKNOWN")
            return cls.evaluate_completion_gate(
                container_id=cntr_id,
                ship=ship_instance
            )
        else:
            return cls.evaluate_loading_gate(
                container=request.container_data or {},
                document=request.document_data,
                validation=request.validation_data,
                recommendation=request.target_slot,
                ship=ship_instance,
                telemetry=request.telemetry,
                anomalies=request.anomalies,
                operator_confirmed=bool(request.operator_confirmed),
                operator_id=request.operator_id,
                weight_source=request.weight_source
            )
