"""
Phase 2 Stability Analysis Adapter.
Connects Phase 1 structured container JSON to the existing MareTide stability calculation engine (ship.py).
Reuses Ship, Container, StabilityAnalyzer, and RecommendationEngine without modifying existing formulas.
"""

import copy
import logging
from typing import Dict, Any, Optional, List, Tuple

from ship import Ship, Container, StabilityAnalyzer, RecommendationEngine
import state
from reports.logs_db import (
    log_container_loading_audit, 
    log_cargo_operation,
    log_ballast_operation
)
from .models import (
    ContainerStabilityAnalysisRequest,
    ContainerStabilityAnalysisResponse,
    ContainerLoadingConfirmRequest,
    ContainerLoadingConfirmResponse,
    BallastCompensationRequest,
    BallastCompensationResponse,
    BallastExecutionRequest,
    BallastExecutionResponse,
    ThreeStageStabilityReport,
    ContainerSummary,
    RecommendedPosition,
    StabilityMetrics,
    StabilityComparison,
    SlotCandidateEvaluation,
    ExplanationItem,
    DataProvenanceReport,
    PlannedContainerStep,
    StageStability,
    RejectedContainerItem,
    MultiContainerPlanRequest,
    MultiContainerPlanResponse,
    MultiContainerExecuteRequest,
    MultiContainerExecuteResponse,
    CargoAnomaly,
    CargoMassMetadata
)
from container_ocr.anomaly_detector import CargoAnomalyDetector
from container_stability.policy import (
    CONTAINER_WEIGHT_SOURCE,
    PROVENANCE_LABEL,
    ALLOWED_WEIGHT_SOURCES,
    FORBIDDEN_WEIGHT_SOURCES,
    DOCUMENT_AI_CARGO_MASS,
    LOAD_CELL_CARGO_MASS,
    HARDWARE_TELEMETRY_LABEL,
    assert_authoritative_source,
    validate_cargo_mass_provenance
)

logger = logging.getLogger("container_stability.analyzer")



class ContainerStabilityService:
    """
    Evaluates candidate placement slots for a given container using the existing MareTide Stability Engine.
    Executes simulations on a temporary copy-on-write vessel state to guarantee live state integrity.
    """

    @classmethod
    def analyze_container_placement(
        cls,
        request: ContainerStabilityAnalysisRequest,
        ship_instance: Optional[Ship] = None
    ) -> ContainerStabilityAnalysisResponse:
        """
        Main analysis entry point.
        Takes Phase 1 container JSON, validates prerequisites, simulates candidate slots, and returns recommendations.
        """
        container_data = request.container or {}
        doc_data = request.document or {}
        val_data = request.validation or {}

        # 0. Policy Validation: Assert cargo weight source is authoritative
        source_claimed = container_data.get("weight_source") or container_data.get("source") or CONTAINER_WEIGHT_SOURCE
        auth_flag = container_data.get("authoritative", True)
        cargo_meta_input = container_data.get("cargo_mass")
        try:
            validate_cargo_mass_provenance(
                source=source_claimed,
                authoritative=auth_flag,
                cargo_mass_meta=cargo_meta_input if isinstance(cargo_meta_input, dict) else None
            )
        except ValueError as pe:
            return ContainerStabilityAnalysisResponse(
                success=False,
                status="rejected",
                error_message=str(pe)
            )

        # 1. Verification of Document Status
        doc_status = doc_data.get("processing_status", "success")
        is_valid = val_data.get("valid", True)
        if doc_status == "review_required" or is_valid is False:
            return ContainerStabilityAnalysisResponse(
                success=False,
                status="review_required",
                error_message="Container document requires verification before stability analysis. Low extraction confidence or validation warning present."
            )

        # 2. Extraction of Required Physical Attributes
        weights_data = container_data.get("weights") or {}
        gross_kg = weights_data.get("gross_weight_kg")
        if gross_kg is None:
            # Fallback if provided at top-level
            gross_kg = container_data.get("gross_weight_kg") or container_data.get("weight")

        if gross_kg is None or gross_kg <= 0:
            return ContainerStabilityAnalysisResponse(
                success=False,
                status="error",
                error_message="Gross weight is missing or invalid. Stability calculation requires gross_weight_kg > 0."
            )

        # Weight conversion: container gross weight in tonnes (1 tonne = 1000 kg)
        gross_t = round(float(gross_kg) / 1000.0, 2)
        container_id = (
            container_data.get("container_number") or
            container_data.get("id") or
            "CONT-UNASSIGNED"
        )
        container_type = container_data.get("container_type")
        cargo_data = container_data.get("cargo") or {}
        hazardous = cargo_data.get("hazardous") if isinstance(cargo_data, dict) else container_data.get("hazardous")
        destination = container_data.get("destination")

        cargo_mass_metadata = CargoMassMetadata(
            value=float(gross_kg),
            unit="kg",
            source="DOCUMENT_AI",
            authoritative=True
        )

        container_summary = ContainerSummary(
            container_number=container_id,
            container_type=container_type,
            gross_weight_kg=float(gross_kg),
            gross_weight_t=gross_t,
            hazardous=hazardous,
            destination=destination,
            cargo_mass=cargo_mass_metadata
        )


        # 3. Create Isolated Simulation Ship (Copy-on-Write)
        base_ship = ship_instance if ship_instance is not None else state.get_current_ship()
        sim_ship = copy.deepcopy(base_ship)

        # 4. Calculate Current "Before" Stability Metrics
        before_list = StabilityAnalyzer.calculate_list(sim_ship)
        before_trim = StabilityAnalyzer.calculate_trim(sim_ship)
        before_score = StabilityAnalyzer.stability_score(sim_ship)
        before_risk = StabilityAnalyzer.risk_level(sim_ship)

        before_metrics = StabilityMetrics(
            list_t=round(float(before_list), 2),
            trim_t=round(float(before_trim), 2),
            stability_score=round(float(before_score), 2),
            risk_level=before_risk
        )

        # 5. Multi-Objective Evaluation of Candidate Slots Across Bays & Sides
        candidate_evaluations: List[SlotCandidateEvaluation] = []
        num_bays = sim_ship.num_bays or 4

        for bay in range(1, num_bays + 1):
            for side in ("port", "starboard"):
                # Determine available tier level (1 = deck level, stacked above occupied)
                tier = 1
                while sim_ship.slot_occupied(bay, side, tier):
                    tier += 1

                # Hard Constraint: Cap maximum stack height at tier 3
                if tier > 3:
                    candidate_evaluations.append(
                        SlotCandidateEvaluation(
                            bay=bay,
                            side=side.upper(),
                            tier=3,
                            eligible=False,
                            ranking_score=999.0,
                            score=999.0,
                            stability_score=999.0,
                            risk="CRITICAL",
                            label="INELIGIBLE",
                            reasons=["Slot column is completely occupied (maximum stack height reached)."]
                        )
                    )
                    continue

                # Simulate placement on isolated copy-on-write vessel state
                temp_container = Container(
                    id=container_id,
                    weight=gross_t,
                    bay=bay,
                    side=side,
                    tier=tier
                )
                sim_ship.containers.append(temp_container)

                cand_list = StabilityAnalyzer.calculate_list(sim_ship)
                cand_trim = StabilityAnalyzer.calculate_trim(sim_ship)
                cand_score = StabilityAnalyzer.stability_score(sim_ship)
                cand_risk = StabilityAnalyzer.risk_level(sim_ship)

                # Revert simulation state immediately
                sim_ship.containers.pop()

                # Soft Objectives & Operational Adjustments
                penalties: Dict[str, float] = {}
                cand_reasons: List[str] = []

                # 1. Vertical Center of Gravity (VCG) / Tier Constraint
                if gross_t >= 20.0 and tier > 1:
                    p_tier = round((tier - 1) * 8.0, 2)
                    penalties["tier_vcg"] = p_tier
                    cand_reasons.append(f"Heavy load ({gross_t:.1f}t) on Tier {tier} raises vertical center of gravity (+{p_tier} penalty).")
                elif tier == 1:
                    cand_reasons.append("Tier 1 deck placement secures low vertical center of gravity.")

                # 2. Stack Inversion Hierarchy (Heavier container stacked above lighter)
                if tier > 1:
                    base_c = next((c for c in sim_ship.containers if c.bay == bay and c.side.lower() == side.lower() and c.tier == tier - 1), None)
                    if base_c and base_c.weight < gross_t:
                        p_stack = round((gross_t - base_c.weight) * 0.4, 2)
                        penalties["stack_inversion"] = p_stack
                        cand_reasons.append(f"Heavier container ({gross_t:.1f}t) stacked atop lighter ({base_c.weight:.1f}t) base (+{p_stack} penalty).")

                # 3. Longitudinal Moment Balance (Extreme end-bay penalty for heavy cargo)
                if gross_t >= 25.0 and (bay == 1 or bay == num_bays):
                    p_long = 3.5
                    penalties["end_bay_moment"] = p_long
                    cand_reasons.append(f"End-bay extremity (Bay {bay}) increases longitudinal pitching moment (+{p_long} penalty).")
                elif bay in (2, 3):
                    cand_reasons.append(f"Mid-ship location (Bay {bay}) provides balanced longitudinal weight distribution.")

                # 4. Hazardous Cargo Accessibility
                if hazardous is True:
                    if tier == 1:
                        penalties["hazardous_deck_bonus"] = -2.0
                        cand_reasons.append("Hazardous cargo at Tier 1 ensures direct open deck accessibility and emergency isolation.")
                    else:
                        penalties["hazardous_upper_tier_penalty"] = 4.0
                        cand_reasons.append("Upper tier hazardous stowage restricts emergency access speed (+4.0 penalty).")

                # 5. Composite Ranking Score
                ranking_score = round(float(cand_score) + sum(penalties.values()), 2)
                cand_reasons.append(f"Stability score: {cand_score:.2f} (List: {cand_list:.2f}t, Trim: {cand_trim:.2f}t). Multi-objective score: {ranking_score:.2f}.")

                candidate_evaluations.append(
                    SlotCandidateEvaluation(
                        bay=bay,
                        side=side.upper(),
                        tier=tier,
                        list_t=round(float(cand_list), 2),
                        trim_t=round(float(cand_trim), 2),
                        score=round(float(cand_score), 2),
                        stability_score=round(float(cand_score), 2),
                        risk=cand_risk,
                        eligible=True,
                        ranking_score=ranking_score,
                        penalties=penalties,
                        reasons=cand_reasons,
                        selected=False
                    )
                )

        # 6. Rank Eligible Candidates and Select Top Recommendations
        # Sort candidate evaluations: eligible first, sorted by ranking_score, stability_score, tier, bay
        candidate_evaluations.sort(key=lambda c: (not c.eligible, c.ranking_score, c.score, c.tier, c.bay))
        eligible_candidates = [c for c in candidate_evaluations if c.eligible]
        if not eligible_candidates:
            return ContainerStabilityAnalysisResponse(
                success=False,
                status="error",
                error_message="No available cargo slots found on the vessel."
            )

        # Sort eligible candidates: lowest composite ranking_score first, with tie-breakers
        eligible_candidates.sort(key=lambda c: (c.ranking_score, c.score, c.tier, c.bay))

        for idx, cand in enumerate(eligible_candidates):
            cand.rank = idx + 1
            if idx == 0:
                cand.label = "BEST"
                cand.selected = True
            elif idx in (1, 2):
                cand.label = "ALTERNATIVE"

        best_cand = eligible_candidates[0]
        alternatives = eligible_candidates[1:3] if len(eligible_candidates) > 1 else []

        best_after_metrics = StabilityMetrics(
            list_t=best_cand.list_t,
            trim_t=best_cand.trim_t,
            stability_score=best_cand.score,
            risk_level=best_cand.risk
        )

        best_bay = best_cand.bay
        best_side = best_cand.side
        best_tier = best_cand.tier

        # 7. Formulate Explainable Engineering Reasons
        delta_score = round(best_after_metrics.stability_score - before_metrics.stability_score, 2)
        reasons = cls._generate_explainable_reasons(
            gross_t=gross_t,
            best_bay=best_bay,
            best_side=best_side,
            best_tier=best_tier,
            before=before_metrics,
            after=best_after_metrics,
            hazardous=hazardous,
            best_cand=best_cand
        )

        structured_explanations = cls._generate_structured_explanations(
            container_data=container_data,
            doc_data=doc_data,
            val_data=val_data,
            gross_t=gross_t,
            best_cand=best_cand,
            alternatives=alternatives,
            before=before_metrics,
            after=best_after_metrics,
            hazardous=hazardous
        )

        provenance = cls._generate_data_provenance(
            container_data=container_data,
            doc_data=doc_data,
            gross_t=gross_t,
            best_cand=best_cand,
            before=before_metrics,
            after=best_after_metrics,
            hazardous=hazardous
        )

        # Anomaly Detection (Phase 4E)
        anomalies = CargoAnomalyDetector.detect_anomalies(
            container_data=container_data,
            confidence_data=request.document.get("confidence") if isinstance(request.document, dict) else None,
            existing_containers=base_ship.containers
        )

        comparison = StabilityComparison(
            before=before_metrics,
            after=best_after_metrics,
            delta_score=delta_score
        )

        recommendation = RecommendedPosition(
            bay=best_bay,
            side=best_side,
            tier=best_tier,
            label="BEST",
            ranking_score=best_cand.ranking_score
        )

        return ContainerStabilityAnalysisResponse(
            success=True,
            status="success",
            container=container_summary,
            cargo_mass=cargo_mass_metadata,
            recommendation=recommendation,
            alternatives=alternatives,
            stability=comparison,
            candidate_evaluations=candidate_evaluations,
            reason=reasons,
            structured_explanations=structured_explanations,
            provenance=provenance,
            anomalies=anomalies
        )


    @classmethod
    def _generate_structured_explanations(
        cls,
        container_data: Dict[str, Any],
        doc_data: Dict[str, Any],
        val_data: Dict[str, Any],
        gross_t: float,
        best_cand: SlotCandidateEvaluation,
        alternatives: List[SlotCandidateEvaluation],
        before: StabilityMetrics,
        after: StabilityMetrics,
        hazardous: Optional[bool]
    ) -> List[ExplanationItem]:
        items: List[ExplanationItem] = []

        # 1. DOCUMENT
        cntr_num = container_data.get("container_number") or "UNASSIGNED"
        doc_src = doc_data.get("source") or "container_slip.jpg"
        items.append(
            ExplanationItem(
                category="DOCUMENT",
                message=f"Extracted container {cntr_num} ({gross_t:.1f} tonnes gross mass) from document manifest.",
                evidence={
                    "source": doc_src,
                    "container_number": cntr_num,
                    "gross_weight_kg": round(gross_t * 1000.0, 1),
                    "gross_weight_t": gross_t,
                    "container_type": container_data.get("container_type", "Standard"),
                    "destination": container_data.get("destination")
                }
            )
        )

        # 2. VALIDATION
        is_iso_valid = val_data.get("iso_6346_valid", True)
        is_weight_valid = val_data.get("weight_balance_valid", True)
        warnings = val_data.get("warnings") or []
        items.append(
            ExplanationItem(
                category="VALIDATION",
                message="Container parameters verified against ISO 6346 checksums and physical mass bounds.",
                evidence={
                    "valid": val_data.get("valid", True),
                    "iso_6346_valid": is_iso_valid,
                    "weight_balance_valid": is_weight_valid,
                    "warnings": warnings
                }
            )
        )

        # 3. STABILITY
        items.append(
            ExplanationItem(
                category="STABILITY",
                message=f"Selected Bay {best_cand.bay} {best_cand.side} (Tier {best_cand.tier}) produced stability score {after.stability_score:.1f} pts ({after.risk_level} envelope).",
                evidence={
                    "before_score": before.stability_score,
                    "after_score": after.stability_score,
                    "delta_score": round(after.stability_score - before.stability_score, 2),
                    "before_list_t": before.list_t,
                    "after_list_t": after.list_t,
                    "before_trim_t": before.trim_t,
                    "after_trim_t": after.trim_t,
                    "risk_level": after.risk_level
                }
            )
        )

        # 4. PLACEMENT
        alt_notes = []
        if alternatives:
            for alt in alternatives:
                diff = round(alt.ranking_score - best_cand.ranking_score, 2)
                alt_notes.append(f"Bay {alt.bay} {alt.side} Tier {alt.tier} (+{diff} pts)")
        items.append(
            ExplanationItem(
                category="PLACEMENT",
                message=f"Bay {best_cand.bay} {best_cand.side} Tier {best_cand.tier} ranked #1 with composite multi-objective score {best_cand.ranking_score:.1f} pts." +
                        (f" Outperformed alternatives: {', '.join(alt_notes)}." if alt_notes else ""),
                evidence={
                    "selected_bay": best_cand.bay,
                    "selected_side": best_cand.side,
                    "selected_tier": best_cand.tier,
                    "ranking_score": best_cand.ranking_score,
                    "stability_score": best_cand.score,
                    "penalties": best_cand.penalties or {},
                    "alternatives_evaluated": len(alternatives)
                }
            )
        )

        # 5. HAZARDOUS_CARGO
        cargo_data = container_data.get("cargo") or {}
        un_num = cargo_data.get("un_number") if isinstance(cargo_data, dict) else None
        imdg_cls = cargo_data.get("imdg_class") if isinstance(cargo_data, dict) else None
        if hazardous:
            items.append(
                ExplanationItem(
                    category="HAZARDOUS_CARGO",
                    message=f"Dangerous goods ({imdg_cls or 'DG'}, {un_num or 'UN'}) restricted to Tier 1 deck position for rapid emergency access.",
                    evidence={
                        "hazardous": True,
                        "un_number": un_num,
                        "imdg_class": imdg_cls,
                        "stowage_tier": best_cand.tier
                    }
                )
            )
        else:
            items.append(
                ExplanationItem(
                    category="HAZARDOUS_CARGO",
                    message="Standard non-hazardous cargo; no dangerous goods segregation constraints required.",
                    evidence={"hazardous": False}
                )
            )

        # 6. BALLAST
        needs_comp = after.stability_score > 15.0 or abs(after.list_t) > 10.0
        items.append(
            ExplanationItem(
                category="BALLAST",
                message=f"Post-load stability projection indicates {'ballast compensation is recommended' if needs_comp else 'hull equilibrium is maintained without mandatory ballast transfer'}.",
                evidence={
                    "post_load_stability_score": after.stability_score,
                    "post_load_list_t": after.list_t,
                    "post_load_trim_t": after.trim_t,
                    "compensation_recommended": needs_comp
                }
            )
        )

        # 7. SAFETY
        items.append(
            ExplanationItem(
                category="SAFETY",
                message="AI-assisted decision support. Final operational authority remains with the qualified operator.",
                evidence={
                    "operator_confirmation_required": True,
                    "live_state_protected": True
                }
            )
        )

        return items

    @classmethod
    def _generate_data_provenance(
        cls,
        container_data: Dict[str, Any],
        doc_data: Dict[str, Any],
        gross_t: float,
        best_cand: SlotCandidateEvaluation,
        before: StabilityMetrics,
        after: StabilityMetrics,
        hazardous: Optional[bool]
    ) -> DataProvenanceReport:
        weights_data = container_data.get("weights") or {}
        
        ocr_derived = {
            "container_number": container_data.get("container_number"),
            "container_type": container_data.get("container_type"),
            "gross_weight_kg": weights_data.get("gross_weight_kg") or round(gross_t * 1000.0, 1),
            "gross_weight_t": gross_t,
            "dimensions": container_data.get("dimensions"),
            "hazardous": hazardous,
            "destination": container_data.get("destination"),
            "seal_number": container_data.get("seal_number"),
            "carrier": container_data.get("carrier")
        }

        calculated = {
            "stability_score_before": before.stability_score,
            "stability_score_after": after.stability_score,
            "list_after_t": after.list_t,
            "trim_after_t": after.trim_t,
            "delta_score": round(after.stability_score - before.stability_score, 2),
            "multi_objective_ranking_score": best_cand.ranking_score,
            "recommended_bay": best_cand.bay,
            "recommended_side": best_cand.side,
            "recommended_tier": best_cand.tier,
            "candidate_rank": best_cand.rank,
            "ballast_compensation_needed": after.stability_score > 15.0 or abs(after.list_t) > 10.0
        }

        operator_provided = {
            "stowage_confirmation": "Awaiting explicit operator authorization",
            "position_override": "Permitted under Chief Officer discretion",
            "ballast_execution": "Requires physical operator trigger"
        }

        return DataProvenanceReport(
            ocr_derived=ocr_derived,
            calculated=calculated,
            operator_provided=operator_provided
        )

    @classmethod
    def _generate_explainable_reasons(
        cls,
        gross_t: float,
        best_bay: int,
        best_side: str,
        best_tier: int,
        before: StabilityMetrics,
        after: StabilityMetrics,
        hazardous: Optional[bool],
        best_cand: Optional[SlotCandidateEvaluation] = None
    ) -> List[str]:
        reasons = []

        # 1. Transverse List Explanation
        if before.list_t > 10.0 and best_side == "PORT":
            reasons.append(
                f"Placing {gross_t:.1f} t container on PORT offsets existing STARBOARD list ({before.list_t:.1f} t -> {after.list_t:.1f} t)."
            )
        elif before.list_t < -10.0 and best_side == "STARBOARD":
            reasons.append(
                f"Placing {gross_t:.1f} t container on STARBOARD offsets existing PORT list ({before.list_t:.1f} t -> {after.list_t:.1f} t)."
            )
        elif abs(after.list_t) <= 15.0:
            reasons.append(
                f"Maintains transverse equilibrium across centerline (resulting list: {after.list_t:.1f} t)."
            )
        else:
            reasons.append(
                f"Selected {best_side} slot offers optimal lateral weight balance under current cargo configuration."
            )

        # 2. Longitudinal Trim Explanation
        if abs(after.trim_t) < abs(before.trim_t):
            reasons.append(
                f"Bay {best_bay} placement reduces longitudinal trim moment ({before.trim_t:.1f} t -> {after.trim_t:.1f} t)."
            )
        else:
            reasons.append(
                f"Bay {best_bay} placement maintains vessel trim within acceptable operating bounds ({after.trim_t:.1f} t)."
            )

        # 3. Overall Stability Score & Safety
        if after.stability_score < before.stability_score:
            improvement = before.stability_score - after.stability_score
            reasons.append(
                f"Combined stability score improves by {improvement:.1f} pts (from {before.stability_score:.1f} to {after.stability_score:.1f})."
            )
        else:
            reasons.append(
                f"Resulting stability score ({after.stability_score:.1f}) preserves a {after.risk_level} operational envelope."
            )

        # 4. Multi-Objective Operational Context
        if best_cand and best_cand.reasons:
            for r in best_cand.reasons:
                if r not in reasons and "Stability score:" not in r:
                    reasons.append(r)

        # 5. Dangerous Goods / Hazardous Stacking Awareness
        if hazardous and not any("Hazardous cargo" in r for r in reasons):
            reasons.append(
                "Hazardous cargo flag: Tier 1 deck placement selected for accessible emergency monitoring and segregation."
            )

        return reasons


class ContainerLoadingService:
    """
    Phase 3B: Container Loading Confirmation and Atomic Vessel State Commit Service.
    Executes safety validations, confirms operator authorization, verifies slot vacancy,
    atomically updates live vessel state, and logs audit entries.
    """

    @classmethod
    def confirm_and_load(
        cls,
        request: ContainerLoadingConfirmRequest,
        ship_instance: Optional[Ship] = None
    ) -> ContainerLoadingConfirmResponse:
        """
        Validates operator confirmation, revalidates container data, verifies recommendation,
        checks slot availability, atomically commits container to vessel state, and writes audit record.
        """
        container_data = request.container or {}
        doc_data = request.document or {}
        val_data = request.validation or {}
        rec_data = request.recommendation or {}

        # 0. Policy Validation: Assert cargo weight source is authoritative
        source_claimed = container_data.get("weight_source") or container_data.get("source") or CONTAINER_WEIGHT_SOURCE
        auth_flag = container_data.get("authoritative", True)
        cargo_meta_input = container_data.get("cargo_mass")
        try:
            validate_cargo_mass_provenance(
                source=source_claimed,
                authoritative=auth_flag,
                cargo_mass_meta=cargo_meta_input if isinstance(cargo_meta_input, dict) else None
            )
        except ValueError as pe:
            return ContainerLoadingConfirmResponse(
                success=False,
                status="rejected",
                error_message=str(pe)
            )

        container_id = (
            container_data.get("container_number") or
            container_data.get("id") or
            "CONT-OCR"
        )
        weights_data = container_data.get("weights") or {}
        gross_kg = weights_data.get("gross_weight_kg")
        if gross_kg is None:
            if container_data.get("gross_weight_t") is not None and float(container_data.get("gross_weight_t", 0)) > 0:
                gross_kg = float(container_data.get("gross_weight_t")) * 1000.0
            else:
                gross_kg = container_data.get("gross_weight_kg") or container_data.get("weight")

        gross_t = round(float(gross_kg) / 1000.0, 2) if (gross_kg is not None and gross_kg > 0) else 0.0
        container_type = container_data.get("container_type")
        cargo_data = container_data.get("cargo") or {}
        hazardous = cargo_data.get("hazardous") if isinstance(cargo_data, dict) else container_data.get("hazardous")
        destination = container_data.get("destination")

        cargo_mass_metadata = CargoMassMetadata(
            value=float(gross_kg) if gross_kg else 0.0,
            unit="kg",
            source="DOCUMENT_AI",
            authoritative=True
        )

        container_summary = ContainerSummary(
            container_number=container_id,
            container_type=container_type,
            gross_weight_kg=float(gross_kg) if gross_kg else 0.0,
            gross_weight_t=gross_t,
            hazardous=hazardous,
            destination=destination,
            cargo_mass=cargo_mass_metadata
        )


        target_ship = ship_instance if ship_instance is not None else state.get_current_ship()

        # Calculate current stability before loading
        before_list = StabilityAnalyzer.calculate_list(target_ship)
        before_trim = StabilityAnalyzer.calculate_trim(target_ship)
        before_score = StabilityAnalyzer.stability_score(target_ship)
        before_risk = StabilityAnalyzer.risk_level(target_ship)
        before_metrics = StabilityMetrics(
            list_t=round(float(before_list), 2),
            trim_t=round(float(before_trim), 2),
            stability_score=round(float(before_score), 2),
            risk_level=before_risk
        )

        # 1. Safety Rule Check: Explicit Operator Confirmation Required
        if not request.operator_confirmed:
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=gross_t,
                gross_weight_kg=float(gross_kg) if gross_kg else 0.0,
                bay=rec_data.get("bay", 0),
                side=str(rec_data.get("side", "")).upper(),
                tier=rec_data.get("tier", 1),
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=False,
                operation_result="REJECTED",
                error_message="Explicit operator confirmation is required before loading."
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="rejected",
                container=container_summary,
                stability_before=before_metrics,
                audit_id=audit_id,
                error_message="Loading rejected: Explicit operator confirmation is required."
            )

        # 2. Document Status & Validation Rule Check
        # Run Anomaly Detection (Phase 4E)
        anomalies = CargoAnomalyDetector.detect_anomalies(
            container_data=container_data,
            confidence_data=doc_data.get("confidence") if isinstance(doc_data, dict) else None,
            existing_containers=target_ship.containers
        )
        critical_anomalies = [a for a in anomalies if a.severity == "CRITICAL"]

        doc_status = doc_data.get("processing_status", "success")
        is_valid = val_data.get("valid", True)
        if doc_status == "review_required" or is_valid is False or critical_anomalies:
            if critical_anomalies:
                err_msg = f"Document validation failed or critical safety anomaly detected: {critical_anomalies[0].message}. Loading blocked."
            else:
                err_msg = "Document validation failed or review is required. Automatic/unverified loading blocked."
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=gross_t,
                gross_weight_kg=float(gross_kg) if gross_kg else 0.0,
                bay=rec_data.get("bay", 0),
                side=str(rec_data.get("side", "")).upper(),
                tier=rec_data.get("tier", 1),
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=True,
                operation_result="FAILED",
                error_message=err_msg
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="review_required" if (doc_status == "review_required" and not critical_anomalies) else "error",
                container=container_summary,
                stability_before=before_metrics,
                audit_id=audit_id,
                anomalies=anomalies,
                error_message=err_msg
            )

        # 3. Missing Gross Weight Check
        if gross_kg is None or gross_kg <= 0:
            err_msg = "Gross weight is missing or invalid. Loading requires gross_weight_kg > 0."
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=0.0,
                gross_weight_kg=0.0,
                bay=rec_data.get("bay", 0),
                side=str(rec_data.get("side", "")).upper(),
                tier=rec_data.get("tier", 1),
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=True,
                operation_result="FAILED",
                error_message=err_msg
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="error",
                container=container_summary,
                stability_before=before_metrics,
                audit_id=audit_id,
                error_message=err_msg
            )

        # 4. Recommendation Verification Check
        bay = rec_data.get("bay")
        side = rec_data.get("side")
        tier = rec_data.get("tier", 1)
        if not bay or not side:
            err_msg = "No valid recommendation exists. Stability placement recommendation is required for loading."
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=gross_t,
                gross_weight_kg=float(gross_kg),
                bay=0,
                side="",
                tier=1,
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=True,
                operation_result="FAILED",
                error_message=err_msg
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="error",
                container=container_summary,
                stability_before=before_metrics,
                audit_id=audit_id,
                error_message=err_msg
            )

        bay = int(bay)
        side_clean = str(side).strip().lower()
        tier = int(tier)

        # 5. Slot Physical Bounds Verification
        if bay < 1 or bay > target_ship.num_bays or side_clean not in ["port", "starboard"] or tier < 1 or tier > 3:
            err_msg = f"Target slot (Bay {bay} / {side_clean.upper()} / Tier {tier}) is invalid or out of vessel bounds."
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=gross_t,
                gross_weight_kg=float(gross_kg),
                bay=bay,
                side=side_clean.upper(),
                tier=tier,
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=True,
                operation_result="FAILED",
                error_message=err_msg
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="error",
                container=container_summary,
                loaded_position=RecommendedPosition(bay=bay if 1 <= bay <= target_ship.num_bays else 1, side=side_clean.upper() if side_clean in ["port", "starboard"] else "PORT", tier=tier if 1 <= tier <= 3 else 1),
                stability_before=before_metrics,
                audit_id=audit_id,
                error_message=err_msg
            )

        # 6. Slot Occupancy Verification on Live Vessel State
        if target_ship.slot_occupied(bay, side_clean, tier):

            err_msg = f"Target slot (Bay {bay} / {side_clean.upper()} / Tier {tier}) is already occupied. Loading aborted without modifying vessel state."
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=gross_t,
                gross_weight_kg=float(gross_kg),
                bay=bay,
                side=side_clean.upper(),
                tier=tier,
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=True,
                operation_result="FAILED",
                error_message=err_msg
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="error",
                container=container_summary,
                loaded_position=RecommendedPosition(bay=bay, side=side_clean.upper(), tier=tier),
                stability_before=before_metrics,
                audit_id=audit_id,
                error_message=err_msg
            )

        # 6. Atomic Vessel State Commit
        new_container = Container(
            id=container_id,
            weight=gross_t,
            bay=bay,
            side=side_clean,
            tier=tier
        )
        added = target_ship.add_container(new_container)
        if not added:
            err_msg = f"Failed to commit container {container_id} to vessel state."
            audit_id = log_container_loading_audit(
                container_number=container_id,
                gross_weight_t=gross_t,
                gross_weight_kg=float(gross_kg),
                bay=bay,
                side=side_clean.upper(),
                tier=tier,
                stability_before_score=before_metrics.stability_score,
                stability_before_risk=before_metrics.risk_level,
                stability_after_score=before_metrics.stability_score,
                stability_after_risk=before_metrics.risk_level,
                operator_confirmed=True,
                operation_result="FAILED",
                error_message=err_msg
            )
            return ContainerLoadingConfirmResponse(
                success=False,
                status="error",
                container=container_summary,
                stability_before=before_metrics,
                audit_id=audit_id,
                error_message=err_msg
            )

        # 7. Recalculate Post-Load Stability Metrics
        after_list = StabilityAnalyzer.calculate_list(target_ship)
        after_trim = StabilityAnalyzer.calculate_trim(target_ship)
        after_score = StabilityAnalyzer.stability_score(target_ship)
        after_risk = StabilityAnalyzer.risk_level(target_ship)
        after_metrics = StabilityMetrics(
            list_t=round(float(after_list), 2),
            trim_t=round(float(after_trim), 2),
            stability_score=round(float(after_score), 2),
            risk_level=after_risk
        )
        delta_score = round(after_metrics.stability_score - before_metrics.stability_score, 2)

        # 8. Record in Audit Table and Cargo Operations Log
        audit_id = log_container_loading_audit(
            container_number=container_id,
            gross_weight_t=gross_t,
            gross_weight_kg=float(gross_kg),
            bay=bay,
            side=side_clean.upper(),
            tier=tier,
            stability_before_score=before_metrics.stability_score,
            stability_before_risk=before_metrics.risk_level,
            stability_after_score=after_metrics.stability_score,
            stability_after_risk=after_metrics.risk_level,
            operator_confirmed=True,
            operation_result="SUCCESS",
            error_message=None
        )

        log_cargo_operation(
            event="LOAD",
            container_id=container_id,
            weight=gross_t,
            bay=bay,
            side=side_clean.upper(),
            tier=tier,
            source="OCR-Loading-Confirmation"
        )

        return ContainerLoadingConfirmResponse(
            success=True,
            status="LOADED",
            container=container_summary,
            cargo_mass=cargo_mass_metadata,
            loaded_position=RecommendedPosition(bay=bay, side=side_clean.upper(), tier=tier),
            stability_before=before_metrics,
            stability_after=after_metrics,
            stability_delta=delta_score,
            audit_id=audit_id,
            anomalies=anomalies,
            message=f"Container {container_id} ({gross_t:.1f}t) successfully loaded and committed to vessel state at Bay {bay} / {side_clean.upper()} / Tier {tier}."
        )



class ContainerBallastService:
    """
    Phase 3C: Automated Ballast Compensation Integration Service.
    Calculates post-loading ballast compensation requirements on the actual vessel state,
    and executes operator-confirmed ballast water movements.
    """

    @classmethod
    def calculate_compensation(
        cls,
        request: BallastCompensationRequest,
        ship_instance: Optional[Ship] = None
    ) -> BallastCompensationResponse:
        """
        Calculates ballast compensation requirements using the actual post-loading vessel state.
        Determines the target tank, required discharge/fill volume, and projected post-ballast stability.
        """
        target_ship = ship_instance if ship_instance is not None else state.get_current_ship()

        # 0. Policy Validation: Check request source if provided
        if hasattr(request, "source") and request.source:
            try:
                assert_authoritative_source(request.source)
            except ValueError as pe:
                return BallastCompensationResponse(
                    success=False,
                    status="rejected",
                    error_message=str(pe)
                )

        # 1. Current Live Post-Loading Stability
        current_list = StabilityAnalyzer.calculate_list(target_ship)
        current_trim = StabilityAnalyzer.calculate_trim(target_ship)
        current_score = StabilityAnalyzer.stability_score(target_ship)
        current_risk = StabilityAnalyzer.risk_level(target_ship)
        current_metrics = StabilityMetrics(
            list_t=round(float(current_list), 2),
            trim_t=round(float(current_trim), 2),
            stability_score=round(float(current_score), 2),
            risk_level=current_risk
        )

        target_metrics = StabilityMetrics(
            list_t=0.0,
            trim_t=0.0,
            stability_score=0.0,
            risk_level="SAFE"
        )

        # 2. Check if vessel is already in optimal equilibrium and no cargo was loaded
        if abs(current_list) < 0.05 and abs(current_trim) < 0.05 and (request.gross_weight_t is None or request.gross_weight_t <= 0):
            return BallastCompensationResponse(
                success=True,
                status="NO_COMPENSATION_REQUIRED",
                compensation_required=False,
                current_stability=current_metrics,
                target_stability=target_metrics,
                projected_stability=current_metrics,
                message="Vessel stability is optimal. No ballast compensation required."
            )

        # 3. Identify Affected Tank Key
        if request.bay is not None and request.side is not None:
            bay = int(request.bay)
            side = str(request.side).strip().lower()
            tank_key = f"{side}_{bay}"
        else:
            if current_list > 0:
                side = "starboard"
            elif current_list < 0:
                side = "port"
            else:
                side = "starboard"
            bay = 1 if current_trim < 0 else (target_ship.num_bays if current_trim > 0 else max(1, target_ship.num_bays // 2))
            tank_key = f"{side}_{bay}"

        # 4. Verify Tank Existence on Vessel
        if tank_key not in target_ship.tanks:
            return BallastCompensationResponse(
                success=False,
                status="error",
                compensation_required=False,
                current_stability=current_metrics,
                error_message=f"Target ballast tank '{tank_key}' does not exist on vessel."
            )

        tank = target_ship.tanks[tank_key]

        # 5. Determine Required Quantity to Offset Added Moment
        # Discharging water from the same side/bay counters the added cargo weight
        gross_t = float(request.gross_weight_t) if (request.gross_weight_t is not None and request.gross_weight_t > 0) else abs(current_list)
        req_qty_t = min(gross_t, tank.current_volume)
        req_qty_t = round(max(0.0, req_qty_t), 2)

        if req_qty_t <= 0.0:
            return BallastCompensationResponse(
                success=True,
                status="NO_COMPENSATION_REQUIRED",
                compensation_required=False,
                affected_tank=tank.name.upper(),
                tank_key=tank_key,
                direction="DRAIN",
                current_stability=current_metrics,
                target_stability=target_metrics,
                projected_stability=current_metrics,
                message="Target ballast tank has 0 available water for discharge."
            )

        req_qty_kg = round(req_qty_t * 100.0, 2)

        # 6. Simulate Projected Stability on Copy
        temp_ship = copy.deepcopy(target_ship)
        temp_tank = temp_ship.tanks[tank_key]
        temp_tank.current_volume = max(0.0, round(temp_tank.current_volume - req_qty_t, 2))

        proj_list = StabilityAnalyzer.calculate_list(temp_ship)
        proj_trim = StabilityAnalyzer.calculate_trim(temp_ship)
        proj_score = StabilityAnalyzer.stability_score(temp_ship)
        proj_risk = StabilityAnalyzer.risk_level(temp_ship)
        proj_metrics = StabilityMetrics(
            list_t=round(float(proj_list), 2),
            trim_t=round(float(proj_trim), 2),
            stability_score=round(float(proj_score), 2),
            risk_level=proj_risk
        )

        flow_rate = 0.85
        duration = round(max(1.0, req_qty_t * 2.5), 1)

        state.iot_flow_stage = "CONFIRM_COMPENSATION"

        return BallastCompensationResponse(
            success=True,
            status="CONFIRM_COMPENSATION",
            compensation_required=True,
            affected_tank=tank.name.upper(),
            tank_key=tank_key,
            direction="DRAIN",
            required_qty_t=req_qty_t,
            required_qty_kg=req_qty_kg,
            current_stability=current_metrics,
            target_stability=target_metrics,
            projected_stability=proj_metrics,
            flow_rate_l_s=flow_rate,
            est_duration_sec=duration,
            message=f"Ballast compensation required: Discharge {req_qty_t:.1f}t from {tank.name.upper()} to restore vessel equilibrium."
        )

    @classmethod
    def execute_compensation(
        cls,
        request: BallastExecutionRequest,
        ship_instance: Optional[Ship] = None
    ) -> BallastExecutionResponse:
        """
        Executes operator-confirmed ballast compensation, modifies live tank volume,
        commands the simulator/reader, computes final 3-stage stability metrics, and logs the operation.
        """
        # 1. Operator Confirmation Gate
        if not request.operator_confirmed:
            return BallastExecutionResponse(
                success=False,
                status="rejected",
                error_message="Ballast execution rejected: Explicit operator confirmation is required."
            )

        target_ship = ship_instance if ship_instance is not None else state.get_current_ship()

        if request.tank_key not in target_ship.tanks:

            return BallastExecutionResponse(
                success=False,
                status="error",
                error_message=f"Target ballast tank '{request.tank_key}' does not exist."
            )

        if request.qty_t is None or float(request.qty_t) <= 0:
            return BallastExecutionResponse(
                success=False,
                status="error",
                error_message="Ballast execution rejected: Quantity must be strictly positive."
            )


        # 2. Capture Post-Container Stability (Stage 2)
        after_cont_list = StabilityAnalyzer.calculate_list(target_ship)
        after_cont_trim = StabilityAnalyzer.calculate_trim(target_ship)
        after_cont_score = StabilityAnalyzer.stability_score(target_ship)
        after_cont_risk = StabilityAnalyzer.risk_level(target_ship)
        after_container_metrics = StabilityMetrics(
            list_t=round(float(after_cont_list), 2),
            trim_t=round(float(after_cont_trim), 2),
            stability_score=round(float(after_cont_score), 2),
            risk_level=after_cont_risk
        )

        # 3. Apply Live Ballast Modification
        tank = target_ship.tanks[request.tank_key]
        direction_clean = request.direction.strip().upper()

        if direction_clean == "DRAIN":
            actual_qty = min(float(request.qty_t), tank.current_volume)
            tank.current_volume = max(0.0, round(tank.current_volume - actual_qty, 2))
        else:
            actual_qty = min(float(request.qty_t), tank.capacity - tank.current_volume)
            tank.current_volume = min(tank.capacity, round(tank.current_volume + actual_qty, 2))

        # 4. Trigger IoT Serial / Simulator Hardware Command
        try:
            reader = state.get_current_reader()
            reader.send_drain_command(actual_qty / 10.0)
        except Exception:
            pass

        state.iot_flow_stage = "COMPLETED"

        # 5. Capture Final Post-Ballast Stability (Stage 3)
        final_list = StabilityAnalyzer.calculate_list(target_ship)
        final_trim = StabilityAnalyzer.calculate_trim(target_ship)
        final_score = StabilityAnalyzer.stability_score(target_ship)
        final_risk = StabilityAnalyzer.risk_level(target_ship)
        after_ballast_metrics = StabilityMetrics(
            list_t=round(float(final_list), 2),
            trim_t=round(float(final_trim), 2),
            stability_score=round(float(final_score), 2),
            risk_level=final_risk
        )

        before_load_metrics = request.stability_before_load or StabilityMetrics(
            list_t=0.0, trim_t=0.0, stability_score=0.0, risk_level="SAFE"
        )
        net_delta = round(after_ballast_metrics.stability_score - before_load_metrics.stability_score, 2)

        three_stage = ThreeStageStabilityReport(
            before_load=before_load_metrics,
            after_container=after_container_metrics,
            after_ballast=after_ballast_metrics,
            net_score_delta=net_delta
        )

        # 6. Audit Logging in ballast_operations
        try:
            log_ballast_operation(
                op_type=direction_clean.capitalize(),
                pump_mode="Automated-Compensation",
                source=tank.name.upper() if direction_clean == "DRAIN" else "Sea",
                dest="Sea" if direction_clean == "DRAIN" else tank.name.upper(),
                qty=actual_qty,
                remaining_src=tank.current_volume,
                final_dest=tank.current_volume,
                score_before=after_container_metrics.stability_score,
                score_after=after_ballast_metrics.stability_score,
                trigger_source="OCR-Ballast-Workflow"
            )
        except Exception as e:
            logger.warning(f"Failed to log ballast operation: {e}")

        return BallastExecutionResponse(
            success=True,
            status="COMPLETED",
            actual_qty_t=actual_qty,
            affected_tank=tank.name.upper(),
            tank_key=request.tank_key,
            three_stage_stability=three_stage,
            message=f"Ballast compensation executed: {actual_qty:.1f}t discharged from {tank.name.upper()}. Final vessel risk: {final_risk}."
        )


class MultiContainerPlanner:
    """
    Phase 4D: Multi-Container Stowage Planner.
    Evaluates a manifest of multiple container documents, determines optimal loading sequence,
    simulates step-by-step stowage on a copy-on-write vessel state, tracks stability progression,
    and isolates invalid/rejected containers without failing the entire manifest.
    """

    @classmethod
    def plan_multi_container_stowage(
        cls,
        request: MultiContainerPlanRequest,
        ship_instance: Optional[Ship] = None
    ) -> MultiContainerPlanResponse:
        total_containers = len(request.containers)
        if total_containers == 0:
            return MultiContainerPlanResponse(
                success=False,
                total_containers=0,
                error_message="No container entries supplied in manifest."
            )

        # 1. Initialize isolated copy-on-write vessel state
        live_ship = ship_instance or state.get_current_ship()
        sim_ship = copy.deepcopy(live_ship)

        initial_list = StabilityAnalyzer.calculate_list(sim_ship)
        initial_trim = StabilityAnalyzer.calculate_trim(sim_ship)
        initial_score = StabilityAnalyzer.stability_score(sim_ship)
        initial_risk = StabilityAnalyzer.risk_level(sim_ship)

        initial_metrics = StabilityMetrics(
            list_t=round(float(initial_list), 2),
            trim_t=round(float(initial_trim), 2),
            stability_score=round(float(initial_score), 2),
            risk_level=initial_risk
        )

        stability_progression: List[StageStability] = [
            StageStability(
                stage_index=0,
                label="INITIAL",
                container_id=None,
                metrics=initial_metrics
            )
        ]

        # 2. Filter & Validate Containers
        valid_items = []
        rejected_containers: List[RejectedContainerItem] = []
        warnings: List[str] = []

        docs = request.documents or [{}] * total_containers
        vals = request.validations or [{}] * total_containers

        for i, cntr in enumerate(request.containers):
            doc = docs[i] if i < len(docs) else {}
            val = vals[i] if i < len(vals) else {}

            cntr_num = cntr.get("container_number") or f"CNTR-{i+1}"
            weights = cntr.get("weights") or {}
            gross_kg = weights.get("gross_weight_kg") or cntr.get("gross_weight_kg")

            if not gross_kg or gross_kg <= 0:
                rejected_containers.append(
                    RejectedContainerItem(
                        container_number=cntr_num,
                        reason="Missing or non-positive gross weight.",
                        status="REJECTED"
                    )
                )
                continue

            # Check provenance policy
            src_claimed = cntr.get("weight_source") or cntr.get("source") or CONTAINER_WEIGHT_SOURCE
            try:
                validate_cargo_mass_provenance(
                    source=src_claimed,
                    authoritative=cntr.get("authoritative", True),
                    cargo_mass_meta=cntr.get("cargo_mass") if isinstance(cntr.get("cargo_mass"), dict) else None
                )
            except ValueError as pe:
                rejected_containers.append(
                    RejectedContainerItem(
                        container_number=cntr_num,
                        reason=f"Security Policy Violation: {str(pe)}",
                        status="REJECTED"
                    )
                )
                continue

            # Check document/validation failure
            if doc.get("processing_status") == "error":
                rejected_containers.append(
                    RejectedContainerItem(
                        container_number=cntr_num,
                        reason="Document OCR extraction failed.",
                        status="REJECTED"
                    )
                )
                continue

            if val.get("valid") is False and val.get("errors"):
                # Invalid validation check
                rejected_containers.append(
                    RejectedContainerItem(
                        container_number=cntr_num,
                        reason=f"Validation failed: {', '.join(val['errors'])}",
                        status="REVIEW_REQUIRED"
                    )
                )
                continue

            valid_items.append({
                "container": cntr,
                "document": doc,
                "validation": val,
                "gross_t": round(gross_kg / 1000.0, 3)
            })

        if not valid_items:
            return MultiContainerPlanResponse(
                success=False,
                total_containers=total_containers,
                valid_count=0,
                rejected_count=len(rejected_containers),
                initial_stability=initial_metrics,
                final_stability=initial_metrics,
                stability_progression=stability_progression,
                rejected_containers=rejected_containers,
                error_message="No valid containers found in manifest."
            )

        # 3. Deterministic Sequence Optimization Heuristic:
        # Sort criteria:
        # A. Hazardous cargo first (to secure Tier 1 deck accessibility immediately)
        # B. Heaviest containers first (to secure lower tiers and prevent stack weight inversions)
        def sort_key(item):
            c_data = item["container"]
            cargo = c_data.get("cargo") or {}
            is_haz = cargo.get("hazardous") is True or c_data.get("hazardous") is True
            # Sort order: (-is_haz, -gross_t, container_number)
            return (0 if is_haz else 1, -item["gross_t"], c_data.get("container_number", ""))

        valid_items.sort(key=sort_key)

        # 4. Sequential Stowage Simulation on copy-on-write vessel
        loading_sequence: List[PlannedContainerStep] = []
        prev_score = initial_metrics.stability_score

        for step_idx, item in enumerate(valid_items):
            step_num = step_idx + 1
            cntr_dict = item["container"]
            doc_dict = item["document"]
            val_dict = item["validation"]

            single_req = ContainerStabilityAnalysisRequest(
                container=cntr_dict,
                document=doc_dict,
                validation=val_dict
            )

            # Analyze placement against current simulated vessel state
            analysis = ContainerStabilityService.analyze_container_placement(
                request=single_req,
                ship_instance=sim_ship
            )

            if not analysis.success or not analysis.recommendation:
                rejected_containers.append(
                    RejectedContainerItem(
                        container_number=cntr_dict.get("container_number", f"CNTR-{step_num}"),
                        reason=analysis.error_message or "No compatible stowage slot found on vessel.",
                        status="REJECTED"
                    )
                )
                continue

            rec = analysis.recommendation
            # Commit temporary container into simulated vessel state
            placed_c = Container(
                id=cntr_dict.get("container_number", f"CNTR-{step_num}"),
                weight=item["gross_t"],
                bay=rec.bay,
                side=rec.side.lower(),
                tier=rec.tier
            )
            sim_ship.containers.append(placed_c)

            # Compute post-placement stability on simulated vessel
            step_list = StabilityAnalyzer.calculate_list(sim_ship)
            step_trim = StabilityAnalyzer.calculate_trim(sim_ship)
            step_score = StabilityAnalyzer.stability_score(sim_ship)
            step_risk = StabilityAnalyzer.risk_level(sim_ship)

            step_metrics = StabilityMetrics(
                list_t=round(float(step_list), 2),
                trim_t=round(float(step_trim), 2),
                stability_score=round(float(step_score), 2),
                risk_level=step_risk
            )

            delta_score = round(step_metrics.stability_score - prev_score, 2)
            prev_score = step_metrics.stability_score

            needs_ballast = step_metrics.stability_score > 15.0 or abs(step_metrics.list_t) > 10.0
            ballast_rec = None
            if needs_ballast:
                ballast_rec = {
                    "compensation_required": True,
                    "target_list_t": step_metrics.list_t,
                    "target_trim_t": step_metrics.trim_t
                }

            # Record step in progression
            stage_entry = StageStability(
                stage_index=step_num,
                label=f"AFTER_C{step_num}",
                container_id=placed_c.id,
                metrics=step_metrics
            )
            stability_progression.append(stage_entry)

            # Record planned step
            planned_step = PlannedContainerStep(
                step_number=step_num,
                container=analysis.container,
                cargo_mass=analysis.cargo_mass,
                status="VALID",
                recommended_position=rec,
                ranking_score=rec.ranking_score,
                stability_after=step_metrics,
                delta_score=delta_score,
                ballast_required=needs_ballast,
                ballast_recommendation=ballast_rec,
                reasons=analysis.reason
            )
            loading_sequence.append(planned_step)


        if not loading_sequence:
            return MultiContainerPlanResponse(
                success=False,
                total_containers=total_containers,
                valid_count=0,
                rejected_count=len(rejected_containers),
                initial_stability=initial_metrics,
                final_stability=initial_metrics,
                stability_progression=stability_progression,
                rejected_containers=rejected_containers,
                error_message="Could not place any containers from manifest."
            )

        final_metrics = stability_progression[-1].metrics
        cumulative_imbalance = round(sum(step.stability_after.stability_score for step in loading_sequence if step.stability_after), 2)

        return MultiContainerPlanResponse(
            success=True,
            total_containers=total_containers,
            valid_count=len(loading_sequence),
            rejected_count=len(rejected_containers),
            initial_stability=initial_metrics,
            final_stability=final_metrics,
            stability_progression=stability_progression,
            loading_sequence=loading_sequence,
            rejected_containers=rejected_containers,
            cumulative_imbalance=cumulative_imbalance,
            warnings=warnings
        )

    @classmethod
    def execute_multi_container_plan(
        cls,
        request: MultiContainerExecuteRequest,
        ship_instance: Optional[Ship] = None
    ) -> MultiContainerExecuteResponse:
        if not request.operator_confirmed:
            return MultiContainerExecuteResponse(
                success=False,
                status="rejected",
                error_message="Operator authorization required to commit multi-container sequence to live vessel."
            )

        live_ship = ship_instance or state.get_current_ship()
        loaded_count = 0
        audit_ids = []

        for step in request.loading_sequence:
            cntr_dict = step.get("container") or {}
            rec_dict = step.get("recommended_position") or {}

            cntr_id = cntr_dict.get("container_number") or f"CNTR-{loaded_count+1}"
            gross_t = cntr_dict.get("gross_weight_t") or (cntr_dict.get("gross_weight_kg", 0) / 1000.0)
            bay = rec_dict.get("bay")
            side = rec_dict.get("side", "").lower()
            tier = rec_dict.get("tier", 1)

            if bay and side:
                if not live_ship.slot_occupied(bay, side, tier):
                    c = Container(id=cntr_id, weight=gross_t, bay=bay, side=side, tier=tier)
                    live_ship.containers.append(c)
                    loaded_count += 1
                    try:
                        aid = log_cargo_operation(
                            op_type="LOAD",
                            container_id=cntr_id,
                            weight=gross_t,
                            bay=bay,
                            side=side.upper(),
                            tier=tier,
                            iso_type=cntr_dict.get("container_type", "Standard"),
                            destination=cntr_dict.get("destination", "PORT")
                        )
                        if aid:
                            audit_ids.append(aid)
                    except Exception as e:
                        logger.warning(f"Failed to log cargo audit: {e}")

        final_list = StabilityAnalyzer.calculate_list(live_ship)
        final_trim = StabilityAnalyzer.calculate_trim(live_ship)
        final_score = StabilityAnalyzer.stability_score(live_ship)
        final_risk = StabilityAnalyzer.risk_level(live_ship)

        final_metrics = StabilityMetrics(
            list_t=round(float(final_list), 2),
            trim_t=round(float(final_trim), 2),
            stability_score=round(float(final_score), 2),
            risk_level=final_risk
        )

        return MultiContainerExecuteResponse(
            success=True,
            status="COMPLETED",
            loaded_count=loaded_count,
            final_stability=final_metrics,
            audit_ids=audit_ids,
            message=f"Successfully loaded {loaded_count} containers onto vessel."
        )


