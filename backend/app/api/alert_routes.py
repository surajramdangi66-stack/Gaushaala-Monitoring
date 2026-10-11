from fastapi import APIRouter, HTTPException, Depends, Query, Response
from typing import List, Dict, Any, Optional
from pathlib import Path
from backend.app.auth import get_current_user
from backend.app.alerts.alert_engine import get_alert_engine
from backend.app.config import SNAPSHOT_DIR

router = APIRouter(tags=["Alerts"])

@router.get("/api/alerts")
async def list_alerts(
    severity: Optional[str] = Query(None, description="CRITICAL, WARNING, or INFO"),
    camera_id: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    engine = get_alert_engine()
    return engine.get_alerts(severity=severity, camera_id=camera_id, resolved=resolved, limit=limit)

@router.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    engine = get_alert_engine()
    success = engine.resolve_alert(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Alert marked as resolved", "alert_id": alert_id}

@router.post("/api/alerts/clear")
async def clear_alerts(current_user: Dict[str, Any] = Depends(get_current_user)):
    engine = get_alert_engine()
    engine.clear_all()
    return {"message": "All alerts cleared"}

@router.get("/api/snapshots/{filename}")
async def get_snapshot_file(filename: str):
    # Public or token authenticated image access
    safe_name = Path(filename).name
    filepath = SNAPSHOT_DIR / safe_name
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Snapshot image not found")
    with open(filepath, "rb") as f:
        data = f.read()
    return Response(content=data, media_type="image/jpeg")
