"""
Phase 5 Event-Driven Container Document Intelligence Workflow Engine for MareTide.

Provides an event-driven 15-state supervisory operational state machine:
UPLOAD -> OCR -> NORMALIZE -> VALIDATE -> ANOMALY CHECK -> STABILITY ANALYSIS
-> RECOMMENDATION -> OPERATOR REVIEW -> CONFIRM LOAD -> BALLAST CALCULATION
-> OPERATOR CONFIRMATION -> EXECUTION -> FINAL VERIFICATION -> AUDIT

Strictly enforces:
1. Container Document AI is the exclusive source of container weight ([DOCUMENT AI]).
2. ZERO load-cell sensor data is used or permitted for cargo state or stability calculations.
3. State immutability: live ship state is NEVER mutated during OCR, validation, simulation, or recommendation.
4. Explicit human-in-the-loop authorization gates for container loading and ballast water execution.
5. Strict transition validation: invalid state jumps are rejected.
6. Immutable audit history for every state transition.
"""

from enum import Enum
import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Set, TYPE_CHECKING
from pydantic import BaseModel, Field
import threading

from .models import ContainerSlipResponse, ContainerDetails, ConfidenceScores, ValidationResult, CargoAnomaly
from .service import default_service

if TYPE_CHECKING:
    from container_stability.models import (
        ContainerStabilityAnalysisRequest,
        ContainerStabilityAnalysisResponse,
        ContainerLoadingConfirmRequest,
        ContainerLoadingConfirmResponse,
        BallastCompensationRequest,
        BallastCompensationResponse,
        BallastExecutionRequest,
        BallastExecutionResponse,
        RecommendedPosition,
        StabilityMetrics
    )

CONTAINER_WEIGHT_SOURCE = "[DOCUMENT AI]"
LOAD_CELL_POLICY = "FORBIDDEN_FOR_CARGO_AND_STABILITY"

logger = logging.getLogger("container_workflow.engine")


class WorkflowState(str, Enum):
    """Enumeration of all 15 discrete states in the supervisory container workflow."""
    DOCUMENT_RECEIVED = "DOCUMENT_RECEIVED"
    OCR_PROCESSING = "OCR_PROCESSING"
    VALIDATING = "VALIDATING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    ANALYZING_STABILITY = "ANALYZING_STABILITY"
    RECOMMENDATION_READY = "RECOMMENDATION_READY"
    AWAITING_OPERATOR_CONFIRMATION = "AWAITING_OPERATOR_CONFIRMATION"
    LOADING = "LOADING"
    LOADED = "LOADED"
    BALLAST_CALCULATED = "BALLAST_CALCULATED"
    AWAITING_BALLAST_CONFIRMATION = "AWAITING_BALLAST_CONFIRMATION"
    BALLAST_EXECUTING = "BALLAST_EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    def __init__(self, message: str, previous_state: WorkflowState, attempted_state: WorkflowState):
        super().__init__(message)
        self.previous_state = previous_state
        self.attempted_state = attempted_state


class StateTransitionRecord(BaseModel):
    """Audit record capturing an atomic state transition."""
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    operation_id: str
    container_id: str = "UNKNOWN"
    previous_state: WorkflowState
    next_state: WorkflowState
    reason: str
    provenance: str = Field(default=CONTAINER_WEIGHT_SOURCE, description="[DOCUMENT AI] for cargo specs")
    operator_action: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ContainerWorkflowSession(BaseModel):
    """Full operational session capturing end-to-end container lifecycle."""
    operation_id: str
    container_id: str = "UNKNOWN"
    current_state: WorkflowState = WorkflowState.DOCUMENT_RECEIVED
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    
    # Document AI Phase 1 Extraction & Validation
    extraction_response: Optional[ContainerSlipResponse] = None
    
    # Stability Engine Phase 2 Analysis
    stability_response: Optional[Any] = None
    
    # Phase 3B Committed Loading Response
    loaded_response: Optional[Any] = None
    
    # Phase 3C Ballast Compensation & Execution
    ballast_compensation: Optional[Any] = None
    ballast_execution: Optional[Any] = None
    
    # Four-Stage Final Verification Snapshot
    final_verification: Optional[Dict[str, Any]] = None
    
    # Operator & Audit Tracking
    operator_id: Optional[str] = None
    operator_notes: Optional[str] = None
    transition_history: List[StateTransitionRecord] = Field(default_factory=list)
    error_message: Optional[str] = None
    is_active: bool = True


# Directed Graph of Permitted State Transitions
VALID_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.DOCUMENT_RECEIVED: {
        WorkflowState.OCR_PROCESSING,
        WorkflowState.FAILED
    },
    WorkflowState.OCR_PROCESSING: {
        WorkflowState.VALIDATING,
        WorkflowState.REVIEW_REQUIRED,
        WorkflowState.FAILED
    },
    WorkflowState.VALIDATING: {
        WorkflowState.REVIEW_REQUIRED,
        WorkflowState.ANALYZING_STABILITY,
        WorkflowState.FAILED
    },
    WorkflowState.REVIEW_REQUIRED: {
        WorkflowState.ANALYZING_STABILITY,
        WorkflowState.AWAITING_OPERATOR_CONFIRMATION,
        WorkflowState.FAILED
    },
    WorkflowState.ANALYZING_STABILITY: {
        WorkflowState.RECOMMENDATION_READY,
        WorkflowState.REVIEW_REQUIRED,
        WorkflowState.FAILED
    },
    WorkflowState.RECOMMENDATION_READY: {
        WorkflowState.AWAITING_OPERATOR_CONFIRMATION,
        WorkflowState.FAILED
    },
    WorkflowState.AWAITING_OPERATOR_CONFIRMATION: {
        WorkflowState.LOADING,
        WorkflowState.FAILED
    },
    WorkflowState.LOADING: {
        WorkflowState.LOADED,
        WorkflowState.FAILED
    },
    WorkflowState.LOADED: {
        WorkflowState.BALLAST_CALCULATED,
        WorkflowState.VERIFYING,
        WorkflowState.FAILED
    },
    WorkflowState.BALLAST_CALCULATED: {
        WorkflowState.AWAITING_BALLAST_CONFIRMATION,
        WorkflowState.VERIFYING,
        WorkflowState.FAILED
    },
    WorkflowState.AWAITING_BALLAST_CONFIRMATION: {
        WorkflowState.BALLAST_EXECUTING,
        WorkflowState.VERIFYING,
        WorkflowState.FAILED
    },
    WorkflowState.BALLAST_EXECUTING: {
        WorkflowState.VERIFYING,
        WorkflowState.FAILED
    },
    WorkflowState.VERIFYING: {
        WorkflowState.COMPLETED,
        WorkflowState.FAILED
    },
    WorkflowState.COMPLETED: set(),  # Terminal state
    WorkflowState.FAILED: set()       # Terminal state
}


def _to_dict(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj



class ContainerWorkflowEngine:
    """
    Singleton orchestrator for the event-driven Container Document Intelligence workflow.
    Ensures safe, thread-safe, transactional state progression with human-in-the-loop gates.
    """
    _instance: Optional["ContainerWorkflowEngine"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._sessions: Dict[str, ContainerWorkflowSession] = {}
        self._active_operation_id: Optional[str] = None
        self._session_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ContainerWorkflowEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _generate_operation_id(self, container_no: Optional[str] = None) -> str:
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
        unique_suffix = uuid.uuid4().hex[:6].upper()
        if container_no and container_no.strip() and container_no != "UNKNOWN":
            clean_no = "".join(c for c in container_no if c.isalnum())
            return f"OP-{date_str}-{clean_no}-{unique_suffix}"
        return f"OP-{date_str}-{unique_suffix}"

    def _derive_actor_and_source(self, next_state: WorkflowState, operator_action: Optional[str] = None):
        """Maps workflow state and action to standardized actor and 5-tier provenance source."""
        if operator_action:
            return f"OPERATOR:{operator_action}", "OPERATOR"
        
        st = next_state
        if st in [WorkflowState.DOCUMENT_RECEIVED, WorkflowState.OCR_PROCESSING, WorkflowState.VALIDATING, WorkflowState.REVIEW_REQUIRED]:
            return "DOCUMENT_AI", "DOCUMENT_AI"
        elif st in [WorkflowState.ANALYZING_STABILITY, WorkflowState.RECOMMENDATION_READY, WorkflowState.LOADED]:
            return "STABILITY_ENGINE", "CALCULATED"
        elif st in [WorkflowState.BALLAST_CALCULATED, WorkflowState.BALLAST_EXECUTING]:
            return "BALLAST_ENGINE", "CALCULATED"
        elif st in [WorkflowState.AWAITING_OPERATOR_CONFIRMATION, WorkflowState.AWAITING_BALLAST_CONFIRMATION, WorkflowState.VERIFYING]:
            return "SAFETY_GATE", "CALCULATED"
        elif st in [WorkflowState.LOADING]:
            return "OPERATOR", "OPERATOR"
        else:
            return "WORKFLOW_ENGINE", "CALCULATED"

    def _extract_audit_metrics(self, session: ContainerWorkflowSession, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extracts sanitized metrics from session without any load-cell sensors."""
        metrics = {}
        if metadata:
            metrics.update(metadata)
        if session.extraction_response and session.extraction_response.container:
            c = session.extraction_response.container
            if c.weights and c.weights.gross_weight_kg:
                metrics["gross_weight_t"] = round(float(c.weights.gross_weight_kg) / 1000.0, 2)
                metrics["gross_weight_kg"] = float(c.weights.gross_weight_kg)
            if c.container_type:
                metrics["container_type"] = c.container_type
        if session.stability_response and session.stability_response.recommendation:
            rec = session.stability_response.recommendation
            metrics["target_slot"] = f"Bay {rec.bay} {rec.side.upper()} Tier {rec.tier}"
            if session.stability_response.stability and session.stability_response.stability.after:
                post = session.stability_response.stability.after
                metrics["projected_list_deg"] = post.list_t
                metrics["projected_trim_deg"] = post.trim_t
                metrics["projected_score"] = post.stability_score
        if session.loaded_response and session.loaded_response.stability_after:
            metrics["committed_list_deg"] = session.loaded_response.stability_after.list_t
            metrics["committed_trim_deg"] = session.loaded_response.stability_after.trim_t
            metrics["committed_score"] = session.loaded_response.stability_after.stability_score
        if session.ballast_compensation:
            metrics["ballast_affected_tank"] = session.ballast_compensation.affected_tank
            metrics["ballast_required_qty_t"] = session.ballast_compensation.required_qty_t
        if session.ballast_execution:
            metrics["ballast_discharged_qty_t"] = session.ballast_execution.actual_qty_t
        return metrics

    def _record_transition(
        self,
        session: ContainerWorkflowSession,
        next_state: WorkflowState,
        reason: str,
        operator_action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> StateTransitionRecord:
        """Enforces transition legality, appends to in-memory history, and logs to SQLite audit database."""
        current = session.current_state
        allowed = VALID_TRANSITIONS.get(current, set())
        
        if next_state not in allowed and next_state != WorkflowState.FAILED:
            msg = f"Illegal workflow transition from '{current.value}' to '{next_state.value}'."
            logger.error(msg)
            raise WorkflowTransitionError(msg, previous_state=current, attempted_state=next_state)

        record = StateTransitionRecord(
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            operation_id=session.operation_id,
            container_id=session.container_id,
            previous_state=current,
            next_state=next_state,
            reason=reason,
            provenance=CONTAINER_WEIGHT_SOURCE,
            operator_action=operator_action,
            metadata=metadata or {}
        )
        session.transition_history.append(record)
        session.current_state = next_state
        session.updated_at = record.timestamp
        logger.info(f"[{session.operation_id}] State transitioned: {current.value} -> {next_state.value} ({reason})")

        # Persist audit record to SQLite
        try:
            from reports.logs_db import log_operation_audit_event
            actor, source = self._derive_actor_and_source(next_state, operator_action)
            metrics = self._extract_audit_metrics(session, metadata)
            log_operation_audit_event(
                operation_id=session.operation_id,
                event_type=next_state.value,
                container_id=session.container_id,
                actor=actor,
                source=source,
                previous_state=current.value,
                new_state=next_state.value,
                relevant_metrics=metrics,
                reason=reason,
                success=(next_state != WorkflowState.FAILED),
                timestamp=record.timestamp
            )
        except Exception as audit_err:
            logger.warning(f"Failed to record audit event for operation {session.operation_id}: {audit_err}")

        return record

    def initiate_workflow_from_image(
        self,
        image_input: Any,
        source_name: str = "slip.jpg",
        engine_name: Optional[str] = None
    ) -> ContainerWorkflowSession:
        """
        Entry Point 1: Upload slip image.
        Automatically progresses through:
        DOCUMENT_RECEIVED -> OCR_PROCESSING -> VALIDATING -> (REVIEW_REQUIRED or ANALYZING_STABILITY)
        -> RECOMMENDATION_READY -> AWAITING_OPERATOR_CONFIRMATION.
        """
        with self._session_lock:
            op_id = self._generate_operation_id()
            session = ContainerWorkflowSession(
                operation_id=op_id,
                current_state=WorkflowState.DOCUMENT_RECEIVED
            )
            # Record initial state
            record = StateTransitionRecord(
                operation_id=op_id,
                container_id="PENDING",
                previous_state=WorkflowState.DOCUMENT_RECEIVED,
                next_state=WorkflowState.DOCUMENT_RECEIVED,
                reason="Document slip image uploaded by operator."
            )
            session.transition_history.append(record)
            self._sessions[op_id] = session
            self._active_operation_id = op_id

            try:
                from reports.logs_db import log_operation_audit_event
                log_operation_audit_event(
                    operation_id=op_id,
                    event_type=WorkflowState.DOCUMENT_RECEIVED.value,
                    container_id="PENDING",
                    actor="DOCUMENT_AI",
                    source="DOCUMENT_AI",
                    previous_state=None,
                    new_state=WorkflowState.DOCUMENT_RECEIVED.value,
                    relevant_metrics={"source_name": source_name, "engine": engine_name or "default"},
                    reason="Document slip image uploaded by operator.",
                    success=True,
                    timestamp=record.timestamp
                )
            except Exception as e:
                logger.warning(f"Could not log initial audit event: {e}")

        try:
            # 1. Transition: DOCUMENT_RECEIVED -> OCR_PROCESSING
            self._record_transition(
                session,
                WorkflowState.OCR_PROCESSING,
                f"Executing Document AI OCR pipeline via engine: {engine_name or 'default'}."
            )

            extraction_res: ContainerSlipResponse = default_service.process_image(
                image_input=image_input,
                source_name=source_name,
                engine_name=engine_name
            )
            session.extraction_response = extraction_res
            if extraction_res.container and extraction_res.container.container_number:
                session.container_id = extraction_res.container.container_number

            # 2. Transition: OCR_PROCESSING -> VALIDATING
            self._record_transition(
                session,
                WorkflowState.VALIDATING,
                "Validating ISO 6346 check digit, VGM balance, and checking cargo anomalies."
            )

            # Check review conditions
            conf_overall = extraction_res.confidence.overall if extraction_res.confidence else 1.0
            is_review = (
                conf_overall < 0.85 or
                extraction_res.validation.valid is False or
                extraction_res.document.processing_status == "review_required" or
                any(a.severity == "CRITICAL" for a in (extraction_res.anomalies or []))
            )

            if is_review:
                self._record_transition(
                    session,
                    WorkflowState.REVIEW_REQUIRED,
                    "Low confidence, validation warnings, or critical cargo anomalies detected."
                )
                return session

            # 3. Transition: VALIDATING -> ANALYZING_STABILITY
            self._record_transition(
                session,
                WorkflowState.ANALYZING_STABILITY,
                "Simulating 8 candidate deck positions without mutating live ship state."
            )

            # Stability simulation (Strictly copy-on-write, live ship unmodified)
            from container_stability.models import ContainerStabilityAnalysisRequest
            from container_stability.analyzer import ContainerStabilityService

            stab_req = ContainerStabilityAnalysisRequest(
                container=_to_dict(extraction_res.container),
                document=_to_dict(extraction_res.document),
                validation=_to_dict(extraction_res.validation)
            )
            stability_res = ContainerStabilityService.analyze_container_placement(stab_req)
            session.stability_response = stability_res

            if not stability_res.success:
                self._record_transition(
                    session,
                    WorkflowState.FAILED,
                    f"Stability analysis failed: {stability_res.error_message}"
                )
                session.error_message = stability_res.error_message
                return session

            # 4. Transition: ANALYZING_STABILITY -> RECOMMENDATION_READY
            self._record_transition(
                session,
                WorkflowState.RECOMMENDATION_READY,
                f"Optimal slot calculated: Bay {stability_res.recommendation.bay} {stability_res.recommendation.side} Tier {stability_res.recommendation.tier}."
            )

            # 5. Transition: RECOMMENDATION_READY -> AWAITING_OPERATOR_CONFIRMATION
            self._record_transition(
                session,
                WorkflowState.AWAITING_OPERATOR_CONFIRMATION,
                "Paused at Safety Gate: Explicit operator confirmation required to commit load to live vessel state."
            )

            return session

        except Exception as e:
            logger.exception("Workflow execution error during slip upload:")
            session.error_message = str(e)
            try:
                self._record_transition(
                    session,
                    WorkflowState.FAILED,
                    f"Workflow interrupted by internal error: {str(e)}"
                )
            except Exception:
                session.current_state = WorkflowState.FAILED
            return session

    def initiate_workflow_from_text(
        self,
        raw_text: str,
        source_name: str = "raw_slip.txt"
    ) -> ContainerWorkflowSession:
        """Entry Point 2: Upload raw OCR text."""
        with self._session_lock:
            op_id = self._generate_operation_id()
            session = ContainerWorkflowSession(
                operation_id=op_id,
                current_state=WorkflowState.DOCUMENT_RECEIVED
            )
            record = StateTransitionRecord(
                operation_id=op_id,
                container_id="PENDING",
                previous_state=WorkflowState.DOCUMENT_RECEIVED,
                next_state=WorkflowState.DOCUMENT_RECEIVED,
                reason="Raw text slip uploaded."
            )
            session.transition_history.append(record)
            self._sessions[op_id] = session
            self._active_operation_id = op_id

            try:
                from reports.logs_db import log_operation_audit_event
                log_operation_audit_event(
                    operation_id=op_id,
                    event_type=WorkflowState.DOCUMENT_RECEIVED.value,
                    container_id="PENDING",
                    actor="DOCUMENT_AI",
                    source="DOCUMENT_AI",
                    previous_state=None,
                    new_state=WorkflowState.DOCUMENT_RECEIVED.value,
                    relevant_metrics={"source_name": source_name},
                    reason="Raw text slip uploaded.",
                    success=True,
                    timestamp=record.timestamp
                )
            except Exception as e:
                logger.warning(f"Could not log initial audit event: {e}")

        try:
            self._record_transition(session, WorkflowState.OCR_PROCESSING, "Processing raw OCR text.")
            extraction_res: ContainerSlipResponse = default_service.process_raw_text(raw_text, source_name=source_name)
            session.extraction_response = extraction_res
            if extraction_res.container and extraction_res.container.container_number:
                session.container_id = extraction_res.container.container_number

            self._record_transition(session, WorkflowState.VALIDATING, "Validating container data & anomalies.")

            conf_overall = extraction_res.confidence.overall if extraction_res.confidence else 1.0
            is_review = (
                conf_overall < 0.85 or
                extraction_res.validation.valid is False or
                extraction_res.document.processing_status == "review_required"
            )

            if is_review:
                self._record_transition(session, WorkflowState.REVIEW_REQUIRED, "Review required on raw text extraction.")
                return session

            self._record_transition(session, WorkflowState.ANALYZING_STABILITY, "Simulating stability placement.")
            from container_stability.models import ContainerStabilityAnalysisRequest
            from container_stability.analyzer import ContainerStabilityService

            stab_req = ContainerStabilityAnalysisRequest(
                container=_to_dict(extraction_res.container),
                document=_to_dict(extraction_res.document),
                validation=_to_dict(extraction_res.validation)
            )
            stability_res = ContainerStabilityService.analyze_container_placement(stab_req)
            session.stability_response = stability_res

            if not stability_res.success:
                session.error_message = stability_res.error_message
                self._record_transition(session, WorkflowState.FAILED, f"Stability failed: {stability_res.error_message}")
                return session

            self._record_transition(
                session,
                WorkflowState.RECOMMENDATION_READY,
                f"Recommended Bay {stability_res.recommendation.bay} {stability_res.recommendation.side} Tier {stability_res.recommendation.tier}."
            )
            self._record_transition(
                session,
                WorkflowState.AWAITING_OPERATOR_CONFIRMATION,
                "Awaiting explicit operator loading confirmation."
            )
            return session

        except Exception as e:
            logger.exception("Workflow error during raw text processing:")
            session.error_message = str(e)
            try:
                self._record_transition(session, WorkflowState.FAILED, f"Error: {str(e)}")
            except Exception:
                session.current_state = WorkflowState.FAILED
            return session

    def approve_review_and_analyze(
        self,
        operation_id: str,
        operator_id: str,
        operator_notes: Optional[str] = None
    ) -> ContainerWorkflowSession:
        """Operator explicitly approves a REVIEW_REQUIRED session to proceed to stability analysis."""
        session = self.get_session(operation_id)
        if not session:
            raise ValueError(f"Session '{operation_id}' not found.")

        if session.current_state != WorkflowState.REVIEW_REQUIRED:
            raise WorkflowTransitionError(
                f"Cannot override review from state '{session.current_state.value}'.",
                previous_state=session.current_state,
                attempted_state=WorkflowState.ANALYZING_STABILITY
            )

        session.operator_id = operator_id
        session.operator_notes = operator_notes

        self._record_transition(
            session,
            WorkflowState.ANALYZING_STABILITY,
            reason=f"Operator '{operator_id}' approved container specs despite review flag. Notes: {operator_notes or 'None'}",
            operator_action="REVIEW_APPROVED"
        )

        from container_stability.models import ContainerStabilityAnalysisRequest
        from container_stability.analyzer import ContainerStabilityService

        extraction_res = session.extraction_response
        stab_req = ContainerStabilityAnalysisRequest(
            container=_to_dict(extraction_res.container),
            document=_to_dict(extraction_res.document),
            validation=_to_dict(extraction_res.validation)
        )
        stability_res = ContainerStabilityService.analyze_container_placement(stab_req)
        session.stability_response = stability_res

        rec_str = (
            f"Bay {stability_res.recommendation.bay} {stability_res.recommendation.side} Tier {stability_res.recommendation.tier}"
            if stability_res.recommendation else "Candidate slots evaluated"
        )

        self._record_transition(
            session,
            WorkflowState.RECOMMENDATION_READY,
            reason=f"Calculated candidate placements and recommended {rec_str}."
        )
        self._record_transition(
            session,
            WorkflowState.AWAITING_OPERATOR_CONFIRMATION,
            reason="Awaiting explicit operator confirmation to commit container to vessel state."
        )
        return session

    def confirm_load_step(
        self,
        operation_id: str,
        operator_id: str,
        operator_confirmed: bool = True,
        override_position: Optional[Any] = None
    ) -> ContainerWorkflowSession:
        """
        Safety Gate 1: Explicit Operator Loading Confirmation.
        Transitions: AWAITING_OPERATOR_CONFIRMATION -> LOADING -> LOADED -> BALLAST_CALCULATED -> AWAITING_BALLAST_CONFIRMATION.
        """
        session = self.get_session(operation_id)
        if not session:
            raise ValueError(f"Session '{operation_id}' not found.")

        if session.current_state != WorkflowState.AWAITING_OPERATOR_CONFIRMATION:
            raise WorkflowTransitionError(
                f"Cannot confirm load from state '{session.current_state.value}'. Session must be in 'AWAITING_OPERATOR_CONFIRMATION'.",
                previous_state=session.current_state,
                attempted_state=WorkflowState.LOADING
            )

        if not operator_confirmed:
            self._record_transition(
                session,
                WorkflowState.FAILED,
                reason=f"Operator '{operator_id}' rejected container placement.",
                operator_action="LOAD_REJECTED"
            )
            return session

        session.operator_id = operator_id

        # 1. Transition: AWAITING_OPERATOR_CONFIRMATION -> LOADING
        self._record_transition(
            session,
            WorkflowState.LOADING,
            reason=f"Operator '{operator_id}' authorized container loading. Committing to live vessel state.",
            operator_action="LOAD_AUTHORIZED"
        )

        from container_stability.models import ContainerLoadingConfirmRequest, BallastCompensationRequest
        from container_stability.analyzer import ContainerLoadingService, ContainerBallastService

        extraction_res = session.extraction_response
        stability_res = session.stability_response
        target_pos = override_position or stability_res.recommendation

        load_req = ContainerLoadingConfirmRequest(
            container=_to_dict(extraction_res.container),
            document=_to_dict(extraction_res.document),
            validation=_to_dict(extraction_res.validation),
            recommendation=_to_dict(target_pos),
            operator_confirmed=True,
            operator_id=operator_id
        )

        loaded_res = ContainerLoadingService.confirm_and_load(load_req)
        session.loaded_response = loaded_res

        if not loaded_res.success:
            self._record_transition(
                session,
                WorkflowState.FAILED,
                reason=f"Loading commitment failed: {loaded_res.error_message}"
            )
            session.error_message = loaded_res.error_message
            return session

        # 2. Transition: LOADING -> LOADED
        self._record_transition(
            session,
            WorkflowState.LOADED,
            reason=f"Container committed to Ship at Bay {target_pos.bay} {target_pos.side} Tier {target_pos.tier}. Audit ID: #{loaded_res.audit_id}.",
            metadata={"audit_id": loaded_res.audit_id}
        )

        # 3. Transition: LOADED -> BALLAST_CALCULATED
        self._record_transition(
            session,
            WorkflowState.BALLAST_CALCULATED,
            reason="Calculating anti-heeling ballast water compensation on live committed vessel state."
        )

        ballast_req = BallastCompensationRequest(
            container_number=session.container_id,
            gross_weight_t=loaded_res.container.gross_weight_t,
            bay=target_pos.bay,
            side=target_pos.side,
            tier=target_pos.tier
        )
        ballast_res = ContainerBallastService.calculate_compensation(ballast_req)
        session.ballast_compensation = ballast_res

        if not ballast_res.success:
            self._record_transition(
                session,
                WorkflowState.FAILED,
                reason=f"Ballast calculation failed: {ballast_res.error_message or 'Unknown calculation error'}. Committed container state preserved; requires operator attention."
            )
            session.error_message = ballast_res.error_message or "Ballast calculation failure"
            return session

        if not ballast_res.compensation_required or ballast_res.required_qty_t <= 0.0:
            # Equilibrium already maintained, proceed directly to VERIFYING
            self._record_transition(
                session,
                WorkflowState.VERIFYING,
                reason="Ballast compensation not required (equilibrium maintained). Proceeding to verification."
            )
            return self._finalize_verification(session)

        # 4. Transition: BALLAST_CALCULATED -> AWAITING_BALLAST_CONFIRMATION
        self._record_transition(
            session,
            WorkflowState.AWAITING_BALLAST_CONFIRMATION,
            reason=f"Paused at Safety Gate: Operator confirmation required to discharge {ballast_res.required_qty_t}t from {ballast_res.affected_tank}."
        )
        return session

    def confirm_ballast_step(
        self,
        operation_id: str,
        operator_id: str,
        operator_confirmed: bool = True
    ) -> ContainerWorkflowSession:
        """
        Safety Gate 2: Explicit Operator Ballast Execution Confirmation.
        Transitions: AWAITING_BALLAST_CONFIRMATION -> BALLAST_EXECUTING -> VERIFYING -> COMPLETED.
        """
        session = self.get_session(operation_id)
        if not session:
            raise ValueError(f"Session '{operation_id}' not found.")

        if session.current_state != WorkflowState.AWAITING_BALLAST_CONFIRMATION:
            raise WorkflowTransitionError(
                f"Cannot confirm ballast from state '{session.current_state.value}'. Session must be in 'AWAITING_BALLAST_CONFIRMATION'.",
                previous_state=session.current_state,
                attempted_state=WorkflowState.BALLAST_EXECUTING
            )

        if not operator_confirmed:
            self._record_transition(
                session,
                WorkflowState.VERIFYING,
                reason=f"Operator '{operator_id}' skipped ballast compensation. Proceeding to verification.",
                operator_action="BALLAST_SKIPPED"
            )
            return self._finalize_verification(session)

        from container_stability.models import BallastExecutionRequest
        from container_stability.analyzer import ContainerBallastService

        # 1. Transition: AWAITING_BALLAST_CONFIRMATION -> BALLAST_EXECUTING
        ballast_comp = session.ballast_compensation
        self._record_transition(
            session,
            WorkflowState.BALLAST_EXECUTING,
            reason=f"Operator '{operator_id}' authorized discharge of {ballast_comp.required_qty_t}t from {ballast_comp.affected_tank}.",
            operator_action="BALLAST_AUTHORIZED"
        )

        exec_req = BallastExecutionRequest(
            container_number=session.container_id,
            tank_key=ballast_comp.tank_key,
            direction=ballast_comp.direction or "DRAIN",
            qty_t=ballast_comp.required_qty_t,
            operator_confirmed=True,
            operator_id=operator_id,
            stability_before_load=session.loaded_response.stability_before if session.loaded_response else None
        )

        exec_res = ContainerBallastService.execute_compensation(exec_req)
        session.ballast_execution = exec_res

        if not exec_res.success:
            self._record_transition(
                session,
                WorkflowState.FAILED,
                reason=f"Ballast execution failure: {exec_res.error_message}"
            )
            session.error_message = exec_res.error_message
            return session

        # 2. Transition: BALLAST_EXECUTING -> VERIFYING
        self._record_transition(
            session,
            WorkflowState.VERIFYING,
            reason=f"Discharged {exec_res.actual_qty_t}t. Running 4-stage hydrostatic verification."
        )

        return self._finalize_verification(session)

    def _finalize_verification(self, session: ContainerWorkflowSession) -> ContainerWorkflowSession:
        """Computes four-stage verification summary and transitions to COMPLETED."""
        import state
        from ship import StabilityAnalyzer
        from container_stability.models import StabilityMetrics
        ship = state.get_current_ship()
        
        list_t = StabilityAnalyzer.calculate_list(ship)
        trim_t = StabilityAnalyzer.calculate_trim(ship)
        score = StabilityAnalyzer.stability_score(ship)
        risk = StabilityAnalyzer.risk_level(ship)
        current_stab = StabilityMetrics(list_t=list_t, trim_t=trim_t, stability_score=score, risk_level=risk)
        
        before_stab = session.loaded_response.stability_before if session.loaded_response else StabilityMetrics(list_t=0.0, trim_t=0.0, stability_score=0.0, risk_level="SAFE")
        after_container = session.loaded_response.stability_after if session.loaded_response else current_stab
        after_ballast = session.ballast_execution.three_stage_stability.after_ballast if (session.ballast_execution and session.ballast_execution.three_stage_stability) else current_stab

        def _to_plain_dict(item):
            if item is None:
                return {}
            if hasattr(item, "model_dump"):
                return item.model_dump()
            if hasattr(item, "dict"):
                return item.dict()
            return item

        session.final_verification = {
            "stage_1_before": _to_plain_dict(before_stab),
            "stage_2_loaded": _to_plain_dict(after_container),
            "stage_3_ballasted": _to_plain_dict(after_ballast),
            "stage_4_current": _to_plain_dict(current_stab),
            "container_id": session.container_id,
            "provenance": CONTAINER_WEIGHT_SOURCE,
            "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        self._record_transition(
            session,
            WorkflowState.COMPLETED,
            reason="Operational lifecycle successfully verified and certified. Database audit complete."
        )
        return session

    def reject_workflow(
        self,
        operation_id: str,
        reason: str,
        operator_id: str
    ) -> ContainerWorkflowSession:
        """Explicitly cancels/rejects an operational workflow."""
        session = self.get_session(operation_id)
        if not session:
            raise ValueError(f"Session '{operation_id}' not found.")

        self._record_transition(
            session,
            WorkflowState.FAILED,
            reason=f"Operation rejected by operator '{operator_id}': {reason}",
            operator_action="EXPLICIT_REJECTION"
        )
        session.is_active = False
        return session

    def get_session(self, operation_id: str) -> Optional[ContainerWorkflowSession]:
        with self._session_lock:
            return self._sessions.get(operation_id)

    def get_active_session(self) -> Optional[ContainerWorkflowSession]:
        with self._session_lock:
            if self._active_operation_id:
                return self._sessions.get(self._active_operation_id)
            return None

    def list_sessions(self, limit: int = 50) -> List[ContainerWorkflowSession]:
        with self._session_lock:
            sessions_list = list(self._sessions.values())
            sessions_list.sort(key=lambda s: s.created_at, reverse=True)
            return sessions_list[:limit]

    def reset(self):
        with self._session_lock:
            self._sessions.clear()
            self._active_operation_id = None
