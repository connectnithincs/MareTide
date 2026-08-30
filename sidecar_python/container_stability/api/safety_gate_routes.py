"""
FastAPI Routes for Phase 5 Real-Time Operational Safety Gate.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from container_stability.models import (
    SafetyGateStatus,
    SafetyGateType,
    SafetyGateEvaluationRequest,
    SafetyGateEvaluationResult
)
from container_stability.safety_gate import RealTimeSafetyGate
import state

logger = logging.getLogger("safety_gate.api")

router = APIRouter(prefix="/api/safety-gate", tags=["Real-Time Operational Safety Gate"])


@router.post(
    "/evaluate",
    response_model=SafetyGateEvaluationResult,
    summary="Evaluate Operational Safety Gate",
    description="Evaluates operational safety constraints across loading, ballast, or completion."
)
async def evaluate_safety_gate(payload: SafetyGateEvaluationRequest) -> SafetyGateEvaluationResult:
    """Evaluates generic safety gate request."""
    try:
        ship = state.get_current_ship()
        return RealTimeSafetyGate.evaluate_general_gate(payload, ship=ship)
    except Exception as e:
        logger.exception("Error during safety gate evaluation:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Safety Gate evaluation failed: {str(e)}"
        )


@router.post(
    "/evaluate-loading",
    response_model=SafetyGateEvaluationResult,
    summary="Evaluate Container Loading Safety Gate",
    description="Specific safety check before authorizing container loading."
)
async def evaluate_loading_gate(payload: SafetyGateEvaluationRequest) -> SafetyGateEvaluationResult:
    """Evaluates container loading safety gate."""
    try:
        ship = state.get_current_ship()
        return RealTimeSafetyGate.evaluate_loading_gate(
            container=payload.container_data or {},
            document=payload.document_data,
            validation=payload.validation_data,
            recommendation=payload.target_slot,
            ship=ship,
            telemetry=payload.telemetry,
            anomalies=payload.anomalies,
            operator_confirmed=bool(payload.operator_confirmed),
            operator_id=payload.operator_id,
            weight_source=payload.weight_source
        )
    except Exception as e:
        logger.exception("Error during loading safety gate evaluation:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Loading safety gate evaluation failed: {str(e)}"
        )


@router.post(
    "/evaluate-ballast",
    response_model=SafetyGateEvaluationResult,
    summary="Evaluate Ballast Execution Safety Gate",
    description="Specific safety check before authorizing ballast water transfer."
)
async def evaluate_ballast_gate(payload: SafetyGateEvaluationRequest) -> SafetyGateEvaluationResult:
    """Evaluates ballast water execution safety gate."""
    try:
        ship = state.get_current_ship()
        target_b = payload.target_ballast or {}
        return RealTimeSafetyGate.evaluate_ballast_gate(
            tank_key=target_b.get("tank_key", "port_1"),
            direction=target_b.get("direction", "DRAIN"),
            qty_t=float(target_b.get("qty_t", 0.0)),
            ship=ship,
            operator_confirmed=bool(payload.operator_confirmed),
            operator_id=payload.operator_id,
            telemetry=payload.telemetry
        )
    except Exception as e:
        logger.exception("Error during ballast safety gate evaluation:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ballast safety gate evaluation failed: {str(e)}"
        )


@router.get(
    "/status",
    summary="Safety Gate Policy Status",
    description="Returns active safety gating rules and policy configuration."
)
async def get_safety_gate_status() -> Dict[str, Any]:
    """Returns safety gate policy metadata."""
    return {
        "status": "ACTIVE",
        "subsystem": "Phase 5 Real-Time Operational Safety Gate",
        "authoritative_weight_source": "[DOCUMENT AI]",
        "load_cell_policy": "FORBIDDEN_FOR_CARGO_AND_STABILITY",
        "safety_states": [s.value for s in SafetyGateStatus],
        "enforced_rules": [
            "Rule 1: Invalid OCR/document data -> BLOCKED",
            "Rule 2: Critical cargo anomaly -> BLOCKED",
            "Rule 3: Invalid container identifier -> BLOCKED",
            "Rule 4: Missing gross weight -> BLOCKED",
            "Rule 5: Unsafe candidate placement (occupied slot / critical list/trim) -> BLOCKED",
            "Rule 6: Stale required telemetry -> REVIEW_REQUIRED / BLOCKED",
            "Rule 7: Missing operator confirmation -> BLOCKED",
            "Rule 8: Load-cell sensor data -> BLOCKED (Security Policy Violation)"
        ]
    }
