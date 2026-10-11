import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.app.db.database import init_db
from backend.app.scheduler import get_scheduler
from backend.app.camera.stream_manager import get_stream_manager
from backend.app.api.auth_routes import router as auth_router
from backend.app.api.metrics_routes import router as metrics_router
from backend.app.api.camera_routes import router as camera_router
from backend.app.api.alert_routes import router as alert_router
from backend.app.api.ai_routes import router as ai_router
from backend.app.api.websocket_routes import router as ws_router
from backend.app.api.cattle_routes import router as cattle_router
from backend.app.api.census_routes import router as census_router
from backend.app.api.feeding_routes import router as feeding_router
from backend.app.api.detection_routes import router as detection_router

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup 1: Initialize Database schema and seed baselines
    init_db()

    # Startup 2: Start camera ingestion threads
    manager = get_stream_manager()
    manager.start_all()
    print(">>> Smart Gaushala CCTV AI Vision Pipelines Started Successfully.")

    # Startup 3: Start automated background census & feeding scheduler
    scheduler = get_scheduler()
    await scheduler.start()
    print(">>> Smart Gaushala Automated Census & Feeding Scheduler Started (05:00/17:00 IST).")

    yield

    # Shutdown: Stop scheduler and camera threads cleanly
    await scheduler.stop()
    manager.stop_all()
    print(">>> Smart Gaushala CCTV AI Pipelines and Scheduler Terminated Cleanly.")

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
app.include_router(cattle_router)
app.include_router(census_router)
app.include_router(feeding_router)
app.include_router(detection_router)
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
