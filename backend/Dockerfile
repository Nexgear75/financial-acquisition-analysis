FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md /build/
COPY src /build/src

RUN pip install --upgrade pip setuptools wheel && pip install /build


FROM python:3.11-slim AS dev

ENV PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  APP_ENV=development \
  PATH="/opt/venv/bin:$PATH"

WORKDIR /workspace

RUN python -m venv /opt/venv

COPY pyproject.toml README.md /workspace/
COPY src /workspace/src

RUN pip install --upgrade pip setuptools wheel && pip install -e /workspace && pip install pytest

EXPOSE 8000

CMD ["uvicorn", "ma_mna_analyzer.api:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/workspace/src"]


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /opt/venv /opt/venv

RUN mkdir -p /app/.cache/ma_mna_analyzer && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"]

CMD ["uvicorn", "ma_mna_analyzer.api:app", "--host", "0.0.0.0", "--port", "8000"]
