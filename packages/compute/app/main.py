"""InsightMirror Compute Service - FastAPI entry point."""

from fastapi import FastAPI

# Import v1 to trigger auto-registration
import app.core.feature.v1  # noqa: F401

from app.api.query import router as query_router
from app.api.admin import router as admin_router

app = FastAPI(
    title="InsightMirror Compute",
    description="Feature calculation and similarity search service",
    version="0.1.0",
)

app.include_router(query_router)
app.include_router(admin_router)


@app.get("/compute/health")
def health():
    return {"status": "ok", "service": "compute"}
