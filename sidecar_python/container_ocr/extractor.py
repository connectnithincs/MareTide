"""
Field Extraction Logic for Container Slips (Phase 1 & Phase 4A Hardening).
Performs pattern matching, anchor proximity detection, and regular expression extraction
on raw text/blocks for all required container manifest fields without fabricating missing values.
"""

import re
from typing import Dict, Any, List, Optional, Tuple
from .config import ISO_TYPE_MAP, HAZARDOUS_KEYWORDS, NON_HAZARDOUS_KEYWORDS, KNOWN_PORTS
from .ocr_engine import OCRResult, OCRTextBlock


class FieldExtractor:
    """
    Extracts raw field candidates from OCR text and bounding blocks without mutating values.
    """

    # --- REGEX PATTERNS ---
    CONTAINER_NUM_PATTERN = re.compile(
        r'\b([A-Z]{3}[UJZ])\s*[-.]?\s*(\d{6})\s*[-.]?\s*(\d)\b',
        re.IGNORECASE
    )
    CONTAINER_NUM_LOOSE = re.compile(
        r'(?:CONTAINER\s*(?:NO|ID|#)?|CNTR\s*(?:NO|#)?|EQUIPMENT\s*(?:NO|#)?|UNIT\s*(?:NO|#)?)\s*[:.-]?\s*([A-Z]{3,4}\s*\d{6,7})',
        re.IGNORECASE
    )

    WEIGHT_PATTERN_KG = re.compile(r'(\d+(?:[,\s]\d{3})*(?:\.\d+)?)\s*(?:KG|KGS|KILOGRAMS)', re.IGNORECASE)
    WEIGHT_PATTERN_LBS = re.compile(r'(\d+(?:[,\s]\d{3})*(?:\.\d+)?)\s*(?:LB|LBS|POUNDS)', re.IGNORECASE)
    WEIGHT_PATTERN_MT = re.compile(r'(\d+(?:[,\s]\d{3})*(?:\.\d+)?)\s*(?:MT|TONS?|TONNES?|\bT\b)', re.IGNORECASE)
    RAW_NUMBER_PATTERN = re.compile(r'(\d+(?:[,\s]\d{3})*(?:\.\d+)?)')

    DIMENSION_PATTERN = re.compile(
        r'(\d{2})\s*(?:\'|FT)?\s*[xX*]\s*(\d(?:\.\d+)?)\s*(?:\'|FT)?\s*[xX*]\s*(\d+(?:\.\d+)?(?:\'|\"|\s*ft)?)',
        re.IGNORECASE
    )

    UN_NUMBER_PATTERN = re.compile(r'\bUN\s*[-#]?\s*(\d{4})\b', re.IGNORECASE)
    IMDG_CLASS_PATTERN = re.compile(r'\b(?:CLASS|IMDG|IMO)\s*[:.-]?\s*([1-9](?:\.[1-9])?)\b', re.IGNORECASE)

    BOOKING_PATTERN = re.compile(r'(?:BOOKING|BKG|B/L|BILL\s*OF\s*LADING|CONSIGNMENT|REF)\s*(?:NO|#|NBR)?\s*[:.-]?\s*([A-Z0-9\-_]{6,20})', re.IGNORECASE)
    SEAL_PATTERN = re.compile(r'(?:SEAL)\s*(?:NO|#|NUMBER)?\s*[:.-]?\s*([A-Z0-9\-_]{5,20})', re.IGNORECASE)

    KNOWN_CARRIERS = [
        ("MEDITERRANEAN SHIPPING COMPANY", "MSC"),
        ("MAERSK", "MAERSK"),
        ("CMA CGM", "CMA CGM"),
        ("COSCO SHIPPING", "COSCO"),
        ("HAPAG-LLOYD", "HAPAG-LLOYD"),
        ("OCEAN NETWORK EXPRESS", "ONE"),
        ("EVERGREEN", "EVERGREEN"),
        ("YANG MING", "YANG MING"),
        ("HMM", "HMM"),
        ("ZIM", "ZIM")
    ]

    @classmethod
    def extract_candidates(cls, ocr_result: OCRResult) -> Dict[str, Any]:
        """
        Extracts raw candidates and matching confidences for all required fields.
        """
        text = ocr_result.raw_text
        lines = [b.text for b in ocr_result.blocks] if ocr_result.blocks else text.splitlines()

        candidates: Dict[str, Any] = {
            "container_number": cls._extract_container_number(text, lines, ocr_result.blocks),
            "container_type": cls._extract_container_type(text, lines),
            "dimensions": cls._extract_dimensions(text, lines),
            "weights": cls._extract_weights(text, lines),
            "cargo": cls._extract_cargo(text, lines),
            "destination": cls._extract_destination(text, lines),
            "references": cls._extract_references(text, lines),
            "carrier": cls._extract_carrier(text, lines)
        }

        return candidates

    @classmethod
    def _extract_container_number(cls, text: str, lines: List[str], blocks: List[OCRTextBlock]) -> Dict[str, Any]:
        match = cls.CONTAINER_NUM_PATTERN.search(text)
        if match:
            owner, serial, check = match.groups()
            raw_val = f"{owner}{serial}{check}".upper()
            return {"value": raw_val, "raw_match": match.group(0), "confidence": 0.95}

        match_anchor = cls.CONTAINER_NUM_LOOSE.search(text)
        if match_anchor:
            raw_val = re.sub(r'[\s\-.]', '', match_anchor.group(1)).upper()
            return {"value": raw_val, "raw_match": match_anchor.group(0), "confidence": 0.85}

        for line in lines:
            if any(k in line.upper() for k in ["CONTAINER", "CNTR", "EQUIPMENT", "UNIT"]):
                candidate = re.search(r'\b([A-Z]{3,4}\s*\d{6,7})\b', line.upper())
                if candidate:
                    raw_val = re.sub(r'[\s\-.]', '', candidate.group(1))
                    return {"value": raw_val, "raw_match": line, "confidence": 0.75}

        return {"value": None, "raw_match": None, "confidence": 0.0}

    @classmethod
    def _extract_container_type(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        text_upper = text.upper()
        iso_code_match = None

        # 1. Search for explicit 4-character ISO 6346 size/type codes (e.g. 45G1, 42G1, 22G1, 22R1, 45R1, L5G1)
        iso_pattern = re.search(r'\b([24L][0-9][A-Z][0-9])\b', text_upper)
        if iso_pattern:
            iso_cand = iso_pattern.group(1)
            if iso_cand in ISO_TYPE_MAP:
                details = ISO_TYPE_MAP[iso_cand]
                return {
                    "value": details["standard_type"],
                    "matched_code": iso_cand,
                    "iso_type": iso_cand,
                    "type_name": details["name"],
                    "confidence": 0.96
                }

        # 2. Check for standard container type abbreviations (e.g. 40HC, 20GP, 40RF)
        for code, details in ISO_TYPE_MAP.items():
            pattern = rf'\b{re.escape(code)}\b'
            if re.search(pattern, text_upper):
                return {
                    "value": details["standard_type"],
                    "matched_code": code,
                    "iso_type": None,
                    "type_name": details["name"],
                    "confidence": 0.92
                }

        # 3. Check regex for size + code (e.g. 40 HC, 20 GP)
        type_regex = re.search(r'\b(20|40|45)\s*(?:[\'’]|FT)?\s*[-/]?\s*(HC|HQ|GP|DC|RF|OT|FR|TK|HR)\b', text_upper)
        if type_regex:
            size, kind = type_regex.groups()
            norm_code = f"{size}{kind}"
            std_type = "40HC" if norm_code in ["40HC", "40HQ"] else ("45HC" if norm_code in ["45HC", "45HQ"] else ("20GP" if norm_code in ["20GP", "20DC"] else norm_code))
            return {
                "value": std_type,
                "matched_code": norm_code,
                "iso_type": None,
                "type_name": ISO_TYPE_MAP.get(norm_code, {}).get("name", f"{size}ft {kind}"),
                "confidence": 0.90
            }

        # 4. Line-by-line inspection
        for line in lines:
            lu = line.upper()
            if any(k in lu for k in ["TYPE:", "CONTAINER TYPE", "EQUIPMENT TYPE", "ISO CODE"]):
                for code, details in ISO_TYPE_MAP.items():
                    if code in lu.replace(" ", "").replace("-", ""):
                        is_iso = len(code) == 4 and code not in ["40HC", "20GP", "40GP", "40RF", "20RF"] and code[0].isdigit() and code[1].isdigit()
                        return {
                            "value": details["standard_type"],
                            "matched_code": code,
                            "iso_type": code if is_iso else None,
                            "type_name": details["name"],
                            "confidence": 0.88
                        }

        return {"value": None, "matched_code": None, "iso_type": None, "confidence": 0.0}

    @classmethod
    def _extract_dimensions(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        metric_match = re.search(r'(\d{1,2}(?:\.\d+)?)\s*m\s*[xX*]\s*(\d(?:\.\d+)?)\s*m\s*[xX*]\s*(\d(?:\.\d+)?)\s*m', text, re.IGNORECASE)
        if metric_match:
            l_m, w_m, h_m = metric_match.groups()
            return {
                "raw_length_m": l_m,
                "raw_width_m": w_m,
                "raw_height_m": h_m,
                "confidence": 0.95
            }

        match = cls.DIMENSION_PATTERN.search(text)
        if match:
            l_str, w_str, h_str = match.groups()
            return {
                "raw_length": l_str,
                "raw_width": w_str,
                "raw_height": h_str,
                "confidence": 0.90
            }

        return {"raw_length": None, "raw_width": None, "raw_height": None, "confidence": 0.0}

    @classmethod
    def _extract_weights(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        weights: Dict[str, Any] = {
            "tare": {"raw_value": None, "unit": None, "confidence": 0.0},
            "cargo": {"raw_value": None, "unit": None, "confidence": 0.0},
            "gross": {"raw_value": None, "unit": None, "confidence": 0.0},
            "vgm": {"raw_value": None, "unit": None, "verified": False, "method": None, "confidence": 0.0}
        }

        tare_anchors = ["TARE", "TARE WT", "TARE WEIGHT", "EMPTY WT", "UNLADEN"]
        cargo_anchors = ["CARGO WT", "CARGO WEIGHT", "NET WT", "NET WEIGHT", "NETCARGO", "PAYLOAD", "GOODS WT"]
        gross_anchors = ["GROSS WT", "GROSS WEIGHT", "VGM", "VERIFIED GROSS", "VERIFIEDGROSS", "MAX GROSS", "TOTAL WT"]

        non_weight_keywords = ["CONTAINER", "TYPE", "SEAL", "DIMENSION", "VOYAGE", "VESSEL", "RECEIPT", "INTERCHANGE", "CERTIFICATE", "ROUTING", "DISCHARGE", "CARRIER"]
        n_lines = len(lines)
        for i, line in enumerate(lines):
            lu = line.upper()

            # Gross / VGM
            if any(a in lu for a in gross_anchors) and not weights["gross"]["raw_value"]:
                val, unit, conf = cls._parse_weight_from_line(line)
                if not val and i + 1 < n_lines and not any(a in lines[i + 1].upper() for a in tare_anchors + cargo_anchors + non_weight_keywords):
                    val, unit, conf = cls._parse_weight_from_line(lines[i + 1])
                if not val and i > 0 and not any(a in lines[i - 1].upper() for a in tare_anchors + cargo_anchors + non_weight_keywords):
                    val, unit, conf = cls._parse_weight_from_line(lines[i - 1])
                if val:
                    weights["gross"] = {"raw_value": val, "unit": unit, "confidence": conf}

            # Tare
            if any(a in lu for a in tare_anchors) and not weights["tare"]["raw_value"]:
                val, unit, conf = cls._parse_weight_from_line(line)
                if not val and i + 1 < n_lines and not any(a in lines[i + 1].upper() for a in gross_anchors + cargo_anchors + non_weight_keywords):
                    val, unit, conf = cls._parse_weight_from_line(lines[i + 1])
                if not val and i > 0 and not any(a in lines[i - 1].upper() for a in gross_anchors + cargo_anchors + non_weight_keywords):
                    val, unit, conf = cls._parse_weight_from_line(lines[i - 1])
                if val:
                    weights["tare"] = {"raw_value": val, "unit": unit, "confidence": conf}

            # Cargo / Net
            if any(a in lu for a in cargo_anchors) and not weights["cargo"]["raw_value"]:
                val, unit, conf = cls._parse_weight_from_line(line)
                if not val and i + 1 < n_lines and not any(a in lines[i + 1].upper() for a in gross_anchors + tare_anchors + non_weight_keywords):
                    val, unit, conf = cls._parse_weight_from_line(lines[i + 1])
                if not val and i > 0 and not any(a in lines[i - 1].upper() for a in gross_anchors + tare_anchors + non_weight_keywords):
                    val, unit, conf = cls._parse_weight_from_line(lines[i - 1])
                if val:
                    weights["cargo"] = {"raw_value": val, "unit": unit, "confidence": conf}

        # Check explicit VGM certification and method in text
        text_upper = text.upper()
        if "VGM" in text_upper or "VERIFIED GROSS" in text_upper:
            vgm_verified = any(k in text_upper for k in ["VERIFIED ACCURATE", "VGM CERTIFICATE", "APPROVED FOR LOADING", "CERTIFIED ACCURATE"])
            vgm_method = "Method 1 - Direct Weighing" if "WEIGH" in text_upper else ("Method 2 - Calculation" if "CALCULAT" in text_upper else "SOLAS VGM Standard")
            vgm_val = weights["gross"]["raw_value"]
            vgm_unit = weights["gross"]["unit"] or "KG"
            weights["vgm"] = {
                "raw_value": vgm_val,
                "unit": vgm_unit,
                "verified": vgm_verified,
                "method": vgm_method,
                "confidence": weights["gross"]["confidence"]
            }

        return weights

    @classmethod
    def _parse_weight_from_line(cls, line: str) -> Tuple[Optional[str], Optional[str], float]:
        kg_m = cls.WEIGHT_PATTERN_KG.search(line)
        if kg_m:
            return kg_m.group(1).replace(",", "").replace(" ", ""), "KG", 0.95

        lbs_m = cls.WEIGHT_PATTERN_LBS.search(line)
        if lbs_m:
            return lbs_m.group(1).replace(",", "").replace(" ", ""), "LBS", 0.95

        mt_m = cls.WEIGHT_PATTERN_MT.search(line)
        if mt_m:
            return mt_m.group(1).replace(",", "").replace(" ", ""), "MT", 0.90

        nums = cls.RAW_NUMBER_PATTERN.findall(line)
        for n in nums:
            clean_n = n.replace(",", "").replace(" ", "")
            try:
                val = float(clean_n)
                if val > 100:
                    return clean_n, "KG", 0.70
            except ValueError:
                continue

        return None, None, 0.0

    @classmethod
    def _extract_cargo(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        desc = None
        desc_conf = 0.0
        hazardous = None
        haz_conf = 0.0
        un_num = None
        imdg_cls = None

        text_upper = text.upper()

        un_match = cls.UN_NUMBER_PATTERN.search(text)
        if un_match:
            un_num = f"UN {un_match.group(1)}"
            hazardous = True
            haz_conf = 0.98

        imdg_match = cls.IMDG_CLASS_PATTERN.search(text)
        if imdg_match:
            imdg_cls = f"Class {imdg_match.group(1)}"
            hazardous = True
            haz_conf = max(haz_conf, 0.95)

        neg_patterns = [
            r'\b(?:HAZMAT|HAZARDOUS|DG|DANGEROUS\s*GOODS)\s*[:.-]?\s*(?:NO|N|FALSE|NONE)\b',
            r'(?:NON[- ]?HAZARDOUS|NON[- ]?HAZMAT|NON[- ]?DG|NO\s*DG|GENERAL\s*CARGO|NOT\s*RESTRICTED)'
        ]
        is_explicit_neg = any(re.search(p, text_upper) for p in neg_patterns) or ("NON-HAZARDOUS" in text_upper)

        if is_explicit_neg and hazardous is not True:
            hazardous = False
            haz_conf = 0.95

        if hazardous is None:
            pos_patterns = [
                r'\b(?:HAZMAT|HAZARDOUS|DG|DANGEROUS\s*GOODS)\s*[:.-]?\s*(?:YES|Y|TRUE)\b',
                r'\bDANGEROUS\s*GOODS\b',
                r'\bHAZARDOUS\s*CARGO\b'
            ]
            is_explicit_pos = any(re.search(p, text_upper) for p in pos_patterns)
            if is_explicit_pos:
                hazardous = True
                haz_conf = 0.95
            elif any(hk in text_upper for hk in HAZARDOUS_KEYWORDS) and not is_explicit_neg:
                hazardous = True
                haz_conf = 0.88

        cargo_anchors = ["CARGO DESC", "CARGO DESCRIPTION", "COMMODITY DESC", "COMMODITY", "DESCRIPTION OF GOODS", "CONTENTS", "CARGO:"]
        n_lines = len(lines)
        for i, line in enumerate(lines):
            lu = line.upper()
            for anchor in cargo_anchors:
                if anchor in lu:
                    parts = re.split(rf'{re.escape(anchor)}\s*[:.-]?', line, flags=re.IGNORECASE)
                    if len(parts) > 1 and parts[1].strip() and len(parts[1].strip()) > 3:
                        desc = parts[1].strip()
                        desc_conf = 0.88
                        break
                    elif i + 1 < n_lines and lines[i + 1].strip():
                        next_line = lines[i + 1].strip()
                        if not any(k in next_line.upper() for k in ["HAZMAT", "STATUS", "WEIGHT", "PORT", "SEAL", "CARRIER"]):
                            desc = next_line
                            desc_conf = 0.88
                            break
            if desc:
                break

        return {
            "description": desc,
            "desc_confidence": desc_conf,
            "hazardous": hazardous,
            "hazardous_confidence": haz_conf,
            "un_number": un_num,
            "imdg_class": imdg_cls
        }

    @classmethod
    def _extract_destination(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        dest = None
        dest_conf = 0.0

        dest_anchors = [
            "PORT OF DISCHARGE", "DISCHARGE PORT", "POD", "DESTINATION",
            "FINAL DESTINATION", "DISCHARGE:", "DEST:"
        ]

        for line in lines:
            lu = line.upper()
            for anchor in dest_anchors:
                if anchor in lu:
                    parts = re.split(rf'{re.escape(anchor)}\s*[:.-]?', line, flags=re.IGNORECASE)
                    if len(parts) > 1 and parts[1].strip():
                        candidate = parts[1].strip()
                        dest = candidate
                        dest_conf = 0.85
                        break
            if dest:
                break

        if not dest:
            text_upper = text.upper()
            for port_name, locode in KNOWN_PORTS.items():
                if port_name in text_upper or locode in text_upper:
                    dest = port_name
                    dest_conf = 0.90
                    break

        return {"value": dest, "confidence": dest_conf}

    @classmethod
    def _extract_references(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        booking_ref = None
        booking_conf = 0.0
        seal_num = None
        seal_conf = 0.0

        bkg_m = cls.BOOKING_PATTERN.search(text)
        if bkg_m:
            booking_ref = bkg_m.group(1).strip()
            booking_conf = 0.88

        seal_m = cls.SEAL_PATTERN.search(text)
        if seal_m:
            seal_num = seal_m.group(1).strip()
            seal_conf = 0.90

        # Line scan for SEAL NUMBER:
        if not seal_num:
            for line in lines:
                if "SEAL NUMBER" in line.upper() or "SEAL NO" in line.upper():
                    parts = re.split(r'SEAL\s*(?:NUMBER|NO|#)?\s*[:.-]?', line, flags=re.IGNORECASE)
                    if len(parts) > 1 and parts[1].strip():
                        seal_num = parts[1].strip().split()[0]
                        seal_conf = 0.85
                        break

        return {
            "booking_reference": booking_ref,
            "booking_confidence": booking_conf,
            "seal_number": seal_num,
            "seal_confidence": seal_conf
        }

    @classmethod
    def _extract_carrier(cls, text: str, lines: List[str]) -> Dict[str, Any]:
        text_upper = text.upper()
        for fullname, shortcode in cls.KNOWN_CARRIERS:
            if fullname in text_upper:
                return {"value": fullname, "confidence": 0.92}
            elif re.search(rf'\b{re.escape(shortcode)}\b', text_upper):
                return {"value": fullname, "confidence": 0.85}

        # Check line anchor: CARRIER:
        for line in lines:
            if "CARRIER" in line.upper() or "OPERATOR:" in line.upper():
                parts = re.split(r'(?:CARRIER|OPERATOR)\s*[:.-]?', line, flags=re.IGNORECASE)
                if len(parts) > 1 and parts[1].strip():
                    return {"value": parts[1].strip(), "confidence": 0.80}

        return {"value": None, "confidence": 0.0}
