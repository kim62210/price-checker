# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /build
COPY pyproject.toml ./

RUN pip install --prefix=/install '.[ui]'

COPY app ./app
RUN pip install --prefix=/install --no-deps .


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/usr/local/bin:/install/bin:$PATH \
    PYTHONPATH=/install/lib/python3.12/site-packages

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libx11-6 libxcomposite1 \
        libxdamage1 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 \
        libasound2 fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /install
WORKDIR /app
COPY app ./app
COPY alembic.ini ./

RUN python -m playwright install chromium

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
