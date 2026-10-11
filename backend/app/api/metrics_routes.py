from fastapi import APIRouter, Depends
from typing import Dict, Any
from backend.app.auth import get_current_user
from backend.app.camera.stream_manager import get_stream_manager

router = APIRouter(prefix="/api/metrics", tags=["Metrics"])

@router.get("/summary")
async def get_summary_metrics(current_user: Dict[str, Any] = Depends(get_current_user)):
    manager = get_stream_manager()
    return manager.get_system_metrics()
