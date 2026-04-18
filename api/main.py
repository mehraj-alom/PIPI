"""
FastAPI application entry-point.

Provides:
  GET  /health           — health check
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.services.SKIN_TELLIGENT.inference import InferencePipeline
from logger import SKIN_TELLIGENT_logger as logger
from api.routers import skintelligent_router

app = FastAPI(
    title="OptimaCare Voice AI Backend",
    description="PIPI, AI-powered healthcare assistant designed to streamline patient " \
                "interactions and enhance care delivery through natural language processing and intelligent automation.",
    version="v0.0.1",
)
app.include_router(skintelligent_router.router)
@app.on_event("startup")
async def startup_event():
    """Initialize the vision pipeline on startup."""
    app.state.vision_pipeline = InferencePipeline()

@app.get("/health", tags=["Utility"])
async def health_check() -> dict:
    return {"status": "ok"}