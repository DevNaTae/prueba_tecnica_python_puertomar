# syntax=docker/dockerfile:1.7

FROM python:3.14-slim-bookworm AS base

ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid "${APP_GID}" \
        --create-home --shell /usr/sbin/nologin app \
    && chown app:app /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app src/ ./src/
COPY --chown=app:app samples/ ./samples/

USER app

FROM base AS runtime

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["samples/input.json", "--output", "salida/reporte.json", "--persist"]

FROM base AS tests

COPY --chown=app:app pytest.ini ./
COPY --chown=app:app tests/ ./tests/

ENTRYPOINT ["pytest"]
CMD ["-q"]
