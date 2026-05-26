from pydantic import BaseModel
from datetime import date
from typing import Optional
from models import InvoiceStatus


# ── MyCompany ────────────────────────────────────────────────────────────────

class MyCompanyBase(BaseModel):
    name: str
    address: Optional[str] = None
    country: Optional[str] = None
    company_number: Optional[str] = None
    iban: Optional[str] = None
    swift: Optional[str] = None
    vat: Optional[str] = None
    notes: Optional[str] = None

class MyCompanyCreate(MyCompanyBase):
    pass

class MyCompanyOut(MyCompanyBase):
    id: int
    model_config = {"from_attributes": True}


# ── ServiceItem ──────────────────────────────────────────────────────────────

class ServiceItemBase(BaseModel):
    description: str
    unit: str = "Hours"
    default_rate: float

class ServiceItemCreate(ServiceItemBase):
    pass

class ServiceItemOut(ServiceItemBase):
    id: int
    model_config = {"from_attributes": True}


# ── Counterparty ─────────────────────────────────────────────────────────────

class CounterpartyBase(BaseModel):
    name: str
    address: Optional[str] = None
    old_address: Optional[str] = None
    company_number: Optional[str] = None
    eu_vat: Optional[str] = None
    iban: Optional[str] = None
    swift: Optional[str] = None
    vat: Optional[str] = None
    notes: Optional[str] = None

class CounterpartyCreate(CounterpartyBase):
    pass

class CounterpartyUpdate(CounterpartyBase):
    name: Optional[str] = None

class CounterpartyOut(CounterpartyBase):
    id: int
    invoice_count: Optional[int] = 0
    total_billed: Optional[float] = 0.0
    model_config = {"from_attributes": True}


# ── Invoice Item ──────────────────────────────────────────────────────────────

class InvoiceItemBase(BaseModel):
    description: str
    unit: str = "Hours"
    rate: float
    minutes: int
    amount: float

class InvoiceItemOut(InvoiceItemBase):
    id: int
    time_formatted: str
    model_config = {"from_attributes": True}


# ── Invoice ───────────────────────────────────────────────────────────────────

class InvoiceItemInput(BaseModel):
    description: str
    unit: str = "Hours"
    rate: float

class InvoiceCreate(BaseModel):
    number: str
    date: date
    due_date: Optional[date] = None
    currency: str = "EUR"
    total_amount: float
    counterparty_id: int
    template_id: int
    my_company_id: Optional[int] = None
    notes: Optional[str] = None
    items: list[InvoiceItemInput]

class InvoiceUpdate(BaseModel):
    number: Optional[str] = None
    date: Optional[date] = None
    due_date: Optional[date] = None
    currency: Optional[str] = None
    total_amount: Optional[float] = None
    counterparty_id: Optional[int] = None
    template_id: Optional[int] = None
    my_company_id: Optional[int] = None
    status: Optional[InvoiceStatus] = None
    notes: Optional[str] = None
    items: Optional[list[InvoiceItemInput]] = None

class InvoiceOut(BaseModel):
    id: int
    number: str
    date: date
    due_date: Optional[date]
    currency: str
    total_amount: float
    status: InvoiceStatus
    notes: Optional[str]
    pdf_path: Optional[str]
    counterparty_id: int
    template_id: int
    my_company_id: Optional[int]
    counterparty: CounterpartyOut
    items: list[InvoiceItemOut]
    model_config = {"from_attributes": True}

class InvoiceListItem(BaseModel):
    id: int
    number: str
    date: date
    total_amount: float
    currency: str
    status: InvoiceStatus
    counterparty_name: str
    model_config = {"from_attributes": True}


# ── Template ──────────────────────────────────────────────────────────────────

class TemplateOut(BaseModel):
    id: int
    name: str
    filename: str
    usage_count: int
    model_config = {"from_attributes": True}


# ── ServiceItemRate ───────────────────────────────────────────────────────────

class ServiceItemRateBase(BaseModel):
    my_company_id: int
    rate: float

class ServiceItemRateOut(ServiceItemRateBase):
    id: int
    my_company_name: Optional[str] = None
    model_config = {"from_attributes": True}


# ── ServiceItem (extended with rates) ────────────────────────────────────────

class ServiceItemDetailOut(BaseModel):
    id: int
    description: str
    unit: str
    default_rate: float
    rates: list[ServiceItemRateOut] = []
    model_config = {"from_attributes": True}
