"""
Pydantic Models for Phase 2 & Phase 4B: Container JSON -> Multi-Objective Stability & Stowage Optimization.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from container_ocr.models import CargoAnomaly, CargoMassMetadata
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    LOAD_CELL_POLICY,
    DOCUMENT_AI_CARGO_MASS,
    LOAD_CELL_CARGO_MASS,
    HARDWARE_TELEMETRY_LABEL,
    ALLOWED_WEIGHT_SOURCES,
    FORBIDDEN_WEIGHT_SOURCES
)


class StabilityMetrics(BaseModel):
    list_t: float = Field(..., description="Transverse list imbalance in tonnes (positive = starboard, negative = port)")
    trim_t: float = Field(..., description="Longitudinal trim imbalance in tonnes (positive = stern, negative = bow)")
    stability_score: float = Field(..., description="Combined list and trim absolute imbalance score")
    risk_level: str = Field(..., description="Vessel stability risk level: SAFE, WARNING, or CRITICAL")
    normalized_score: Optional[float] = Field(None, description="Normalized stability score (0-100 scale)")


class StabilityComparison(BaseModel):
    before: StabilityMetrics
    after: StabilityMetrics
    delta_score: float = Field(..., description="Change in stability score (negative = improvement)")


class RecommendedPosition(BaseModel):
    bay: int = Field(..., description="Recommended bay number (1-based)")
    side: str = Field(..., description="Recommended side: 'PORT' or 'STARBOARD'")
    tier: int = Field(1, description="Recommended tier level (1 = deck level)")
    label: Optional[str] = Field(default="BEST", description="'BEST' or 'ALTERNATIVE'")
    ranking_score: Optional[float] = Field(default=None, description="Multi-objective composite ranking score")


class SlotCandidateEvaluation(BaseModel):
    bay: int
    side: str
    tier: int
    list_t: float = 0.0
    trim_t: float = 0.0
    score: float = 0.0  # Ground-truth stability score: abs(list) + abs(trim)
    stability_score: float = 0.0  # Explicit alias
    risk: str = "SAFE"
    eligible: bool = True  # False if hard constraint violated
    ranking_score: float = 0.0  # Multi-objective composite score
    penalties: Optional[Dict[str, float]] = None  # Breakdown of operational adjustments
    reasons: List[str] = Field(default_factory=list, description="Reasons for eligibility, penalties, or ineligibility")
    rank: Optional[int] = None  # 1 = Best, 2 = 2nd Best, 3 = 3rd Best
    label: Optional[str] = None  # 'BEST', 'ALTERNATIVE', or 'INELIGIBLE'
    selected: bool = False


class ContainerSummary(BaseModel):
    container_number: str
    container_type: Optional[str] = None
    iso_type: Optional[str] = None
    gross_weight_kg: float
    gross_weight_t: float
    hazardous: Optional[bool] = None
    destination: Optional[str] = None
    seal_number: Optional[str] = None
    carrier: Optional[str] = None
    cargo_mass: Optional[CargoMassMetadata] = Field(default=None, description="Explicit Phase 6A Document AI provenance metadata")


class ContainerStabilityAnalysisRequest(BaseModel):
    container: Dict[str, Any] = Field(..., description="Container details dictionary from Phase 1 or manual entry")
    document: Optional[Dict[str, Any]] = Field(default=None, description="Document metadata from Phase 1")
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Validation result from Phase 1")


class ExplanationItem(BaseModel):
    category: str = Field(..., description="Explanation category: DOCUMENT, VALIDATION, STABILITY, PLACEMENT, HAZARDOUS_CARGO, BALLAST, SAFETY")
    message: str = Field(..., description="Concise human-readable explanation")
    evidence: Optional[Dict[str, Any]] = Field(default=None, description="Actual verified values supporting the explanation")


class DataProvenanceReport(BaseModel):
    ocr_derived: Dict[str, Any] = Field(default_factory=dict, description="Fields extracted from container document image")
    calculated: Dict[str, Any] = Field(default_factory=dict, description="Values computed deterministically by the stability engine")
    operator_provided: Dict[str, Any] = Field(default_factory=dict, description="Human operator authorization, confirmation, or overrides")


class ContainerStabilityAnalysisResponse(BaseModel):
    success: bool
    status: str = Field("success", description="Status: 'success', 'review_required', or 'error'")
    container: Optional[ContainerSummary] = None
    cargo_mass: Optional[CargoMassMetadata] = Field(default=None, description="Explicit Phase 6A Document AI provenance metadata")
    recommendation: Optional[RecommendedPosition] = None
    alternatives: Optional[List[SlotCandidateEvaluation]] = Field(default=None, description="Top 2nd and 3rd alternative slot recommendations")
    stability: Optional[StabilityComparison] = None
    candidate_evaluations: Optional[List[SlotCandidateEvaluation]] = None
    reason: List[str] = Field(default_factory=list, description="Explainable engineering reasons for the recommendation")
    structured_explanations: Optional[List[ExplanationItem]] = Field(default_factory=list, description="Categorical explainability objects with evidence")
    provenance: Optional[DataProvenanceReport] = Field(default=None, description="Detailed data provenance attribution report")
    anomalies: List[CargoAnomaly] = Field(default_factory=list, description="Structured cargo safety & data anomaly items")
    disclaimer: str = Field(
        "AI-assisted decision support. Final operational authority remains with the qualified operator.",
        description="Non-certified prototype advisory disclaimer"
    )
    error_message: Optional[str] = None


class ContainerLoadingConfirmRequest(BaseModel):
    container: Dict[str, Any] = Field(..., description="Container details dictionary from Phase 1 or manual entry")
    document: Optional[Dict[str, Any]] = Field(default=None, description="Document metadata from Phase 1")
    validation: Optional[Dict[str, Any]] = Field(default=None, description="Validation result from Phase 1")
    recommendation: Optional[Dict[str, Any]] = Field(default=None, description="Target recommendation dictionary (bay, side, tier)")
    operator_confirmed: bool = Field(default=False, description="Explicit operator authorization flag")
    operator_id: Optional[str] = Field(default="operator", description="Operator identifier")


class ContainerLoadingConfirmResponse(BaseModel):
    success: bool
    status: str = Field(..., description="Loading status: 'LOADED', 'review_required', 'rejected', or 'error'")
    container: Optional[ContainerSummary] = None
    cargo_mass: Optional[CargoMassMetadata] = Field(default=None, description="Explicit Phase 6A Document AI provenance metadata")
    loaded_position: Optional[RecommendedPosition] = None
    stability_before: Optional[StabilityMetrics] = None
    stability_after: Optional[StabilityMetrics] = None
    stability_delta: Optional[float] = None
    audit_id: Optional[int] = None
    anomalies: List[CargoAnomaly] = Field(default_factory=list, description="Structured cargo safety & data anomaly items")
    message: str = Field(default="", description="Operational result message")
    error_message: Optional[str] = None


# Phase 3C: Automated Ballast Compensation Models
class BallastCompensationRequest(BaseModel):
    container_number: Optional[str] = Field(default=None, description="Container identifier")
    gross_weight_t: Optional[float] = Field(default=None, description="Container gross weight in tonnes")
    bay: Optional[int] = Field(default=None, description="Loaded bay")
    side: Optional[str] = Field(default=None, description="Loaded side ('PORT' or 'STARBOARD')")
    tier: Optional[int] = Field(default=1, description="Loaded tier")


class BallastCompensationResponse(BaseModel):
    success: bool
    status: str = Field(..., description="Stage status: 'CONFIRM_COMPENSATION', 'NO_COMPENSATION_REQUIRED', or 'error'")
    compensation_required: bool
    affected_tank: Optional[str] = None
    tank_key: Optional[str] = None
    direction: Optional[str] = None  # "DRAIN", "FILL", "TRANSFER"
    required_qty_t: float = 0.0
    required_qty_kg: float = 0.0
    current_stability: Optional[StabilityMetrics] = None
    target_stability: Optional[StabilityMetrics] = None
    projected_stability: Optional[StabilityMetrics] = None
    flow_rate_l_s: float = 0.85
    est_duration_sec: float = 0.0
    message: str = ""
    error_message: Optional[str] = None


class BallastExecutionRequest(BaseModel):
    container_number: Optional[str] = None
    tank_key: str = Field(..., description="Target tank key e.g. 'starboard_2'")
    direction: str = Field(default="DRAIN", description="Ballast action: 'DRAIN', 'FILL', 'TRANSFER'")
    qty_t: float = Field(..., description="Quantity of ballast to move in tonnes")
    operator_confirmed: bool = Field(default=False, description="Operator confirmation flag")
    operator_id: Optional[str] = Field(default="ChiefOfficer")
    stability_before_load: Optional[StabilityMetrics] = None


class ThreeStageStabilityReport(BaseModel):
    before_load: StabilityMetrics
    after_container: StabilityMetrics
    after_ballast: StabilityMetrics
    net_score_delta: float


class BallastExecutionResponse(BaseModel):
    success: bool
    status: str = Field(..., description="Execution status: 'COMPLETED', 'DRAINING', 'rejected', or 'error'")
    actual_qty_t: float = 0.0
    affected_tank: Optional[str] = None
    tank_key: Optional[str] = None
    three_stage_stability: Optional[ThreeStageStabilityReport] = None
    audit_id: Optional[int] = None
    message: str = ""
    error_message: Optional[str] = None


# ---------------------------------------------------------
# Phase 4D: Multi-Container Stowage Optimization Models
# ---------------------------------------------------------

class PlannedContainerStep(BaseModel):
    step_number: int
    container: ContainerSummary
    cargo_mass: Optional[CargoMassMetadata] = Field(default=None, description="Explicit Phase 6A Document AI provenance metadata")
    status: str = Field("VALID", description="'VALID', 'REVIEW_REQUIRED', or 'REJECTED'")
    recommended_position: Optional[RecommendedPosition] = None
    ranking_score: Optional[float] = None
    stability_after: Optional[StabilityMetrics] = None
    delta_score: Optional[float] = None
    ballast_required: bool = False
    ballast_recommendation: Optional[Dict[str, Any]] = None
    reasons: List[str] = Field(default_factory=list)



class StageStability(BaseModel):
    stage_index: int
    label: str
    container_id: Optional[str] = None
    metrics: StabilityMetrics


class RejectedContainerItem(BaseModel):
    container_number: str
    reason: str
    status: str = Field("REJECTED", description="'REVIEW_REQUIRED' or 'REJECTED'")


class MultiContainerPlanRequest(BaseModel):
    containers: List[Dict[str, Any]] = Field(..., description="List of container extraction dictionaries")
    documents: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional document metadata per container")
    validations: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional validation results per container")


class MultiContainerPlanResponse(BaseModel):
    success: bool
    total_containers: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    initial_stability: Optional[StabilityMetrics] = None
    final_stability: Optional[StabilityMetrics] = None
    stability_progression: List[StageStability] = Field(default_factory=list)
    loading_sequence: List[PlannedContainerStep] = Field(default_factory=list)
    rejected_containers: List[RejectedContainerItem] = Field(default_factory=list)
    cumulative_imbalance: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    disclaimer: str = Field(
        "AI-assisted decision support. Final operational authority remains with the qualified operator.",
        description="Operational advisory disclaimer"
    )
    error_message: Optional[str] = None


class MultiContainerExecuteRequest(BaseModel):
    loading_sequence: List[Dict[str, Any]] = Field(..., description="Approved sequence of planned container steps")
    operator_confirmed: bool = Field(default=False, description="Explicit operator authorization flag")
    operator_id: Optional[str] = Field(default="ChiefOfficer")


class MultiContainerExecuteResponse(BaseModel):
    success: bool
    status: str = Field("EXECUTED", description="'EXECUTED', 'REJECTED', or 'ERROR'")
    executed_count: int = 0
    final_stability: Optional[StabilityMetrics] = None
    audit_ids: List[int] = Field(default_factory=list)
    message: str = ""
    error_message: Optional[str] = None


# ---------------------------------------------------------
# Phase 4F: Cargo-Aware Digital Twin & Predictive Monitoring Models
# ---------------------------------------------------------

class OperationalSafetyAlert(BaseModel):
    alert_type: str = Field(..., description="'EXCESSIVE_LIST', 'EXCESSIVE_TRIM', 'BALLAST_IMBALANCE', or 'STATE_MISMATCH'")
    severity: str = Field(..., description="'INFO', 'WARNING', or 'CRITICAL'")
    threshold: str = Field(..., description="Operating safety threshold limit")
    observed_value: float = Field(..., description="Observed sensor or hydrostatic value")
    message: str = Field(..., description="Human-readable warning explanation")
    action: str = Field(..., description="Actionable operator countermeasure")


from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    ALLOWED_WEIGHT_SOURCES,
    FORBIDDEN_WEIGHT_SOURCES
)

class DigitalTwinVesselState(BaseModel):
    ship_name: str
    containers: List[Dict[str, Any]] = Field(default_factory=list)
    ballast_tanks: Dict[str, Any] = Field(default_factory=dict)
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    list_t: float = 0.0
    trim_t: float = 0.0
    stability_score: float = 0.0
    risk_level: str = "SAFE"
    is_simulated: bool = True
    telemetry_source: str = Field("SIMULATED_TELEMETRY", description="'SIMULATED_TELEMETRY' or 'HARDWARE_SENSOR'")
    authoritative_weight_source: str = Field(PROVENANCE_LABEL, description="Authoritative source for cargo mass")
    operation_status: str = "IDLE"
    alerts: List[OperationalSafetyAlert] = Field(default_factory=list)
    
    # Phase 5 Real-Time Operational Telemetry Quality & Provenance fields
    telemetry_timestamp: Optional[str] = Field(default=None, description="UTC ISO-8601 timestamp of telemetry reading")
    telemetry_freshness: str = Field("FRESH", description="'FRESH', 'STALE', 'DEGRADED', or 'DISCONNECTED'")
    stale_seconds: float = Field(0.0, description="Elapsed seconds since last physical telemetry update")
    connection_status: str = Field("CONNECTED", description="'CONNECTED', 'DISCONNECTED', 'STALE', 'DEGRADED', or 'SIMULATED'")
    pump_state: str = Field("IDLE", description="'IDLE', 'DRAINING', 'FILLING', 'TRANSFERRING', or 'OFF'")
    pump_flow_l_s: float = Field(0.0, description="Active line flow rate in litres per second")
    pump_active: bool = Field(False, description="True if pump or valve is actively transferring fluid")
    provenance_map: Dict[str, str] = Field(
        default_factory=lambda: {
            "cargo_weight": "[DOCUMENT AI]",
            "vessel_hydrostatics": "[CALCULATED]",
            "telemetry": "[SIMULATED TELEMETRY]",
            "predictions": "[PREDICTED]"
        },
        description="Explicit multi-layer data provenance mapping"
    )


class PredictiveComparison(BaseModel):
    container_id: Optional[str] = None
    projected_list_t: float = 0.0
    projected_trim_t: float = 0.0
    projected_stability_score: float = 0.0
    projected_ballast_req_t: float = 0.0
    actual_list_t: Optional[float] = None
    actual_trim_t: Optional[float] = None
    actual_stability_score: Optional[float] = None
    actual_ballast_state_t: Optional[float] = None
    status: str = Field("PROJECTED", description="'PROJECTED' (pre-load simulation) or 'COMMITTED' (actual vessel state)")


class FourStageLifecycle(BaseModel):
    vessel_before: Optional[DigitalTwinVesselState] = None
    container_loaded: Optional[DigitalTwinVesselState] = None
    ballast_compensated: Optional[DigitalTwinVesselState] = None
    current_vessel_state: DigitalTwinVesselState
    alerts: List[OperationalSafetyAlert] = Field(default_factory=list)


# ---------------------------------------------------------
# Phase 5: Real-Time Operational Integration Models
# ---------------------------------------------------------

class LiveOperationalStatusResponse(BaseModel):
    success: bool = True
    operational_stage: str = Field("IDLE", description="Active operational flow stage")
    ship_name: str
    total_containers: int = 0
    total_cargo_weight_t: float = 0.0
    total_ballast_weight_t: float = 0.0
    list_t: float = 0.0
    trim_t: float = 0.0
    stability_score: float = 0.0
    risk_level: str = "SAFE"
    telemetry: Dict[str, Any] = Field(default_factory=dict)
    telemetry_source: str = "SIMULATED_TELEMETRY"
    authoritative_weight_source: str = PROVENANCE_LABEL
    load_cell_policy: str = "FORBIDDEN_FOR_CARGO_AND_STABILITY"
    hardware_telemetry_label: str = HARDWARE_TELEMETRY_LABEL
    cargo_mass_provenance_rule: str = "DOCUMENT_AI_AUTHORITATIVE_LOAD_CELL_FORBIDDEN"
    active_alerts: List[OperationalSafetyAlert] = Field(default_factory=list)


class OperationalResetResponse(BaseModel):
    success: bool = True
    stage: str = "WAITING_FOR_CARGO"
    message: str = "Operational staging workflow reset. Committed vessel state preserved."


class OperationalPolicyResponse(BaseModel):
    success: bool = True
    policy_name: str = "MareTide Phase 6A Authoritative Data Policy"
    container_weight_source: str = CONTAINER_WEIGHT_SOURCE
    provenance_label: str = PROVENANCE_LABEL
    document_ai_cargo_mass: str = DOCUMENT_AI_CARGO_MASS
    load_cell_cargo_mass: str = LOAD_CELL_CARGO_MASS
    hardware_telemetry_label: str = HARDWARE_TELEMETRY_LABEL
    allowed_sources: List[str] = Field(default_factory=lambda: list(ALLOWED_WEIGHT_SOURCES))
    forbidden_sources: List[str] = Field(default_factory=lambda: list(FORBIDDEN_WEIGHT_SOURCES))
    authoritative_sources: List[str] = Field(
        default_factory=lambda: [
            "Validated OCR / Document Cargo JSON (gross_weight_kg, tare_weight_kg, dimensions, ISO 6346, hazardous class)",
            "Committed Vessel State (Ship.containers, Ship.tanks)",
            "Permitted Ballast Tank Level Telemetry (distance, ballast_pct, volume)"
        ]
    )
    non_authoritative_sources: List[str] = Field(
        default_factory=lambda: [
            "Hardware Telemetry Sensor Stream ([HARDWARE TELEMETRY — NON-AUTHORITATIVE])",
            "Simulated Environmental Telemetry (wave jitter)",
            "Predictive Projections (pre-load simulations)",
            "Derived Values (metacentric height estimations)"
        ]
    )



# ---------------------------------------------------------
# Phase 5: Centralized Real-Time Safety Gate Models
# ---------------------------------------------------------

from enum import Enum
import datetime

class SafetyGateStatus(str, Enum):
    SAFE = "SAFE"
    WARNING = "WARNING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CRITICAL = "CRITICAL"
    BLOCKED = "BLOCKED"


class SafetyGateType(str, Enum):
    OCR_VALIDATION = "OCR_VALIDATION"
    STABILITY_SIMULATION = "STABILITY_SIMULATION"
    LOADING_CONFIRMATION = "LOADING_CONFIRMATION"
    BALLAST_EXECUTION = "BALLAST_EXECUTION"
    OPERATION_COMPLETION = "OPERATION_COMPLETION"


class SafetyGateReason(BaseModel):
    category: str = Field(..., description="'VALIDATION', 'ANOMALY', 'IDENTIFIER', 'WEIGHT', 'STABILITY', 'SLOT', 'BALLAST', 'TELEMETRY', 'AUTHORIZATION', 'POLICY'")
    message: str = Field(..., description="Concise human-readable explanation")
    severity: str = Field("CRITICAL", description="'INFO', 'WARNING', 'CRITICAL', 'BLOCKING'")
    evidence: Optional[Dict[str, Any]] = Field(default=None, description="Diagnostic values supporting the decision")


class SafetyGateEvaluationResult(BaseModel):
    allowed: bool = Field(..., description="True if operation is permitted to proceed")
    status: str = Field(..., description="'SAFE', 'WARNING', 'REVIEW_REQUIRED', 'CRITICAL', or 'BLOCKED'")
    gate_type: str = Field(..., description="Type of operation being gated")
    reasons: List[SafetyGateReason] = Field(default_factory=list, description="Structured reasons explaining decisions")
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    provenance: str = Field(PROVENANCE_LABEL, description="Authoritative cargo provenance")
    load_cell_policy: str = "FORBIDDEN_FOR_CARGO_AND_STABILITY"


class SafetyGateEvaluationRequest(BaseModel):
    gate_type: str = Field("LOADING_CONFIRMATION", description="Operation type being gated")
    container_data: Optional[Dict[str, Any]] = None
    document_data: Optional[Dict[str, Any]] = None
    validation_data: Optional[Dict[str, Any]] = None
    target_slot: Optional[Dict[str, Any]] = None
    target_ballast: Optional[Dict[str, Any]] = None
    stability_metrics: Optional[Dict[str, Any]] = None
    telemetry: Optional[Dict[str, Any]] = None
    anomalies: Optional[List[Dict[str, Any]]] = None
    operator_confirmed: Optional[bool] = None
    operator_id: Optional[str] = None
    weight_source: Optional[str] = None

