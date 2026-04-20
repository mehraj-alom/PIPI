# PIPI

<p align="center"><strong>Patient Intelligence & Processing Interface</strong></p>

<p align="center">
  <a href="https://www.python.org/"><img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white"></a>
  <a href="https://fastapi.tiangolo.com/"><img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white"></a>
  <a href="https://pytorch.org/"><img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-Vision-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white"></a>
  <a href="https://www.docker.com/"><img alt="Docker" src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white"></a>
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-MIT-F7DF1E?style=for-the-badge"></a>
</p>

PIPI is an AI-powered medical upload and care-navigation system built on FastAPI. In this repo, skin-image analysis, document extraction, and voice-assisted scheduling are brought into one case-based workflow instead of being handled as separate tools.

> Medical disclaimer: This project is built for research and educational use only. It is not a diagnostic tool and should not be used as a substitute for licensed clinical judgment.

## Overview

PIPI is designed for one practical problem: patient cases arrive as a mix of photos, reports, prescriptions, and scheduling needs, but those inputs usually live in separate tools.

This project brings them together in one interface:

- skin images go through the `SKIN_TELLIGENT` pipeline for detection, classification, and Grad-CAM explainability
- medical documents go through a structured extraction pipeline that returns markdown, chunks, and medical fields
- the floating call button opens a voice agent that can manage patient lookup and appointment actions while also triggering uploads from the call UI
- a shared `patient_id` or `x-session-id` keeps outputs grouped under one case folder in `output/`

The result is a cleaner pre-visit workflow where patient material is organized before the appointment, reducing repeated intake and saving clinician time.

## Problem Statement

In a real care journey, a single case may involve:

- a skin photo that needs visual analysis
- a lab report or prescription that needs structured extraction
- doctor search and appointment booking before the visit

When these steps live in separate systems, the case becomes fragmented. Context is lost between uploads, extracted results, and scheduling actions.

## Solution

PIPI solves that with a unified case workflow:

- one UI for skin uploads, document uploads, and scheduling support
- one backend for vision, document parsing, and voice-agent tools
- one case context for outputs tied to a patient or session
- one patient-facing entry point that can escalate into richer clinical support when needed

The floating call button is not just a voice shortcut. In this repo it can open an in-call upload modal and send skin images or documents straight to the backend.

## Project Lineage

`SKIN_TELLIGENT` inside PIPI is an evolution of earlier standalone work, now integrated into a broader patient workflow.

- [Original SKIN_TELLIGENT project](https://github.com/mehraj-alom/SKIN_TELLIGENT)
- [Earlier SKIN_DISEASE_CLASSIFIER (`skinV0`)](https://github.com/mehraj-alom/SKIN_DISEASE_CLASSIFIER/tree/skinV0)
- [Updated training notebook](https://www.kaggle.com/code/mehrajalomtapadar/notebooka1e763f51a)

## Architecture

```mermaid
flowchart LR
    User["User"]

    subgraph Browser["Browser UI (webui/)"]
        WebUI["Upload forms + case context"]
        CallButton["Floating call button"]
        PhoneWidget["Phone panel + upload modal"]
        ClientTools["Client tools:
getPatientDetails
registerNewPatient
searchDoctors
checkDoctorAvailability
bookAppointment
cancelAppointment
getPatientAppointments
rescheduleAppointment
requestUpload"]
        WebUI --> CallButton
        CallButton --> PhoneWidget
        PhoneWidget --> ClientTools
    end

    User --> WebUI
    WebUI -->|skin image| SkinAPI["POST /Skin/SKIN_TELLIGENT"]
    WebUI -->|lab report / prescription| DocAPI["POST /ade/upload"]
    ClientTools -->|voice tool calls| VoiceAPI["/tools/VoiceAgent/*"]
    PhoneWidget -->|requestUpload: skin_image| SkinAPI
    PhoneWidget -->|requestUpload: lab_report or prescription| DocAPI

    SkinAPI --> SkinPipeline["SKIN_TELLIGENT
detection + ROI classification + Grad-CAM"]
    DocAPI --> DocPipeline["Document extraction pipeline
markdown + chunks + medical fields"]
    VoiceAPI --> DB["SQLite + SQLAlchemy
patients
doctors
appointments
call_sessions"]

    SkinPipeline --> Case["Shared case folder
output/<case_id>/"]
    DocPipeline --> Case
```

## Voice-Assisted Upload Flow

```mermaid
sequenceDiagram
    participant U as User (voice)
    participant A as Voice agent
    participant W as Phone widget
    participant B as FastAPI backend

    U->>A: "I have a skin rash on my arm"
    A->>W: requestUpload({ upload_type: "skin_image" })
    W-->>U: Open upload modal with camera or file input
    U->>W: Select or capture skin image
    W->>B: POST /Skin/SKIN_TELLIGENT
    B-->>W: detections + classification results + case metadata
    W-->>A: Return JSON result
    A-->>U: Continue the conversation with the case result
```

## Tech Stack

| Layer | Technology | Purpose |
| --- | --- | --- |
| Backend API | Python, FastAPI, Uvicorn | Core application and HTTP endpoints |
| Vision | PyTorch, Torchvision, OpenCV | Skin detection, classification, preprocessing, explainability |
| Detection | YOLO-style ONNX detector loaded through OpenCV DNN | Localizes skin regions before classification |
| Classification | EfficientNet-B4 (transfer learning) | 27-class skin condition prediction |
| Explainability | Grad-CAM++ | Visual attribution over skin regions |
| Document pipeline | Python-based document extraction stack | Extracts markdown, chunks, and structured medical fields |
| Voice workflow | ElevenLabs browser client + FastAPI tools | Voice-guided patient lookup, scheduling, and upload triggering |
| Database | SQLite, SQLAlchemy, Alembic | Patients, doctors, appointments, and call sessions |
| Frontend | HTML, CSS, JavaScript | Upload UI and floating phone widget |
| Packaging | Docker, Docker Compose | Local and containerized deployment |
| Testing | Pytest | Router and workflow validation |

## SKIN_TELLIGENT

`SKIN_TELLIGENT` is the vision core of PIPI. In this project it is presented as the updated version of the earlier standalone work, with improved overall results.

This project uses `EfficientNet-B4` for transfer learning. In the 27-class setting, training a classifier from scratch did not produce a strong classification report, so transfer learning was used to improve generalization and overall performance.

### Pipeline

| Stage | Technology | What it does |
| --- | --- | --- |
| Detection | ONNX model through OpenCV DNN | Localizes candidate skin regions |
| Classification | EfficientNet-B4 (PyTorch, transfer learning) | Predicts one of 27 skin-condition classes |
| Explainability | Grad-CAM++ | Highlights image regions influencing the prediction |

### Confidence Gating

| Confidence | State | Behaviour |
| --- | --- | --- |
| `>= 80%` | High | Full result with Grad-CAM explainability |
| `60% - 80%` | Uncertain | Result shown with explicit uncertainty |
| `< 60%` | Low confidence | Marked as low confidence |

### Updated Model Performance

The updated vision model used for this project is described as a stronger version of the earlier standalone pipeline, with materially better recall and overall classification quality.

| Metric | v1.0 | v2.0 | Delta |
| --- | --- | --- | --- |
| Accuracy | 71.1% | 82.3% | +11.2% |
| Macro Precision | 67.1% | 80.3% | +13.2% |
| Macro Recall | 77.0% | 91.4% | +14.4% |
| Macro F1 | 70.1% | 84.1% | +14.0% |

For training details and the updated notebook, see the [training notebook](https://www.kaggle.com/code/mehrajalomtapadar/notebooka1e763f51a). For the older detailed standalone vision writeup, see [VISION_README.md](backend/services/SKIN_TELLIGENT/VISION_README.md).

## Pre-Visit Doctor Handoff

PIPI is structured around a pre-visit handoff outcome: by the time the appointment happens, the patient case can already contain the uploaded skin material, extracted report content, and appointment context in one place.

That saves time by reducing repeated intake during the visit and making the case easier to review ahead of consultation.

The current repo already supports the pieces that make this handoff useful:

- skin-image outputs with detection and Grad-CAM artifacts
- parsed document outputs with structured medical fields
- appointment and patient context in the scheduling workflow
- case-based storage under a shared output folder

## Interface Placeholders

Replace these repo-local placeholders with your actual screenshots once you add them to the repository.

![PIPI landing screen placeholder](docs/images/pipi-home-placeholder.svg)

![PIPI uploads and voice widget placeholder](docs/images/pipi-uploads-voice-placeholder.svg)

## What Is In This Repo

- `api/`: FastAPI entrypoint plus routers for vision, documents, and voice-agent tools
- `backend/services/SKIN_TELLIGENT/`: detection, classification, Grad-CAM, and inference code
- `backend/services/DOCPROCESS/`: document-processing clients and utilities
- `backend/database/`: SQLAlchemy models, sessions, and query logic
- `webui/`: upload interface and floating voice widget
- `artifacts/`: model files such as `best_skin_model.pth` and `detector_model.onnx`
- `tests/`: API and workflow tests
- `SEED_DOCTORS.py`: seed data for doctor availability

## Core Workflows

### 1. Skin Image Workflow

- Endpoint: `POST /Skin/SKIN_TELLIGENT`
- Input: image file, optional `patient_id`, optional `x-session-id`
- Output: detection count, classification results, case metadata, and saved artifact paths
- Saved artifacts: original image, boxed detection image, ROI crops, Grad-CAM images, and a classification report

If the detector does not produce a strong region, the pipeline falls back to full-image classification.

### 2. Document Workflow

- Endpoint: `POST /ade/upload`
- Input: `.pdf`, `.png`, `.jpg`, `.jpeg`, plus `report_type` of `lab_report` or `prescription`
- Output: submission metadata, extracted markdown, chunks, medical fields, and saved artifact paths
- Saved artifacts: original upload, parsed markdown, medical fields JSON, chunks JSON, and full result JSON

### 3. Voice-Agent Workflow

The voice tool routes currently support:

- patient lookup
- new patient registration
- doctor search by specialization
- doctor availability lookup
- appointment booking
- appointment cancellation
- patient appointment retrieval
- appointment rescheduling
- in-call upload requests

The upload modal triggered during a call can send:

- `skin_image` to `POST /Skin/SKIN_TELLIGENT`
- `lab_report` to `POST /ade/upload`
- `prescription` to `POST /ade/upload`

## Case Output Layout

When the same `patient_id` or `x-session-id` is reused, skin and document outputs can live under the same case folder:

```text
output/<case_id>/
  skintelligent/
    images/
    detections/
    detection_boxes/
    gradcam/
    reports/
  documents/
    originals/
    parsed/
```

## Repo Layout

```text
api/
  main.py
  routers/
backend/
  database/
  services/
    DOCPROCESS/
    SKIN_TELLIGENT/
config/
artifacts/
webui/
tests/
SEED_DOCTORS.py
Dockerfile
docker-compose.yml
```

## Environment

Create a `.env` file in the repository root. The current repo expects these values when the related workflows are used:

- `OPENAI_API_KEY` for the document extraction pipeline
- `VISION_AGENT_API_KEY` or `VISION_API_KEY` for the document extraction pipeline
- `ELEVENLABS_API_KEY` for voice-agent session startup
- `ELEVENLABS_AGENT_ID` for the browser voice widget
- `DATABASE_URL` is optional and defaults to SQLite at `.langgraph/app.sqlite`

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Run database migrations:

```bash
alembic upgrade head
```

Optional: seed doctor records for the scheduling flow:

```bash
python SEED_DOCTORS.py
```

Start the backend:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

With the backend running, the mounted web UI is available at:

```text
http://127.0.0.1:8000/
```

If you want to serve the static frontend separately:

```bash
python -m http.server 5501 --directory webui
```

## Run With Docker

```bash
docker-compose up --build
```

This repo currently defines:

- `backend` on port `8000`
- `webui` on host port `5502`

## Health Check And Tests

Health check:

```text
GET /health
```

Run tests:

```bash
pytest -q
```

CI is also configured in [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Notes On The Current UI

- the web UI accepts optional `patient_id` and `x-session-id` values to group outputs
- the skin card defaults to a boxed-region preview first and reveals richer details on demand
- the document card defaults to a submission summary first and reveals extracted details on demand
- the page includes a floating voice call button for the voice-agent workflow

## License

This repository is licensed under the MIT License. See [LICENSE](LICENSE).
