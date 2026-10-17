from datetime import datetime, timezone
import json
from sqlalchemy import Column, Integer, String, Boolean, Float, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="operator", nullable=False)
    created_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "created_at": self.created_at
        }

class CattleModel(Base):
    __tablename__ = "cattle_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tag_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=True)
    enclosure_id = Column(String(64), nullable=False, default="cam-01", index=True)
    breed = Column(String(64), nullable=True, default="Gir / Indigenous")
    category = Column(String(32), nullable=False, default="cow")  # "cow", "bull", "calf"
    gender = Column(String(16), nullable=False, default="female")  # "female", "male"
    lactation_stage = Column(String(32), nullable=False, default="dry")  # "milking", "dry", "pregnant", "na"
    health_status = Column(String(32), nullable=False, default="healthy")  # "healthy", "under_treatment", "quarantine"
    inaph_tag = Column(String(32), nullable=True, index=True)  # 12-digit Bharat Pashudhan (INAPH) tag
    intake_source = Column(String(64), nullable=False, default="rescue")  # "rescue", "donated", "born"
    age_years = Column(Float, nullable=True, default=3.0)
    photo_url = Column(String(256), nullable=True)  # Profile image or CCTV snapshot
    mother_tag = Column(String(64), nullable=True)  # Lineage Dam
    father_tag = Column(String(64), nullable=True)  # Lineage Sire
    status = Column(String(32), nullable=False, default="active", index=True)  # "active" | "inactive"
    notes = Column(Text, nullable=True)
    created_at = Column(String(64), default=utc_now_iso, nullable=False)
    updated_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "tag_id": self.tag_id,
            "name": self.name,
            "enclosure_id": self.enclosure_id,
            "breed": self.breed,
            "category": self.category,
            "gender": self.gender,
            "lactation_stage": self.lactation_stage,
            "health_status": self.health_status,
            "inaph_tag": self.inaph_tag,
            "intake_source": self.intake_source,
            "age_years": self.age_years,
            "photo_url": self.photo_url,
            "mother_tag": self.mother_tag,
            "father_tag": self.father_tag,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

class CattleMedicalModel(Base):
    __tablename__ = "cattle_medical_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cattle_id = Column(Integer, nullable=False, index=True)
    tag_id = Column(String(64), nullable=False, index=True)
    record_type = Column(String(32), nullable=False)  # "vaccination", "deworming", "checkup", "treatment"
    title = Column(String(128), nullable=False)
    administered_date = Column(String(32), nullable=False)
    next_due_date = Column(String(32), nullable=True)
    doctor_name = Column(String(128), nullable=True)
    batch_id = Column(String(64), nullable=True, index=True)  # Batch vaccination group ID
    vial_batch_no = Column(String(64), nullable=True)  # Medicine/vaccine manufacturing batch
    dosage = Column(String(64), nullable=True)  # e.g., "5ml SC", "100ml Oral"
    status = Column(String(32), default="completed", nullable=False)  # "completed", "due", "overdue"
    notes = Column(Text, nullable=True)
    created_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "cattle_id": self.cattle_id,
            "tag_id": self.tag_id,
            "record_type": self.record_type,
            "title": self.title,
            "administered_date": self.administered_date,
            "next_due_date": self.next_due_date,
            "doctor_name": self.doctor_name,
            "batch_id": self.batch_id,
            "vial_batch_no": self.vial_batch_no,
            "dosage": self.dosage,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at
        }

class CensusRecordModel(Base):
    __tablename__ = "census_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), unique=True, nullable=False, index=True)
    camera_id = Column(String(64), nullable=False, index=True)
    enclosure_name = Column(String(128), nullable=False)
    census_type = Column(String(64), nullable=False)  # "SCHEDULED_MORNING", "SCHEDULED_EVENING", "MANUAL_DIAGNOSTIC"
    scheduled_time = Column(String(64), nullable=False)  # "05:00", "17:00", "MANUAL"
    executed_at = Column(String(64), default=utc_now_iso, nullable=False)
    expected_count = Column(Integer, nullable=False)
    detected_count = Column(Integer, nullable=True)  # Null if NOT_VERIFIED
    difference = Column(Integer, nullable=True)  # detected - expected, Null if NOT_VERIFIED
    status = Column(String(32), nullable=False, index=True)  # "MATCH", "SHORTFALL", "EXCESS", "NOT_VERIFIED"
    camera_online = Column(Boolean, default=True, nullable=False)
    frames_analyzed = Column(Integer, default=0, nullable=False)
    unique_tracks_count = Column(Integer, default=0, nullable=False)
    evidence_snapshot_url = Column(String(256), nullable=True)  # Optical proof CCTV snapshot
    evidence_hash = Column(String(128), nullable=True)  # Cryptographic SHA-256 integrity hash
    diagnostic_details = Column(Text, nullable=True)

    def to_dict(self):
        details = {}
        if self.diagnostic_details:
            try:
                details = json.loads(self.diagnostic_details)
            except Exception:
                details = {"raw": self.diagnostic_details}
        return {
            "id": self.id,
            "session_id": self.session_id,
            "camera_id": self.camera_id,
            "enclosure_name": self.enclosure_name,
            "census_type": self.census_type,
            "scheduled_time": self.scheduled_time,
            "executed_at": self.executed_at,
            "expected_count": self.expected_count,
            "detected_count": self.detected_count,
            "difference": self.difference,
            "status": self.status,
            "camera_online": self.camera_online,
            "frames_analyzed": self.frames_analyzed,
            "unique_tracks_count": self.unique_tracks_count,
            "evidence_snapshot_url": self.evidence_snapshot_url,
            "evidence_hash": self.evidence_hash,
            "diagnostic_details": details
        }

class SubsidyConfigModel(Base):
    __tablename__ = "subsidy_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cow_rate = Column(Float, default=40.0, nullable=False)
    bull_rate = Column(Float, default=35.0, nullable=False)
    calf_rate = Column(Float, default=20.0, nullable=False)
    sick_rate = Column(Float, default=50.0, nullable=False)
    state_agency_name = Column(String(128), default="State Gau Seva Ayog / Animal Husbandry Dept", nullable=False)
    updated_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "cow_rate": self.cow_rate,
            "bull_rate": self.bull_rate,
            "calf_rate": self.calf_rate,
            "sick_rate": self.sick_rate,
            "state_agency_name": self.state_agency_name,
            "updated_at": self.updated_at
        }

class CensusSettingModel(Base):
    __tablename__ = "census_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    primary_camera_id = Column(String(64), default="cam-01", nullable=False)
    morning_time = Column(String(16), default="05:00", nullable=False)
    evening_time = Column(String(16), default="17:00", nullable=False)
    capture_window_seconds = Column(Float, default=5.0, nullable=False)
    min_stable_frames = Column(Integer, default=3, nullable=False)
    timezone = Column(String(64), default="Asia/Kolkata", nullable=False)
    updated_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "primary_camera_id": self.primary_camera_id,
            "morning_time": self.morning_time,
            "evening_time": self.evening_time,
            "capture_window_seconds": self.capture_window_seconds,
            "min_stable_frames": self.min_stable_frames,
            "timezone": self.timezone,
            "updated_at": self.updated_at
        }

class FeedingScheduleModel(Base):
    __tablename__ = "feeding_schedules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), default="cam-01", nullable=False)
    trough_name = Column(String(128), default="Feeder Trough A", nullable=False)
    target_time = Column(String(16), default="10:00", nullable=False)
    observation_window_seconds = Column(Float, default=5.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "trough_name": self.trough_name,
            "target_time": self.target_time,
            "observation_window_seconds": self.observation_window_seconds,
            "is_active": self.is_active,
            "created_at": self.created_at
        }

class FeedingObservationModel(Base):
    __tablename__ = "feeding_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_id = Column(Integer, nullable=True)
    session_id = Column(String(128), unique=True, nullable=False, index=True)
    camera_id = Column(String(64), nullable=False)
    trough_name = Column(String(128), nullable=False)
    observed_at = Column(String(64), default=utc_now_iso, nullable=False)
    fodder_detected = Column(Boolean, nullable=True)
    status = Column(String(32), nullable=False)  # "FEED_VISIBLE", "MISSED_FEEDING", "NOT_VERIFIED"
    diagnostic_details = Column(Text, nullable=True)
    alert_generated = Column(Boolean, default=False, nullable=False)

    def to_dict(self):
        details = {}
        if self.diagnostic_details:
            try:
                details = json.loads(self.diagnostic_details)
            except Exception:
                details = {"raw": self.diagnostic_details}
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "session_id": self.session_id,
            "camera_id": self.camera_id,
            "trough_name": self.trough_name,
            "observed_at": self.observed_at,
            "fodder_detected": self.fodder_detected,
            "status": self.status,
            "diagnostic_details": details,
            "alert_generated": self.alert_generated
        }

class AlertModel(Base):
    __tablename__ = "alerts"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(128), nullable=True, index=True)
    camera_id = Column(String(64), nullable=False, index=True)
    zone_name = Column(String(128), nullable=False)
    alert_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False, index=True)
    message = Column(Text, nullable=False)
    snapshot_filename = Column(String(256), nullable=True)
    details_json = Column(Text, nullable=True)
    timestamp = Column(String(64), default=utc_now_iso, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_at = Column(String(64), nullable=True)

    def to_dict(self):
        details = {}
        if self.details_json:
            try:
                details = json.loads(self.details_json)
            except Exception:
                details = {"raw": self.details_json}
        return {
            "id": self.id,
            "session_id": self.session_id,
            "camera_id": self.camera_id,
            "zone_name": self.zone_name,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "snapshot_url": f"/api/snapshots/{self.snapshot_filename}" if self.snapshot_filename else None,
            "timestamp": self.timestamp,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "details": details
        }

class ShedZoneConfigModel(Base):
    __tablename__ = "shed_zone_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), unique=True, nullable=False, index=True)
    zones_json = Column(Text, nullable=False)
    updated_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        try:
            zones = json.loads(self.zones_json)
        except Exception:
            zones = {}
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "zones": zones,
            "updated_at": self.updated_at
        }

class CVODispatchModel(Base):
    __tablename__ = "cvo_dispatches"

    id = Column(String(64), primary_key=True)
    camera_id = Column(String(64), nullable=False, index=True)
    shed_name = Column(String(128), nullable=False)
    severity = Column(String(32), default="CRITICAL", nullable=False)
    event_type = Column(String(64), nullable=False)  # "MORTALITY_ALERT", "DISEASE_OUTBREAK_SUSPECTED", "QUARANTINE_BREACH"
    affected_tags = Column(String(256), nullable=True)  # Comma-separated tag IDs
    message = Column(Text, nullable=False)
    snapshot_filename = Column(String(256), nullable=True)
    evidence_hash = Column(String(128), nullable=True)
    dispatched_at = Column(String(64), default=utc_now_iso, nullable=False)
    cvo_status = Column(String(32), default="DISPATCHED", nullable=False)  # "DISPATCHED", "ACKNOWLEDGED", "ATTENDED"
    officer_name = Column(String(128), default="Chief Veterinary Officer (CVO) District Animal Husbandry", nullable=False)
    notes = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "shed_name": self.shed_name,
            "severity": self.severity,
            "event_type": self.event_type,
            "affected_tags": [t.strip() for t in (self.affected_tags or "").split(",") if t.strip()],
            "message": self.message,
            "snapshot_url": f"/api/snapshots/{self.snapshot_filename}" if self.snapshot_filename else None,
            "evidence_hash": self.evidence_hash,
            "dispatched_at": self.dispatched_at,
            "cvo_status": self.cvo_status,
            "officer_name": self.officer_name,
            "notes": self.notes
        }

class FodderSubsidyDailyModel(Base):
    __tablename__ = "fodder_subsidy_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_date = Column(String(32), nullable=False, index=True)  # YYYY-MM-DD
    camera_id = Column(String(64), nullable=False, index=True)
    shed_name = Column(String(128), nullable=False)
    total_headcount = Column(Integer, default=0, nullable=False)
    cow_count = Column(Integer, default=0, nullable=False)
    bull_count = Column(Integer, default=0, nullable=False)
    calf_count = Column(Integer, default=0, nullable=False)
    sick_count = Column(Integer, default=0, nullable=False)
    daily_subsidy_amount = Column(Float, default=0.0, nullable=False)  # In INR (₹)
    attendance_rate = Column(Float, default=100.0, nullable=False)  # Percentage
    verified_by = Column(String(128), default="CCTV YOLO Vision Audit Engine", nullable=False)
    created_at = Column(String(64), default=utc_now_iso, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "report_date": self.report_date,
            "camera_id": self.camera_id,
            "shed_name": self.shed_name,
            "total_headcount": self.total_headcount,
            "cow_count": self.cow_count,
            "bull_count": self.bull_count,
            "calf_count": self.calf_count,
            "sick_count": self.sick_count,
            "daily_subsidy_amount": round(self.daily_subsidy_amount, 2),
            "attendance_rate": round(self.attendance_rate, 1),
            "verified_by": self.verified_by,
            "created_at": self.created_at
        }

