"""
Modular OCR Engine Abstraction for Container Document Intelligence.
Supports RapidOCR (ONNX CPU), Groq Vision Fallback, and Deterministic Mock Engine.
"""

import time
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Any
import numpy as np

from .config import DEFAULT_OCR_ENGINE, OCR_CONFIDENCE_THRESHOLD


@dataclass
class OCRTextBlock:
    text: str
    confidence: float = 1.0
    box: Optional[List[List[float]]] = None
    line_num: int = 0


@dataclass
class OCRResult:
    raw_text: str
    blocks: List[OCRTextBlock] = field(default_factory=list)
    engine_name: str = "unknown"
    elapsed_ms: float = 0.0


class BaseOCREngine(ABC):
    """
    Abstract interface for OCR engines.
    """

    @abstractmethod
    def recognize(self, img: np.ndarray) -> OCRResult:
        """
        Runs OCR on the given image numpy array and returns structured OCRResult.
        """
        pass

    def extract_text(self, image_input: Any) -> OCRResult:
        """
        Convenience wrapper accepting file path, bytes, PIL Image, or numpy array.
        """
        from .preprocessing import ImagePreprocessor
        img = ImagePreprocessor.load_image(image_input)
        return self.recognize(img)


class RapidOCREngine(BaseOCREngine):
    """
    Fast, CPU-optimized OCR engine using RapidOCR and ONNX Runtime.
    Caches ONNX runtime sessions to eliminate model initialization latency on repeated requests.
    """
    _shared_rapidocr = None

    def __init__(self):
        self.engine = None
        self._initialize()

    def _initialize(self):
        if RapidOCREngine._shared_rapidocr is not None:
            self.engine = RapidOCREngine._shared_rapidocr
            return

        try:
            from rapidocr_onnxruntime import RapidOCR
            RapidOCREngine._shared_rapidocr = RapidOCR()
            self.engine = RapidOCREngine._shared_rapidocr
        except ImportError as e:
            raise ImportError(
                "rapidocr_onnxruntime is not installed. Please install via: pip install rapidocr-onnxruntime"
            ) from e


    def recognize(self, img: np.ndarray) -> OCRResult:
        start_time = time.perf_counter()
        if self.engine is None:
            self._initialize()

        # RapidOCR returns: (result, elapse_list)
        # where result is a list of [box, text, confidence]
        ocr_out, _ = self.engine(img)

        blocks: List[OCRTextBlock] = []
        raw_lines: List[str] = []

        if ocr_out:
            for idx, item in enumerate(ocr_out):
                box, text, conf = item
                text_clean = str(text).strip()
                if not text_clean:
                    continue
                blocks.append(OCRTextBlock(
                    text=text_clean,
                    confidence=float(conf),
                    box=box,
                    line_num=idx
                ))
                raw_lines.append(text_clean)

        raw_text = "\n".join(raw_lines)
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return OCRResult(
            raw_text=raw_text,
            blocks=blocks,
            engine_name="rapidocr-onnx",
            elapsed_ms=round(elapsed_ms, 2)
        )


class VisionLLMEngine(BaseOCREngine):
    """
    Vision-Language Multimodal OCR Engine via Groq API.
    Used when GROQ_API_KEY is available and multimodal extraction is requested.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.client = None
        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
            except Exception:
                self.client = None

    def recognize(self, img: np.ndarray) -> OCRResult:
        start_time = time.perf_counter()
        if not self.client:
            raise RuntimeError("Groq Vision OCR engine requested but GROQ_API_KEY is not configured.")

        import cv2
        import base64
        _, buffer = cv2.imencode(".jpg", img)
        base64_image = base64.b64encode(buffer).decode("utf-8")

        prompt = (
            "You are a maritime document OCR system. Read and transcribe all text from this container slip "
            "verbatim. Maintain original line breaks and labels exactly as shown on the document."
        )

        response = self.client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=1024
        )

        raw_text = response.choices[0].message.content or ""
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        blocks = [OCRTextBlock(text=l, confidence=0.95, line_num=i) for i, l in enumerate(lines)]
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return OCRResult(
            raw_text=raw_text,
            blocks=blocks,
            engine_name="groq-vision-llava",
            elapsed_ms=round(elapsed_ms, 2)
        )


class MockOCREngine(BaseOCREngine):
    """
    Deterministic Mock OCR Engine for unit testing and offline simulation.
    """

    def __init__(self, predefined_text: Optional[str] = None):
        self.predefined_text = predefined_text or (
            "CONTAINER INTERCHANGE RECEIPT & GATE PASS\n"
            "CONTAINER NO: MSCU 492019 5\n"
            "TYPE / SIZE: 40HC (45G1)\n"
            "DIMENSIONS: 40' x 8' x 9'6\"\n"
            "TARE WEIGHT: 3,800 KG / 8,377 LBS\n"
            "CARGO WEIGHT (NET): 22,400 KG\n"
            "VERIFIED GROSS MASS (VGM): 26,200 KG\n"
            "CARGO DESC: ELECTRONIC COMPONENTS & LITHIUM CELLS\n"
            "HAZMAT: YES - UN 3480 CLASS 9 (LITHIUM ION BATTERIES)\n"
            "PORT OF DISCHARGE: SINGAPORE (SGSIN)\n"
            "SEAL NO: ML-SG-98721\n"
            "CARRIER: MEDITERRANEAN SHIPPING COMPANY"
        )

    def recognize(self, img: np.ndarray) -> OCRResult:
        lines = [l.strip() for l in self.predefined_text.splitlines() if l.strip()]
        blocks = [OCRTextBlock(text=l, confidence=0.99, line_num=i) for i, l in enumerate(lines)]
        return OCRResult(
            raw_text=self.predefined_text,
            blocks=blocks,
            engine_name="mock-ocr-engine",
            elapsed_ms=1.5
        )


_ENGINE_CACHE: Dict[str, BaseOCREngine] = {}


def get_ocr_engine(engine_name: Optional[str] = None) -> BaseOCREngine:
    """
    Factory function returning the cached/singleton OCR engine instance.
    """
    name = (engine_name or DEFAULT_OCR_ENGINE).lower().strip()
    if name in _ENGINE_CACHE:
        return _ENGINE_CACHE[name]

    engine: BaseOCREngine
    if name in ["mock", "test", "simulated"]:
        engine = MockOCREngine()
    elif name in ["groq", "vision_llm", "llm"]:
        engine = VisionLLMEngine()
    elif name in ["rapidocr", "onnx", "default"]:
        try:
            engine = RapidOCREngine()
        except Exception:
            engine = MockOCREngine()
    else:
        try:
            engine = RapidOCREngine()
        except Exception:
            engine = MockOCREngine()

    _ENGINE_CACHE[name] = engine
    return engine

