from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
import enum
from database import Base


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    paid = "paid"


class MyCompany(Base):
    """Реквизиты моей компании (может быть несколько)"""
    __tablename__ = "my_companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    country = Column(String)
    company_number = Column(String)
    iban = Column(String)
    swift = Column(String)
    vat = Column(String)
    notes = Column(Text)

    invoices = relationship("Invoice", back_populates="my_company")
    service_rates = relationship("ServiceItemRate", back_populates="my_company", cascade="all, delete-orphan")


class ServiceItem(Base):
    """Библиотека позиций — переиспользуемые услуги"""
    __tablename__ = "service_items"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    unit = Column(String, default="Hours")
    default_rate = Column(Float, nullable=False)

    rates = relationship("ServiceItemRate", back_populates="service_item", cascade="all, delete-orphan")


class Counterparty(Base):
    __tablename__ = "counterparties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    address = Column(String)
    old_address = Column(String)
    company_number = Column(String)
    eu_vat = Column(String)
    iban = Column(String)
    swift = Column(String)
    vat = Column(String)
    notes = Column(Text)

    invoices = relationship("Invoice", back_populates="counterparty")


class InvoiceTemplate(Base):
    __tablename__ = "invoice_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    usage_count = Column(Integer, default=0)

    invoices = relationship("Invoice", back_populates="template")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String, nullable=False, unique=True)
    date = Column(Date, nullable=False)
    due_date = Column(Date)
    currency = Column(String, default="EUR")
    total_amount = Column(Float, nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.draft)
    notes = Column(Text)
    pdf_path = Column(String)

    counterparty_id = Column(Integer, ForeignKey("counterparties.id"))
    template_id = Column(Integer, ForeignKey("invoice_templates.id"))
    my_company_id = Column(Integer, ForeignKey("my_companies.id"))

    counterparty = relationship("Counterparty", back_populates="invoices")
    template = relationship("InvoiceTemplate", back_populates="invoices")
    my_company = relationship("MyCompany", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    description = Column(String, nullable=False)
    unit = Column(String, default="Hours")
    rate = Column(Float, nullable=False)
    minutes = Column(Integer, nullable=False)
    amount = Column(Float, nullable=False)

    invoice = relationship("Invoice", back_populates="items")

    @property
    def time_formatted(self) -> str:
        h = self.minutes // 60
        m = self.minutes % 60
        return f"{h}:{m:02d}"


class ServiceItemRate(Base):
    """Ставка конкретной позиции для конкретной компании"""
    __tablename__ = "service_item_rates"

    id = Column(Integer, primary_key=True, index=True)
    service_item_id = Column(Integer, ForeignKey("service_items.id"), nullable=False)
    my_company_id = Column(Integer, ForeignKey("my_companies.id"), nullable=False)
    rate = Column(Float, nullable=False)

    service_item = relationship("ServiceItem", back_populates="rates")
    my_company = relationship("MyCompany", back_populates="service_rates")
