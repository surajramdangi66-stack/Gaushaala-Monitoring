import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.camera.stream_manager import get_stream_manager
from backend.app.api.auth_routes import router as auth_router
from backend.app.api.metrics_routes import router as metrics_router
from backend.app.api.camera_routes import router as camera_router
from backend.app.api.alert_routes import router as alert_router
from backend.app.api.ai_routes import router as ai_router
from backend.app.api.websocket_routes import router as ws_router

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start camera ingestion threads
    manager = get_stream_manager()
    manager.start_all()
    print(">>> Smart Gaushala CCTV AI Vision Pipelines Started Successfully.")
    yield
    # Shutdown: Stop camera threads cleanly
    manager.stop_all()
    print(">>> Smart Gaushala CCTV AI Pipelines Terminated Cleanly.")

app = FastAPI(
    title="Smart Gaushala AI CCTV Monitoring System",
    description="Production-grade AI Cattle Surveillance, Multi-object Tracking, Behavioral Analytics, and Alert Platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(auth_router)
app.include_router(metrics_router)
app.include_router(camera_router)
app.include_router(alert_router)
app.include_router(ai_router)
app.include_router(ws_router)

# Mount Frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"})
    return {"message": "Smart Gaushala CCTV Monitoring Backend Online"}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "gaushala-ai-cctv", "version": "2.0.0"}
