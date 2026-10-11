from fastapi import APIRouter, Depends
from typing import Dict, Any
from backend.app.vision.presence_manager import get_presence_manager

router = APIRouter(prefix="/api/detections", tags=["Detections & Quick Access"])

@router.get("/live")
def get_live_detections() -> Dict[str, Any]:
    """
    Returns real-time detection telemetry for all cattle and workers:
    - Lists active entities currently inside on premises
    - Records entry & exit timestamps without duplicate re-detection spam
    - Captures duration and camera node
    """
    mgr = get_presence_manager()
    return mgr.get_live_data()

@router.get("/quick-access")
def get_quick_access_summary() -> Dict[str, Any]:
    """
    Provides quick-access metrics for the home dashboard:
    - Total active workers currently on site
    - Total active cattle / calves currently in view
    - Total entry events recorded today
    - Filtered active worker and cattle lists
    """
    mgr = get_presence_manager()
    data = mgr.get_live_data()
    
    workers = [item for item in data["inside"] if item["entity_type"] == "worker"]
    cattle = [item for item in data["inside"] if item["entity_type"] == "animal"]
    
    return {
        "active_workers_count": data["active_workers"],
        "active_animals_count": data["active_animals"],
        "total_active_inside": data["active_count"],
        "total_entries_today": data["total_entries_today"],
        "active_workers": workers,
        "active_cattle": cattle,
        "recent_events": data["recent_events"]
    }

@router.post("/reset")
def reset_detection_history() -> Dict[str, Any]:
    mgr = get_presence_manager()
    mgr.clear_history()
    return {"message": "Detection history cleared successfully"}
