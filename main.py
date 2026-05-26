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

# builtin_templates — всегда в репозитории, никогда не перезаписываются volume
# TEMPLATES_DIR    — volume или локальная папка, куда пользователь загружает шаблоны
BUILTIN_DIR = Path(__file__).parent / "builtin_templates"
TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "templates"))
TEMPLATES_DIR.mkdir(exist_ok=True)

# Копируем встроенные шаблоны в TEMPLATES_DIR при каждом старте
# (перезаписываем только если файл отсутствует — не трогаем загруженные пользователем)
for tmpl_file in BUILTIN_DIR.glob("*"):
    dst = TEMPLATES_DIR / tmpl_file.name
    if not dst.exists():
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
