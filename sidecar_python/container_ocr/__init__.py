"""
MareTide Container Document Intelligence / OCR Subsystem (Phase 1).
Extracts and normalizes container identification, weights, dimensions, and cargo classifications from document images.
"""

from .models import (
    ContainerSlipResponse,
    DocumentMetadata,
    ContainerDetails,
    ContainerDimensions,
    ContainerWeights,
    CargoDetails,
    ConfidenceScores,
    ValidationResult,
    RawTextRequest
)
from .service import ContainerSlipService, extract_container_slip, process_container_slip, default_service
from .workflow import (
    WorkflowState,
    WorkflowTransitionError,
    StateTransitionRecord,
    ContainerWorkflowSession,
    ContainerWorkflowEngine,
    VALID_TRANSITIONS
)
from .api import container_router, workflow_router

__all__ = [
    "ContainerSlipResponse",
    "DocumentMetadata",
    "ContainerDetails",
    "ContainerDimensions",
    "ContainerWeights",
    "CargoDetails",
    "ConfidenceScores",
    "ValidationResult",
    "RawTextRequest",
    "ContainerSlipService",
    "extract_container_slip",
    "process_container_slip",
    "default_service",
    "WorkflowState",
    "WorkflowTransitionError",
    "StateTransitionRecord",
    "ContainerWorkflowSession",
    "ContainerWorkflowEngine",
    "VALID_TRANSITIONS",
    "container_router",
    "workflow_router"
]
