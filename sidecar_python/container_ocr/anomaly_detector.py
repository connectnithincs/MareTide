"""
Cargo Data Anomaly & Safety Intelligence Engine (Phase 4E).
Detects discrepancies, physical impossibilities, duplicate stowage, and classification ambiguities.
Enforces non-silent reporting policy: never mutates raw values, only produces structured, actionable anomaly reports.
"""

from typing import List, Optional, Any, Dict
from .config import (
    MIN_TARE_KG, MAX_TARE_KG,
    MIN_GROSS_KG, MAX_GROSS_KG, WEIGHT_TOLERANCE_KG,
    MIN_LENGTH_FT, MAX_LENGTH_FT, MIN_HEIGHT_FT, MAX_HEIGHT_FT
)
from .models import CargoAnomaly


class CargoAnomalyDetector:
    """
    Evaluates container document data, physical boundaries, and vessel operational context
    to generate structured anomaly alerts categorized by severity (INFO, WARNING, CRITICAL).
    """

    @classmethod
    def detect_anomalies(
        cls,
        container_data: Dict[str, Any],
        confidence_data: Optional[Dict[str, Any]] = None,
        existing_containers: Optional[List[Any]] = None,
        active_planned_ids: Optional[List[str]] = None
    ) -> List[CargoAnomaly]:
        """
        Inspects container entity, confidence scores, and current ship cargo list.
        Returns a list of structured CargoAnomaly records.
        """
        anomalies: List[CargoAnomaly] = []

        container_number = container_data.get("container_number")
        container_type = container_data.get("container_type")
        weights = container_data.get("weights") or {}
        dims = container_data.get("dimensions") or {}
        cargo = container_data.get("cargo") or {}

        # -------------------------------------------------------------------------
        # 1. Missing Required Fields
        # -------------------------------------------------------------------------
        if not container_number:
            anomalies.append(
                CargoAnomaly(
                    field="container_number",
                    observed="None",
                    expected="11-character ISO 6346 identifier (e.g. MSCU1234567)",
                    severity="CRITICAL",
                    message="Mandatory container identification number is missing from document.",
                    action="Enter container number manually from physical door stencil."
                )
            )

        gross_kg = weights.get("gross_weight_kg")
        if gross_kg is None:
            # Check fallback top-level weight
            gross_kg = container_data.get("gross_weight_kg") or container_data.get("weight")

        if gross_kg is None:
            anomalies.append(
                CargoAnomaly(
                    field="gross_weight",
                    observed="None",
                    expected="Gross weight > 0 kg (SOLAS VGM mandatory)",
                    severity="CRITICAL",
                    message="Mandatory Verified Gross Mass (VGM) is missing from document.",
                    action="Acquire certified weighbridge ticket or verify bill of lading before loading."
                )
            )
        elif gross_kg <= 0:
            anomalies.append(
                CargoAnomaly(
                    field="gross_weight",
                    observed=gross_kg,
                    expected="Gross weight > 0 kg",
                    severity="CRITICAL",
                    message=f"Gross weight ({gross_kg} kg) must be strictly positive.",
                    action="Re-weigh container or correct OCR misreading."
                )
            )

        # -------------------------------------------------------------------------
        # 2. VGM Equilibrium Mismatch: tare + cargo != gross
        # -------------------------------------------------------------------------
        tare_kg = weights.get("tare_weight_kg")
        cargo_kg = weights.get("cargo_weight_kg")

        if gross_kg is not None and tare_kg is not None and cargo_kg is not None:
            expected_sum = tare_kg + cargo_kg
            diff = abs(gross_kg - expected_sum)
            if diff > WEIGHT_TOLERANCE_KG:
                anomalies.append(
                    CargoAnomaly(
                        field="gross_weight",
                        observed=gross_kg,
                        expected=f"tare ({tare_kg:.1f} kg) + cargo ({cargo_kg:.1f} kg) = {expected_sum:.1f} kg (±{WEIGHT_TOLERANCE_KG}kg)",
                        severity="CRITICAL",
                        message=f"Gross weight ({gross_kg:.1f} kg) does not equal tare plus cargo weight (expected {expected_sum:.1f} kg, discrepancy {diff:.1f} kg).",
                        action="Review document before loading. Physical weighbridge verification required."
                    )
                )

        # -------------------------------------------------------------------------
        # 3. Suspicious Weight Bounds
        # -------------------------------------------------------------------------
        if gross_kg is not None and gross_kg > 0:
            if gross_kg < 1000.0:
                anomalies.append(
                    CargoAnomaly(
                        field="gross_weight",
                        observed=gross_kg,
                        expected="Gross weight >= 1,000 kg for intermodal freight",
                        severity="WARNING",
                        message=f"Gross weight ({gross_kg:.1f} kg) is unusually low for an intermodal container.",
                        action="Confirm if container is empty (tare only) or verify scale calibration."
                    )
                )
            elif gross_kg > 36000.0:
                anomalies.append(
                    CargoAnomaly(
                        field="gross_weight",
                        observed=gross_kg,
                        expected="Gross weight <= 36,000 kg (ISO Maximum Gross Rating)",
                        severity="CRITICAL",
                        message=f"Gross weight ({gross_kg:.1f} kg) exceeds maximum ISO structural rating (36,000 kg).",
                        action="Hold container for special breakbulk / heavy-lift engineering assessment."
                    )
                )
            elif gross_kg > MAX_GROSS_KG:  # e.g. > 32,500kg
                anomalies.append(
                    CargoAnomaly(
                        field="gross_weight",
                        observed=gross_kg,
                        expected=f"Gross weight <= {MAX_GROSS_KG:.0f} kg",
                        severity="WARNING",
                        message=f"Gross weight ({gross_kg:.1f} kg) is near maximum structural capacity.",
                        action="Ensure stowage on bottom tier (Tier 1) directly on tank top."
                    )
                )

        if tare_kg is not None:
            if tare_kg < MIN_TARE_KG or tare_kg > MAX_TARE_KG:
                anomalies.append(
                    CargoAnomaly(
                        field="tare_weight",
                        observed=tare_kg,
                        expected=f"Tare weight between {MIN_TARE_KG:.0f} kg and {MAX_TARE_KG:.0f} kg",
                        severity="WARNING",
                        message=f"Tare weight ({tare_kg:.1f} kg) is outside standard marine container norms.",
                        action="Verify tare weight on container CSC safety approval plate."
                    )
                )

        # -------------------------------------------------------------------------
        # 4. Impossible Dimensions
        # -------------------------------------------------------------------------
        len_ft = dims.get("length_ft")
        wid_ft = dims.get("width_ft")
        hgt_ft = dims.get("height_ft")

        if len_ft is not None:
            if len_ft <= 0:
                anomalies.append(
                    CargoAnomaly(
                        field="dimensions.length",
                        observed=len_ft,
                        expected="Length > 0 ft",
                        severity="CRITICAL",
                        message=f"Impossible container length ({len_ft} ft).",
                        action="Check OCR extraction or measure unit dimensions."
                    )
                )
            elif len_ft > 53.0:
                anomalies.append(
                    CargoAnomaly(
                        field="dimensions.length",
                        observed=len_ft,
                        expected="Length <= 53.0 ft (standard marine max is 45.0 ft)",
                        severity="CRITICAL",
                        message=f"Container length ({len_ft:.1f} ft) exceeds allowable vessel cell guide envelope.",
                        action="Reject cellular container stowage; reclassify for flat-rack/deck cargo."
                    )
                )
            elif len_ft < MIN_LENGTH_FT or len_ft > MAX_LENGTH_FT:
                anomalies.append(
                    CargoAnomaly(
                        field="dimensions.length",
                        observed=len_ft,
                        expected=f"Length between {MIN_LENGTH_FT:.0f} ft and {MAX_LENGTH_FT:.0f} ft",
                        severity="WARNING",
                        message=f"Non-standard container length ({len_ft:.1f} ft).",
                        action="Verify cell compatibility before assigning bay."
                    )
                )

        if wid_ft is not None:
            if wid_ft <= 0 or wid_ft > 12.0:
                anomalies.append(
                    CargoAnomaly(
                        field="dimensions.width",
                        observed=wid_ft,
                        expected="Standard container width ~8.0 ft (max 8.5 ft for pallet-wide)",
                        severity="CRITICAL" if (wid_ft <= 0 or wid_ft > 10.0) else "WARNING",
                        message=f"Impossible or out-of-gauge container width ({wid_ft:.1f} ft).",
                        action="Verify width with terminal spreader gauge."
                    )
                )

        if hgt_ft is not None:
            if hgt_ft <= 0 or hgt_ft > 13.0:
                anomalies.append(
                    CargoAnomaly(
                        field="dimensions.height",
                        observed=hgt_ft,
                        expected=f"Height between {MIN_HEIGHT_FT:.1f} ft and {MAX_HEIGHT_FT:.1f} ft",
                        severity="CRITICAL" if (hgt_ft <= 0 or hgt_ft > 11.0) else "WARNING",
                        message=f"Impossible or extreme container height ({hgt_ft:.1f} ft).",
                        action="Verify high-cube profile clearance."
                    )
                )

        # -------------------------------------------------------------------------
        # 5. Inconsistent Container Type vs Dimensions
        # -------------------------------------------------------------------------
        if container_type and len_ft is not None and len_ft > 0:
            clean_type = container_type.upper()
            if clean_type.startswith("20") and len_ft >= 35.0:
                anomalies.append(
                    CargoAnomaly(
                        field="container_type",
                        observed=f"Type '{container_type}' with length {len_ft:.1f} ft",
                        expected="20ft container type length ~20.0 ft",
                        severity="CRITICAL",
                        message=f"Container type '{container_type}' indicates a 20ft unit, but extracted length is {len_ft:.1f} ft.",
                        action="Reconcile type designation with physical container size."
                    )
                )
            elif (clean_type.startswith("40") or clean_type.startswith("45")) and len_ft <= 25.0:
                anomalies.append(
                    CargoAnomaly(
                        field="container_type",
                        observed=f"Type '{container_type}' with length {len_ft:.1f} ft",
                        expected="40ft/45ft container type length >= 40.0 ft",
                        severity="CRITICAL",
                        message=f"Container type '{container_type}' indicates a 40ft/45ft unit, but extracted length is {len_ft:.1f} ft.",
                        action="Reconcile type designation with physical container size."
                    )
                )

        # -------------------------------------------------------------------------
        # 6. Invalid ISO 6346 Container Number & Check Digit
        # -------------------------------------------------------------------------
        if container_number:
            from .validator import DomainValidator
            iso_valid, iso_warn = DomainValidator.validate_iso_6346(container_number)
            if iso_valid is False:
                clean_num = container_number.replace(" ", "").replace("-", "").upper()
                if len(clean_num) != 11:
                    anomalies.append(
                        CargoAnomaly(
                            field="container_number",
                            observed=container_number,
                            expected="11-character format: 4 letters + 6 digits + 1 check digit",
                            severity="WARNING",
                            message=f"Container number '{container_number}' has non-standard format/length ({len(clean_num)} characters).",
                            action="Verify container number against bill of lading and physical door stencil."
                        )
                    )
                else:
                    anomalies.append(
                        CargoAnomaly(
                            field="container_number",
                            observed=container_number,
                            expected="Valid ISO 6346 check digit (weighted modulo 11)",
                            severity="WARNING",
                            message=f"Container number '{container_number}' check digit verification failed.",
                            action="Check for potential OCR optical character substitution (e.g. 0 vs O, 1 vs I)."
                        )
                    )

        # -------------------------------------------------------------------------
        # 7. Conflicting OCR Values & Hazardous Classification Uncertainty
        # -------------------------------------------------------------------------
        is_hazardous = cargo.get("hazardous")
        un_num = cargo.get("un_number")
        imdg_class = cargo.get("imdg_class")

        if un_num and is_hazardous is False:
            anomalies.append(
                CargoAnomaly(
                    field="cargo.hazardous",
                    observed=f"hazardous=False with UN Number '{un_num}'",
                    expected="hazardous=True when UN substance code is present",
                    severity="CRITICAL",
                    message=f"Conflicting cargo classification: UN Number '{un_num}' present but marked non-hazardous.",
                    action="Reclassify cargo as hazardous and enforce IMDG segregation rules."
                )
            )
        elif is_hazardous is True and not un_num and not imdg_class:
            anomalies.append(
                CargoAnomaly(
                    field="cargo.imdg_class",
                    observed="hazardous=True (missing UN number and IMDG class)",
                    expected="IMDG Hazard Class 1-9 and 4-digit UN Number (e.g. UN 1993, Class 3)",
                    severity="WARNING",
                    message="Hazardous cargo flag is set, but specific IMDG class and UN number are not declared.",
                    action="Obtain Dangerous Goods Declaration (DGD) sheet from carrier."
                )
            )

        # -------------------------------------------------------------------------
        # 8. Unusually Low Extraction Confidence
        # -------------------------------------------------------------------------
        if confidence_data:
            if isinstance(confidence_data, dict):
                overall_conf = float(confidence_data.get("overall", 1.0))
                weight_conf = float(confidence_data.get("weights", 1.0))
            elif isinstance(confidence_data, (int, float)):
                overall_conf = float(confidence_data)
                weight_conf = float(confidence_data)
            else:
                overall_conf = 1.0
                weight_conf = 1.0

            if overall_conf < 0.75:
                anomalies.append(
                    CargoAnomaly(
                        field="confidence.overall",
                        observed=round(overall_conf, 3),
                        expected="Confidence >= 0.85",
                        severity="WARNING",
                        message=f"Overall OCR extraction confidence ({overall_conf*100:.1f}%) is below reliable threshold.",
                        action="Carefully verify extracted values against original slip image before approval."
                    )
                )

            if weight_conf < 0.70:
                anomalies.append(
                    CargoAnomaly(
                        field="confidence.weights",
                        observed=round(weight_conf, 3),
                        expected="Weight field confidence >= 0.80",
                        severity="WARNING",
                        message=f"Weight field OCR confidence ({weight_conf*100:.1f}%) is degraded.",
                        action="Confirm gross and tare weight numbers on original document."
                    )
                )


        # -------------------------------------------------------------------------
        # 9. Duplicate Container Number on Vessel & Active Operation
        # -------------------------------------------------------------------------
        if container_number and existing_containers:
            clean_target = container_number.replace(" ", "").replace("-", "").upper()
            duplicate_found = False
            for c in existing_containers:
                c_id = getattr(c, "id", None) or getattr(c, "container_number", None) or (c.get("id") if isinstance(c, dict) else None)
                if c_id:
                    clean_existing = str(c_id).replace(" ", "").replace("-", "").upper()
                    if clean_target == clean_existing:
                        duplicate_found = True
                        break

            if duplicate_found:
                anomalies.append(
                    CargoAnomaly(
                        field="container_number",
                        observed=container_number,
                        expected="Unique container identifier across vessel stowage",
                        severity="CRITICAL",
                        message=f"Container '{container_number}' is already stowed in an active slot on the vessel.",
                        action="Reject loading attempt; container is already loaded."
                    )
                )

        if container_number and active_planned_ids:
            clean_target = container_number.replace(" ", "").replace("-", "").upper()
            occurrences = sum(
                1 for p_id in active_planned_ids 
                if str(p_id).replace(" ", "").replace("-", "").upper() == clean_target
            )
            if occurrences > 1:
                anomalies.append(
                    CargoAnomaly(
                        field="container_number",
                        observed=f"'{container_number}' appears {occurrences} times in active plan",
                        expected="Single occurrence per container manifest",
                        severity="CRITICAL",
                        message=f"Duplicate container ID '{container_number}' detected in the active loading sequence.",
                        action="Remove redundant container entry from manifest queue."
                    )
                )

        # -------------------------------------------------------------------------
        # 10. Clean Document Informational Item
        # -------------------------------------------------------------------------
        if len(anomalies) == 0:
            anomalies.append(
                CargoAnomaly(
                    field="document",
                    observed="Verified",
                    expected="All physical and regulatory checks satisfied",
                    severity="INFO",
                    message="Document data passed all ISO, VGM, dimensional, and duplicate anomaly checks.",
                    action="Proceed to AI stability analysis and stowage recommendation."
                )
            )

        return anomalies
