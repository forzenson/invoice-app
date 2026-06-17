import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from database import get_db
from models import InvoiceTemplate
from schemas import TemplateOut
import os

router = APIRouter(prefix="/templates", tags=["templates"])

TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "templates"))
TEMPLATES_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'.html', '.docx', '.doc'}


@router.get("/", response_model=list[TemplateOut])
def list_templates(db: Session = Depends(get_db)):
    return db.query(InvoiceTemplate).order_by(InvoiceTemplate.name).all()


@router.post("/upload", response_model=TemplateOut, status_code=201)
def upload_template(
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Only these file types are supported: {', '.join(ALLOWED_EXTENSIONS)}")

    safe_name = file.filename.replace(" ", "_")
    dest = TEMPLATES_DIR / safe_name

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    tmpl = InvoiceTemplate(name=name, filename=safe_name)
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


@router.post("/{tmpl_id}/duplicate", response_model=TemplateOut, status_code=201)
def duplicate_template(tmpl_id: int, new_name: str, db: Session = Depends(get_db)):
    src = db.query(InvoiceTemplate).get(tmpl_id)
    if not src:
        raise HTTPException(404, "Template not found")

    src_path = TEMPLATES_DIR / src.filename
    new_filename = f"copy_{src.filename}"
    dest_path = TEMPLATES_DIR / new_filename

    if src_path.exists():
        shutil.copy(src_path, dest_path)

    new_tmpl = InvoiceTemplate(name=new_name, filename=new_filename)
    db.add(new_tmpl)
    db.commit()
    db.refresh(new_tmpl)
    return new_tmpl


@router.delete("/{tmpl_id}", status_code=204)
def delete_template(tmpl_id: int, db: Session = Depends(get_db)):
    tmpl = db.query(InvoiceTemplate).get(tmpl_id)
    if not tmpl:
        raise HTTPException(404, "Template not found")
    file_path = TEMPLATES_DIR / tmpl.filename
    if file_path.exists():
        file_path.unlink()
    db.delete(tmpl)
    db.commit()
