import csv
import io
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query, Response, status
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


@router.post("/reconcile")
def run_ai_census_reconcile(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Automated AI Reconcile Engine:
    Compares live CCTV headcounts across all camera pipelines against the registered cattle in each enclosure.
    Calculates exact variance (Matching, Missing/Shortfall, or Excess/Unregistered) and daily government feed subsidy.
    """
    stream_mgr = get_stream_manager()
    summaries = stream_mgr.get_all_summaries()

    active_cattle = db.query(CattleModel).filter(CattleModel.status == "active").all()
    total_registered = len(active_cattle)

    # Group registered cattle by enclosure
    reg_by_enclosure: Dict[str, List[Dict[str, Any]]] = {}
    for c in active_cattle:
        reg_by_enclosure.setdefault(c.enclosure_id, []).append(c.to_dict())

    pen_reports = []
    total_live_detected = 0

    for s in summaries:
        cam_id = s["id"]
        cam_name = s["name"]
        is_online = (s["status"] == "online")
        live_count = s["total_cattle"] if is_online else 0
        total_live_detected += live_count

        expected_pen_list = reg_by_enclosure.get(cam_id, [])
        expected_pen_count = len(expected_pen_list)

        diff = live_count - expected_pen_count if is_online else None

        if not is_online:
            pen_status = "STANDBY"
            recommendation = f"{cam_name} is in standby or awaiting hardware video connection."
        elif diff == 0:
            pen_status = "MATCH"
            recommendation = "CCTV headcount matches 100% with registered herd in this pen."
        elif diff < 0:
            pen_status = "SHORTFALL"
            recommendation = f"ALERT: {abs(diff)} cattle missing from {cam_name}. Check perimeter gate or medical bay."
        else:
            pen_status = "EXCESS"
            recommendation = f"NOTICE: {diff} unregistered or visiting cattle detected in {cam_name}."

        pen_reports.append({
            "camera_id": cam_id,
            "enclosure_name": cam_name,
            "camera_online": is_online,
            "expected_count": expected_pen_count,
            "detected_count": live_count if is_online else None,
            "difference": diff,
            "status": pen_status,
            "recommendation": recommendation,
            "registered_tags": [c["tag_id"] for c in expected_pen_list]
        })

    # Herd-wide subsidy calculation (Government standard rate: ₹40/day)
    subsidy_rate = 40
    daily_subsidy_expected = total_registered * subsidy_rate
    daily_subsidy_verified = total_live_detected * subsidy_rate

    overall_diff = total_live_detected - total_registered
    if overall_diff == 0:
        overall_status = "VERIFIED_PERFECT_MATCH"
    elif overall_diff < 0:
        overall_status = "HERD_SHORTFALL"
    else:
        overall_status = "HERD_EXCESS"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_registered_herd": total_registered,
        "total_live_detected": total_live_detected,
        "overall_difference": overall_diff,
        "overall_status": overall_status,
        "government_subsidy": {
            "rate_per_cattle_daily_inr": subsidy_rate,
            "registered_daily_amount_inr": daily_subsidy_expected,
            "verified_daily_amount_inr": daily_subsidy_verified,
            "monthly_projected_amount_inr": daily_subsidy_expected * 30
        },
        "enclosures": pen_reports
    }


@router.get("/export/audit-report")
def export_census_audit_report_csv(
    db: Session = Depends(get_db)
):
    """
    Exports official Government Census Audit Muster Roll as a downloadable CSV.
    Contains time-stamped CCTV verified counts, variance, subsidy entitlement, and supervisor sign-off line.
    """
    records = db.query(CensusRecordModel).order_by(CensusRecordModel.executed_at.desc()).limit(100).all()

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Microsoft Excel
    writer = csv.writer(output)

    writer.writerow(["================================================================"])
    writer.writerow(["SMART GAUSHALA AI CATTLE CENSUS & OFFICIAL AUDIT MUSTER ROLL"])
    writer.writerow([f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST"])
    writer.writerow(["Daily Feed Subsidy Benchmark: Rs. 40.00 / Head / Day"])
    writer.writerow(["================================================================"])
    writer.writerow([])

    writer.writerow([
        "Session ID",
        "Enclosure Name",
        "Camera Node",
        "Scheduled Time",
        "Execution Timestamp (UTC)",
        "Expected Baseline",
        "CCTV Verified Count",
        "Variance / Discrepancy",
        "Verification Status",
        "Frames Analyzed",
        "Camera State",
        "Daily Subsidy Verified (INR)"
    ])

    for r in records:
        det = r.detected_count if r.detected_count is not None else "—"
        diff = r.difference if r.difference is not None else "—"
        subsidy_val = (r.detected_count * 40) if (r.detected_count is not None) else 0

        writer.writerow([
            r.session_id,
            r.enclosure_name,
            r.camera_id,
            r.scheduled_time,
            r.executed_at[:19] if r.executed_at else "",
            r.expected_count,
            det,
            diff,
            r.status,
            r.frames_analyzed,
            "ONLINE" if r.camera_online else "OFFLINE",
            f"{subsidy_val:.2f}"
        ])

    csv_data = output.getvalue()
    filename = f"gaushala_census_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
