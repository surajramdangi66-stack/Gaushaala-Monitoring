from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import FeedingScheduleModel, FeedingObservationModel
from backend.app.feeding.feeding_engine import get_feeding_engine
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/feeding", tags=["Feeding Compliance"])

class FeedingScheduleCreateSchema(BaseModel):
    camera_id: str = Field("cam-01", max_length=64)
    trough_name: str = Field("Feeder Trough A", max_length=128)
    target_time: str = Field("10:00", pattern=r"^\d{2}:\d{2}$")
    observation_window_seconds: float = Field(5.0, ge=1.0, le=60.0)
    is_active: bool = True

class FeedingCheckNowSchema(BaseModel):
    schedule_id: Optional[int] = None
    camera_id: Optional[str] = "cam-01"
    trough_name: Optional[str] = "Feeder Trough A"

@router.get("/schedules", response_model=List[Dict[str, Any]])
def list_feeding_schedules(db: Session = Depends(get_db)):
    schedules = db.query(FeedingScheduleModel).all()
    return [s.to_dict() for s in schedules]

@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_feeding_schedule(
    payload: FeedingScheduleCreateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    schedule = FeedingScheduleModel(
        camera_id=payload.camera_id,
        trough_name=payload.trough_name,
        target_time=payload.target_time,
        observation_window_seconds=payload.observation_window_seconds,
        is_active=payload.is_active
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule.to_dict()

@router.put("/schedules/{schedule_id}")
def update_feeding_schedule(
    schedule_id: int,
    payload: FeedingScheduleCreateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    sched = db.query(FeedingScheduleModel).filter(FeedingScheduleModel.id == schedule_id).first()
    if not sched:
        raise HTTPException(status_code=404, detail="Feeding schedule not found")

    sched.camera_id = payload.camera_id
    sched.trough_name = payload.trough_name
    sched.target_time = payload.target_time
    sched.observation_window_seconds = payload.observation_window_seconds
    sched.is_active = payload.is_active
    db.commit()
    db.refresh(sched)
    return sched.to_dict()

@router.get("/observations")
def list_feeding_observations(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    records = db.query(FeedingObservationModel).order_by(
        FeedingObservationModel.observed_at.desc()
    ).limit(limit).all()
    return [r.to_dict() for r in records]

@router.post("/check-now")
def trigger_feeding_check_now(
    payload: FeedingCheckNowSchema,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    feeding_engine = get_feeding_engine()
    result = feeding_engine.check_feeding_compliance(
        schedule_id=payload.schedule_id,
        camera_id=payload.camera_id or "cam-01",
        trough_name=payload.trough_name or "Feeder Trough A"
    )
    return result
