"""
Container Document Intelligence Service Orchestrator (Phase 1 & Phase 4A).
Coordinates Quality Assessment -> Preprocessing -> OCR -> Extraction -> Normalization -> Validation -> Confidence Scoring -> Standardized JSON.
"""

import time
from typing import Union, Optional
import numpy as np
from PIL import Image

from .models import (
    ContainerSlipResponse, DocumentMetadata, DocumentQuality,
    ContainerDetails, ValidationResult, ConfidenceScores
)
from .preprocessing import ImagePreprocessor
from .ocr_engine import get_ocr_engine, BaseOCREngine, OCRResult, OCRTextBlock
from .extractor import FieldExtractor
from .normalizer import DataNormalizer
from .validator import DomainValidator
from .confidence import ConfidenceScorer
from .config import EXTRACTION_REVIEW_THRESHOLD


class ContainerSlipService:
    """
    High-level service interface for processing shipping slips and container documentation.
    """

    def __init__(self, default_engine: Optional[str] = None):
        self.default_engine_name = default_engine
        self._engine: Optional[BaseOCREngine] = None

    def get_engine(self, engine_name: Optional[str] = None) -> BaseOCREngine:
        selected_name = engine_name or self.default_engine_name
        if self._engine is None or engine_name is not None:
            self._engine = get_ocr_engine(selected_name)
        return self._engine


    def process_image(
        self,
        image_input: Union[bytes, str, Image.Image, np.ndarray],
        source_name: str = "container_slip.jpg",
        engine_name: Optional[str] = None,
        include_raw_text: bool = True
    ) -> ContainerSlipResponse:
        """
        Processes a container slip image through the full intelligence pipeline with automated quality evaluation.
        Fails safely if image is corrupted or OCR engine encounters an error.
        """
        start_time = time.perf_counter()
        
        if source_name == "container_slip.jpg" and isinstance(image_input, str):
            import os
            source_name = os.path.basename(image_input)

        try:
            # 1. Standardize and load image once
            loaded_img = ImagePreprocessor.load_image(image_input)

            # 2. Document Image Quality Assessment
            document_quality = ImagePreprocessor.assess_document_quality(loaded_img)

            # 3. Image Preprocessing for OCR (reusing quality metadata)
            engine = self.get_engine(engine_name)
            preprocessed_img = ImagePreprocessor.process_for_ocr(loaded_img, quality_meta=document_quality)

            # 4. OCR Detection & Recognition
            ocr_result = engine.recognize(preprocessed_img)


            # 4. Field Extraction
            candidates = FieldExtractor.extract_candidates(ocr_result)

            # 5. Normalization
            container_details, raw_confidences = DataNormalizer.normalize_all(candidates)

            # 6. Domain Validation
            validation = DomainValidator.validate_container(container_details)

            # 7. Confidence Scoring
            confidence = ConfidenceScorer.calculate_scores(
                container=container_details,
                raw_confidences=raw_confidences,
                validation=validation
            )

            total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # 8. Determine Processing Status & Safety Gate
            if confidence.overall < EXTRACTION_REVIEW_THRESHOLD:
                status = "review_required"
            elif not validation.valid:
                status = "review_required"
            elif document_quality.quality in ["poor", "unusable"]:
                status = "review_required"
            else:
                status = "success"

            doc_meta = DocumentMetadata(
                source=source_name,
                processing_status=status,
                processing_time_ms=round(total_elapsed_ms, 2),
                ocr_engine=ocr_result.engine_name
            )

            return ContainerSlipResponse(
                success=True,
                document=doc_meta,
                document_quality=document_quality,
                container=container_details,
                confidence=confidence,
                validation=validation,
                anomalies=validation.anomalies,
                raw_text=ocr_result.raw_text if include_raw_text else None
            )

        except Exception as e:
            total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            doc_meta = DocumentMetadata(
                source=source_name,
                processing_status="ocr_failed",
                processing_time_ms=round(total_elapsed_ms, 2),
                ocr_engine=engine_name or "unknown"
            )
            return ContainerSlipResponse(
                success=False,
                document=doc_meta,
                document_quality=DocumentQuality(quality="unusable", issues=[f"Processing failure: {str(e)}"]),
                container=ContainerDetails(),
                confidence=ConfidenceScores(),
                validation=ValidationResult(
                    valid=False,
                    errors=[f"Document OCR processing error: {str(e)}"],
                    warnings=[]
                ),
                anomalies=[],
                raw_text=None
            )

    def process_raw_text(
        self,
        raw_text: str,
        source_name: str = "raw_input.txt",
        include_raw_text: bool = True
    ) -> ContainerSlipResponse:
        """
        Processes raw text directly through extraction, normalization, and validation.
        Useful for debugging, test fixtures, and testing candidate extraction logic.
        """
        start_time = time.perf_counter()

        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
        blocks = [OCRTextBlock(text=l, confidence=0.95, line_num=i) for i, l in enumerate(lines)]
        ocr_result = OCRResult(
            raw_text=raw_text,
            blocks=blocks,
            engine_name="direct-text-parser",
            elapsed_ms=0.5
        )

        candidates = FieldExtractor.extract_candidates(ocr_result)
        container_details, raw_confidences = DataNormalizer.normalize_all(candidates)
        validation = DomainValidator.validate_container(container_details)
        confidence = ConfidenceScorer.calculate_scores(
            container=container_details,
            raw_confidences=raw_confidences,
            validation=validation
        )

        total_elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        if confidence.overall < EXTRACTION_REVIEW_THRESHOLD or not validation.valid:
            status = "review_required"
        else:
            status = "success"

        doc_meta = DocumentMetadata(
            source=source_name,
            processing_status=status,
            processing_time_ms=round(total_elapsed_ms, 2),
            ocr_engine="direct-text-parser"
        )

        return ContainerSlipResponse(
            success=True,
            document=doc_meta,
            document_quality=DocumentQuality(quality="good", issues=[], resolution="direct_text"),
            container=container_details,
            confidence=confidence,
            validation=validation,
            anomalies=validation.anomalies,
            raw_text=raw_text if include_raw_text else None
        )


# Global Service Singleton
default_service = ContainerSlipService()


def process_container_slip(
    image_input: Union[bytes, str, Image.Image, np.ndarray],
    source_name: str = "container_slip.jpg",
    engine_name: Optional[str] = None
) -> ContainerSlipResponse:
    """
    Standard service entrypoint: processes image and returns standardized JSON result.
    """
    return default_service.process_image(
        image_input=image_input,
        source_name=source_name,
        engine_name=engine_name
    )


def extract_container_slip(
    image_input: Union[bytes, str, Image.Image, np.ndarray],
    source_name: str = "container_slip.jpg",
    engine_name: Optional[str] = None
) -> ContainerSlipResponse:
    """
    Convenience function to extract container slip data from image input.
    """
    return process_container_slip(
        image_input=image_input,
        source_name=source_name,
        engine_name=engine_name
    )
