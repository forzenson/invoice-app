from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import ServiceItem, ServiceItemRate, MyCompany
from schemas import ServiceItemCreate, ServiceItemOut, ServiceItemDetailOut, ServiceItemRateBase, ServiceItemRateOut

router = APIRouter(prefix="/service-items", tags=["service-items"])


def _enrich(item: ServiceItem, db: Session) -> ServiceItemDetailOut:
    rates = []
    for r in item.rates:
        mc = db.query(MyCompany).get(r.my_company_id)
        rates.append(ServiceItemRateOut(
            id=r.id,
            my_company_id=r.my_company_id,
            rate=r.rate,
            my_company_name=mc.name if mc else None,
        ))
    return ServiceItemDetailOut(
        id=item.id,
        description=item.description,
        unit=item.unit,
        default_rate=item.default_rate,
        rates=rates,
    )


@router.get("/", response_model=list[ServiceItemDetailOut])
def list_items(db: Session = Depends(get_db)):
    return [_enrich(i, db) for i in db.query(ServiceItem).order_by(ServiceItem.description).all()]


@router.post("/", response_model=ServiceItemDetailOut, status_code=201)
def create_item(data: ServiceItemCreate, db: Session = Depends(get_db)):
    item = ServiceItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return _enrich(item, db)


@router.put("/{item_id}", response_model=ServiceItemDetailOut)
def update_item(item_id: int, data: ServiceItemCreate, db: Session = Depends(get_db)):
    item = db.query(ServiceItem).get(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return _enrich(item, db)


@router.post("/{item_id}/rates", response_model=ServiceItemRateOut, status_code=201)
def add_rate(item_id: int, data: ServiceItemRateBase, db: Session = Depends(get_db)):
    item = db.query(ServiceItem).get(item_id)
    if not item:
        raise HTTPException(404, "Service item not found")
    if not db.query(MyCompany).get(data.my_company_id):
        raise HTTPException(404, "Company not found")
    # Обновляем если уже есть
    existing = next((r for r in item.rates if r.my_company_id == data.my_company_id), None)
    if existing:
        existing.rate = data.rate
        db.commit()
        db.refresh(existing)
        mc = db.query(MyCompany).get(existing.my_company_id)
        return ServiceItemRateOut(id=existing.id, my_company_id=existing.my_company_id,
                                  rate=existing.rate, my_company_name=mc.name if mc else None)
    rate = ServiceItemRate(service_item_id=item_id, my_company_id=data.my_company_id, rate=data.rate)
    db.add(rate)
    db.commit()
    db.refresh(rate)
    mc = db.query(MyCompany).get(rate.my_company_id)
    return ServiceItemRateOut(id=rate.id, my_company_id=rate.my_company_id,
                              rate=rate.rate, my_company_name=mc.name if mc else None)


@router.delete("/{item_id}/rates/{rate_id}", status_code=204)
def delete_rate(item_id: int, rate_id: int, db: Session = Depends(get_db)):
    rate = db.query(ServiceItemRate).filter(
        ServiceItemRate.id == rate_id,
        ServiceItemRate.service_item_id == item_id
    ).first()
    if not rate:
        raise HTTPException(404, "Rate not found")
    db.delete(rate)
    db.commit()


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(ServiceItem).get(item_id)
    if not item:
        raise HTTPException(404, "Not found")
    db.delete(item)
    db.commit()
