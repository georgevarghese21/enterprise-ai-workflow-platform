FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependencies install in their own layer, cached across rebuilds as long as
# pyproject.toml doesn't change. `pip install -e .` still needs *some*
# package structure to satisfy setuptools' package discovery even though it
# doesn't need the real source yet, so a placeholder stands in until the
# actual app/ is copied in below - editing app code alone then only busts
# the (fast) final COPY layer, not the (slow) dependency-install one.
COPY pyproject.toml ./
RUN mkdir -p app && touch app/__init__.py \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]"

COPY . .

EXPOSE 8000

# Purely informational here (nothing in docker-compose.yml gates on it via
# `condition: service_healthy`, unlike Postgres) - makes `docker ps` and any
# future orchestration able to see whether the app actually came up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# No --reload here: that's a dev-time concern, so docker-compose.yml's own
# `command:` (which enables it) overrides this CMD entirely for local dev.
# This is what actually runs if the image is ever run standalone.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
