from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import MyCompany
from schemas import MyCompanyCreate, MyCompanyOut

router = APIRouter(prefix="/my-companies", tags=["my-companies"])


@router.get("/", response_model=list[MyCompanyOut])
def list_companies(db: Session = Depends(get_db)):
    return db.query(MyCompany).order_by(MyCompany.name).all()


@router.post("/", response_model=MyCompanyOut, status_code=201)
def create_company(data: MyCompanyCreate, db: Session = Depends(get_db)):
    c = MyCompany(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{c_id}", response_model=MyCompanyOut)
def update_company(c_id: int, data: MyCompanyCreate, db: Session = Depends(get_db)):
    c = db.query(MyCompany).get(c_id)
    if not c:
        raise HTTPException(404, "Not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{c_id}", status_code=204)
def delete_company(c_id: int, db: Session = Depends(get_db)):
    c = db.query(MyCompany).get(c_id)
    if not c:
        raise HTTPException(404, "Not found")
    db.delete(c)
    db.commit()
