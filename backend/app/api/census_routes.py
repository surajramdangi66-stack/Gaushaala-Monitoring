from typing import Optional, Dict, Any
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import CensusRecordModel, CensusSettingModel, CattleModel
from backend.app.census.census_engine import get_census_engine
from backend.app.camera.stream_manager import get_stream_manager
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/census", tags=["Herd Census"])

class CensusSettingsUpdateSchema(BaseModel):
    primary_camera_id: Optional[str] = Field(None, max_length=64)
    morning_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    evening_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    capture_window_seconds: Optional[float] = Field(None, ge=1.0, le=30.0)

class RunDiagnosticSchema(BaseModel):
    camera_id: Optional[str] = None
    capture_window_seconds: Optional[float] = Field(5.0, ge=1.0, le=30.0)

@router.get("/latest")
def get_latest_census(db: Session = Depends(get_db)):
    settings = db.query(CensusSettingModel).first()
    primary_cam = settings.primary_camera_id if settings else "cam-01"
    morning_time = settings.morning_time if settings else "05:00"
    evening_time = settings.evening_time if settings else "17:00"

    # Latest overall record
    latest = db.query(CensusRecordModel).order_by(CensusRecordModel.executed_at.desc()).first()
    # Last morning census
    last_morning = db.query(CensusRecordModel).filter(
        CensusRecordModel.census_type == "SCHEDULED_MORNING"
    ).order_by(CensusRecordModel.executed_at.desc()).first()
    # Last evening census
    last_evening = db.query(CensusRecordModel).filter(
        CensusRecordModel.census_type == "SCHEDULED_EVENING"
    ).order_by(CensusRecordModel.executed_at.desc()).first()

    # Active registered herd
    active_registered = db.query(CattleModel).filter(CattleModel.status == "active").count()

    # Check camera connection state
    stream_mgr = get_stream_manager()
    pipeline = stream_mgr.get_pipeline(primary_cam)
    camera_online = pipeline.source.is_online if (pipeline and pipeline.source) else False

    # Calculate next scheduled run in Asia/Kolkata
    tz = ZoneInfo("Asia/Kolkata")
    now_ist = datetime.now(tz)
    cur_hm = now_ist.strftime("%H:%M")
    
    if cur_hm < morning_time:
        next_run = f"Today at {morning_time} IST"
    elif cur_hm < evening_time:
        next_run = f"Today at {evening_time} IST"
    else:
        next_run = f"Tomorrow at {morning_time} IST"

    return {
        "latest_census": latest.to_dict() if latest else None,
        "last_morning": last_morning.to_dict() if last_morning else None,
        "last_evening": last_evening.to_dict() if last_evening else None,
        "active_registered_herd": active_registered,
        "camera_id": primary_cam,
        "camera_online": camera_online,
        "next_scheduled_run": next_run,
        "settings": settings.to_dict() if settings else {
            "primary_camera_id": "cam-01",
            "morning_time": "05:00",
            "evening_time": "17:00",
            "capture_window_seconds": 5.0,
            "timezone": "Asia/Kolkata"
        }
    }

@router.get("/history")
def get_census_history(
    camera_id: Optional[str] = None,
    census_status: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(CensusRecordModel)
    if camera_id:
        query = query.filter(CensusRecordModel.camera_id == camera_id)
    if census_status:
        query = query.filter(CensusRecordModel.status == census_status)

    total_count = query.count()
    records = query.order_by(CensusRecordModel.executed_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total_count,
        "limit": limit,
        "offset": offset,
        "records": [r.to_dict() for r in records]
    }

@router.get("/settings")
def get_census_settings(db: Session = Depends(get_db)):
    settings = db.query(CensusSettingModel).first()
    if not settings:
        settings = CensusSettingModel(
            primary_camera_id="cam-01",
            morning_time="05:00",
            evening_time="17:00",
            capture_window_seconds=5.0,
            min_stable_frames=3,
            timezone="Asia/Kolkata"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings.to_dict()

@router.put("/settings")
def update_census_settings(
    payload: CensusSettingsUpdateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    settings = db.query(CensusSettingModel).first()
    if not settings:
        settings = CensusSettingModel()
        db.add(settings)

    if payload.primary_camera_id is not None:
        settings.primary_camera_id = payload.primary_camera_id
    if payload.morning_time is not None:
        settings.morning_time = payload.morning_time
    if payload.evening_time is not None:
        settings.evening_time = payload.evening_time
    if payload.capture_window_seconds is not None:
        settings.capture_window_seconds = payload.capture_window_seconds

    settings.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(settings)
    return settings.to_dict()

@router.post("/run-diagnostic", status_code=status.HTTP_200_OK)
def trigger_diagnostic_census(
    payload: RunDiagnosticSchema,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    On-demand diagnostic manual census run.
    Uses actual multi-frame capture window and strict cow detection.
    """
    census_engine = get_census_engine()
    result = census_engine.run_census(
        camera_id=payload.camera_id,
        census_type="MANUAL_DIAGNOSTIC",
        scheduled_time="MANUAL",
        capture_window_seconds=payload.capture_window_seconds
    )
    return result.to_dict()
