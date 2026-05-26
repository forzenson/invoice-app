from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Counterparty, Invoice
from schemas import CounterpartyCreate, CounterpartyUpdate, CounterpartyOut

router = APIRouter(prefix="/counterparties", tags=["counterparties"])


def _enrich(cp: Counterparty, db: Session) -> CounterpartyOut:
    count = db.query(func.count(Invoice.id)).filter(Invoice.counterparty_id == cp.id).scalar()
    total = db.query(func.sum(Invoice.total_amount)).filter(Invoice.counterparty_id == cp.id).scalar() or 0.0
    out = CounterpartyOut.model_validate(cp)
    out.invoice_count = count
    out.total_billed = round(total, 2)
    return out


@router.get("/", response_model=list[CounterpartyOut])
def list_counterparties(db: Session = Depends(get_db)):
    cps = db.query(Counterparty).order_by(Counterparty.name).all()
    return [_enrich(cp, db) for cp in cps]


@router.get("/{cp_id}", response_model=CounterpartyOut)
def get_counterparty(cp_id: int, db: Session = Depends(get_db)):
    cp = db.query(Counterparty).get(cp_id)
    if not cp:
        raise HTTPException(404, "Counterparty not found")
    return _enrich(cp, db)


@router.post("/", response_model=CounterpartyOut, status_code=201)
def create_counterparty(data: CounterpartyCreate, db: Session = Depends(get_db)):
    cp = Counterparty(**data.model_dump())
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return _enrich(cp, db)


@router.put("/{cp_id}", response_model=CounterpartyOut)
def update_counterparty(cp_id: int, data: CounterpartyUpdate, db: Session = Depends(get_db)):
    cp = db.query(Counterparty).get(cp_id)
    if not cp:
        raise HTTPException(404, "Counterparty not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(cp, field, value)
    db.commit()
    db.refresh(cp)
    return _enrich(cp, db)


@router.delete("/{cp_id}", status_code=204)
def delete_counterparty(cp_id: int, db: Session = Depends(get_db)):
    cp = db.query(Counterparty).get(cp_id)
    if not cp:
        raise HTTPException(404, "Counterparty not found")
    db.delete(cp)
    db.commit()
