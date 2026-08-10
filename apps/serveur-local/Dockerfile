# syntax=docker/dockerfile:1.7
# ─── PharmApp — Image de production durcie ──────────────────────────────────
FROM python:3.12-slim AS base

# Sécurité : ne pas exécuter en root
ARG APP_UID=10001
ARG APP_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=pharmapp.settings

RUN groupadd --gid ${APP_GID} pharmapp \
 && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin pharmapp \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ─── Étape dépendances (cache) ────────────────────────────────────────────────
FROM base AS deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ─── Étape finale ────────────────────────────────────────────────────────────
FROM deps AS runtime
COPY --chown=pharmapp:pharmapp . /app

# Créer les dossiers write-only pour l'utilisateur applicatif
RUN mkdir -p /app/logs /app/media /app/staticfiles \
 && chown -R pharmapp:pharmapp /app/logs /app/media /app/staticfiles

USER pharmapp

EXPOSE 8000

# Healthcheck simple
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
  CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["gunicorn", "pharmapp.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--threads", "2", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--forwarded-allow-ips", "*"]
