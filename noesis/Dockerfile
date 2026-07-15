# syntax=docker/dockerfile:1.7
FROM python:3.12.13-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir ".[rag,local-llm,coordination]"

FROM python:3.12.13-slim AS runtime
ARG NOESIS_UID=10001
ARG NOESIS_GID=10001
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NOESIS_DATA_DIR=/app/.noesis_data \
    NOESIS_LOG_DIR=/app/.noesis_data/logs
RUN groupadd --gid "${NOESIS_GID}" noesis \
    && useradd --uid "${NOESIS_UID}" --gid "${NOESIS_GID}" --home-dir /app --create-home noesis \
    && install -d -o "${NOESIS_UID}" -g "${NOESIS_GID}" \
       /app/.noesis_data /app/.noesis_data/logs /app/.noesis_data/tmp /app/.noesis_data/cache
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
USER noesis
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=2)"
CMD ["noesis"]
