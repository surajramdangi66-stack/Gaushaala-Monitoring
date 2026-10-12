import csv
import io
import os
import uuid
import hashlib
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import CattleModel, CattleMedicalModel, SubsidyConfigModel
from backend.app.camera.stream_manager import get_stream_manager
from backend.app.auth import get_current_user

router = APIRouter(tags=["Cattle Registry & Verification"])

# Directory for photos
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
PHOTOS_DIR = BASE_DIR / "frontend" / "photos"
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------------------------------------------
# PYDANTIC SCHEMAS
# -------------------------------------------------------------

class CattleCreateSchema(BaseModel):
    tag_id: str = Field(..., min_length=2, max_length=64, description="Unique ear tag or collar RFID")
    name: Optional[str] = Field(None, max_length=128)
    enclosure_id: str = Field("cam-01", max_length=64)
    breed: Optional[str] = Field("Gir / Indigenous", max_length=64)
    category: Optional[str] = Field("cow", pattern="^(cow|bull|calf)$")
    gender: Optional[str] = Field("female", pattern="^(female|male)$")
    lactation_stage: Optional[str] = Field("dry", pattern="^(milking|dry|pregnant|na)$")
    health_status: Optional[str] = Field("healthy", pattern="^(healthy|under_treatment|quarantine)$")
    inaph_tag: Optional[str] = Field(None, max_length=32)
    intake_source: Optional[str] = Field("rescue", max_length=64)
    age_years: Optional[float] = Field(3.0, ge=0.0, le=30.0)
    photo_url: Optional[str] = None
    mother_tag: Optional[str] = None
    father_tag: Optional[str] = None
    status: str = Field("active", pattern="^(active|inactive)$")
    notes: Optional[str] = None

class CattleUpdateSchema(BaseModel):
    name: Optional[str] = None
    enclosure_id: Optional[str] = None
    breed: Optional[str] = None
    category: Optional[str] = Field(None, pattern="^(cow|bull|calf)$")
    gender: Optional[str] = Field(None, pattern="^(female|male)$")
    lactation_stage: Optional[str] = Field(None, pattern="^(milking|dry|pregnant|na)$")
    health_status: Optional[str] = Field(None, pattern="^(healthy|under_treatment|quarantine)$")
    inaph_tag: Optional[str] = None
    intake_source: Optional[str] = None
    age_years: Optional[float] = None
    photo_url: Optional[str] = None
    mother_tag: Optional[str] = None
    father_tag: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")
    notes: Optional[str] = None

class MedicalRecordCreateSchema(BaseModel):
    record_type: str = Field("vaccination", pattern="^(vaccination|deworming|checkup|treatment)$")
    title: str = Field(..., min_length=2, max_length=128)
    administered_date: str = Field(...)
    next_due_date: Optional[str] = None
    doctor_name: Optional[str] = None
    batch_id: Optional[str] = None
    vial_batch_no: Optional[str] = None
    dosage: Optional[str] = None
    status: str = Field("completed", pattern="^(completed|due|overdue)$")
    notes: Optional[str] = None

class BatchVaccinationSchema(BaseModel):
    enclosure_id: Optional[str] = None
    cattle_ids: Optional[List[int]] = None
    record_type: str = Field("vaccination", pattern="^(vaccination|deworming|checkup|treatment)$")
    title: str = Field(..., min_length=2, max_length=128)
    administered_date: str = Field(...)
    next_due_date: Optional[str] = None
    doctor_name: Optional[str] = None
    vial_batch_no: Optional[str] = None
    dosage: Optional[str] = None
    status: str = Field("completed", pattern="^(completed|due|overdue)$")
    notes: Optional[str] = None

class SubsidyConfigUpdateSchema(BaseModel):
    cow_rate: Optional[float] = Field(None, ge=0.0)
    bull_rate: Optional[float] = Field(None, ge=0.0)
    calf_rate: Optional[float] = Field(None, ge=0.0)
    sick_rate: Optional[float] = Field(None, ge=0.0)
    state_agency_name: Optional[str] = None
    scheme_title: Optional[str] = None
    disbursing_dept: Optional[str] = None


class BulkCommitPayloadSchema(BaseModel):
    conflict_resolution: Optional[str] = Field("skip", pattern="^(skip|overwrite)$")
    conflict_mode: Optional[str] = None
    rows: Optional[List[Dict[str, Any]]] = None
    items: Optional[List[Dict[str, Any]]] = None

class AutoSchedulePayloadSchema(BaseModel):
    protocol_ids: Optional[List[str]] = None



# -------------------------------------------------------------
# NATIONAL VACCINATION PROTOCOLS (NADCP STANDARDS)
# -------------------------------------------------------------
NATIONAL_PROTOCOLS = [
    {
        "id": "FMD",
        "title": "FMD (खुरपका-मुंहपका) Bi-annual Booster",
        "record_type": "vaccination",
        "interval_months": 6,
        "season_target": "May & November",
        "default_dosage": "3ml SC",
        "description": "Foot-and-Mouth Disease bi-annual prophylactic immunization for entire herd (Cows, Bulls, Calves > 4 mo)."
    },
    {
        "id": "LSD",
        "title": "Lumpy Skin Disease (लंपी त्वचा रोग) Annual Prophylactic",
        "record_type": "vaccination",
        "interval_months": 12,
        "season_target": "Pre-Monsoon (June)",
        "default_dosage": "3ml SC (Goat Pox Vaccine)",
        "description": "Annual pre-monsoon vaccination against capripoxvirus for all indigenous desi cattle."
    },
    {
        "id": "HS_BQ",
        "title": "HS & BQ (गलघोंटू एवं लंगड़ा बुखार) Dual Vaccine",
        "record_type": "vaccination",
        "interval_months": 12,
        "season_target": "Pre-Monsoon (May/June)",
        "default_dosage": "5ml SC",
        "description": "Combined prophylactic against Haemorrhagic Septicaemia and Black Quarter prior to rainy season."
    },
    {
        "id": "DEWORM",
        "title": "Broad-Spectrum Deworming (कृमिनाशक Albendazole/Fenbendazole)",
        "record_type": "deworming",
        "interval_months": 3,
        "season_target": "Quarterly (Jan, Apr, Jul, Oct)",
        "default_dosage": "100ml Oral Liquid",
        "description": "Quarterly rotational deworming against gastrointestinal nematodes, liver fluke, and tapeworms."
    },
    {
        "id": "BRUCELLA",
        "title": "Brucellosis S19 Calfhood Vaccine",
        "record_type": "vaccination",
        "interval_months": 0,  # One-time
        "season_target": "Calf Age 4-8 Months",
        "default_dosage": "2ml SC",
        "description": "Mandatory one-time lifetime vaccination for female calves aged between 4 and 8 months."
    }
]

# -------------------------------------------------------------
# CATTLE REGISTRY CRUD & LISTING
# -------------------------------------------------------------

@router.get("/api/cattle", response_model=List[Dict[str, Any]])
def list_cattle(
    status_filter: Optional[str] = Query(None, alias="status"),
    enclosure_id: Optional[str] = None,
    category: Optional[str] = None,
    health_status: Optional[str] = None,
    lactation_stage: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(CattleModel)
    if status_filter:
        query = query.filter(CattleModel.status == status_filter)
    if enclosure_id:
        query = query.filter(CattleModel.enclosure_id == enclosure_id)
    if category:
        query = query.filter(CattleModel.category == category)
    if health_status:
        query = query.filter(CattleModel.health_status == health_status)
    if lactation_stage:
        query = query.filter(CattleModel.lactation_stage == lactation_stage)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            (CattleModel.tag_id.ilike(search_fmt)) |
            (CattleModel.name.ilike(search_fmt)) |
            (CattleModel.breed.ilike(search_fmt)) |
            (CattleModel.inaph_tag.ilike(search_fmt))
        )
    cattle_list = query.order_by(CattleModel.created_at.desc()).all()
    return [c.to_dict() for c in cattle_list]


@router.get("/api/cattle/summary")
def get_cattle_summary(db: Session = Depends(get_db)):
    """Computes category-wise herd counts and tiered daily/monthly government subsidy."""
    all_cattle = db.query(CattleModel).all()
    active_count = sum(1 for c in all_cattle if c.status == "active")
    inactive_count = sum(1 for c in all_cattle if c.status == "inactive")

    # Load Subsidy Configuration
    sub_config = db.query(SubsidyConfigModel).first()
    cow_rate = sub_config.cow_rate if sub_config else 40.0
    bull_rate = sub_config.bull_rate if sub_config else 35.0
    calf_rate = sub_config.calf_rate if sub_config else 20.0
    sick_rate = sub_config.sick_rate if sub_config else 50.0
    agency_name = sub_config.state_agency_name if sub_config else "State Gau Seva Ayog"

    by_enclosure: Dict[str, int] = {}
    by_category = {"cow": 0, "bull": 0, "calf": 0}
    by_lactation = {"milking": 0, "dry": 0, "pregnant": 0, "na": 0}
    by_health = {"healthy": 0, "under_treatment": 0, "quarantine": 0}

    for c in all_cattle:
        if c.status == "active":
            by_enclosure[c.enclosure_id] = by_enclosure.get(c.enclosure_id, 0) + 1
            cat = getattr(c, "category", "cow") or "cow"
            by_category[cat] = by_category.get(cat, 0) + 1
            lac = getattr(c, "lactation_stage", "dry") or "dry"
            by_lactation[lac] = by_lactation.get(lac, 0) + 1
            hea = getattr(c, "health_status", "healthy") or "healthy"
            by_health[hea] = by_health.get(hea, 0) + 1

    # Tiered Subsidy calculation:
    # Healthy cows get cow_rate; Bulls get bull_rate; Calves get calf_rate.
    # Sick/under_treatment/quarantine animals receive special infirm diet rate (sick_rate).
    cow_count = by_category.get("cow", 0)
    bull_count = by_category.get("bull", 0)
    calf_count = by_category.get("calf", 0)
    sick_count = by_health.get("under_treatment", 0) + by_health.get("quarantine", 0)

    # Base allocation
    cow_daily = cow_count * cow_rate
    bull_daily = bull_count * bull_rate
    calf_daily = calf_count * calf_rate
    # Sick allowance delta: if sick_rate > cow_rate, add difference for sick animals
    sick_allowance = max(0.0, (sick_rate - cow_rate) * sick_count)

    daily_total = cow_daily + bull_daily + calf_daily + sick_allowance
    monthly_total = daily_total * 30

    return {
        "total_registered": len(all_cattle),
        "active_herd": active_count,
        "inactive_herd": inactive_count,
        "by_enclosure": by_enclosure,
        "by_category": by_category,
        "by_lactation": by_lactation,
        "by_health": by_health,
        "subsidy": {
            "agency_name": agency_name,
            "rates": {
                "cow_rate_inr": cow_rate,
                "bull_rate_inr": bull_rate,
                "calf_rate_inr": calf_rate,
                "sick_rate_inr": sick_rate
            },
            "itemized_daily_inr": {
                "cows": cow_daily,
                "bulls": bull_daily,
                "calves": calf_daily,
                "sick_allowance": sick_allowance
            },
            "daily_total_inr": round(daily_total, 2),
            "monthly_total_inr": round(monthly_total, 2)
        }
    }


@router.get("/api/cattle/subsidy-config")
def get_subsidy_config(db: Session = Depends(get_db)):
    config = db.query(SubsidyConfigModel).first()
    if not config:
        config = SubsidyConfigModel()
        db.add(config)
        db.commit()
        db.refresh(config)
    return config.to_dict()


@router.put("/api/cattle/subsidy-config")
def update_subsidy_config(
    payload: SubsidyConfigUpdateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    config = db.query(SubsidyConfigModel).first()
    if not config:
        config = SubsidyConfigModel()
        db.add(config)

    if payload.cow_rate is not None:
        config.cow_rate = payload.cow_rate
    if payload.bull_rate is not None:
        config.bull_rate = payload.bull_rate
    if payload.calf_rate is not None:
        config.calf_rate = payload.calf_rate
    if payload.sick_rate is not None:
        config.sick_rate = payload.sick_rate
    if payload.state_agency_name is not None:
        config.state_agency_name = payload.state_agency_name.strip()
    elif payload.scheme_title is not None:
        agency_val = payload.scheme_title.strip()
        if payload.disbursing_dept:
            agency_val += f" ({payload.disbursing_dept.strip()})"
        config.state_agency_name = agency_val


    config.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(config)
    return config.to_dict()


@router.post("/api/cattle", status_code=status.HTTP_201_CREATED)
def register_cattle(
    payload: CattleCreateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    clean_tag = payload.tag_id.strip()
    existing = db.query(CattleModel).filter(CattleModel.tag_id == clean_tag).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cattle tag ID '{payload.tag_id}' is already registered."
        )

    now = datetime.now(timezone.utc).isoformat()
    cattle = CattleModel(
        tag_id=clean_tag,
        name=payload.name.strip() if payload.name else None,
        enclosure_id=payload.enclosure_id.strip(),
        breed=payload.breed.strip() if payload.breed else "Gir / Indigenous",
        category=payload.category or "cow",
        gender=payload.gender or "female",
        lactation_stage=payload.lactation_stage or "dry",
        health_status=payload.health_status or "healthy",
        inaph_tag=payload.inaph_tag.strip() if payload.inaph_tag else None,
        intake_source=payload.intake_source or "rescue",
        age_years=payload.age_years or 3.0,
        photo_url=payload.photo_url,
        mother_tag=payload.mother_tag.strip() if payload.mother_tag else None,
        father_tag=payload.father_tag.strip() if payload.father_tag else None,
        status=payload.status,
        notes=payload.notes,
        created_at=now,
        updated_at=now
    )
    db.add(cattle)
    db.commit()
    db.refresh(cattle)
    return cattle.to_dict()


@router.get("/api/cattle/{cattle_id:int}")
def get_cattle_detail(cattle_id: int, db: Session = Depends(get_db)):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")
    data = cattle.to_dict()

    med_records = db.query(CattleMedicalModel).filter(
        CattleMedicalModel.cattle_id == cattle_id
    ).order_by(CattleMedicalModel.administered_date.desc()).all()
    data["medical_history"] = [m.to_dict() for m in med_records]
    return data


@router.put("/api/cattle/{cattle_id:int}")
def update_cattle(
    cattle_id: int,
    payload: CattleUpdateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    if payload.name is not None:
        cattle.name = payload.name.strip()
    if payload.enclosure_id is not None:
        cattle.enclosure_id = payload.enclosure_id.strip()
    if payload.breed is not None:
        cattle.breed = payload.breed.strip()
    if payload.category is not None:
        cattle.category = payload.category
    if payload.gender is not None:
        cattle.gender = payload.gender
    if payload.lactation_stage is not None:
        cattle.lactation_stage = payload.lactation_stage
    if payload.health_status is not None:
        cattle.health_status = payload.health_status
    if payload.inaph_tag is not None:
        cattle.inaph_tag = payload.inaph_tag.strip() if payload.inaph_tag else None
    if payload.intake_source is not None:
        cattle.intake_source = payload.intake_source
    if payload.age_years is not None:
        cattle.age_years = payload.age_years
    if payload.photo_url is not None:
        cattle.photo_url = payload.photo_url
    if payload.mother_tag is not None:
        cattle.mother_tag = payload.mother_tag.strip() if payload.mother_tag else None
    if payload.father_tag is not None:
        cattle.father_tag = payload.father_tag.strip() if payload.father_tag else None
    if payload.status is not None:
        cattle.status = payload.status
    if payload.notes is not None:
        cattle.notes = payload.notes

    cattle.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(cattle)
    return cattle.to_dict()


@router.patch("/api/cattle/{cattle_id:int}/status")
def toggle_cattle_status(
    cattle_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    cattle.status = "inactive" if cattle.status == "active" else "active"
    cattle.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(cattle)
    return cattle.to_dict()


@router.delete("/api/cattle/{cattle_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cattle(
    cattle_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    db.query(CattleMedicalModel).filter(CattleMedicalModel.cattle_id == cattle_id).delete()
    db.delete(cattle)
    db.commit()
    return None

# -------------------------------------------------------------
# PHOTO UPLOAD & 1-CLICK CCTV SNAPSHOT PROFILE PHOTO
# -------------------------------------------------------------

@router.post("/api/cattle/{cattle_id:int}/photo")
async def upload_cattle_photo(
    cattle_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    ext = Path(file.filename or "photo.jpg").suffix or ".jpg"
    filename = f"cow_{cattle.id}_{int(datetime.now().timestamp())}{ext}"
    filepath = PHOTOS_DIR / filename

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    rel_url = f"/static/photos/{filename}"
    cattle.photo_url = rel_url
    cattle.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(cattle)
    return {"success": True, "photo_url": rel_url}


@router.post("/api/cattle/{cattle_id:int}/capture-cctv-photo")
def capture_cctv_photo(
    cattle_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Captures live CCTV camera frame from cow's enclosure and assigns as profile photo."""
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    target_cam = cattle.enclosure_id or "cam-01"
    stream_mgr = get_stream_manager()
    pipeline = stream_mgr.get_pipeline(target_cam)

    if not pipeline or not pipeline.source or pipeline.source.last_frame is None:
        raise HTTPException(status_code=503, detail=f"Camera feed '{target_cam}' is not online or ready.")

    import cv2
    frame = pipeline.source.last_frame
    filename = f"cctv_cow_{cattle.id}_{int(datetime.now().timestamp())}.jpg"
    filepath = PHOTOS_DIR / filename
    cv2.imwrite(str(filepath), frame)

    rel_url = f"/static/photos/{filename}"
    cattle.photo_url = rel_url
    cattle.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(cattle)
    return {"success": True, "photo_url": rel_url, "source_camera": target_cam}

# -------------------------------------------------------------
# SAMPLE CSV TEMPLATE DOWNLOAD FOR BULK REGISTRATION
# -------------------------------------------------------------

@router.get("/api/cattle/template/csv")
def download_cattle_csv_template():
    """Returns a standardized CSV template with example rows for bulk cattle registration."""
    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel compatibility
    writer = csv.writer(output)

    writer.writerow([
        "Tag ID / RFID",
        "INAPH National ID",
        "Name / Identifier",
        "Enclosure Pen",
        "Breed",
        "Category",
        "Gender",
        "Lactation Stage",
        "Health Status",
        "Age (Years)",
        "Mother Tag (Dam)",
        "Father Tag (Sire)",
        "Intake Source",
        "Notes"
    ])

    # Sample rows demonstrating valid values
    writer.writerow([
        "GAU-DEMO-01",
        "900100234561",
        "Kamdhenu",
        "cam-01",
        "Gir Indigenous",
        "cow",
        "female",
        "milking",
        "healthy",
        "4.5",
        "GAU-001",
        "GAU-SIRE-9",
        "dairy",
        "High milk yield indigenous milch cow"
    ])
    writer.writerow([
        "GAU-DEMO-02",
        "900100234562",
        "Nandi Bull",
        "cam-02",
        "Sahiwal",
        "bull",
        "male",
        "na",
        "healthy",
        "5.0",
        "",
        "",
        "rescue",
        "Pedigree breeding bull"
    ])
    writer.writerow([
        "GAU-DEMO-03",
        "900100234563",
        "Gauri Calf",
        "cam-01",
        "Tharparkar",
        "calf",
        "female",
        "na",
        "healthy",
        "0.8",
        "GAU-DEMO-01",
        "GAU-DEMO-02",
        "birth",
        "Under NADCP deworming protocol"
    ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cattle_registration_template.csv"}
    )


# -------------------------------------------------------------
# INTERACTIVE DRY-RUN BULK VALIDATION & COMMIT
# -------------------------------------------------------------

@router.post("/api/cattle/bulk-validate")
async def bulk_validate_cattle_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Dry-run validation of uploaded CSV. Parses rows, checks duplicate tags in DB,
    and returns an interactive preview with validation status (VALID, CONFLICT, ERROR).
    """
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except Exception:
        text = contents.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    existing_tags = set(r[0] for r in db.query(CattleModel.tag_id).all())

    preview_rows = []
    valid_count = 0
    conflict_count = 0
    error_count = 0

    row_index = 1
    for raw_row in reader:
        # Create normalized lowercase key mapping for robust header resolution
        row = {str(k).strip().lower(): (v or "") for k, v in raw_row.items() if k is not None}

        tag_id = (row.get("tag id / rfid") or row.get("tag_id") or row.get("tag id") or row.get("tag") or "").strip()
        name = (row.get("name / identifier") or row.get("name") or "").strip() or None
        enclosure = (row.get("enclosure pen") or row.get("enclosure_id") or row.get("enclosure") or row.get("pen") or "cam-01").strip()
        breed = (row.get("breed") or row.get("indigenous breed") or "Gir / Indigenous").strip()
        category = (row.get("category") or "cow").strip().lower()
        if category not in ["cow", "bull", "calf"]:
            category = "cow"
        gender = (row.get("gender") or "female").strip().lower()
        if gender not in ["female", "male"]:
            gender = "female"
        lactation = (row.get("lactation stage") or row.get("lactation_stage") or "dry").strip().lower()
        if lactation not in ["milking", "dry", "pregnant", "na"]:
            lactation = "dry"
        health = (row.get("health status") or row.get("health_status") or "healthy").strip().lower()
        if health not in ["healthy", "under_treatment", "quarantine"]:
            health = "healthy"
        inaph = (row.get("inaph national id") or row.get("inaph_tag") or row.get("inaph") or "").strip() or None
        mother_tag = (row.get("mother tag (dam)") or row.get("mother_tag") or row.get("dam") or row.get("mother tag") or "").strip() or None
        father_tag = (row.get("father tag (sire)") or row.get("father_tag") or row.get("sire") or row.get("father tag") or "").strip() or None
        intake = (row.get("intake source") or row.get("intake_source") or "rescue").strip()
        try:
            age_raw = row.get("age (years)") or row.get("age_years") or row.get("age") or "3.0"
            age = float(age_raw)
        except Exception:
            age = 3.0

        notes = (row.get("notes") or row.get("note") or "").strip() or None

        errors = []
        if not tag_id:
            errors.append("Missing Tag ID")
        if len(tag_id) > 64:
            errors.append("Tag ID exceeds 64 chars")

        status_flag = "VALID"
        if errors:
            status_flag = "ERROR"
            error_count += 1
        elif tag_id in existing_tags:
            status_flag = "CONFLICT"
            conflict_count += 1
        else:
            valid_count += 1

        preview_rows.append({
            "row_index": row_index,
            "row_num": row_index,
            "status": status_flag,
            "validation_status": status_flag,
            "errors": errors,
            "detail": ", ".join(errors) if errors else ("Duplicate tag found in database" if status_flag == "CONFLICT" else "Valid and ready for import"),
            "tag_id": tag_id,
            "inaph_tag": inaph,
            "name": name,
            "enclosure_id": enclosure,
            "breed": breed,
            "category": category,
            "gender": gender,
            "lactation_stage": lactation,
            "health_status": health,
            "age_years": age,
            "mother_tag": mother_tag,
            "father_tag": father_tag,
            "intake_source": intake,
            "notes": notes
        })
        row_index += 1

    return {
        "success": True,
        "total_rows": len(preview_rows),
        "valid_count": valid_count,
        "valid_rows": valid_count,
        "conflict_count": conflict_count,
        "conflict_rows": conflict_count,
        "error_count": error_count,
        "error_rows": error_count,
        "rows": preview_rows
    }


@router.post("/api/cattle/bulk-commit", status_code=status.HTTP_201_CREATED)
def bulk_commit_cattle(
    payload: BulkCommitPayloadSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Commits validated rows to DB with specified conflict resolution (skip or overwrite)."""
    now = datetime.now(timezone.utc).isoformat()
    imported = 0
    updated = 0
    skipped = 0

    resolution = payload.conflict_resolution or payload.conflict_mode or "skip"
    target_rows = payload.rows or payload.items or []

    for item in target_rows:
        tag_id = (item.get("tag_id") or "").strip()
        if not tag_id:
            skipped += 1
            continue

        existing = db.query(CattleModel).filter(CattleModel.tag_id == tag_id).first()
        if existing:
            if resolution == "overwrite":
                existing.name = item.get("name") or existing.name
                existing.enclosure_id = item.get("enclosure_id") or existing.enclosure_id
                existing.breed = item.get("breed") or existing.breed
                existing.category = item.get("category") or existing.category
                existing.gender = item.get("gender") or existing.gender
                existing.lactation_stage = item.get("lactation_stage") or existing.lactation_stage
                existing.health_status = item.get("health_status") or existing.health_status
                existing.inaph_tag = item.get("inaph_tag") or existing.inaph_tag
                existing.mother_tag = item.get("mother_tag") or existing.mother_tag
                existing.father_tag = item.get("father_tag") or existing.father_tag
                existing.intake_source = item.get("intake_source") or existing.intake_source
                existing.age_years = item.get("age_years", existing.age_years)
                existing.notes = item.get("notes") or existing.notes
                existing.updated_at = now
                updated += 1
            else:
                skipped += 1
            continue

        c = CattleModel(
            tag_id=tag_id,
            name=item.get("name"),
            enclosure_id=item.get("enclosure_id") or "cam-01",
            breed=item.get("breed") or "Gir / Indigenous",
            category=item.get("category") or "cow",
            gender=item.get("gender") or "female",
            lactation_stage=item.get("lactation_stage") or "dry",
            health_status=item.get("health_status") or "healthy",
            inaph_tag=item.get("inaph_tag"),
            mother_tag=item.get("mother_tag"),
            father_tag=item.get("father_tag"),
            intake_source=item.get("intake_source") or "rescue",
            age_years=item.get("age_years") or 3.0,
            status="active",
            notes=item.get("notes"),
            created_at=now,
            updated_at=now
        )
        db.add(c)
        imported += 1

    db.commit()
    return {
        "success": True,
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "total_processed": len(target_rows)
    }


# -------------------------------------------------------------
# ADVANCED MEDICAL & BATCH VACCINATION
# -------------------------------------------------------------

@router.get("/api/cattle/medical/protocols")
def get_vaccination_protocols():
    """Returns National Animal Disease Control Programme (NADCP) standard protocols."""
    return {"protocols": NATIONAL_PROTOCOLS}


@router.get("/api/cattle/medical/coverage-summary")
def get_herd_immunity_coverage(db: Session = Depends(get_db)):
    """
    Computes herd immunity coverage percentages across active cattle for key NADCP diseases:
    FMD (Foot & Mouth), LSD (Lumpy Skin), HS/BQ (Haemorrhagic Septicaemia/Black Quarter), and Deworming.
    """
    active_cattle = db.query(CattleModel).filter(CattleModel.status == "active").all()
    total_herd = len(active_cattle)

    if total_herd == 0:
        return {
            "total_herd": 0,
            "overall_immunity_score": 0.0,
            "fmd": {"covered": 0, "pct": 0.0, "status": "INACTIVE"},
            "lsd": {"covered": 0, "pct": 0.0, "status": "INACTIVE"},
            "hsbq": {"covered": 0, "pct": 0.0, "status": "INACTIVE"},
            "deworming": {"covered": 0, "pct": 0.0, "status": "INACTIVE"}
        }

    # Fetch all completed medical records
    completed_records = db.query(CattleMedicalModel).filter(
        CattleMedicalModel.status == "completed"
    ).all()

    # Map completed records by cattle_id
    fmd_cattle_ids = set()
    lsd_cattle_ids = set()
    hsbq_cattle_ids = set()
    deworm_cattle_ids = set()

    for r in completed_records:
        title_lower = (r.title or "").lower()
        if "fmd" in title_lower or "foot" in title_lower:
            fmd_cattle_ids.add(r.cattle_id)
        if "lsd" in title_lower or "lumpy" in title_lower:
            lsd_cattle_ids.add(r.cattle_id)
        if "hs" in title_lower or "bq" in title_lower or "septicaemia" in title_lower or "quarter" in title_lower:
            hsbq_cattle_ids.add(r.cattle_id)
        if "deworm" in title_lower or "anthelmintic" in title_lower or "alben" in title_lower or "ivermectin" in title_lower:
            deworm_cattle_ids.add(r.cattle_id)

    active_id_set = set(c.id for c in active_cattle)

    fmd_cov = len(fmd_cattle_ids.intersection(active_id_set))
    lsd_cov = len(lsd_cattle_ids.intersection(active_id_set))
    hsbq_cov = len(hsbq_cattle_ids.intersection(active_id_set))
    deworm_cov = len(deworm_cattle_ids.intersection(active_id_set))

    fmd_pct = round((fmd_cov / total_herd) * 100, 1)
    lsd_pct = round((lsd_cov / total_herd) * 100, 1)
    hsbq_pct = round((hsbq_cov / total_herd) * 100, 1)
    deworm_pct = round((deworm_cov / total_herd) * 100, 1)

    overall_score = round((fmd_pct + lsd_pct + hsbq_pct + deworm_pct) / 4, 1)

    return {
        "total_herd": total_herd,
        "overall_immunity_score": overall_score,
        "fmd": {
            "covered": fmd_cov,
            "target": total_herd,
            "pct": fmd_pct,
            "status": "OPTIMAL" if fmd_pct >= 85 else ("MODERATE" if fmd_pct >= 50 else "VULNERABLE")
        },
        "lsd": {
            "covered": lsd_cov,
            "target": total_herd,
            "pct": lsd_pct,
            "status": "OPTIMAL" if lsd_pct >= 85 else ("MODERATE" if lsd_pct >= 50 else "VULNERABLE")
        },
        "hsbq": {
            "covered": hsbq_cov,
            "target": total_herd,
            "pct": hsbq_pct,
            "status": "OPTIMAL" if hsbq_pct >= 85 else ("MODERATE" if hsbq_pct >= 50 else "VULNERABLE")
        },
        "deworming": {
            "covered": deworm_cov,
            "target": total_herd,
            "pct": deworm_pct,
            "status": "OPTIMAL" if deworm_pct >= 85 else ("MODERATE" if deworm_pct >= 50 else "VULNERABLE")
        }
    }


@router.post("/api/cattle/medical/batch", status_code=status.HTTP_201_CREATED)
def batch_vaccinate_herd(
    payload: BatchVaccinationSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Logs vaccine or health treatment for an entire pen or list of cattle in 1 transaction."""
    query = db.query(CattleModel).filter(CattleModel.status == "active")
    if payload.cattle_ids:
        query = query.filter(CattleModel.id.in_(payload.cattle_ids))
    elif payload.enclosure_id and payload.enclosure_id != "all":
        query = query.filter(CattleModel.enclosure_id == payload.enclosure_id)

    target_cattle = query.all()
    if not target_cattle:
        raise HTTPException(status_code=400, detail="No active cattle found matching target criteria.")

    batch_uuid = f"BATCH-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()

    created_records = []
    for c in target_cattle:
        rec = CattleMedicalModel(
            cattle_id=c.id,
            tag_id=c.tag_id,
            record_type=payload.record_type,
            title=payload.title.strip(),
            administered_date=payload.administered_date.strip(),
            next_due_date=payload.next_due_date.strip() if payload.next_due_date else None,
            doctor_name=payload.doctor_name.strip() if payload.doctor_name else None,
            batch_id=batch_uuid,
            vial_batch_no=payload.vial_batch_no.strip() if payload.vial_batch_no else None,
            dosage=payload.dosage.strip() if payload.dosage else None,
            status=payload.status,
            notes=payload.notes,
            created_at=now_iso
        )
        db.add(rec)
        created_records.append(rec)

    db.commit()
    return {
        "success": True,
        "batch_id": batch_uuid,
        "vaccinated_count": len(created_records),
        "vaccinated_cattle_count": len(created_records),
        "target_pen": payload.enclosure_id or "selected_tags",
        "title": payload.title
    }


@router.post("/api/cattle/medical/auto-schedule")
def auto_schedule_herd_protocols(
    payload: Optional[AutoSchedulePayloadSchema] = None,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Generates scheduled due dates for the entire herd based on National Veterinary protocols."""
    active_cattle = db.query(CattleModel).filter(CattleModel.status == "active").all()
    if not active_cattle:
        raise HTTPException(status_code=400, detail="No active cattle in herd registry.")

    target_protocols = NATIONAL_PROTOCOLS
    if payload and payload.protocol_ids:
        target_protocols = [p for p in NATIONAL_PROTOCOLS if p["id"] in payload.protocol_ids]

    now = datetime.now()
    now_iso = datetime.now(timezone.utc).isoformat()
    scheduled_count = 0

    for proto in target_protocols:
        if proto["interval_months"] <= 0:
            continue
        due_date = (now + timedelta(days=proto["interval_months"] * 30)).strftime("%Y-%m-%d")

        for c in active_cattle:
            # Check if this protocol is already scheduled and pending
            existing = db.query(CattleMedicalModel).filter(
                CattleMedicalModel.cattle_id == c.id,
                CattleMedicalModel.title == proto["title"],
                CattleMedicalModel.status == "due"
            ).first()
            if existing:
                continue

            rec = CattleMedicalModel(
                cattle_id=c.id,
                tag_id=c.tag_id,
                record_type=proto["record_type"],
                title=proto["title"],
                administered_date=now.strftime("%Y-%m-%d"),
                next_due_date=due_date,
                dosage=proto["default_dosage"],
                status="due",
                notes=f"Auto-generated via National Protocol: {proto['description']}",
                created_at=now_iso
            )
            db.add(rec)
            scheduled_count += 1

    db.commit()
    return {
        "success": True,
        "scheduled_entries": scheduled_count,
        "records_created": scheduled_count,
        "active_herd_size": len(active_cattle),
        "unique_cattle_scheduled": len(active_cattle)
    }



@router.get("/api/cattle/medical/notifications")
def get_medical_notifications(db: Session = Depends(get_db)):
    """Prepares formatted WhatsApp and SMS message queue for overdue and upcoming vaccinations."""
    records = db.query(CattleMedicalModel).filter(CattleMedicalModel.status.in_(["due", "overdue"])).all()
    today_str = datetime.now().strftime("%Y-%m-%d")

    overdue_items = []
    upcoming_items = []

    for r in records:
        is_overdue = bool(r.next_due_date and r.next_due_date < today_str)
        item = {
            "id": r.id,
            "tag_id": r.tag_id,
            "title": r.title,
            "due_date": r.next_due_date,
            "doctor": r.doctor_name or "Assigned Veterinarian",
            "is_overdue": is_overdue
        }
        if is_overdue:
            overdue_items.append(item)
        else:
            upcoming_items.append(item)

    # Prepare formatted WhatsApp dispatch text
    wa_message = f"🚨 *GAUSHALA VETERINARY HEALTH ALERT* 🚨\nDate: {today_str}\n\n"
    if overdue_items:
        wa_message += f"⚠️ *OVERDUE VACCINES ({len(overdue_items)} HEADS)*:\n"
        for o in overdue_items[:5]:
            wa_message += f"• Tag {o['tag_id']}: {o['title']} (Due: {o['due_date']})\n"
        if len(overdue_items) > 5:
            wa_message += f"... and {len(overdue_items) - 5} more.\n"
        wa_message += "\n"

    if upcoming_items:
        wa_message += f"📅 *UPCOMING DUE THIS MONTH ({len(upcoming_items)} HEADS)*:\n"
        for u in upcoming_items[:5]:
            wa_message += f"• Tag {u['tag_id']}: {u['title']} (Due: {u['due_date']})\n"

    import urllib.parse
    encoded_wa = urllib.parse.quote(wa_message)

    return {
        "overdue_count": len(overdue_items),
        "upcoming_count": len(upcoming_items),
        "overdue_list": overdue_items[:20],
        "upcoming_list": upcoming_items[:20],
        "overdue_alerts": overdue_items,
        "due_soon_alerts": upcoming_items,
        "formatted_whatsapp_text": wa_message,
        "whatsapp_click_url": f"https://api.whatsapp.com/send?text={encoded_wa}"
    }


@router.get("/api/cattle/medical/alerts")
def get_medical_alerts(db: Session = Depends(get_db)):
    records = db.query(CattleMedicalModel).order_by(CattleMedicalModel.next_due_date.asc()).all()
    today_str = datetime.now().strftime("%Y-%m-%d")

    upcoming = []
    completed = []
    for r in records:
        r_dict = r.to_dict()
        if r.next_due_date:
            if r.next_due_date < today_str and r.status != "completed":
                r_dict["alert_status"] = "OVERDUE"
            elif r.next_due_date >= today_str:
                r_dict["alert_status"] = "UPCOMING"
            else:
                r_dict["alert_status"] = "COMPLETED"
        else:
            r_dict["alert_status"] = "COMPLETED"

        if r_dict["alert_status"] in ["OVERDUE", "UPCOMING"]:
            upcoming.append(r_dict)
        else:
            completed.append(r_dict)

    return {
        "due_soon_count": len(upcoming),
        "upcoming_records": upcoming[:30],
        "recent_completed": completed[:10]
    }


@router.get("/api/cattle/{cattle_id:int}/medical")
def get_cattle_medical_history(cattle_id: int, db: Session = Depends(get_db)):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    records = db.query(CattleMedicalModel).filter(
        CattleMedicalModel.cattle_id == cattle_id
    ).order_by(CattleMedicalModel.administered_date.desc()).all()
    return [r.to_dict() for r in records]


@router.post("/api/cattle/{cattle_id:int}/medical", status_code=status.HTTP_201_CREATED)
def add_cattle_medical_record(
    cattle_id: int,
    payload: MedicalRecordCreateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    rec = CattleMedicalModel(
        cattle_id=cattle_id,
        tag_id=cattle.tag_id,
        record_type=payload.record_type,
        title=payload.title.strip(),
        administered_date=payload.administered_date.strip(),
        next_due_date=payload.next_due_date.strip() if payload.next_due_date else None,
        doctor_name=payload.doctor_name.strip() if payload.doctor_name else None,
        batch_id=payload.batch_id,
        vial_batch_no=payload.vial_batch_no,
        dosage=payload.dosage,
        status=payload.status,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec.to_dict()


@router.delete("/api/cattle/medical/{record_id:int}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medical_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    rec = db.query(CattleMedicalModel).filter(CattleMedicalModel.id == record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Medical record not found")
    db.delete(rec)
    db.commit()
    return None

# -------------------------------------------------------------
# CSV EXPORT
# -------------------------------------------------------------

@router.get("/api/cattle/export/csv")
def export_cattle_registry_csv(db: Session = Depends(get_db)):
    all_cattle = db.query(CattleModel).order_by(CattleModel.tag_id.asc()).all()

    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM
    writer = csv.writer(output)

    writer.writerow([
        "Tag ID / RFID",
        "INAPH National ID",
        "Name / Identifier",
        "Enclosure Pen",
        "Breed",
        "Category",
        "Gender",
        "Lactation Stage",
        "Health Status",
        "Age (Years)",
        "Mother Tag (Dam)",
        "Father Tag (Sire)",
        "Intake Source",
        "Status",
        "Notes",
        "Registered Date"
    ])

    for c in all_cattle:
        writer.writerow([
            c.tag_id,
            getattr(c, "inaph_tag", "") or "—",
            c.name or "—",
            c.enclosure_id,
            c.breed or "Desi Indigenous",
            getattr(c, "category", "cow") or "cow",
            getattr(c, "gender", "female") or "female",
            getattr(c, "lactation_stage", "dry") or "dry",
            getattr(c, "health_status", "healthy") or "healthy",
            getattr(c, "age_years", 3.0) or 3.0,
            getattr(c, "mother_tag", "") or "—",
            getattr(c, "father_tag", "") or "—",
            getattr(c, "intake_source", "rescue") or "rescue",
            c.status,
            c.notes or "",
            c.created_at[:10] if c.created_at else ""
        ])

    csv_data = output.getvalue()
    filename = f"gaushala_cattle_registry_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# -------------------------------------------------------------
# LIVE SCANNABLE PUBLIC INSPECTOR PASSPORT WEB PAGE (/verify/{tag})
# -------------------------------------------------------------

@router.get("/verify/{tag_id}", response_class=HTMLResponse)
@router.get("/api/cattle/verify/{tag_id}", response_class=HTMLResponse)
def public_verify_cattle_page(tag_id: str, db: Session = Depends(get_db)):
    """
    Public mobile-responsive Livestock Digital Passport opened when scanning cattle QR code.
    Shows animal photo, INAPH UID, breed, health credentials, and vaccination status.
    """
    clean_tag = tag_id.strip()
    cattle = db.query(CattleModel).filter(CattleModel.tag_id == clean_tag).first()
    if not cattle:
        return HTMLResponse(
            status_code=404,
            content=f"""
            <!DOCTYPE html>
            <html>
            <head><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Cattle Not Found</title></head>
            <body style="font-family:sans-serif; text-align:center; padding:3rem 1rem; background:#0f172a; color:#fff;">
                <h1 style="color:#ef4444;">⚠️ Record Not Found</h1>
                <p>No cattle registered with Ear Tag ID: <strong>{clean_tag}</strong></p>
                <a href="/" style="color:#38bdf8;">Return to Gaushala Monitoring Portal</a>
            </body>
            </html>
            """
        )

    # Fetch medical history
    med_records = db.query(CattleMedicalModel).filter(
        CattleMedicalModel.cattle_id == cattle.id
    ).order_by(CattleMedicalModel.administered_date.desc()).all()

    photo_src = cattle.photo_url or "/static/images/gaushala_hero.jpg"
    cat_label = "गाय (Cow)" if cattle.category == "cow" else "नंदी / बैल (Bull)" if cattle.category == "bull" else "बछड़ा / बछिया (Calf)"
    status_color = "#10b981" if cattle.status == "active" else "#ef4444"
    health_color = "#10b981" if cattle.health_status == "healthy" else "#f59e0b"

    med_rows_html = "".join([
        f"""
        <div style="border-left:3px solid #10b981; padding:8px 12px; margin-bottom:8px; background:rgba(255,255,255,0.03); border-radius:0 8px 8px 0;">
            <div style="font-weight:700; color:#f8fafc; font-size:0.9rem;">{r.title}</div>
            <div style="font-size:0.75rem; color:#94a3b8; display:flex; justify-content:space-between; margin-top:2px;">
                <span>Administered: <strong>{r.administered_date}</strong></span>
                <span>Next Due: <strong style="color:#38bdf8;">{r.next_due_date or '—'}</strong></span>
            </div>
            <div style="font-size:0.75rem; color:#64748b; margin-top:2px;">Doctor: {r.doctor_name or 'Veterinary Officer'}</div>
        </div>
        """ for r in med_records[:6]
    ]) or "<p style='color:#64748b; font-size:0.85rem;'>No medical treatments logged yet.</p>"

    # Check disease immunization stamps
    has_fmd = any("fmd" in (r.title or "").lower() and r.status == "completed" for r in med_records)
    has_lsd = any("lsd" in (r.title or "").lower() and r.status == "completed" for r in med_records)
    has_hsbq = any(("hs" in (r.title or "").lower() or "bq" in (r.title or "").lower()) and r.status == "completed" for r in med_records)
    has_deworm = any("deworm" in (r.title or "").lower() and r.status == "completed" for r in med_records)

    inaph_val = cattle.inaph_tag or f"900{str(cattle.id).zfill(9)}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="hi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Sovereign Bharat Pashudhan Passport | {cattle.tag_id}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@600;700&display=swap" rel="stylesheet">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', -apple-system, sans-serif; }}
            body {{ background: #070b14; color: #f8fafc; padding: 16px 12px; min-height: 100vh; display: flex; justify-content: center; align-items: flex-start; }}
            .passport-card {{ width: 100%; max-width: 520px; background: #0f172a; border: 1.5px solid #1e293b; border-radius: 18px; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.6); position: relative; }}
            .tricolor-bar {{ height: 5px; background: linear-gradient(90deg, #ff9933 0%, #ffffff 50%, #138808 100%); width: 100%; }}
            .header-banner {{ background: linear-gradient(135deg, #064e3b 0%, #065f46 60%, #047857 100%); padding: 18px 20px; border-bottom: 2px solid #10b981; display: flex; align-items: center; justify-content: space-between; }}
            .header-left {{ display: flex; align-items: center; gap: 12px; }}
            .emblem {{ font-size: 2.2rem; line-height: 1; }}
            .dept-title {{ font-size: 0.65rem; letter-spacing: 0.08em; text-transform: uppercase; color: #a7f3d0; font-weight: 800; }}
            .doc-title {{ font-size: 1.05rem; font-weight: 900; color: #ffffff; letter-spacing: 0.02em; margin-top: 2px; }}
            .verified-pill {{ background: #10b981; color: #042f2e; font-weight: 900; font-size: 0.72rem; padding: 4px 10px; border-radius: 9999px; letter-spacing: 0.04em; box-shadow: 0 4px 12px rgba(16,185,129,0.3); white-space: nowrap; }}
            
            .identity-strip {{ display: grid; grid-template-columns: 120px 1fr; gap: 16px; padding: 18px 20px; border-bottom: 1px solid #1e293b; background: rgba(15,23,42,0.6); align-items: center; }}
            .photo-wrap {{ width: 120px; height: 130px; border-radius: 12px; overflow: hidden; border: 2px solid #10b981; position: relative; box-shadow: 0 4px 12px rgba(0,0,0,0.4); }}
            .photo-wrap img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
            .id-details {{ display: flex; flex-direction: column; gap: 4px; }}
            .tag-id {{ font-size: 1.6rem; font-weight: 900; color: #10b981; font-family: 'JetBrains Mono', monospace; line-height: 1.1; letter-spacing: 0.02em; }}
            .inaph-badge {{ font-size: 0.8rem; color: #cbd5e1; font-family: 'JetBrains Mono', monospace; margin-top: 4px; }}
            .inaph-badge strong {{ color: #38bdf8; }}
            .name-badge {{ font-size: 1.1rem; font-weight: 800; color: #f8fafc; margin-top: 2px; }}
            .breed-badge {{ font-size: 0.82rem; color: #a7f3d0; font-weight: 600; }}

            .content-body {{ padding: 18px 20px; }}
            .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px; }}
            .info-item {{ background: #1e293b; padding: 10px 12px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.05); }}
            .info-lbl {{ font-size: 0.68rem; text-transform: uppercase; color: #94a3b8; font-weight: 700; letter-spacing: 0.03em; }}
            .info-val {{ font-size: 0.92rem; font-weight: 700; color: #f8fafc; margin-top: 2px; }}

            /* Lineage Tree */
            .pedigree-box {{ background: #0b1120; border: 1px solid #334155; border-radius: 12px; padding: 12px 14px; margin-bottom: 16px; }}
            .pedigree-header {{ font-size: 0.75rem; font-weight: 800; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.05em; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }}
            .pedigree-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
            .pedigree-node {{ background: #1e293b; border-radius: 8px; padding: 8px 10px; }}
            .pedigree-node-dam {{ border-left: 3px solid #f43f5e; }}
            .pedigree-node-sire {{ border-left: 3px solid #3b82f6; }}
            .pedigree-role {{ font-size: 0.68rem; font-weight: 700; color: #94a3b8; }}
            .pedigree-tag {{ font-family: 'JetBrains Mono', monospace; font-size: 0.88rem; font-weight: 800; color: #f8fafc; margin-top: 2px; }}

            /* Immunization Stamps */
            .immunization-box {{ background: #0b1120; border: 1px solid #1e293b; border-radius: 12px; padding: 12px 14px; margin-bottom: 16px; }}
            .immunization-header {{ font-size: 0.72rem; text-transform: uppercase; color: #94a3b8; font-weight: 800; letter-spacing: 0.04em; margin-bottom: 8px; }}
            .stamp-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; text-align: center; }}
            .stamp-card {{ background: #1e293b; padding: 8px 4px; border-radius: 8px; }}
            .stamp-name {{ font-size: 0.7rem; color: #94a3b8; font-weight: 700; }}
            .stamp-status {{ font-size: 0.72rem; font-weight: 800; margin-top: 3px; }}
            .stamp-ok {{ color: #10b981; }}
            .stamp-pending {{ color: #f59e0b; }}

            /* Clinical Log */
            .sec-title {{ font-size: 0.82rem; font-weight: 800; color: #cbd5e1; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }}
            
            .footer-row {{ padding: 16px 20px; background: #070b14; text-align: center; font-size: 0.75rem; color: #64748b; border-top: 1px solid #1e293b; }}
            .footer-row code {{ color: #94a3b8; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; }}
        </style>
    </head>
    <body>
        <div class="passport-card">
            <div class="tricolor-bar"></div>
            
            <div class="header-banner">
                <div class="header-left">
                    <div class="emblem">🏛️</div>
                    <div>
                        <div class="dept-title">GOVERNMENT OF INDIA &bull; NATIONAL LIVESTOCK MISSION</div>
                        <div class="doc-title">SOVEREIGN BHARAT PASHUDHAN PASSPORT (पशु आधार)</div>
                    </div>
                </div>
                <div class="verified-pill">✓ AI VERIFIED</div>
            </div>

            <div class="identity-strip">
                <div class="photo-wrap">
                    <img src="{photo_src}" alt="Cattle Photo" onerror="this.src='/static/images/gaushala_hero.jpg'" />
                </div>
                <div class="id-details">
                    <div style="font-size:0.65rem; color:#94a3b8; font-weight:800; text-transform:uppercase; letter-spacing:0.04em;">EAR TAG / COLLAR RFID</div>
                    <div class="tag-id">{cattle.tag_id}</div>
                    <div class="inaph-badge">INAPH UID: <strong>{inaph_val}</strong></div>
                    <div class="name-badge">{cattle.name or 'Gomata'}</div>
                    <div class="breed-badge">Indigenous Breed: {cattle.breed or 'Gir Cow'}</div>
                </div>
            </div>

            <div class="content-body">
                <div class="grid-2">
                    <div class="info-item">
                        <div class="info-lbl">Category & Gender</div>
                        <div class="info-val">{cat_label} ({cattle.gender.capitalize()})</div>
                    </div>
                    <div class="info-item">
                        <div class="info-lbl">Age & Lactation Stage</div>
                        <div class="info-val">{cattle.age_years or 3} Yrs &bull; {cattle.lactation_stage.capitalize()}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-lbl">Health Condition</div>
                        <div class="info-val" style="color:{health_color};">{cattle.health_status.replace('_', ' ').upper()}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-lbl">Assigned Enclosure</div>
                        <div class="info-val" style="color:#38bdf8;">{cattle.enclosure_id}</div>
                    </div>
                </div>

                <!-- 3-Generation Sovereign Lineage Tree -->
                <div class="pedigree-box">
                    <div class="pedigree-header">
                        <span>🧬 Sovereign Pedigree Lineage Tree (वंशावली कुलवृक्ष)</span>
                    </div>
                    <div class="pedigree-grid">
                        <div class="pedigree-node pedigree-node-dam">
                            <div class="pedigree-role">♀ Mother Tag (Dam / मातृ गोवंश)</div>
                            <div class="pedigree-tag">{cattle.mother_tag or 'Natural Herd Baseline'}</div>
                            <div style="font-size:0.68rem; color:#94a3b8; margin-top:2px;">Desi Gir Purebred Lineage</div>
                        </div>
                        <div class="pedigree-node pedigree-node-sire">
                            <div class="pedigree-role">♂ Father Tag (Sire / पितृ नंदी)</div>
                            <div class="pedigree-tag">{cattle.father_tag or 'Natural Herd Baseline'}</div>
                            <div style="font-size:0.68rem; color:#94a3b8; margin-top:2px;">Pedigree Progeny Tested Sire</div>
                        </div>
                    </div>
                </div>

                <!-- National NADCP Immunization Stamps -->
                <div class="immunization-box">
                    <div class="immunization-header">
                        💉 National NADCP Immunization Stamps (टीकाकरण मुहर)
                    </div>
                    <div class="stamp-grid">
                        <div class="stamp-card">
                            <div class="stamp-name">FMD</div>
                            <div class="stamp-status {'stamp-ok' if has_fmd else 'stamp-pending'}">
                                {'✓ IMMUNIZED' if has_fmd else '⏳ PENDING'}
                            </div>
                        </div>
                        <div class="stamp-card">
                            <div class="stamp-name">LSD</div>
                            <div class="stamp-status {'stamp-ok' if has_lsd else 'stamp-pending'}">
                                {'✓ IMMUNIZED' if has_lsd else '⏳ PENDING'}
                            </div>
                        </div>
                        <div class="stamp-card">
                            <div class="stamp-name">HS/BQ</div>
                            <div class="stamp-status {'stamp-ok' if has_hsbq else 'stamp-pending'}">
                                {'✓ IMMUNIZED' if has_hsbq else '⏳ PENDING'}
                            </div>
                        </div>
                        <div class="stamp-card">
                            <div class="stamp-name">DEWORM</div>
                            <div class="stamp-status {'stamp-ok' if has_deworm else 'stamp-pending'}">
                                {'✓ DOSING OK' if has_deworm else '⏳ PENDING'}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="sec-title">
                    <span>📋 Recent Veterinary Clinical Treatments</span>
                </div>
                <div>
                    {med_rows_html}
                </div>
            </div>

            <div class="footer-row">
                <p>Smart Gaushala CCTV AI Telemetry &bull; Registered: {cattle.created_at[:10] if cattle.created_at else 'Active'}</p>
                <p style="margin-top:4px;">Cryptographic Hash: <code>GAU-{cattle.id}-PASSPORT-VERIFIED</code></p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
