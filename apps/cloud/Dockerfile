# ─── PharmApp Cloud — Dockerfile multi-stage ─────────────────────────────────
# Build : docker build -t pharmapp-cloud .
# Run   : docker run --env-file .env -p 8001:8001 pharmapp-cloud

# ── Stage 1 : Builder ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Dépendances système minimales pour psycopg[binary] et argon2-cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2 : Runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Utilisateur non-root (UID 10001)
RUN groupadd -r pharmapp && useradd -r -g pharmapp -u 10001 pharmapp

# tini comme PID 1 (gestion correcte des signaux)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances installées depuis le builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copier le code applicatif
COPY --chown=pharmapp:pharmapp . .

# Collecte des fichiers statiques (whitenoise)
RUN python manage.py collectstatic --noinput --settings=pharmapp_cloud.settings 2>/dev/null || true

USER pharmapp

EXPOSE 8001

# Healthcheck Docker
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/cloud/healthz/')" || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "pharmapp_cloud.wsgi", \
     "--bind", "0.0.0.0:8001", \
     "--workers", "4", \
     "--worker-class", "sync", \
     "--timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
