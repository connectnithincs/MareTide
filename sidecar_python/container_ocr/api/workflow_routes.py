"""
FastAPI REST Endpoints for Phase 5 Event-Driven Container Document Intelligence Workflow.

Exposes:
- POST /api/container/workflow/initiate
- POST /api/container/workflow/confirm-load
- POST /api/container/workflow/confirm-ballast
- POST /api/container/workflow/approve-review
- POST /api/container/workflow/reject
- GET  /api/container/workflow/session/{operation_id}
- GET  /api/container/workflow/active
- GET  /api/container/workflow/history
"""

import logging
import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile, Query, HTTPException, Body, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from ..workflow import (
    WorkflowState,
    ContainerWorkflowSession,
    ContainerWorkflowEngine,
    WorkflowTransitionError
)

logger = logging.getLogger("container_workflow.api")

router = APIRouter(prefix="/api/container/workflow", tags=["Event-Driven Document Intelligence Workflow"])

ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
MAX_UPLOAD_BYTES = 15 * 1024 * 1024


class RawTextWorkflowRequest(BaseModel):
    raw_text: str = Field(..., min_length=5, description="Raw OCR text payload")
    source_name: Optional[str] = "raw_slip.txt"


class ConfirmLoadRequest(BaseModel):
    operation_id: str
    operator_id: str = Field("ChiefOfficer", description="Supervisory Officer ID")
    operator_confirmed: bool = Field(True, description="Explicit operator authorization")
    override_position: Optional[Any] = None


class ConfirmBallastRequest(BaseModel):
    operation_id: str
    operator_id: str = Field("ChiefOfficer", description="Supervisory Officer ID")
    operator_confirmed: bool = Field(True, description="Explicit operator authorization")


class ApproveReviewRequest(BaseModel):
    operation_id: str
    operator_id: str = Field("ChiefOfficer", description="Supervisory Officer ID")
    operator_notes: Optional[str] = None


class RejectWorkflowRequest(BaseModel):
    operation_id: str
    operator_id: str = Field("ChiefOfficer", description="Supervisory Officer ID")
    reason: str = Field(..., description="Reason for rejecting the container operation")


@router.post(
    "/initiate",
    response_model=ContainerWorkflowSession,
    status_code=status.HTTP_200_OK,
    summary="Initiate Event-Driven Container Workflow from Image",
    description="Uploads a container slip image and automatically triggers the end-to-end OCR -> Validation -> Stability -> Recommendation pipeline."
)
async def initiate_workflow_from_image(
    image: Optional[UploadFile] = File(None, description="Container slip image file"),
    file: Optional[UploadFile] = File(None, description="Alternative field name for image"),
    engine: Optional[str] = Query(None, description="Optional OCR engine override")
):
    upload = image or file
    if upload is None or not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image file provided in field 'image' or 'file'."
        )

    filename_lower = upload.filename.lower()
    if not filename_lower.endswith(ALLOWED_IMAGE_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{upload.filename}'."
        )

    try:
        content = await upload.read()
    except Exception as e:
        logger.error(f"Failed to read image upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded file content."
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes)."
        )

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds limit of {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
        )

    nparr = np.frombuffer(content, np.uint8)
    decoded_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if decoded_img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or invalid image data."
        )

    engine_inst = ContainerWorkflowEngine.get_instance()
    session = engine_inst.initiate_workflow_from_image(
        image_input=decoded_img,
        source_name=upload.filename,
        engine_name=engine
    )
    return session


@router.post(
    "/initiate-text",
    response_model=ContainerWorkflowSession,
    status_code=status.HTTP_200_OK,
    summary="Initiate Event-Driven Container Workflow from Raw Text"
)
async def initiate_workflow_from_text(payload: RawTextWorkflowRequest):
    engine_inst = ContainerWorkflowEngine.get_instance()
    session = engine_inst.initiate_workflow_from_text(
        raw_text=payload.raw_text,
        source_name=payload.source_name or "raw_slip.txt"
    )
    return session


@router.post(
    "/confirm-load",
    response_model=ContainerWorkflowSession,
    status_code=status.HTTP_200_OK,
    summary="Explicit Operator Authorization for Container Loading",
    description="Requires explicit human-in-the-loop confirmation to commit container to live vessel state and compute ballast compensation."
)
async def confirm_container_load(payload: ConfirmLoadRequest):
    engine_inst = ContainerWorkflowEngine.get_instance()
    try:
        session = engine_inst.confirm_load_step(
            operation_id=payload.operation_id,
            operator_id=payload.operator_id,
            operator_confirmed=payload.operator_confirmed,
            override_position=payload.override_position
        )
        return session
    except WorkflowTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Confirm load failure:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Loading confirmation failed: {str(e)}"
        )


@router.post(
    "/confirm-ballast",
    response_model=ContainerWorkflowSession,
    status_code=status.HTTP_200_OK,
    summary="Explicit Operator Authorization for Ballast Execution",
    description="Requires explicit human-in-the-loop authorization to execute ballast pump/valve operation on live hardware/twin."
)
async def confirm_ballast_execution(payload: ConfirmBallastRequest):
    engine_inst = ContainerWorkflowEngine.get_instance()
    try:
        session = engine_inst.confirm_ballast_step(
            operation_id=payload.operation_id,
            operator_id=payload.operator_id,
            operator_confirmed=payload.operator_confirmed
        )
        return session
    except WorkflowTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.exception("Confirm ballast failure:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ballast execution failed: {str(e)}"
        )


@router.post(
    "/approve-review",
    response_model=ContainerWorkflowSession,
    status_code=status.HTTP_200_OK,
    summary="Approve Container Review and Proceed to Stability Analysis"
)
async def approve_container_review(payload: ApproveReviewRequest):
    engine_inst = ContainerWorkflowEngine.get_instance()
    try:
        session = engine_inst.approve_review_and_analyze(
            operation_id=payload.operation_id,
            operator_id=payload.operator_id,
            operator_notes=payload.operator_notes
        )
        return session
    except WorkflowTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid state transition: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post(
    "/reject",
    response_model=ContainerWorkflowSession,
    status_code=status.HTTP_200_OK,
    summary="Reject Operational Workflow"
)
async def reject_workflow(payload: RejectWorkflowRequest):
    engine_inst = ContainerWorkflowEngine.get_instance()
    try:
        session = engine_inst.reject_workflow(
            operation_id=payload.operation_id,
            reason=payload.reason,
            operator_id=payload.operator_id
        )
        return session
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get(
    "/session/{operation_id}",
    response_model=ContainerWorkflowSession,
    summary="Get Container Workflow Session"
)
async def get_workflow_session(operation_id: str):
    engine_inst = ContainerWorkflowEngine.get_instance()
    session = engine_inst.get_session(operation_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow session '{operation_id}' not found."
        )
    return session


@router.get(
    "/active",
    response_model=Optional[ContainerWorkflowSession],
    summary="Get Active Container Workflow Session"
)
async def get_active_workflow_session():
    engine_inst = ContainerWorkflowEngine.get_instance()
    return engine_inst.get_active_session()


@router.get(
    "/history",
    response_model=List[ContainerWorkflowSession],
    summary="Get Recent Workflow Sessions"
)
async def get_workflow_history(limit: int = Query(20, ge=1, le=100)):
    engine_inst = ContainerWorkflowEngine.get_instance()
    return engine_inst.list_sessions(limit=limit)


# ---------------------------------------------------------
# Phase 5: Operational Traceability & Timeline Endpoints
# ---------------------------------------------------------

from reports.logs_db import (
    get_operation_timeline,
    get_all_audit_events,
    get_recent_operation_summaries
)


@router.get(
    "/timeline/{operation_id}",
    summary="Get Operation Timeline",
    description="Retrieves the full, chronologically ordered audit trail for a specific operation."
)
async def get_workflow_timeline(operation_id: str):
    events = get_operation_timeline(operation_id)
    if not events:
        # Fallback to session transition history if not in DB yet
        engine_inst = ContainerWorkflowEngine.get_instance()
        session = engine_inst.get_session(operation_id)
        if session:
            events = [
                {
                    "id": idx + 1,
                    "operation_id": session.operation_id,
                    "timestamp": t.timestamp,
                    "event_type": t.next_state.value if hasattr(t.next_state, "value") else str(t.next_state),
                    "container_id": t.container_id,
                    "actor": t.operator_action or "SYSTEM",
                    "source": "DOCUMENT_AI" if "DOCUMENT" in str(t.next_state) else "CALCULATED",
                    "previous_state": t.previous_state.value if hasattr(t.previous_state, "value") else str(t.previous_state),
                    "new_state": t.next_state.value if hasattr(t.next_state, "value") else str(t.next_state),
                    "relevant_metrics": t.metadata,
                    "reason": t.reason,
                    "success": (t.next_state != WorkflowState.FAILED)
                }
                for idx, t in enumerate(session.transition_history)
            ]
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Operation '{operation_id}' not found."
            )
    return {
        "operation_id": operation_id,
        "total_events": len(events),
        "timeline": events
    }


@router.get(
    "/timeline",
    summary="Get Recent Operation Timelines Summary",
    description="Retrieves recent operations with their start/update timestamps and total event counts."
)
async def get_recent_timelines(limit: int = Query(20, ge=1, le=100)):
    return {
        "operations": get_recent_operation_summaries(limit=limit)
    }


@router.get(
    "/events",
    summary="Get Audit Events",
    description="Retrieves flat list of recent operational audit events with provenance tags."
)
async def get_audit_events(
    limit: int = Query(100, ge=1, le=500),
    container_id: Optional[str] = Query(None, description="Optional container ID filter")
):
    return {
        "events": get_all_audit_events(limit=limit, container_id=container_id)
    }

