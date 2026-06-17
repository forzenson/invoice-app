from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import shutil, os

from database import engine, Base
from routers import invoices, counterparties, templates
from routers import my_company, service_items

Base.metadata.create_all(bind=engine)


def _ensure_columns(table: str, columns: dict[str, str]) -> None:
    """Лёгкая миграция без Alembic: для каждой колонки из columns
    делаем ALTER TABLE ADD COLUMN, если её ещё нет.
    create_all НЕ добавляет колонки в существующие таблицы — поэтому ходим сами."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return  # create_all сам создаст с актуальной схемой
    existing = {c["name"] for c in insp.get_columns(table)}
    to_add = {name: type_ for name, type_ in columns.items() if name not in existing}
    if not to_add:
        return
    with engine.begin() as conn:
        for name, type_ in to_add.items():
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {type_}'))


# Новые поля у MyCompany — на проде my_companies уже существует с прошлым набором.
_ensure_columns("my_companies", {
    "account_number": "VARCHAR",
    "routing_number": "VARCHAR",
})

# builtin_templates — канонические шаблоны из репозитория, обновляются каждым деплоем.
# TEMPLATES_DIR    — volume или локальная папка, куда пользователь может загружать
#                    свои шаблоны с УНИКАЛЬНЫМИ именами (не пересекающимися с builtin).
BUILTIN_DIR = Path(__file__).parent / "builtin_templates"
TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "templates"))
TEMPLATES_DIR.mkdir(exist_ok=True)

# Всегда перезаписываем builtin-копии в TEMPLATES_DIR: builtin — источник истины
# (если просто проверять exists, в volume застревает старая версия и фикс дизайна
# из репозитория не доезжает до прода).
for tmpl_file in BUILTIN_DIR.glob("*"):
    dst = TEMPLATES_DIR / tmpl_file.name
    shutil.copy(tmpl_file, dst)

# Seed БД
from sqlalchemy.orm import Session
from models import InvoiceTemplate
_db = Session(engine)
if not _db.query(InvoiceTemplate).first():
    _db.add(InvoiceTemplate(name="Стандартный EN", filename="invoice_default.html"))
    _db.commit()
_db.close()

app = FastAPI(title="Invoice Generator", version="1.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:;"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(invoices.router)
app.include_router(counterparties.router)
app.include_router(templates.router)
app.include_router(my_company.router)
app.include_router(service_items.router)

static_dir = Path("static")
static_dir.mkdir(exist_ok=True)

@app.get("/")
def root():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
