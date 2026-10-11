from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.database import get_db
from backend.app.db.models import CattleModel
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/cattle", tags=["Cattle Registry"])

class CattleCreateSchema(BaseModel):
    tag_id: str = Field(..., min_length=2, max_length=64, description="Unique ear tag or collar RFID")
    name: Optional[str] = Field(None, max_length=128)
    enclosure_id: str = Field("cam-01", max_length=64)
    breed: Optional[str] = Field("Gir / Indigenous", max_length=64)
    status: str = Field("active", pattern="^(active|inactive)$")
    notes: Optional[str] = None

class CattleUpdateSchema(BaseModel):
    name: Optional[str] = None
    enclosure_id: Optional[str] = None
    breed: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive)$")
    notes: Optional[str] = None

@router.get("", response_model=List[Dict[str, Any]])
def list_cattle(
    status_filter: Optional[str] = Query(None, alias="status"),
    enclosure_id: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(CattleModel)
    if status_filter:
        query = query.filter(CattleModel.status == status_filter)
    if enclosure_id:
        query = query.filter(CattleModel.enclosure_id == enclosure_id)
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            (CattleModel.tag_id.ilike(search_fmt)) |
            (CattleModel.name.ilike(search_fmt)) |
            (CattleModel.breed.ilike(search_fmt))
        )
    cattle_list = query.order_by(CattleModel.created_at.desc()).all()
    return [c.to_dict() for c in cattle_list]

@router.get("/summary")
def get_cattle_summary(db: Session = Depends(get_db)):
    all_cattle = db.query(CattleModel).all()
    active_count = sum(1 for c in all_cattle if c.status == "active")
    inactive_count = sum(1 for c in all_cattle if c.status == "inactive")

    by_enclosure = {}
    for c in all_cattle:
        if c.status == "active":
            by_enclosure[c.enclosure_id] = by_enclosure.get(c.enclosure_id, 0) + 1

    return {
        "total_registered": len(all_cattle),
        "active_herd": active_count,
        "inactive_herd": inactive_count,
        "by_enclosure": by_enclosure
    }

@router.post("", status_code=status.HTTP_201_CREATED)
def register_cattle(
    payload: CattleCreateSchema,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    # Enforce unique tag_id
    existing = db.query(CattleModel).filter(CattleModel.tag_id == payload.tag_id.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cattle tag ID '{payload.tag_id}' is already registered."
        )

    now = datetime.now(timezone.utc).isoformat()
    cattle = CattleModel(
        tag_id=payload.tag_id.strip(),
        name=payload.name.strip() if payload.name else None,
        enclosure_id=payload.enclosure_id.strip(),
        breed=payload.breed.strip() if payload.breed else "Gir / Indigenous",
        status=payload.status,
        notes=payload.notes,
        created_at=now,
        updated_at=now
    )
    db.add(cattle)
    db.commit()
    db.refresh(cattle)
    return cattle.to_dict()

@router.get("/{cattle_id}")
def get_cattle_detail(cattle_id: int, db: Session = Depends(get_db)):
    cattle = db.query(CattleModel).filter(CattleModel.id == cattle_id).first()
    if not cattle:
        raise HTTPException(status_code=404, detail="Cattle record not found")
    return cattle.to_dict()

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
    db.delete(cattle)
    db.commit()
    return None
