import os
import re
from datetime import date as date_type
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from database import get_db
from models import Invoice, InvoiceItem, InvoiceTemplate, Counterparty, InvoiceStatus, MyCompany
from schemas import InvoiceCreate, InvoiceUpdate, InvoiceOut, InvoiceListItem
from time_distributor import distribute_time


def _safe_filename_part(s: str | None) -> str:
    """Чистим имя для использования в filename — выкидываем запрещённые символы
    и схлопываем пробелы. Точку оставляем (s.r.o. → s.r.o.), но в конце имени
    обрезаем — Windows не любит файлы, заканчивающиеся точкой."""
    if not s:
        return ""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    return s


def _build_pdf_context(inv: "Invoice") -> tuple[dict, str]:
    """Собирает (context, template_file) для рендера инвойса в PDF.
    Вынесено отдельно, чтобы GET /pdf и POST /generate-pdf не дублировали логику."""
    template_file = inv.template.filename if inv.template else "invoice_default.html"
    cp = inv.counterparty
    mc = inv.my_company
    context = {
        "invoice_number": inv.number,
        "invoice_date": inv.date.strftime("%B %d, %Y"),
        "due_date": inv.due_date.strftime("%B %d, %Y") if inv.due_date else None,
        "currency": inv.currency,
        "total_amount": inv.total_amount,
        "notes": inv.notes or "",
        "company_name": mc.name if mc else "Insha s.r.o.",
        "company_address": mc.address if mc else "Novozamocka 353, 951 12 Ivanka pri Nitre",
        "company_country": mc.country if mc else "Slovak Republic",
        "company_number": mc.company_number if mc else "5482834",
        "company_swift": mc.swift if mc else "TRWIBEB1XXX",
        "company_iban": mc.iban if mc else "BE21 9679 1901 0803",
        "company_vat": mc.vat if mc else "SK2121797700",
        "company_account_number": mc.account_number if mc else "",
        "company_routing_number": mc.routing_number if mc else "",
        "cp_name": cp.name if cp else "",
        "cp_address": cp.address or "",
        "cp_old_address": cp.old_address or "",
        "cp_company_number": cp.company_number or "",
        "cp_eu_vat": cp.eu_vat or "",
        "items": [{"description": i.description, "unit": i.unit, "rate": i.rate,
                   "time_formatted": i.time_formatted, "amount": i.amount} for i in inv.items],
    }
    return context, template_file


def _invoice_pdf_filename(inv: "Invoice") -> str:
    """МояКомпания_Контрагент_Номер.pdf"""
    parts = [
        _safe_filename_part(inv.my_company.name if inv.my_company else None),
        _safe_filename_part(inv.counterparty.name if inv.counterparty else None),
        _safe_filename_part(inv.number),
    ]
    return "_".join(p for p in parts if p) + ".pdf"

router = APIRouter(prefix="/invoices", tags=["invoices"])

PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "templates"))


def _build_invoice_out(inv: Invoice) -> InvoiceOut:
    return InvoiceOut.model_validate(inv)


@router.get("/", response_model=list[InvoiceListItem])
def list_invoices(status: InvoiceStatus | None = None, counterparty_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Invoice).order_by(Invoice.date.desc())
    if status:
        q = q.filter(Invoice.status == status)
    if counterparty_id:
        q = q.filter(Invoice.counterparty_id == counterparty_id)
    return [InvoiceListItem(
        id=inv.id, number=inv.number, date=inv.date,
        total_amount=inv.total_amount, currency=inv.currency,
        status=inv.status,
        counterparty_name=inv.counterparty.name if inv.counterparty else "—",
        my_company_name=inv.my_company.name if inv.my_company else None,
    ) for inv in q.all()]


@router.get("/{inv_id}", response_model=InvoiceOut)
def get_invoice(inv_id: int, db: Session = Depends(get_db)):
    inv = db.query(Invoice).get(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    return _build_invoice_out(inv)


@router.post("/", response_model=InvoiceOut, status_code=201)
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db)):
    if not db.query(Counterparty).get(data.counterparty_id):
        raise HTTPException(404, "Counterparty not found")
    if not db.query(InvoiceTemplate).get(data.template_id):
        raise HTTPException(404, "Template not found")
    if db.query(Invoice).filter(Invoice.number == data.number).first():
        raise HTTPException(400, f"Invoice number '{data.number}' already exists")

    distributed = distribute_time(data.total_amount, data.items)
    inv = Invoice(
        number=data.number, date=data.date, due_date=data.due_date,
        currency=data.currency, total_amount=data.total_amount,
        counterparty_id=data.counterparty_id, template_id=data.template_id,
        my_company_id=data.my_company_id, notes=data.notes,
        status=InvoiceStatus.draft,
    )
    db.add(inv)
    db.flush()
    for item_data in distributed:
        db.add(InvoiceItem(invoice_id=inv.id, **item_data))
    db.commit()
    db.refresh(inv)
    return _build_invoice_out(inv)


@router.put("/{inv_id}", response_model=InvoiceOut)
def update_invoice(inv_id: int, data: InvoiceUpdate, db: Session = Depends(get_db)):
    inv = db.query(Invoice).get(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    update_data = data.model_dump(exclude_unset=True)
    update_data.pop("items", None)  # items обрабатываем отдельно ниже
    for field, value in update_data.items():
        setattr(inv, field, value)
    # data.items — Pydantic-модели (distribute_time ждёт именно их, не dict-ы)
    if data.items is not None:
        for old_item in inv.items:
            db.delete(old_item)
        db.flush()
        for item_data in distribute_time(data.total_amount or inv.total_amount, data.items):
            db.add(InvoiceItem(invoice_id=inv.id, **item_data))
    db.commit()
    db.refresh(inv)
    return _build_invoice_out(inv)


@router.patch("/{inv_id}/status", response_model=InvoiceOut)
def update_status(inv_id: int, status: InvoiceStatus, db: Session = Depends(get_db)):
    inv = db.query(Invoice).get(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    inv.status = status
    db.commit()
    db.refresh(inv)
    return _build_invoice_out(inv)


@router.post("/{inv_id}/duplicate", response_model=InvoiceOut, status_code=201)
def duplicate_invoice(inv_id: int, db: Session = Depends(get_db)):
    src = db.query(Invoice).get(inv_id)
    if not src:
        raise HTTPException(404, "Invoice not found")
    today = date_type.today()
    new_inv = Invoice(
        number=f"{src.number}-copy-{today.strftime('%d%m%Y')}",
        date=today, due_date=src.due_date, currency=src.currency,
        total_amount=src.total_amount, counterparty_id=src.counterparty_id,
        template_id=src.template_id, my_company_id=src.my_company_id,
        notes=src.notes, status=InvoiceStatus.draft,
    )
    db.add(new_inv)
    db.flush()
    for si in src.items:
        db.add(InvoiceItem(invoice_id=new_inv.id, description=si.description,
            unit=si.unit, rate=si.rate, minutes=si.minutes, amount=si.amount))
    db.commit()
    db.refresh(new_inv)
    return _build_invoice_out(new_inv)


@router.get("/{inv_id}/pdf")
async def download_pdf(inv_id: int, db: Session = Depends(get_db)):
    """Всегда рендерим PDF из текущего состояния инвойса в БД и стримим в ответ.
    Не читаем закешированный файл с диска — это был источник бага:
    при изменении номера/повторном использовании номера старые файлы перетирались
    и/или браузер кешировал PDF по URL, поэтому скачивался не тот инвойс.
    Cache-Control: no-store гарантирует, что браузер тоже не закеширует ответ."""
    inv = db.query(Invoice).get(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")

    context, template_file = _build_pdf_context(inv)

    from pdf_generator import generate_invoice_pdf
    try:
        pdf_bytes = await generate_invoice_pdf(context, template_file)
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        import traceback
        raise HTTPException(500, f"PDF generation failed: {type(e).__name__}: {e}\n\n{traceback.format_exc()}")

    filename = _invoice_pdf_filename(inv)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        },
    )


@router.post("/{inv_id}/generate-pdf", response_model=dict)
async def generate_pdf(inv_id: int, db: Session = Depends(get_db)):
    """Эндпоинт оставлен для обратной совместимости с фронтом, но кеш-файл
    больше не используется при отдаче. Главное side-effect — перевод
    статуса draft → sent и инкремент usage_count шаблона."""
    inv = db.query(Invoice).get(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")

    context, template_file = _build_pdf_context(inv)

    # Используем id, чтобы файлы НИКОГДА не сталкивались
    # (раньше ключом был inv.number, и при смене номера или его повторном
    # использовании файлы перезатирались).
    pdf_path = PDF_DIR / f"{inv.id}_{_safe_filename_part(inv.number) or 'inv'}.pdf"

    from pdf_generator import generate_invoice_pdf
    try:
        pdf_bytes = await generate_invoice_pdf(context, template_file)
    except FileNotFoundError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        import traceback
        raise HTTPException(500, f"PDF generation failed: {type(e).__name__}: {e}\n\n{traceback.format_exc()}")

    with open(str(pdf_path), "wb") as f:
        f.write(pdf_bytes)

    inv.pdf_path = str(pdf_path)
    if inv.status == InvoiceStatus.draft:
        inv.status = InvoiceStatus.sent
    if inv.template:
        inv.template.usage_count += 1
    db.commit()

    return {"pdf_path": str(pdf_path), "message": "PDF generated successfully"}


@router.delete("/{inv_id}", status_code=204)
def delete_invoice(inv_id: int, db: Session = Depends(get_db)):
    inv = db.query(Invoice).get(inv_id)
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.pdf_path and os.path.exists(inv.pdf_path):
        os.remove(inv.pdf_path)
    db.delete(inv)
    db.commit()
