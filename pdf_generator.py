"""
PDF-генератор инвойсов.

Рендерим HTML-шаблон (Jinja2) → отдаём headless Chromium через Playwright,
получаем PDF. Это даёт полный контроль над дизайном через CSS, и превью
шаблона в обычном браузере выглядит ровно так же, как итоговый PDF.

Контракт `generate_invoice_pdf(context)` сохранён — роутер не меняется
(кроме await — функция теперь async, см. FastAPI handler).
"""
import os
from pathlib import Path
from jinja2 import Template
from playwright.async_api import async_playwright


BUILTIN_TEMPLATES_DIR = Path(__file__).parent / "builtin_templates"
TEMPLATES_DIR = Path(os.environ.get("TEMPLATES_DIR", "templates"))
DEFAULT_TEMPLATE = "invoice_default.html"


def _resolve_template_path(filename: str) -> Path:
    """
    Сначала ищем в TEMPLATES_DIR (volume / user uploads),
    потом в builtin_templates (всегда в репо). Фоллбэк — встроенный default.
    """
    for base in (TEMPLATES_DIR, BUILTIN_TEMPLATES_DIR):
        p = base / filename
        if p.exists():
            return p
    fallback = BUILTIN_TEMPLATES_DIR / DEFAULT_TEMPLATE
    if not fallback.exists():
        raise FileNotFoundError(f"Template {filename!r} not found and no builtin default")
    return fallback


def _render_html(context: dict, template_filename: str = DEFAULT_TEMPLATE) -> str:
    path = _resolve_template_path(template_filename)
    return Template(path.read_text(encoding="utf-8")).render(**context)


async def generate_invoice_pdf(context: dict, template_filename: str = DEFAULT_TEMPLATE) -> bytes:
    """
    Сгенерировать PDF инвойса.

    context — словарь с теми же ключами, что и раньше:
        invoice_number, invoice_date, due_date, currency, total_amount, notes,
        company_*, cp_*, items (list of dicts).
    template_filename — имя HTML-шаблона из templates/ или builtin_templates/.

    Async, потому что внутри FastAPI uvicorn — родная асинхронная среда,
    и sync_playwright там конфликтует с уже работающим event loop.
    """
    html = _render_html(context, template_filename)

    async with async_playwright() as p:
        # --no-sandbox обязательно для контейнеров без user namespaces (Railway).
        # --disable-dev-shm-usage обходит проблему маленького /dev/shm в Docker.
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            pdf_bytes = await page.pdf(
                format="A4",
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                print_background=True,
            )
        finally:
            await browser.close()

    return pdf_bytes
