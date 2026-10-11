import csv
import io
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import CattleModel, CattleMedicalModel
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/cattle", tags=["Cattle Registry"])

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
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")
    notes: Optional[str] = None

class MedicalRecordCreateSchema(BaseModel):
    record_type: str = Field("vaccination", pattern="^(vaccination|deworming|checkup|treatment)$")
    title: str = Field(..., min_length=2, max_length=128)
    administered_date: str = Field(...)
    next_due_date: Optional[str] = None
    doctor_name: Optional[str] = None
    status: str = Field("completed", pattern="^(completed|due|overdue)$")
    notes: Optional[str] = None

class BulkCattleItemSchema(BaseModel):
    tag_id: str
    name: Optional[str] = None
    enclosure_id: Optional[str] = "cam-01"
    breed: Optional[str] = "Gir / Indigenous"
    category: Optional[str] = "cow"
    gender: Optional[str] = "female"
    lactation_stage: Optional[str] = "dry"
    health_status: Optional[str] = "healthy"
    inaph_tag: Optional[str] = None
    intake_source: Optional[str] = "rescue"
    age_years: Optional[float] = 3.0
    status: Optional[str] = "active"
    notes: Optional[str] = None

class BulkImportPayloadSchema(BaseModel):
    items: List[BulkCattleItemSchema]


@router.get("", response_model=List[Dict[str, Any]])
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


@router.get("/summary")
def get_cattle_summary(db: Session = Depends(get_db)):
    all_cattle = db.query(CattleModel).all()
    active_count = sum(1 for c in all_cattle if c.status == "active")
    inactive_count = sum(1 for c in all_cattle if c.status == "inactive")

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

    # Standard Government Subsidy rate: ₹40/day per registered cattle
    daily_subsidy = active_count * 40
    monthly_subsidy = daily_subsidy * 30

    return {
        "total_registered": len(all_cattle),
        "active_herd": active_count,
        "inactive_herd": inactive_count,
        "by_enclosure": by_enclosure,
        "by_category": by_category,
        "by_lactation": by_lactation,
        "by_health": by_health,
        "subsidy": {
            "per_day_rate_inr": 40,
            "daily_total_inr": daily_subsidy,
            "monthly_total_inr": monthly_subsidy
        }
    }


@router.get("/export/csv")
def export_cattle_registry_csv(db: Session = Depends(get_db)):
    """Exports the official cattle registry muster roll as a downloadable CSV."""
    all_cattle = db.query(CattleModel).order_by(CattleModel.tag_id.asc()).all()

    output = io.StringIO()
    # Write UTF-8 BOM so Excel opens Hindi/English characters properly
    output.write('\ufeff')
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


@router.post("/bulk-import", status_code=status.HTTP_201_CREATED)
def bulk_import_cattle_json(
    payload: BulkImportPayloadSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Imports cattle records from JSON array."""
    imported = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for item in payload.items:
        clean_tag = item.tag_id.strip()
        if not clean_tag:
            continue
        existing = db.query(CattleModel).filter(CattleModel.tag_id == clean_tag).first()
        if existing:
            skipped += 1
            continue

        c = CattleModel(
            tag_id=clean_tag,
            name=item.name.strip() if item.name else None,
            enclosure_id=item.enclosure_id or "cam-01",
            breed=item.breed or "Gir / Indigenous",
            category=item.category or "cow",
            gender=item.gender or "female",
            lactation_stage=item.lactation_stage or "dry",
            health_status=item.health_status or "healthy",
            inaph_tag=item.inaph_tag.strip() if item.inaph_tag else None,
            intake_source=item.intake_source or "rescue",
            age_years=item.age_years or 3.0,
            status=item.status or "active",
            notes=item.notes,
            created_at=now,
            updated_at=now
        )
        db.add(c)
        imported += 1

    db.commit()
    return {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "total_submitted": len(payload.items)
    }


@router.post("/bulk-import/csv", status_code=status.HTTP_201_CREATED)
async def bulk_import_cattle_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Imports cattle records from an uploaded CSV file."""
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except Exception:
        text = contents.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for row in reader:
        tag_id = (row.get("Tag ID / RFID") or row.get("tag_id") or row.get("Tag ID") or "").strip()
        if not tag_id:
            continue

        existing = db.query(CattleModel).filter(CattleModel.tag_id == tag_id).first()
        if existing:
            skipped += 1
            continue

        name = (row.get("Name / Identifier") or row.get("name") or row.get("Name") or "").strip() or None
        enclosure = (row.get("Enclosure Pen") or row.get("enclosure_id") or row.get("Enclosure") or "cam-01").strip()
        breed = (row.get("Breed") or row.get("breed") or "Gir / Indigenous").strip()
        category = (row.get("Category") or row.get("category") or "cow").strip().lower()
        if category not in ["cow", "bull", "calf"]:
            category = "cow"
        gender = (row.get("Gender") or row.get("gender") or "female").strip().lower()
        if gender not in ["female", "male"]:
            gender = "female"
        lactation = (row.get("Lactation Stage") or row.get("lactation_stage") or "dry").strip().lower()
        if lactation not in ["milking", "dry", "pregnant", "na"]:
            lactation = "dry"
        health = (row.get("Health Status") or row.get("health_status") or "healthy").strip().lower()
        if health not in ["healthy", "under_treatment", "quarantine"]:
            health = "healthy"
        inaph = (row.get("INAPH National ID") or row.get("inaph_tag") or "").strip() or None
        intake = (row.get("Intake Source") or row.get("intake_source") or "rescue").strip()
        try:
            age = float(row.get("Age (Years)") or row.get("age_years") or 3.0)
        except Exception:
            age = 3.0

        c = CattleModel(
            tag_id=tag_id,
            name=name,
            enclosure_id=enclosure,
            breed=breed,
            category=category,
            gender=gender,
            lactation_stage=lactation,
            health_status=health,
            inaph_tag=inaph,
            intake_source=intake,
            age_years=age,
            status="active",
            notes=(row.get("Notes") or row.get("notes") or "").strip() or None,
            created_at=now,
            updated_at=now
        )
        db.add(c)
        imported += 1

    db.commit()
    return {
        "success": True,
        "imported": imported,
        "skipped": skipped
    }


@router.post("", status_code=status.HTTP_201_CREATED)
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
        status=payload.status,
        notes=payload.notes,
        created_at=now,
        updated_at=now
    )
    db.add(cattle)
    db.commit()
    db.refresh(cattle)
    return cattle.to_dict()


@router.get("/medical/alerts")
def get_medical_alerts(db: Session = Depends(get_db)):
    """Returns pending, due, or overdue vaccinations and health treatments across the herd."""
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
        "upcoming_records": upcoming[:25],
        "recent_completed": completed[:10]
    }


@router.get("/{cattle_id}")
def get_cattle_detail(cattle_id: int, db: Session = Depends(get_db)):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")
    data = cattle.to_dict()

    # Attach medical records
    med_records = db.query(CattleMedicalModel).filter(CattleMedicalModel.cattle_id == cattle_id).all()
    data["medical_history"] = [m.to_dict() for m in med_records]
    return data


@router.put("/{cattle_id}")
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
    if payload.status is not None:
        cattle.status = payload.status
    if payload.notes is not None:
        cattle.notes = payload.notes

    cattle.updated_at = datetime.now(timezone.utc).isoformat()
    db.commit()
    db.refresh(cattle)
    return cattle.to_dict()


@router.patch("/{cattle_id}/status")
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


@router.delete("/{cattle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cattle(
    cattle_id: int,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    # Delete related medical records
    db.query(CattleMedicalModel).filter(CattleMedicalModel.cattle_id == cattle_id).delete()
    db.delete(cattle)
    db.commit()
    return None


@router.get("/{cattle_id}/medical")
def get_cattle_medical_history(cattle_id: int, db: Session = Depends(get_db)):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")

    records = db.query(CattleMedicalModel).filter(
        CattleMedicalModel.cattle_id == cattle_id
    ).order_by(CattleMedicalModel.administered_date.desc()).all()
    return [r.to_dict() for r in records]


@router.post("/{cattle_id}/medical", status_code=status.HTTP_201_CREATED)
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
        status=payload.status,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec.to_dict()


@router.delete("/medical/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
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
