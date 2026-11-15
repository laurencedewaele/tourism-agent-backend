FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dépendances d'abord (couche mise en cache tant que le lock ne change pas)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

# Exécution sans les droits root
RUN useradd --create-home --uid 1000 appuser
USER appuser

# Port d'écoute : variable PORT (injectée par Render), 8000 à défaut (local, docker compose)
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://localhost:{os.environ.get('PORT', '8000')}/health\")"

# Forme shell pour développer ${PORT} ; exec pour qu'uvicorn reçoive SIGTERM.
# --proxy-headers : derrière le proxy TLS de Render, uvicorn utilise le schéma https d'origine.
# Un seul worker : 512 Mo de RAM sur l'offre gratuite.
CMD ["sh", "-c", "exec uvicorn tourism_api.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
