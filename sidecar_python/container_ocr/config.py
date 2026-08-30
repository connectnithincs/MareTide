"""
Configuration, Constants, and Reference Tables for Container Document Intelligence (Phase 1).
"""

import os
from typing import Dict, Any

# OCR Engine & Threshold Settings
DEFAULT_OCR_ENGINE = os.getenv("CONTAINER_OCR_ENGINE", "rapidocr")
OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.40"))
EXTRACTION_REVIEW_THRESHOLD = float(os.getenv("EXTRACTION_REVIEW_THRESHOLD", "0.85"))

# Preprocessing Settings
MAX_IMAGE_DIMENSION = 1800
BILATERAL_D = 9
BILATERAL_SIGMA_COLOR = 75
BILATERAL_SIGMA_SPACE = 75



# Weight Bounds for Validation (in KG)
MIN_TARE_KG = 800.0
MAX_TARE_KG = 7500.0
MIN_GROSS_KG = 1500.0
MAX_GROSS_KG = 40000.0
WEIGHT_TOLERANCE_KG = 100.0  # Acceptable discrepancy for Gross == Tare + Cargo

# Dimension Bounds (in Feet)
MIN_LENGTH_FT = 10.0
MAX_LENGTH_FT = 55.0
STANDARD_WIDTH_FT = 8.0
MIN_HEIGHT_FT = 4.0
MAX_HEIGHT_FT = 11.0

# Unit Conversion Constants
LBS_TO_KG = 0.45359237
TONNES_TO_KG = 1000.0

# ISO 6346 Character Values for Check Digit Calculation
# Note: Multiples of 11 (11, 22, 33) are omitted according to ISO 6346 standard
ISO_6346_LETTER_MAP: Dict[str, int] = {
    'A': 10, 'B': 12, 'C': 13, 'D': 14, 'E': 15, 'F': 16, 'G': 17, 'H': 18, 'I': 19, 'J': 20,
    'K': 21, 'L': 23, 'M': 24, 'N': 25, 'O': 26, 'P': 27, 'Q': 28, 'R': 29, 'S': 30, 'T': 31,
    'U': 32, 'V': 34, 'W': 35, 'X': 36, 'Y': 37, 'Z': 38
}

# ISO Size and Type Codes Mapping to Standard Dimensions & Names
# Code structure: [Length][Height/Width][Type][Special]
ISO_TYPE_MAP: Dict[str, Dict[str, Any]] = {
    # 20ft Standard
    "20GP": {"name": "20ft General Purpose", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20GP"},
    "20DC": {"name": "20ft Dry Cargo", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20GP"},
    "22G1": {"name": "20ft General Purpose (Passive Vents)", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20GP"},
    "22G0": {"name": "20ft General Purpose", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20GP"},
    "20FT": {"name": "20ft Standard Dry", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20GP"},
    
    # 40ft Standard
    "40GP": {"name": "40ft General Purpose", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40GP"},
    "40DC": {"name": "40ft Dry Cargo", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40GP"},
    "42G1": {"name": "40ft General Purpose (Passive Vents)", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40GP"},
    "42G0": {"name": "40ft General Purpose", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40GP"},
    "40FT": {"name": "40ft Standard Dry", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40GP"},

    # 40ft High Cube
    "40HC": {"name": "40ft High Cube", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "40HC"},
    "40HQ": {"name": "40ft High Cube", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "40HC"},
    "45G1": {"name": "40ft High Cube (Passive Vents)", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "40HC"},
    "45G0": {"name": "40ft High Cube", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "40HC"},

    # 45ft High Cube
    "45HC": {"name": "45ft High Cube", "length_ft": 45.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "45HC"},
    "45HQ": {"name": "45ft High Cube", "length_ft": 45.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "45HC"},
    "L5G1": {"name": "45ft High Cube", "length_ft": 45.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "45HC"},

    # Reefer
    "20RF": {"name": "20ft Reefer (Refrigerated)", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20RF"},
    "40RF": {"name": "40ft Reefer (Refrigerated)", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40RF"},
    "40HR": {"name": "40ft High Cube Reefer", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "40HR"},
    "22R1": {"name": "20ft Reefer", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20RF"},
    "45R1": {"name": "40ft High Cube Reefer", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 9.5, "standard_type": "40HR"},

    # Open Top & Flat Rack
    "20OT": {"name": "20ft Open Top", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20OT"},
    "40OT": {"name": "40ft Open Top", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40OT"},
    "20FR": {"name": "20ft Flat Rack", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20FR"},
    "40FR": {"name": "40ft Flat Rack", "length_ft": 40.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "40FR"},
    "20TK": {"name": "20ft ISO Tank", "length_ft": 20.0, "width_ft": 8.0, "height_ft": 8.5, "standard_type": "20TK"},
}

# Hazardous Cargo Keywords and Regex Indicators
HAZARDOUS_KEYWORDS = [
    "HAZMAT", "HAZARDOUS", "DANGEROUS GOODS", "IMO CLASS", "IMDG",
    "UN NUMBER", "UN NO", "UN#", "FLAMMABLE", "CORROSIVE", "TOXIC",
    "EXPLOSIVE", "RADIOACTIVE", "OXIDIZING", "POISON", "BIOHAZARD"
]

NON_HAZARDOUS_KEYWORDS = [
    "NON-HAZARDOUS", "NON HAZARDOUS", "NON HAZMAT", "GENERAL CARGO",
    "NOT RESTRICTED", "NO DG", "NON-DG", "STANDARD CARGO"
]

# Major Maritime Discharge Ports & UN/LOCODES for verification
KNOWN_PORTS = {
    "SINGAPORE": "SGSIN",
    "ROTTERDAM": "NLRTM",
    "SHANGHAI": "CNSHA",
    "NINGBO": "CNNGB",
    "BUSAN": "KRPUS",
    "HAMBURG": "DEHAM",
    "ANTWERP": "BEANR",
    "LOS ANGELES": "USLAX",
    "LONG BEACH": "USLGB",
    "NEW YORK": "USNYC",
    "DUBAI": "AEDXB",
    "JEBEL ALI": "AEJEA",
    "PORT KLANG": "MYPKG",
    "TANJUNG PELEPAS": "MYTPP",
    "HONG KONG": "HKHKG",
    "COLOMBO": "LKCMB",
    "MUMBAI": "INBOM",
    "NHAVA SHEVA": "INNSA",
    "CHENNAI": "INMAA",
    "VALENCIA": "ESVLC",
    "PIRAEUS": "GRPIR",
    "BREMERHAVEN": "DEBRV",
    "FELIXSTOWE": "GBFXT",
    "SYDNEY": "AUSYD",
    "MELBOURNE": "AUMEL",
    "TOKYO": "JPTYO",
    "YOKOHAMA": "JPYOK",
    "QINGDAO": "CNQDG",
    "TIANJIN": "CNTNJ",
    "KAOHSIUNG": "TWKHH"
}
