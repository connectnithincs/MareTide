"""
Domain Validation Module for Container Document Intelligence.
Implements ISO 6346 Check Digit verification, weight equilibrium equations, and physical domain constraints.
"""

from typing import Tuple, List, Optional
from .config import (
    ISO_6346_LETTER_MAP, MIN_TARE_KG, MAX_TARE_KG,
    MIN_GROSS_KG, MAX_GROSS_KG, WEIGHT_TOLERANCE_KG,
    MIN_LENGTH_FT, MAX_LENGTH_FT, MIN_HEIGHT_FT, MAX_HEIGHT_FT
)
from .models import ContainerDetails, ValidationResult, CargoAnomaly
from .anomaly_detector import CargoAnomalyDetector


class DomainValidator:
    """
    Validates extracted container entities against international maritime standards and physics.
    """

    @classmethod
    def validate_container(
        cls, 
        container: ContainerDetails,
        confidence_data: Optional[dict] = None,
        existing_containers: Optional[List[Any]] = None
    ) -> ValidationResult:
        warnings: List[str] = []
        errors: List[str] = []

        # 1. Container Number Validation
        if not container.container_number:
            warnings.append("Container number could not be extracted.")
            iso_valid = None
        else:
            iso_valid, iso_warn = cls.validate_iso_6346(container.container_number)
            if iso_warn:
                warnings.append(iso_warn)

        # 2. Container Type Validation
        if not container.container_type:
            warnings.append("Container type could not be confidently identified.")

        # 3. Weight Equilibrium and Physical Sanity
        weight_valid, weight_warns, weight_errs = cls.validate_weights(container.weights)
        warnings.extend(weight_warns)
        errors.extend(weight_errs)

        if container.weights.gross_weight_kg is None:
            warnings.append("Gross weight could not be extracted.")

        # 4. Dimensions Sanity Checks
        dim_warns = cls.validate_dimensions(container.dimensions)
        warnings.extend(dim_warns)

        # 5. Hazardous Cargo Awareness
        if container.cargo and container.cargo.hazardous:
            haz_info = []
            if container.cargo.un_number:
                haz_info.append(container.cargo.un_number)
            if container.cargo.imdg_class:
                haz_info.append(container.cargo.imdg_class)
            haz_str = f" ({', '.join(haz_info)})" if haz_info else ""
            warnings.append(f"Hazardous cargo / dangerous goods detected{haz_str}. Requires stowage segregation.")

        # 6. Structured Anomaly Detection (Phase 4E)
        cntr_dict = container.model_dump()
        anomalies = CargoAnomalyDetector.detect_anomalies(
            container_data=cntr_dict,
            confidence_data=confidence_data,
            existing_containers=existing_containers
        )

        # Any CRITICAL anomaly blocks overall validation validity
        has_critical_anomaly = any(a.severity == "CRITICAL" for a in anomalies)

        # Overall validity: Valid if no fatal errors, no critical anomalies, and has core identifiers
        has_primary_identifiers = bool(container.container_number or container.weights.gross_weight_kg)
        is_overall_valid = (len(errors) == 0) and (not has_critical_anomaly) and has_primary_identifiers

        return ValidationResult(
            valid=is_overall_valid,
            iso_6346_valid=iso_valid,
            weight_balance_valid=weight_valid,
            warnings=warnings,
            errors=errors,
            anomalies=anomalies
        )

    @classmethod
    def validate_iso_6346(cls, container_number: Optional[str]) -> Tuple[Optional[bool], Optional[str]]:
        """
        Validates ISO 6346 Check Digit using weighted modulo 11 algorithm.
        Returns (is_valid, warning_message).
        """
        if not container_number:
            return None, None

        clean_num = container_number.replace(" ", "").replace("-", "").upper()

        if len(clean_num) != 11:
            return False, f"Container number check digit appears invalid: length is {len(clean_num)} characters (expected 11)."

        letters = clean_num[:4]
        digits = clean_num[4:]

        if not (letters.isalpha() and digits.isdigit()):
            return False, f"Container number '{container_number}' does not conform to 4-letter + 7-digit ISO format."

        category_char = letters[3]
        if category_char not in ['U', 'J', 'Z']:
            category_warning = f"Non-standard equipment category identifier '{category_char}' (expected U, J, or Z)."
        else:
            category_warning = None

        total = 0
        for i in range(10):
            char = clean_num[i]
            if char.isalpha():
                val = ISO_6346_LETTER_MAP.get(char, 0)
            else:
                val = int(char)
            total += val * (2 ** i)

        remainder = total % 11
        expected_check_digit = 0 if remainder == 10 else remainder
        actual_check_digit = int(clean_num[10])

        if expected_check_digit == actual_check_digit:
            if category_warning:
                return True, category_warning
            return True, None
        else:
            return False, "Container number check digit appears invalid."

    @classmethod
    def validate_weights(cls, weights) -> Tuple[Optional[bool], List[str], List[str]]:
        warnings: List[str] = []
        errors: List[str] = []

        tare = weights.tare_weight_kg
        cargo = weights.cargo_weight_kg
        gross = weights.gross_weight_kg

        # Check physical bounds
        if tare is not None:
            if tare < MIN_TARE_KG or tare > MAX_TARE_KG:
                warnings.append(f"Tare weight {tare:.1f} kg is outside typical range ({MIN_TARE_KG:.0f} - {MAX_TARE_KG:.0f} kg).")

        if gross is not None:
            if gross < MIN_GROSS_KG:
                warnings.append(f"Gross weight {gross:.1f} kg is unusually low.")
            if gross > MAX_GROSS_KG:
                warnings.append(f"Gross weight {gross:.1f} kg exceeds standard ISO maximum rating ({MAX_GROSS_KG:.0f} kg).")

        # Check balance: Gross == Tare + Cargo
        if gross is not None and tare is not None and cargo is not None:
            expected_gross = tare + cargo
            discrepancy = abs(gross - expected_gross)
            if discrepancy <= WEIGHT_TOLERANCE_KG:
                return True, warnings, errors
            else:
                err_msg = (
                    f"GROSS_WEIGHT_INCONSISTENT: Expected gross {expected_gross:.1f} kg "
                    f"(Tare {tare:.1f} kg + Cargo {cargo:.1f} kg), extracted gross {gross:.1f} kg "
                    f"(difference: {discrepancy:.1f} kg exceeds tolerance)."
                )
                errors.append(err_msg)
                warnings.append(err_msg)
                return False, warnings, errors

        return None, warnings, errors

    @classmethod
    def validate_dimensions(cls, dims) -> List[str]:
        warnings: List[str] = []
        if dims.length_ft is not None:
            if dims.length_ft <= 0:
                warnings.append("Container length must be greater than 0.")
            elif dims.length_ft < MIN_LENGTH_FT or dims.length_ft > MAX_LENGTH_FT:
                warnings.append(f"Suspicious container length: {dims.length_ft:.1f} ft (typical range is {MIN_LENGTH_FT:.0f} - {MAX_LENGTH_FT:.0f} ft).")

        if dims.width_ft is not None:
            if dims.width_ft <= 0:
                warnings.append("Container width must be greater than 0.")
            elif dims.width_ft < 5.0 or dims.width_ft > 12.0:
                warnings.append(f"Suspicious container width: {dims.width_ft:.1f} ft.")

        if dims.height_ft is not None:
            if dims.height_ft <= 0:
                warnings.append("Container height must be greater than 0.")
            elif dims.height_ft < MIN_HEIGHT_FT or dims.height_ft > MAX_HEIGHT_FT:
                warnings.append(f"Suspicious container height: {dims.height_ft:.1f} ft (typical range is {MIN_HEIGHT_FT:.1f} - {MAX_HEIGHT_FT:.1f} ft).")

        return warnings
