"""
Pydantic Data Models for Container Document Intelligence (Phase 1 & Phase 4A).
Defines schemas for Document Metadata, Dimensions, Weights, Cargo, Confidence,
Validation, Document Quality Assessment, and the central ContainerSlipResponse contract.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    source: str = Field(..., description="Original filename or URI of the document")
    processing_status: str = Field(default="success", description="Status: 'success', 'partial', 'review_required', or 'failed'")
    processing_time_ms: Optional[float] = Field(default=None, description="Elapsed processing time in milliseconds")
    ocr_engine: Optional[str] = Field(default=None, description="OCR engine used for text detection")


class DocumentQuality(BaseModel):
    """
    Automated image quality and artifact assessment.
    """
    quality: str = Field(default="good", description="Quality tier: 'good', 'fair', 'poor', or 'unusable'")
    issues: List[str] = Field(default_factory=list, description="Detected quality issues: blur, low_contrast, low_resolution, extreme_rotation, etc.")
    blur_score: Optional[float] = Field(default=None, description="Laplacian variance blur metric (>35 is sharp)")
    contrast_score: Optional[float] = Field(default=None, description="Grayscale standard deviation intensity (>22 is healthy)")
    resolution: Optional[str] = Field(default=None, description="Image dimensions (e.g. '1200x900')")
    detected_angle: Optional[float] = Field(default=None, description="Detected rotation/skew angle in degrees")



class ContainerDimensions(BaseModel):
    length_ft: Optional[float] = Field(default=None, description="Length in feet (e.g. 20.0, 40.0, 45.0)")
    width_ft: Optional[float] = Field(default=None, description="Width in feet (standard 8.0)")
    height_ft: Optional[float] = Field(default=None, description="Height in feet (e.g. 8.5 for standard, 9.5 for HC)")


class CargoMassMetadata(BaseModel):
    """
    Explicit Phase 6A Cargo Mass Provenance Metadata.
    Guarantees container mass originates solely from Document AI / OCR.
    """
    value: float = Field(..., description="Cargo mass numeric value")
    unit: str = Field(default="kg", description="Unit of measurement ('kg')")
    source: str = Field(default="DOCUMENT_AI", description="Authoritative source ('DOCUMENT_AI')")
    authoritative: bool = Field(default=True, description="Whether this cargo mass is authoritative")


class ContainerWeights(BaseModel):
    tare_weight_kg: Optional[float] = Field(default=None, description="Tare (empty) container weight in kg")
    cargo_weight_kg: Optional[float] = Field(default=None, description="Net cargo/payload weight in kg")
    gross_weight_kg: Optional[float] = Field(default=None, description="Total verified gross mass (VGM) in kg")
    vgm_kg: Optional[float] = Field(default=None, description="Verified Gross Mass (VGM) explicit value in kg")
    vgm_method: Optional[str] = Field(default=None, description="SOLAS VGM weighing method (e.g. 'Method 1 - Direct Weighing', 'Method 2 - Calculation')")
    vgm_verified: Optional[bool] = Field(default=None, description="True if document explicitly certifies VGM accuracy")
    cargo_mass: Optional[CargoMassMetadata] = Field(default=None, description="Explicit Phase 6A Document AI provenance metadata")


class CargoDetails(BaseModel):
    description: Optional[str] = Field(default=None, description="Description of goods or cargo contents")
    hazardous: Optional[bool] = Field(default=None, description="True if dangerous goods/IMDG classified, False if general cargo, None if unknown")
    un_number: Optional[str] = Field(default=None, description="UN classification number if detected (e.g. UN 3480)")
    imdg_class: Optional[str] = Field(default=None, description="IMDG Hazard Class if detected (e.g. Class 3, Class 9)")


class ContainerDetails(BaseModel):
    container_number: Optional[str] = Field(default=None, description="Standardized ISO 6346 container number (e.g. MSCU4920194)")
    container_type: Optional[str] = Field(default=None, description="Standardized container type code (e.g. 20GP, 40HC, 40RF)")
    iso_type: Optional[str] = Field(default=None, description="ISO 6346 4-character size and type code (e.g. 45G1, 22G1)")
    dimensions: ContainerDimensions = Field(default_factory=ContainerDimensions)
    weights: ContainerWeights = Field(default_factory=ContainerWeights)
    cargo: CargoDetails = Field(default_factory=CargoDetails)
    cargo_mass: Optional[CargoMassMetadata] = Field(default=None, description="Explicit Phase 6A Document AI provenance metadata")
    destination: Optional[str] = Field(default=None, description="Port of discharge or delivery destination")
    booking_reference: Optional[str] = Field(default=None, description="Booking or consignment reference number")
    seal_number: Optional[str] = Field(default=None, description="Security bolt seal number (e.g. ML-SG-987214)")
    carrier: Optional[str] = Field(default=None, description="Shipping line or ocean carrier name")



class ConfidenceScores(BaseModel):
    overall: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall extraction confidence score (0.0 to 1.0)")
    container_number: float = Field(default=0.0, ge=0.0, le=1.0)
    container_type: float = Field(default=0.0, ge=0.0, le=1.0)
    iso_type: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    dimensions: float = Field(default=0.0, ge=0.0, le=1.0)
    weights: float = Field(default=0.0, ge=0.0, le=1.0)
    cargo: float = Field(default=0.0, ge=0.0, le=1.0)
    hazardous: float = Field(default=0.0, ge=0.0, le=1.0, description="Hazardous classification confidence")
    destination: float = Field(default=0.0, ge=0.0, le=1.0)
    booking_reference: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    seal_number: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class CargoAnomaly(BaseModel):
    field: str = Field(..., description="Target field with detected anomaly")
    observed: Any = Field(..., description="Observed raw or extracted value")
    expected: str = Field(..., description="Expected rule condition or standard bounds")
    severity: str = Field(..., description="Severity level: 'INFO', 'WARNING', or 'CRITICAL'")
    message: str = Field(..., description="Human-readable explanation of why this anomaly was triggered")
    action: str = Field(..., description="Actionable recommendation for operator or surveyor")


class ValidationResult(BaseModel):
    valid: bool = Field(default=False, description="True if core required fields pass domain validation")
    iso_6346_valid: Optional[bool] = Field(default=None, description="ISO 6346 check digit validation result")
    weight_balance_valid: Optional[bool] = Field(default=None, description="Gross == Tare + Cargo verification result")
    warnings: List[str] = Field(default_factory=list, description="Non-critical warnings or partial discrepancies")
    errors: List[str] = Field(default_factory=list, description="Critical validation failures")
    anomalies: List[CargoAnomaly] = Field(default_factory=list, description="Structured cargo safety & data anomaly items")


class ContainerSlipResponse(BaseModel):
    """
    Standardized Central Output Contract for Container Slip Intelligence.
    """
    success: bool = Field(default=True, description="Indicates whether processing completed")
    document: DocumentMetadata = Field(..., description="Document metadata and processing performance")
    document_quality: DocumentQuality = Field(default_factory=DocumentQuality, description="Document image quality and artifact assessment")
    container: ContainerDetails = Field(default_factory=ContainerDetails, description="Extracted container and cargo fields")
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores, description="Granular confidence scores")
    validation: ValidationResult = Field(default_factory=ValidationResult, description="Domain validation results")
    anomalies: List[CargoAnomaly] = Field(default_factory=list, description="Structured safety anomalies for document intelligence")
    raw_text: Optional[str] = Field(default=None, description="Optional raw OCR text extracted from the document")


class RawTextRequest(BaseModel):
    """
    Request model for testing field extraction directly on raw OCR text.
    """
    raw_text: str = Field(..., description="Text from slip or document to extract fields from")
    source_name: Optional[str] = Field(default="raw_input.txt", description="Document source label")
