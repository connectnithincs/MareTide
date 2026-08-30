"""
Data Normalization Module for Container Document Intelligence (Phase 1 & Phase 4A).
Transforms raw extracted candidates into standardized units (KG, FT, ISO codes, VGM metadata).
"""

import re
from typing import Dict, Any, Optional, Tuple
from .config import (
    ISO_TYPE_MAP, LBS_TO_KG, TONNES_TO_KG,
    STANDARD_WIDTH_FT, KNOWN_PORTS
)
from .models import (
    ContainerDimensions, ContainerWeights, CargoDetails, ContainerDetails, CargoMassMetadata
)


class DataNormalizer:
    """
    Normalizes candidate fields to canonical maritime standards and unit systems.
    """

    @classmethod
    def normalize_all(cls, candidates: Dict[str, Any]) -> Tuple[ContainerDetails, Dict[str, float]]:
        """
        Normalizes all candidate fields and returns (ContainerDetails, field_confidences).
        """
        confidences: Dict[str, float] = {}

        # 1. Container Number
        cntr_num, cntr_conf = cls.normalize_container_number(candidates.get("container_number", {}))
        confidences["container_number"] = cntr_conf

        # 2. Container Type & ISO Code
        cntr_type, iso_type, type_conf, iso_conf = cls.normalize_container_type(candidates.get("container_type", {}))
        confidences["container_type"] = type_conf
        if iso_type:
            confidences["iso_type"] = iso_conf

        # 3. Dimensions
        dims, dims_conf = cls.normalize_dimensions(
            candidates.get("dimensions", {}),
            cntr_type
        )
        confidences["dimensions"] = dims_conf

        # 4. Weights & VGM
        weights, weights_conf = cls.normalize_weights(candidates.get("weights", {}))
        confidences["weights"] = weights_conf

        # 5. Cargo & Hazardous
        cargo, cargo_conf, haz_conf = cls.normalize_cargo(candidates.get("cargo", {}))
        confidences["cargo"] = cargo_conf
        confidences["hazardous"] = haz_conf

        # 6. Destination
        destination, dest_conf = cls.normalize_destination(candidates.get("destination", {}))
        confidences["destination"] = dest_conf

        # 7. References (Booking & Seal)
        booking_ref, booking_conf, seal_num, seal_conf = cls.normalize_references(candidates.get("references", {}))
        if booking_ref:
            confidences["booking_reference"] = booking_conf
        if seal_num:
            confidences["seal_number"] = seal_conf

        # 8. Carrier
        carrier, carrier_conf = cls.normalize_carrier(candidates.get("carrier", {}))
        if carrier:
            confidences["carrier"] = carrier_conf

        container_details = ContainerDetails(
            container_number=cntr_num,
            container_type=cntr_type,
            iso_type=iso_type,
            dimensions=dims,
            weights=weights,
            cargo=cargo,
            cargo_mass=weights.cargo_mass,
            destination=destination,
            booking_reference=booking_ref,
            seal_number=seal_num,
            carrier=carrier
        )

        return container_details, confidences


    @classmethod
    def normalize_container_number(cls, raw_data: Dict[str, Any]) -> Tuple[Optional[str], float]:
        raw_val = raw_data.get("value")
        conf = raw_data.get("confidence", 0.0)
        if not raw_val:
            return None, 0.0

        clean = re.sub(r'[^A-Z0-9]', '', str(raw_val).upper())

        # An ISO 6346 container number is exactly 11 characters: 4 letters + 7 digits
        if len(clean) == 11 and clean[:4].isalpha() and clean[4:].isdigit():
            return clean, max(conf, 0.95)
        elif len(clean) == 10 and clean[:4].isalpha() and clean[4:].isdigit():
            return clean, 0.70
        elif len(clean) >= 10:
            return clean[:11], 0.60

        return clean if clean else None, 0.40

    @classmethod
    def normalize_container_type(cls, raw_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], float, float]:
        raw_val = raw_data.get("value")
        iso_code = raw_data.get("iso_type")
        conf = raw_data.get("confidence", 0.0)
        if not raw_val:
            return None, None, 0.0, 0.0

        raw_upper = str(raw_val).upper().strip()

        # Helper to test if a code is a true 4-character ISO 6346 size/type (e.g. 45G1, 22G1, 42G1)
        def is_iso_size_type_code(c: Optional[str]) -> bool:
            if not c or len(c) != 4:
                return False
            if c in ["40HC", "40HQ", "20GP", "40GP", "40RF", "20RF", "40OT", "20OT", "40FR", "20FR", "45HC", "45HQ"]:
                return False
            return c[0].isdigit() and c[1].isdigit()

        # Prioritize explicit iso_code if it is a valid 4-character ISO code
        final_iso = iso_code if is_iso_size_type_code(iso_code) else (raw_upper if is_iso_size_type_code(raw_upper) else None)

        # Check ISO Map
        if raw_upper in ISO_TYPE_MAP:
            matched_std = ISO_TYPE_MAP[raw_upper]["standard_type"]
            return matched_std, final_iso, max(conf, 0.90), max(conf, 0.90)

        for code, details in ISO_TYPE_MAP.items():
            if code in raw_upper or details["standard_type"] == raw_upper:
                if is_iso_size_type_code(code) and not final_iso:
                    final_iso = code
                return details["standard_type"], final_iso, max(conf, 0.85), max(conf, 0.85)

        return raw_upper, final_iso, conf, conf

    @classmethod
    def normalize_dimensions(
        cls,
        raw_data: Dict[str, Any],
        container_type: Optional[str] = None
    ) -> Tuple[ContainerDimensions, float]:
        l_val = raw_data.get("raw_length")
        w_val = raw_data.get("raw_width")
        h_val = raw_data.get("raw_height")
        conf = raw_data.get("confidence", 0.0)

        length_ft: Optional[float] = None
        width_ft: Optional[float] = None
        height_ft: Optional[float] = None

        # Parse metric first if available
        l_m = raw_data.get("raw_length_m")
        w_m = raw_data.get("raw_width_m")
        h_m = raw_data.get("raw_height_m")
        if l_m and w_m and h_m:
            try:
                length_ft = round(float(l_m) * 3.28084, 1)
                width_ft = round(float(w_m) * 3.28084, 1)
                height_ft = round(float(h_m) * 3.28084, 1)
                if 10.0 <= length_ft <= 55.0 and 4.0 <= height_ft <= 13.0:
                    return ContainerDimensions(length_ft=length_ft, width_ft=width_ft, height_ft=height_ft), conf
            except (ValueError, TypeError):
                pass

        # Parse explicit feet/inches
        if l_val and w_val and h_val:
            try:
                length_ft = float(l_val)
                width_ft = float(w_val)
                height_ft = cls._parse_height_ft(h_val)
                if height_ft is not None and (height_ft < 4.0 or height_ft > 13.0):
                    height_ft = None
                if length_ft is not None and height_ft is not None:
                    return ContainerDimensions(length_ft=length_ft, width_ft=width_ft, height_ft=height_ft), conf
            except (ValueError, TypeError):
                pass

        # Infer from standardized container type if explicit dimensions are absent or partial
        if container_type:
            type_upper = container_type.upper()
            if type_upper in ISO_TYPE_MAP:
                iso_dim = ISO_TYPE_MAP[type_upper]
                return ContainerDimensions(
                    length_ft=length_ft or iso_dim["length_ft"],
                    width_ft=width_ft or iso_dim["width_ft"],
                    height_ft=height_ft or iso_dim["height_ft"]
                ), max(conf, 0.85)
            elif "20" in type_upper:
                return ContainerDimensions(length_ft=20.0, width_ft=8.0, height_ft=8.5), max(conf, 0.80)
            elif "40" in type_upper:
                height = 9.5 if ("HC" in type_upper or "HQ" in type_upper) else 8.5
                return ContainerDimensions(length_ft=40.0, width_ft=8.0, height_ft=height), max(conf, 0.80)
            elif "45" in type_upper:
                return ContainerDimensions(length_ft=45.0, width_ft=8.0, height_ft=9.5), max(conf, 0.80)

        return ContainerDimensions(length_ft=length_ft, width_ft=width_ft, height_ft=height_ft), conf

    @classmethod
    def _parse_height_ft(cls, h_val: Any) -> Optional[float]:
        if not h_val:
            return None
        h_str = str(h_val).replace('"', '').replace('ft', '').replace('FT', '').strip()
        if "'" in h_str:
            parts = h_str.split("'")
            feet = float(parts[0].strip())
            inches = float(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0.0
            return round(feet + (inches / 12.0), 2)
        try:
            return float(h_str)
        except ValueError:
            return None

    @classmethod
    def normalize_weights(cls, raw_data: Dict[str, Any]) -> Tuple[ContainerWeights, float]:
        tare_data = raw_data.get("tare", {})
        cargo_data = raw_data.get("cargo", {})
        gross_data = raw_data.get("gross", {})
        vgm_data = raw_data.get("vgm", {})

        tare_kg = cls._convert_to_kg(tare_data.get("raw_value"), tare_data.get("unit"))
        cargo_kg = cls._convert_to_kg(cargo_data.get("raw_value"), cargo_data.get("unit"))
        gross_kg = cls._convert_to_kg(gross_data.get("raw_value"), gross_data.get("unit"))
        vgm_kg = cls._convert_to_kg(vgm_data.get("raw_value"), vgm_data.get("unit")) if vgm_data.get("raw_value") else gross_kg

        # Fallback calculation: If gross is missing but tare and cargo are known
        if gross_kg is None and tare_kg is not None and cargo_kg is not None:
            gross_kg = round(tare_kg + cargo_kg, 1)

        # Fallback calculation: If cargo is missing but gross and tare are known
        if cargo_kg is None and gross_kg is not None and tare_kg is not None and gross_kg >= tare_kg:
            cargo_kg = round(gross_kg - tare_kg, 1)

        confidences = [
            tare_data.get("confidence", 0.0) for d in [tare_data] if tare_kg is not None
        ] + [
            cargo_data.get("confidence", 0.0) for d in [cargo_data] if cargo_kg is not None
        ] + [
            gross_data.get("confidence", 0.0) for d in [gross_data] if gross_kg is not None
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        vgm_verified = vgm_data.get("verified", False)
        vgm_method = vgm_data.get("method")

        cargo_mass_meta = None
        if gross_kg is not None or cargo_kg is not None:
            effective_val = float(gross_kg if gross_kg is not None else cargo_kg)
            cargo_mass_meta = CargoMassMetadata(
                value=effective_val,
                unit="kg",
                source="DOCUMENT_AI",
                authoritative=True
            )

        weights = ContainerWeights(
            tare_weight_kg=tare_kg,
            cargo_weight_kg=cargo_kg,
            gross_weight_kg=gross_kg,
            vgm_kg=vgm_kg,
            vgm_method=vgm_method,
            vgm_verified=vgm_verified,
            cargo_mass=cargo_mass_meta
        )

        return weights, avg_conf


    @classmethod
    def _convert_to_kg(cls, val_str: Optional[str], unit: Optional[str]) -> Optional[float]:
        if val_str is None:
            return None
        try:
            val_clean = str(val_str).replace(" ", "").strip()
            # If dot was OCR-detected as thousands separator, e.g. "34.500" where 3 digits follow dot and prefix >= 10
            if "." in val_clean:
                parts = val_clean.split(".")
                if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit() and float(parts[0]) >= 5:
                    val_clean = parts[0] + parts[1]
            val = float(val_clean.replace(",", ""))
            unit_upper = (unit or "KG").upper().strip()
            if "LB" in unit_upper:
                return round(val * LBS_TO_KG, 1)
            elif "MT" in unit_upper or "TON" in unit_upper:
                return round(val * TONNES_TO_KG, 1)
            elif 5.0 <= val < 100.0:
                # Value was expressed in metric tonnes (e.g. 34.5 t)
                return round(val * TONNES_TO_KG, 1)
            return round(val, 1)
        except (ValueError, TypeError):
            return None

    @classmethod
    def normalize_cargo(cls, raw_data: Dict[str, Any]) -> Tuple[CargoDetails, float, float]:
        desc = raw_data.get("description")
        desc_conf = raw_data.get("desc_confidence", 0.0)
        hazardous = raw_data.get("hazardous")
        haz_conf = raw_data.get("hazardous_confidence", 0.0)
        un_num = raw_data.get("un_number")
        imdg_cls = raw_data.get("imdg_class")

        cargo = CargoDetails(
            description=desc.strip() if desc else None,
            hazardous=hazardous,
            un_number=un_num,
            imdg_class=imdg_cls
        )
        return cargo, desc_conf, haz_conf

    @classmethod
    def normalize_destination(cls, raw_data: Dict[str, Any]) -> Tuple[Optional[str], float]:
        val = raw_data.get("value")
        conf = raw_data.get("confidence", 0.0)
        if not val:
            return None, 0.0

        val_upper = str(val).upper().strip()

        # Match against known ports dictionary
        for port_name, locode in KNOWN_PORTS.items():
            if port_name in val_upper or locode in val_upper:
                return port_name, max(conf, 0.90)

        # Remove trailing port codes if in brackets
        clean = re.sub(r'\s*\([A-Z]{5}\)', '', val_upper).strip()
        clean = re.sub(r'^(PORT OF|PORT)\s+', '', clean).strip()

        return clean.title() if clean else val_upper.title(), conf

    @classmethod
    def normalize_references(cls, raw_data: Dict[str, Any]) -> Tuple[Optional[str], float, Optional[str], float]:
        bkg = raw_data.get("booking_reference")
        bkg_conf = raw_data.get("booking_confidence", 0.0)
        seal = raw_data.get("seal_number")
        seal_conf = raw_data.get("seal_confidence", 0.0)
        return (
            bkg.strip().upper() if bkg else None,
            bkg_conf,
            seal.strip().upper() if seal else None,
            seal_conf
        )

    @classmethod
    def normalize_carrier(cls, raw_data: Dict[str, Any]) -> Tuple[Optional[str], float]:
        val = raw_data.get("value")
        conf = raw_data.get("confidence", 0.0)
        if not val:
            return None, 0.0
        return str(val).strip().title(), conf
