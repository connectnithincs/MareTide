"""
Confidence Scoring Algorithm for Container Document Intelligence (Phase 1 & Phase 4A).
Calculates granular field confidence scores (container number, container type, iso type,
weights, dimensions, cargo, hazardous, destination, booking reference) and aggregates the overall score.
"""

from typing import Dict, Any
from .models import ConfidenceScores, ContainerDetails, ValidationResult


class ConfidenceScorer:
    """
    Computes rigorous confidence metrics based on OCR quality, parsing exactness, and domain validation.
    """

    # Field weights for overall confidence computation (giving high importance to critical fields)
    WEIGHTS_DISTRIBUTION = {
        "container_number": 0.35,
        "weights": 0.35,
        "container_type": 0.15,
        "dimensions": 0.05,
        "cargo": 0.05,
        "destination": 0.05
    }

    @classmethod
    def calculate_scores(
        cls,
        container: ContainerDetails,
        raw_confidences: Dict[str, float],
        validation: ValidationResult
    ) -> ConfidenceScores:
        """
        Calculates normalized confidence scores for all fields and aggregates the overall score.
        """
        # 1. Container Number Confidence
        cntr_conf = raw_confidences.get("container_number", 0.0)
        if container.container_number:
            if validation.iso_6346_valid is True:
                cntr_conf = max(cntr_conf, 0.98)
            elif validation.iso_6346_valid is False:
                cntr_conf = min(cntr_conf if cntr_conf > 0 else 0.70, 0.70)
        else:
            cntr_conf = 0.0

        # 2. Container Type Confidence
        type_conf = raw_confidences.get("container_type", 0.0)
        if not container.container_type:
            type_conf = 0.0

        iso_conf = raw_confidences.get("iso_type") if container.iso_type else None

        # 3. Dimensions Confidence
        dims_conf = raw_confidences.get("dimensions", 0.0)
        if container.dimensions.length_ft is None:
            dims_conf = 0.0
        elif any("Suspicious container" in w for w in validation.warnings):
            dims_conf = min(dims_conf, 0.50)

        # 4. Weights Confidence
        weights_conf = raw_confidences.get("weights", 0.0)
        if container.weights.gross_weight_kg is None:
            weights_conf = 0.0
        elif validation.weight_balance_valid is True:
            weights_conf = max(weights_conf, 0.96)
        elif validation.weight_balance_valid is False:
            weights_conf = min(weights_conf if weights_conf > 0 else 0.60, 0.60)

        # 5. Cargo Confidence
        cargo_conf = raw_confidences.get("cargo", 0.0)
        if not container.cargo.description and container.cargo.hazardous is None:
            cargo_conf = 0.0

        # 6. Hazardous Classification Confidence
        haz_raw = raw_confidences.get("hazardous", 0.0)
        if container.cargo.hazardous is not None:
            if container.cargo.un_number or container.cargo.imdg_class:
                haz_conf = max(haz_raw, 0.98)
            else:
                haz_conf = max(haz_raw, 0.90)
        else:
            haz_conf = 0.0

        # 7. Destination Confidence
        dest_conf = raw_confidences.get("destination", 0.0)
        if not container.destination:
            dest_conf = 0.0

        # 8. References Confidence
        booking_conf = raw_confidences.get("booking_reference") if container.booking_reference else None
        seal_conf = raw_confidences.get("seal_number") if container.seal_number else None

        # Weighted Overall Score
        overall = (
            cntr_conf * cls.WEIGHTS_DISTRIBUTION["container_number"] +
            weights_conf * cls.WEIGHTS_DISTRIBUTION["weights"] +
            type_conf * cls.WEIGHTS_DISTRIBUTION["container_type"] +
            dims_conf * cls.WEIGHTS_DISTRIBUTION["dimensions"] +
            cargo_conf * cls.WEIGHTS_DISTRIBUTION["cargo"] +
            dest_conf * cls.WEIGHTS_DISTRIBUTION["destination"]
        )

        return ConfidenceScores(
            overall=round(float(overall), 2),
            container_number=round(float(cntr_conf), 2),
            container_type=round(float(type_conf), 2),
            iso_type=round(float(iso_conf), 2) if iso_conf is not None else None,
            dimensions=round(float(dims_conf), 2),
            weights=round(float(weights_conf), 2),
            cargo=round(float(cargo_conf), 2),
            hazardous=round(float(haz_conf), 2),
            destination=round(float(dest_conf), 2),
            booking_reference=round(float(booking_conf), 2) if booking_conf is not None else None,
            seal_number=round(float(seal_conf), 2) if seal_conf is not None else None
        )
