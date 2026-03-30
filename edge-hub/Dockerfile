# Multi-arch: amd64 + arm64 (Raspberry Pi 4/5, etc.)
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GDT_HOST=0.0.0.0 \
    GDT_HUB_DATA=/data

# Optional: libffi if any wheel needed — slim is usually enough for pyserial/minimalmodbus wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
COPY run.py .

EXPOSE 8756

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8756/api/health', timeout=4)"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8756"]
