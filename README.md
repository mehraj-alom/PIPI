# PIPI (Patient Intelligence & Processing Interface)

PIPI is a FastAPI-based healthcare backend that combines two pipelines into a unified case workflow:

1. SKIN_TELLIGENT image analysis (detection, classification, Grad-CAM explainability)
2. Medical document processing (ADE and Docling routes)
3. Voice-agent assisted triage, patient lookup, and appointment management

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
- Voice agent phone widget:
	- ElevenLabs WebRTC session in the web UI
	- Backend config endpoint for the runtime agent ID
	- Client tools for patient lookup, registration, doctor search, booking, cancellation, and rescheduling
	- Upload modal triggered by the `requestUpload` client tool
	- Page blur/backdrop effect while the call panel or upload modal is open

- Database-backed voice workflow:
	- SQLAlchemy models for patients, doctors, appointments, and call sessions
	- Alembic migrations for schema changes
	- SQLite default storage under `.langgraph/app.sqlite`
	- Session persistence for voice calls and linked clinical context

## Project Structure

```text
api/
	main.py
	routers/
		skintelligent_router.py
		document_router.py
backend/
	database/
		connections.py
		models.py
		queries.py
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
- Database startup uses:
	- SQLAlchemy `SessionLocal` for request-scoped sessions
	- Alembic migrations from `alembic/versions/`
	- Default SQLite database at `.langgraph/app.sqlite`
- Skin endpoint (`/Skin/SKIN_TELLIGENT`):
	- Accepts image upload
	- Uses shared case context
	- Saves artifacts under `case/skintelligent`
- Document endpoint (`/ade/upload`):
	- Accepts PDF/JPG/JPEG/PNG
	- Routes to ADE or Docling
	- Saves artifacts under `case/documents`
- Voice-agent tools (`/tools/VoiceAgent/*`):
	- Expose non-sensitive ElevenLabs runtime config to the web UI
	- Read and write patient, doctor, appointment, and call-session records
	- Back the client-side voice call widget and its upload flow

## Voice Agent And Database

The voice agent is wired through `api/routers/voice_agent_router.py` and uses the database layer in `backend/database/`.

Available voice-agent tool routes include:

- `GET /tools/VoiceAgent/config`
- `POST /tools/VoiceAgent/getPatientDetails`
- `POST /tools/VoiceAgent/registerNewPatient`
- `POST /tools/VoiceAgent/searchDoctors`
- `POST /tools/VoiceAgent/checkDoctorAvailability`
- `POST /tools/VoiceAgent/bookAppointment`
- `POST /tools/VoiceAgent/cancelAppointment`
- `POST /tools/VoiceAgent/getPatientAppointments`
- `POST /tools/VoiceAgent/rescheduleAppointment`
- `POST /tools/VoiceAgent/sendUploadLink` (legacy fallback; upload is normally handled in the web UI)

The database schema currently includes:

- `patients`
- `doctors`
- `appointments`
- `call_sessions`

Those tables support the voice workflow for patient intake, scheduling, and call-session context persistence.

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
- Voice agent:
	- `ELEVENLABS_API_KEY` (for the ElevenLabs voice session)
	- `ELEVENLABS_AGENT_ID` (the agent ID used by `webui/voice-agent.js`)
	- `ELEVENLABS_VOICE_ID` (voice ID; separate from agent ID)

If these keys are missing, related services will raise startup/runtime errors when invoked.

Note: the browser does not read `.env` directly. The voice UI fetches `ELEVENLABS_AGENT_ID` from the backend at runtime, so restart the backend after changing `.env`.

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

### 4) Voice Agent Tools

- `GET /tools/VoiceAgent/config`
- `POST /tools/VoiceAgent/getPatientDetails`
- `POST /tools/VoiceAgent/registerNewPatient`
- `POST /tools/VoiceAgent/searchDoctors`
- `POST /tools/VoiceAgent/checkDoctorAvailability`
- `POST /tools/VoiceAgent/bookAppointment`
- `POST /tools/VoiceAgent/cancelAppointment`
- `POST /tools/VoiceAgent/getPatientAppointments`
- `POST /tools/VoiceAgent/rescheduleAppointment`
- `POST /tools/VoiceAgent/sendUploadLink`

## Docker Deployment

PIPI includes Docker and Docker Compose configuration for containerized deployment.

### Prerequisites

- Docker 20.10+ and Docker Compose 1.29+
- `.env` file with required API keys (same as local setup)

### Quick Start with Docker Compose

```bash
docker-compose up --build
```

This starts:
- **Backend**: `http://localhost:8000` (FastAPI + uvicorn)
- **Web UI**: `http://localhost:5502` (Static files + Python HTTP server)

### Running Individual Services

Build the backend image:

```bash
docker build -t pipi-backend:latest .
```

Run the backend container:

```bash
docker run -d \
  --name pipi-backend \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/output:/app/output \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/artifacts:/app/artifacts \
  pipi-backend:latest
```

Run the web UI (no build needed):

```bash
docker run -d \
  --name pipi-webui \
	-p 5502:5501 \
  -v $(pwd)/webui:/webui \
  python:3.11-slim \
  python -m http.server 5501 --directory /webui
```

### Docker Compose Services

- **backend**: FastAPI + Uvicorn, exposes port 8000, mounts `output/`, `logs/`, `uploads/`, `artifacts/`
- **webui**: Static file server, exposes port 5502 on the host and mounts `webui/`
- **pipi-network**: Docker bridge network for service communication

### Volumes

- `output/`: Case outputs (skin analysis, document processing results)
- `logs/`: Application logs
- `uploads/`: Temporary upload staging
- `artifacts/`: Model weights and data files

### Environment Variables

Pass via `.env` file (automatically loaded by docker-compose):

```env
OPENAI_API_KEY=sk-...
VISION_AGENT_API_KEY=...
ELEVENLABS_API_KEY=sk-...
ELEVENLABS_AGENT_ID=...
ELEVENLABS_VOICE_ID=...
LOG_LEVEL=INFO
```

### Health Checks

Backend includes a health check that runs every 30 seconds:

```bash
docker-compose ps
```

Should show `pipi-backend` in "healthy" state after ~5s startup.

### Stopping Services

```bash
docker-compose down
```

To remove all data:

```bash
docker-compose down -v
```

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
- voice agent call widget with ElevenLabs session startup
- voice-triggered upload modal for `skin_image`, `lab_report`, and `prescription`

Voice upload behavior:

- When the assistant invokes `requestUpload`, the upload window appears inside the phone widget.
- `skin image` and similar skin phrasing map to the skin upload flow.
- `document`, `lab report`, and similar phrasing map to the document upload flow.
- The page background blurs while the call panel or upload modal is open.

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
- Voice-agent state is persisted in the SQLAlchemy database, not in the case output folders
- If you change database models, add or update the Alembic migration under `alembic/versions/`

## License

See `LICENSE`.