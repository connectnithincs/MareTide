"""
FastAPI REST Routes for Phase 2 & Phase 3B: Container Stability Impact Analysis & Loading Confirmation.
Exposes POST /api/container/stability/analyze, POST /api/container/load/confirm, and GET /api/container/load/audit.
"""

import logging
from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional

from ..models import (
    ContainerStabilityAnalysisRequest, 
    ContainerStabilityAnalysisResponse,
    ContainerLoadingConfirmRequest,
    ContainerLoadingConfirmResponse,
    BallastCompensationRequest,
    BallastCompensationResponse,
    BallastExecutionRequest,
    BallastExecutionResponse,
    MultiContainerPlanRequest,
    MultiContainerPlanResponse,
    MultiContainerExecuteRequest,
    MultiContainerExecuteResponse
)
from ..analyzer import (
    ContainerStabilityService, 
    ContainerLoadingService, 
    ContainerBallastService,
    MultiContainerPlanner
)
from reports.logs_db import get_container_loading_audits

logger = logging.getLogger("container_stability.api")

router = APIRouter(prefix="/api/container", tags=["Container Stability & Loading Integration"])


@router.post(
    "/stability/analyze",
    response_model=ContainerStabilityAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Container Placement Stability Impact",
    description="Evaluates candidate deck positions for a Phase 1 extracted container without modifying live vessel state. Returns explainable placement recommendation and stability metrics."
)
async def analyze_stability_impact(request: ContainerStabilityAnalysisRequest):
    """
    Accepts Phase 1 structured container JSON (or manual container specs),
    simulates candidate slots using the existing MareTide Stability Engine,
    and returns ranked candidates, stability delta, and recommendation.
    """
    try:
        response = ContainerStabilityService.analyze_container_placement(request)
        return response
    except Exception as e:
        logger.exception("Failed to execute stability analysis:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal stability calculation failure: {str(e)}"
        )


@router.post(
    "/stability/manifest-plan",
    response_model=MultiContainerPlanResponse,
    status_code=status.HTTP_200_OK,
    summary="Plan Multi-Container Stowage & Loading Sequence",
    description="Evaluates a manifest of multiple containers, determines optimal loading sequence, and simulates step-by-step stability on a copy-on-write vessel state."
)
async def plan_multi_container_stowage(request: MultiContainerPlanRequest):
    try:
        response = MultiContainerPlanner.plan_multi_container_stowage(request)
        return response
    except Exception as e:
        logger.exception("Failed to generate multi-container stowage plan:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal multi-container planning failure: {str(e)}"
        )


@router.post(
    "/manifest/execute",
    response_model=MultiContainerExecuteResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Approved Multi-Container Stowage Sequence",
    description="Sequentially loads approved container sequence to the live vessel state upon operator confirmation."
)
async def execute_multi_container_manifest(request: MultiContainerExecuteRequest):
    try:
        response = MultiContainerPlanner.execute_multi_container_plan(request)
        return response
    except Exception as e:
        logger.exception("Failed to execute multi-container stowage sequence:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal sequence execution failure: {str(e)}"
        )


@router.post(
    "/load/confirm",
    response_model=ContainerLoadingConfirmResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm and Load Container to Live Vessel State",
    description="Atomically commits a verified and recommended container to the live vessel state upon explicit operator confirmation. Revalidates safety gates and logs an audit record."
)
async def confirm_and_load_container(request: ContainerLoadingConfirmRequest):
    """
    Validates operator authorization, revalidates data and recommendation, checks slot availability,
    atomically adds container to live Ship state, and records audit trail.
    """
    try:
        response = ContainerLoadingService.confirm_and_load(request)
        return response
    except Exception as e:
        logger.exception("Failed to confirm container load:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal loading execution failure: {str(e)}"
        )


@router.post(
    "/ballast/calculate",
    response_model=BallastCompensationResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Automated Ballast Compensation",
    description="Calculates the ballast water discharge/transfer required on actual post-loading vessel state to restore stability equilibrium."
)
async def calculate_ballast_compensation(request: BallastCompensationRequest):
    try:
        response = ContainerBallastService.calculate_compensation(request)
        return response
    except Exception as e:
        logger.exception("Failed to calculate ballast compensation:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal ballast calculation failure: {str(e)}"
        )


@router.post(
    "/ballast/execute",
    response_model=BallastExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute Operator-Confirmed Ballast Compensation",
    description="Executes water movement on the target ballast tank upon explicit operator confirmation, commands simulator/IoT hardware, logs audit trail, and computes 3-stage stability report."
)
async def execute_ballast_compensation(request: BallastExecutionRequest):
    try:
        response = ContainerBallastService.execute_compensation(request)
        return response
    except Exception as e:
        logger.exception("Failed to execute ballast compensation:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal ballast execution failure: {str(e)}"
        )


@router.get(
    "/load/audit",
    summary="Get Container Loading Audit Log",
    description="Returns the historical audit trail of container loading confirmations and attempts."
)
async def get_loading_audit_trail(limit: int = Query(100, ge=1, le=500)):
    try:
        return get_container_loading_audits(limit=limit)
    except Exception as e:
        logger.exception("Failed to fetch loading audit logs:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal audit retrieval failure: {str(e)}"
        )


