"""Filters router — CRUD for alert whitelist/blacklist rules."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.filter_rule import AlertFilterRule
from schemas.filter import FilterRuleCreate, FilterRuleListResponse, FilterRuleOut

router = APIRouter(prefix="/api/filters", tags=["Filters"])


@router.get("", response_model=FilterRuleListResponse)
def list_filters(db: Session = Depends(get_db)):
    """List all filter rules."""
    rules = db.query(AlertFilterRule).order_by(AlertFilterRule.rule_type, AlertFilterRule.filter_field).all()
    return FilterRuleListResponse(filters=rules)


@router.post("", response_model=FilterRuleOut, status_code=201)
def create_filter(data: FilterRuleCreate, db: Session = Depends(get_db)):
    """Create a new filter rule."""
    rule = AlertFilterRule(**data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_filter(rule_id: int, db: Session = Depends(get_db)):
    """Delete a filter rule."""
    rule = db.query(AlertFilterRule).filter(AlertFilterRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Filter rule not found")
    db.delete(rule)
    db.commit()
    return None
