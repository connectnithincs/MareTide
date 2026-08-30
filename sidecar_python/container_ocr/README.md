# Container Document Intelligence / OCR Subsystem (Phase 1)

## Purpose
Modular, CPU-compatible OCR and document parsing subsystem for **MareTide / NAVI-AI**. Extracts standardized container specifications, weights, dimensions, ISO 6346 container numbers, hazardous material classifications, and destination ports from gate slips, interchange receipts, and bills of lading.

---

## REST API Specification

### Primary Endpoint
```http
POST /api/container/extract
Content-Type: multipart/form-data
```

#### Request Parameters
| Parameter | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `image` | `file` (binary) | **Yes** | Container slip image (`.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`). Max 15MB. |
| `file` | `file` (binary) | Optional | Alternative alias field name for the image. |
| `engine` | `string` (query) | Optional | OCR engine override (`rapidocr`, `mock`, `groq`). Default: `rapidocr`. |

#### Response Codes
*   **`200 OK`**: Extraction completed successfully. `processing_status` will be `"success"`, `"partial"`, or `"review_required"`.
*   **`400 Bad Request`**: Missing file, unsupported format, empty file (0 bytes), or corrupted image bytes.
*   **`413 Payload Too Large`**: Upload exceeds 15MB limit.
*   **`500 Internal Server Error`**: Unexpected internal OCR failure (without leaking stack traces).

---

### Example Request (`curl`)
```bash
curl -X POST "http://localhost:8001/api/container/extract" \
  -F "image=@sample_container_slip.jpg"
```

### Example Successful Response (`200 OK`)
```json
{
  "success": true,
  "document": {
    "source": "sample_container_slip.jpg",
    "processing_status": "success",
    "processing_time_ms": 142.5,
    "ocr_engine": "rapidocr-onnx"
  },
  "container": {
    "container_number": "MSCU4920195",
    "container_type": "40HC",
    "dimensions": {
      "length_ft": 40.0,
      "width_ft": 8.0,
      "height_ft": 9.5
    },
    "weights": {
      "tare_weight_kg": 3800.0,
      "cargo_weight_kg": 22400.0,
      "gross_weight_kg": 26200.0
    },
    "cargo": {
      "description": "ELECTRONIC COMPONENTS & LITHIUM CELLS",
      "hazardous": true,
      "un_number": "UN 3480",
      "imdg_class": "Class 9"
    },
    "destination": "SINGAPORE"
  },
  "confidence": {
    "overall": 0.96,
    "container_number": 0.98,
    "container_type": 0.92,
    "dimensions": 0.95,
    "weights": 0.96,
    "cargo": 0.98,
    "destination": 0.95
  },
  "validation": {
    "valid": true,
    "iso_6346_valid": true,
    "weight_balance_valid": true,
    "warnings": [
      "Hazardous cargo / dangerous goods detected (UN 3480, Class 9). Requires stowage segregation."
    ],
    "errors": []
  }
}
```

---

## Direct Python SDK Usage
```python
from container_ocr import process_container_slip

result = process_container_slip("path/to/container_slip.jpg")
print(result.container.container_number)
print(result.container.weights.gross_weight_kg)
```

---

## Health Check Endpoint
```http
GET /api/container/health
```
Returns:
```json
{
  "status": "healthy",
  "service": "MareTide Container Document Intelligence (Phase 1)",
  "endpoint": "POST /api/container/extract",
  "default_ocr_engine": "rapidocr",
  "supported_engines": ["rapidocr", "groq-vision", "mock"],
  "max_upload_size_mb": 15,
  "supported_formats": [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"]
}
```
