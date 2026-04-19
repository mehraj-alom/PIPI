"""
FastAPI application entry-point.

Provides:
  GET  /health           — health check
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.services.SKIN_TELLIGENT.inference import InferencePipeline
from backend.services.output_context import CaseOutputManager
from logger import SKIN_TELLIGENT_logger as logger
from api.routers import skintelligent_router , document_router , voice_agent_router

app = FastAPI(
    title="OptimaCare Voice AI Backend",
    description="PIPI, AI-powered healthcare assistant designed to streamline patient " \
                "interactions and enhance care delivery through natural language processing and intelligent automation.",
    version="v0.0.1",
)

app.mount("/output", StaticFiles(directory="output"), name="output")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://0.0.0.0:5501",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://0.0.0.0:3000",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skintelligent_router.router)
app.include_router(document_router.document_router)
app.include_router(voice_agent_router.router)

# why ? coz  the web UI from the same backend host in production.
# This avoids extra hosting costs and removes cross-origin issues.
app.mount("/", StaticFiles(directory="webui", html=True), name="webui")

@app.on_event("startup")
async def startup_event():
    """Initialize the vision pipeline on startup."""
    app.state.vision_pipeline = InferencePipeline()
    app.state.case_output_manager = CaseOutputManager()

@app.get("/health", tags=["Utility"])
async def health_check() -> dict:
    return {"status": "ok"}