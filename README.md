# PIPI (Patient Intelligence & Processing Interface)

PIPI is a FastAPI-based healthcare backend that combines two pipelines into a unified case workflow:

1. SKIN_TELLIGENT image analysis (detection, classification, Grad-CAM explainability)
2. Medical document processing (ADE and Docling routes)

Both pipelines can write outputs into the same case folder, enabling consolidated per-patient or per-session artifact tracking.

## Key Capabilities

- Skin image inference pipeline with:
	- Lesion detection
	- ROI classification
	- Grad-CAM explainability artifacts
	- Classification report export
- Document ingestion and extraction with:
	- Dynamic routing by report type (`lab_report` or `prescription`)
	- Parsed markdown output
	- Structured medical field extraction
	- JSON artifact persistence
- Unified output context manager:
	- One case folder reused for both skin and document requests
	- Context keyed by `patient_id` or `x-session-id`

## Project Structure

```text
api/
	main.py
	routers/
		skintelligent_router.py
		document_router.py
backend/
	services/
		SKIN_TELLIGENT/
		DOCPROCESS/
		output_context.py
config/
	vision_config.py
webui/
	index.html
	styles.css
	app.js
output/
uploads/
```

## Architecture Overview

- FastAPI app startup initializes:
	- `InferencePipeline` for image inference
	- `CaseOutputManager` for shared case folders
- Skin endpoint (`/Skin/SKIN_TELLIGENT`):
	- Accepts image upload
	- Uses shared case context
	- Saves artifacts under `case/skintelligent`
- Document endpoint (`/ade/upload`):
	- Accepts PDF/JPG/JPEG/PNG
	- Routes to ADE or Docling
	- Saves artifacts under `case/documents`

## Case-Based Output Organization

For a shared context (same `patient_id` or same `x-session-id`), outputs are stored under one case folder:

```text
output/<case_id>/
	skintelligent/
		images/
		detections/
		detection_boxes/
		gradcam/
		reports/
			classification_report_<run_id>.txt
	documents/
		originals/
		parsed/
			<artifact>_medical_fields.json
			<artifact>_chunks.json
			<artifact>_result.json
			<artifact>.md
```

## Requirements

- Python 3.10+ recommended
- Linux/macOS/Windows
- CPU execution is supported (PyTorch CPU wheels configured)

Install dependencies from:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the repository root.

Required variables depend on which pipeline you use:

- Document processing:
	- `OPENAI_API_KEY` (for Docling extraction model integration)
	- `VISION_AGENT_API_KEY` or `VISION_API_KEY` (for ADE client)

If these keys are missing, related services will raise startup/runtime errors when invoked.

## Run the Backend

From repository root:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
GET /health
```

## API Endpoints

### 1) Skin Pipeline

- Method: `POST`
- Path: `/Skin/SKIN_TELLIGENT`
- Content-Type: `multipart/form-data`
- Form fields:
	- `file` (required image)
	- `patient_id` (optional)
- Headers:
	- `x-session-id` (optional)

Response includes:

- detection/classification payload
- `case` metadata
- output paths for generated artifacts

### 2) Document Upload

- Method: `POST`
- Path: `/ade/upload`
- Content-Type: `multipart/form-data`
- Form fields:
	- `file` (required; `.pdf`, `.png`, `.jpg`, `.jpeg`)
	- `report_type` (`lab_report` or `prescription`)
	- `patient_id` (optional)
- Headers:
	- `x-session-id` (optional)

Response includes:

- extraction payload
- `case` metadata
- `stored_outputs` paths:
	- original document
	- parsed markdown
	- medical fields JSON
	- chunks JSON
	- full result JSON

### 3) Field Extraction Helpers

- `POST /ade/extract`
- `POST /ade/docling/ext_markdown`

## Local Web UI (HTML/CSS/JS)

The repository includes a lightweight frontend in `webui/`.

Start static server:

```bash
cd webui
python3 -m http.server 5501
```

Open:

```text
http://127.0.0.1:5501
```

The UI supports:

- shared case context inputs (`patient_id`, `x-session-id`)
- skin upload calls
- document upload calls
- raw JSON response inspection

## CORS

Backend CORS is configured for local development origins (localhost/127.0.0.1/0.0.0.0 with common ports and regex fallback).

If preflight fails, verify:

1. backend restarted after config changes
2. UI origin matches allowed local patterns

## Logging and Artifacts

- Runtime logs are written under `logs/`
- Upload staging occurs under `uploads/`
- Final persistent artifacts are written under `output/`

## Development Notes

- Keep model artifacts in `artifacts/`
- Use form-data fields consistently across clients
- Reuse either `patient_id` or `x-session-id` to keep all outputs in one case folder

## License

See `LICENSE`.