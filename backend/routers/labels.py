"""Labels router — CRUD + merge for user-defined alert classification tags."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from database import get_db
from models.alert_record import alert_record_labels
from models.label import Label
from schemas.label import LabelCreate, LabelListResponse, LabelMerge, LabelOut, LabelUpdate

router = APIRouter(prefix="/api/labels", tags=["Labels"])


@router.get("", response_model=LabelListResponse)
def list_labels(include_inactive: bool = False, db: Session = Depends(get_db)):
    """List all labels (active only by default)."""
    query = db.query(Label)
    if not include_inactive:
        query = query.filter(Label.is_active.is_(True))
    labels = query.order_by(Label.name).all()
    return LabelListResponse(labels=labels)


@router.post("", response_model=LabelOut, status_code=201)
def create_label(data: LabelCreate, db: Session = Depends(get_db)):
    """Create a new label."""
    existing = db.query(Label).filter(Label.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Label with this name already exists")

    label = Label(**data.model_dump())
    db.add(label)
    db.commit()
    db.refresh(label)
    return label


@router.patch("/{label_id}", response_model=LabelOut)
def update_label(label_id: int, data: LabelUpdate, db: Session = Depends(get_db)):
    """Update a label (name, color, description, is_active)."""
    label = db.query(Label).filter(Label.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    update_data = data.model_dump(exclude_unset=True)

    # Check name uniqueness if name is being changed
    if "name" in update_data and update_data["name"] != label.name:
        existing = db.query(Label).filter(Label.name == update_data["name"]).first()
        if existing:
            raise HTTPException(status_code=409, detail="Label with this name already exists")

    for key, value in update_data.items():
        setattr(label, key, value)

    db.commit()
    db.refresh(label)
    return label


@router.delete("/{label_id}", status_code=204)
def soft_delete_label(label_id: int, db: Session = Depends(get_db)):
    """Soft delete a label (mark inactive)."""
    label = db.query(Label).filter(Label.id == label_id).first()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    label.is_active = False
    db.commit()
    return None


@router.post("/merge", response_model=LabelOut)
def merge_labels(data: LabelMerge, db: Session = Depends(get_db)):
    """Merge source label into target label.

    All alert associations from source are reassigned to target,
    then source is soft-deleted.
    """
    if data.source_id == data.target_id:
        raise HTTPException(status_code=422, detail="Source and target must be different")

    source = db.query(Label).filter(Label.id == data.source_id).first()
    target = db.query(Label).filter(Label.id == data.target_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source label not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target label not found")

    # Move associations: update alert_record_labels rows from source → target
    existing_target = set(
        row.alert_record_id
        for row in db.execute(
            alert_record_labels.select().where(alert_record_labels.c.label_id == target.id)
        ).fetchall()
    )

    source_rows = db.execute(
        alert_record_labels.select().where(alert_record_labels.c.label_id == source.id)
    ).fetchall()

    for row in source_rows:
        alert_id = row.alert_record_id
        if alert_id not in existing_target:
            db.execute(
                update(alert_record_labels)
                .where(
                    alert_record_labels.c.alert_record_id == alert_id,
                    alert_record_labels.c.label_id == source.id,
                )
                .values(label_id=target.id)
            )
        else:
            db.execute(
                alert_record_labels.delete().where(
                    alert_record_labels.c.alert_record_id == alert_id,
                    alert_record_labels.c.label_id == source.id,
                )
            )

    source.is_active = False
    db.commit()
    db.refresh(target)
    return target
