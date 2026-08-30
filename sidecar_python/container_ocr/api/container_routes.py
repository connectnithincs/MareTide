"""
FastAPI REST Routes for Container Document Intelligence (Phase 1).
Exposes POST /api/container/extract, POST /api/container/ocr/upload, POST /api/container/ocr/process-raw, and GET /api/container/health.
"""

import logging
import cv2
import numpy as np
from fastapi import APIRouter, File, UploadFile, Query, HTTPException, status
from typing import Optional

from ..models import ContainerSlipResponse, RawTextRequest
from ..service import default_service
from ..config import DEFAULT_OCR_ENGINE

logger = logging.getLogger("container_ocr.api")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/api/container", tags=["Container Document Intelligence"])

# Security & Upload Configuration
ALLOWED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff")
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB limit


@router.post(
    "/extract",
    response_model=ContainerSlipResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract Container Data from Slip Image",
    description="Primary REST endpoint to extract container specifications, dimensions, weights, and cargo data from an uploaded slip image."
)
async def extract_container_from_slip(
    image: Optional[UploadFile] = File(None, description="Container slip image file (.jpg, .png, .webp)"),
    file: Optional[UploadFile] = File(None, description="Alternative field name for container slip image"),
    engine: Optional[str] = Query(None, description="Optional OCR engine override ('rapidocr', 'mock', 'groq')")
):
    """
    Main extraction endpoint:
    - Accepts multipart/form-data with 'image' (or 'file')
    - Performs format validation, size limit checks, and image integrity verification
    - Returns standardized ContainerSlipResponse
    """
    upload = image or file
    if upload is None or not upload.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No image file provided. Please supply an image in multipart field 'image' or 'file'."
        )

    # 1. Format & Extension Validation
    filename_lower = upload.filename.lower()
    if not filename_lower.endswith(ALLOWED_IMAGE_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{upload.filename}'. Allowed formats: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
        )

    # 2. File Read & Size Limit Check
    try:
        content = await upload.read()
    except Exception as e:
        logger.error(f"Failed to read uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded file content."
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded image file is empty (0 bytes)."
        )

    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed limit of {MAX_UPLOAD_BYTES // (1024 * 1024)}MB."
        )

    # 3. Image Integrity Verification
    nparr = np.frombuffer(content, np.uint8)
    decoded_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if decoded_img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or invalid image data. The file cannot be decoded as an image."
        )

    # 4. Execute Service Pipeline
    try:
        response = default_service.process_image(
            image_input=decoded_img,
            source_name=upload.filename,
            engine_name=engine
        )
        return response
    except Exception as e:
        logger.exception("Internal OCR processing failure:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal document OCR processing failure. Please check document quality or server logs."
        )


@router.post(
    "/ocr/upload",
    response_model=ContainerSlipResponse,
    include_in_schema=False
)
async def upload_container_slip_alias(
    image: Optional[UploadFile] = File(None),
    file: Optional[UploadFile] = File(None),
    engine: Optional[str] = Query(None)
):
    """
    Alias route for /api/container/extract.
    """
    return await extract_container_from_slip(image=image, file=file, engine=engine)


@router.post(
    "/ocr/process-raw",
    response_model=ContainerSlipResponse,
    summary="Process Raw OCR Text Directly",
    description="Processes raw OCR text payload directly for testing extraction, normalization, and validation rules without an image."
)
async def process_raw_text(payload: RawTextRequest):
    if not payload.raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input raw_text cannot be empty."
        )

    try:
        response = default_service.process_raw_text(
            raw_text=payload.raw_text,
            source_name=payload.source_name or "raw_input.txt"
        )
        return response
    except Exception as e:
        logger.exception("Text extraction error:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal text extraction failure."
        )


@router.get(
    "/health",

    summary="Container Document Intelligence Health Check",
    description="Returns module status and active OCR engine configuration."
)
@router.get(
    "/ocr/health",
    include_in_schema=False
)
async def get_ocr_health():
    return {
        "status": "healthy",
        "service": "MareTide Container Document Intelligence (Phase 1)",
        "endpoint": "POST /api/container/extract",
        "default_ocr_engine": DEFAULT_OCR_ENGINE,
        "supported_engines": ["rapidocr", "groq-vision", "mock"],
        "max_upload_size_mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        "supported_formats": list(ALLOWED_IMAGE_EXTENSIONS)
    }


# =============================================================================
# PHASE 6E: HACKATHON DEMONSTRATION MODE FIXTURES & CONTROLLERS
# =============================================================================

import os
from fastapi.responses import FileResponse
import state
from reports.logs_db import clear_logs

FIXTURES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "tests",
    "fixtures"
)

DEMO_SCENARIOS = [
    {
        "id": "scenario_golden_path",
        "title": "Scenario 1: Canonical Golden Path (Certified SOLAS Gate Slip)",
        "subtitle": "Complete Workflow: Slip -> OCR -> Optimization -> Live Commit -> Ballast Compensation",
        "filename": "sample_container_slip.jpg",
        "category": "GOLDEN_PATH",
        "container_number": "MSCU 492019 5",
        "expected_result": "SUCCESS",
        "description": "Standard certified gate interchange receipt with verified VGM of 26,200 kg and UN 3480 Class 9 lithium battery cargo destined for Singapore. Demonstrates full safety gate passage, explainable stowage recommendation, operator authorization, atomic twin update, and ballast discharge.",
        "tags": ["Document AI", "Multi-Objective Stowage", "Operator Gate", "Ballast Auto-Calculation", "Audit Trail"]
    },
    {
        "id": "scenario_anomaly_rejection",
        "title": "Scenario 2: Critical Anomaly (VGM Arithmetic Mismatch)",
        "subtitle": "Safety Gate Enforcement: Discrepancy Flagged -> Review Required -> Loading Locked",
        "filename": "inconsistent_weight_slip.jpg",
        "category": "ANOMALY_REJECTION",
        "container_number": "CMAU 555123 4",
        "expected_result": "CRITICAL_ANOMALY",
        "description": "Gate slip with contradictory mass values (Tare 3,800 kg + Cargo 10,000 kg != Gross 28,000 kg, delta >14,000 kg). Demonstrates strict safety gate locking, preventing dangerous loading onto the vessel.",
        "tags": ["Anomaly Detection", "SOLAS VGM Mismatch", "Safety Gate Lock", "Zero State Mutation"]
    },
    {
        "id": "scenario_check_digit_defect",
        "title": "Scenario 3: Corrupted ISO 6346 Check Digit",
        "subtitle": "Validation Rule Check: Modulo-11 Check Digit Mismatch Flagged",
        "filename": "invalid_container_num_slip.jpg",
        "category": "VALIDATION_WARNING",
        "container_number": "MSCU 492019 9",
        "expected_result": "WARNING",
        "description": "Container slip with corrupted check digit (9 instead of calculated 5). Evaluated with check digit warning for human operator review.",
        "tags": ["ISO 6346 Verification", "Check Digit Warning", "Operator Review"]
    },
    {
        "id": "scenario_heavy_cargo",
        "title": "Scenario 4: Heavy Container Loading & Ballast Response",
        "subtitle": "Extreme Load: 34.5t Heavy-Lift Container -> Tank-Top Placement & Ballast Rebalancing",
        "filename": "heavy_container_slip.jpg",
        "category": "HEAVY_CARGO",
        "container_number": "MSCU 889201 3",
        "expected_result": "SUCCESS",
        "description": "High-mass container (34,500 kg) requiring tier 1 tank-top placement and significant ballast counter-trim compensation.",
        "tags": ["Heavy Cargo", "Structural Limit", "Longitudinal Trim Compensation"]
    }
]


@router.get(
    "/demo/fixtures",
    summary="Get Hackathon Demo Scenarios and Fixtures",
    description="Returns pre-validated demo scenarios with fixture images for 3-5 minute live judging demonstration."
)
async def get_demo_scenarios():
    return {
        "status": "ready",
        "mode": "DEMO_MODE",
        "scenarios": DEMO_SCENARIOS
    }


@router.get(
    "/demo/fixtures/{filename}/image",
    summary="Download Demo Fixture Image",
    description="Returns raw binary image of the requested demo fixture."
)
async def get_demo_fixture_image(filename: str):
    safe_name = os.path.basename(filename)
    file_path = os.path.join(FIXTURES_DIR, safe_name)
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Demo fixture '{safe_name}' not found."
        )
    return FileResponse(file_path, media_type="image/jpeg", filename=safe_name)


@router.post(
    "/demo/reset",
    summary="Reset Vessel & Audit State for Clean Demo Run",
    description="Resets vessel containers, restores ballast tanks, and clears audit logs."
)
async def reset_demo_state():
    state.reset_state()
    clear_logs()
    return {
        "status": "reset_complete",
        "vessel": "MareTide Vessel",
        "containers_count": 0,
        "ballast_tanks_initialized": 8,
        "message": "Vessel and audit state successfully reset to baseline equilibrium."
    }

