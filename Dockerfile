# Официальный образ Playwright Python — содержит Python 3.12, playwright 1.49,
# и предустановленные Chromium/Firefox/WebKit со всеми системными библиотеками.
# Намного надёжнее, чем nixpacks + ручная установка Chromium через apt.
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

# Railway передаёт $PORT в runtime. Дефолт на случай локального запуска.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
