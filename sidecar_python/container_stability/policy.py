"""
MareTide Phase 6A: Authoritative Cargo Data & Load-Cell Zero-Use Enforcement Policy.

CRITICAL ARCHITECTURE REQUIREMENT:
Load-cell sensor data (HX711 / scale cargo_kg / weighing sensors / load cell hardware)
MUST NOT be used anywhere in the real-time container loading workflow, stability engine,
optimizer, ballast calculations, digital twin, or audit trails.

The sole authoritative container weight pipeline:
  Document AI / OCR -> Validated Container JSON -> Stowage Optimization -> Loading Commit -> Ballast Calculation -> Audit

Centralized Provenance Rule:
  DOCUMENT_AI_CARGO_MASS = authoritative
  LOAD_CELL_CARGO_MASS = forbidden
"""

from typing import List, Final, Optional, Dict, Any

# Centralized Phase 6A Provenance Rule Constants
DOCUMENT_AI_CARGO_MASS: Final[str] = "authoritative"
LOAD_CELL_CARGO_MASS: Final[str] = "forbidden"

CONTAINER_WEIGHT_SOURCE: Final[str] = "DOCUMENT_AI"
PROVENANCE_LABEL: Final[str] = "[DOCUMENT AI]"
LOAD_CELL_POLICY: Final[str] = "FORBIDDEN_FOR_CARGO_AND_STABILITY"
HARDWARE_TELEMETRY_LABEL: Final[str] = "[HARDWARE TELEMETRY — NON-AUTHORITATIVE]"

ALLOWED_WEIGHT_SOURCES: Final[List[str]] = [
    "DOCUMENT_AI",
    "VALIDATED_OCR_DOCUMENT_JSON"
]

FORBIDDEN_WEIGHT_SOURCES: Final[List[str]] = [
    "LOAD_CELL",
    "LOADCELL",
    "SCALE",
    "WEIGHING_SENSOR",
    "HX711",
    "SENSOR_DERIVED_WEIGHT",
    "HARDWARE_WEIGHT",
    "CARGO_MASS_SENSOR",
    "WEIGHT_SENSOR",
    "SENSOR_DERIVED_CONTAINER_WEIGHT"
]


def assert_authoritative_source(source: str) -> bool:
    """
    Validates that a provided cargo mass data source conforms to the
    Phase 6A Authoritative Data Policy. Raises ValueError if a forbidden
    or unapproved source is provided.
    """
    normalized_source = str(source).strip().upper().replace(" ", "_").replace("-", "_").replace("[", "").replace("]", "")
    if any(forbidden in normalized_source for forbidden in FORBIDDEN_WEIGHT_SOURCES):
        raise ValueError(
            f"Security/Stability Policy Violation: Source '{source}' is in FORBIDDEN_WEIGHT_SOURCES. "
            f"Load-cell/scale measurements cannot be used for cargo weight or stability decisions."
        )
    if normalized_source not in [s.upper().replace(" ", "_").replace("-", "_") for s in ALLOWED_WEIGHT_SOURCES]:
        raise ValueError(
            f"Data Integrity Violation: Source '{source}' is not an authorized cargo source. "
            f"Allowed sources: {ALLOWED_WEIGHT_SOURCES}"
        )
    return True


def validate_cargo_mass_provenance(
    source: Optional[str] = None,
    authoritative: Optional[bool] = None,
    cargo_mass_meta: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Validates that cargo mass metadata or payload strictly originates from
    Document AI and is marked authoritative. Rejects any attempt to override
    Document AI cargo mass with sensor-derived mass.
    """
    if cargo_mass_meta and isinstance(cargo_mass_meta, dict):
        meta_source = str(cargo_mass_meta.get("source", "")).strip()
        meta_auth = cargo_mass_meta.get("authoritative", True)
        if meta_auth is False:
            raise ValueError("Security Policy Violation: Non-authoritative cargo mass cannot be used for loading or stability.")
        if meta_source:
            assert_authoritative_source(meta_source)
            return True

    if authoritative is False:
        raise ValueError("Security Policy Violation: Non-authoritative cargo mass cannot be used for loading or stability.")

    effective_source = str(source or CONTAINER_WEIGHT_SOURCE).strip()
    return assert_authoritative_source(effective_source)

