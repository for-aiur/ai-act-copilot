FROM ghcr.io/astral-sh/uv:0.13.6 AS uv
FROM python:3.12-slim

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY engine/ /app/engine/
RUN uv sync --project engine --extra workbench --extra rag --extra postgres --locked --no-dev \
    && useradd --uid 10001 --create-home aiact \
    && mkdir -p /data /reports \
    && chown aiact:aiact /data /reports
COPY scripts/start-workbench.sh /app/scripts/start-workbench.sh
ENV PATH="/app/engine/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    AIACT_DATA_DIR=/data \
    DATABASE_URL=sqlite:////data/aiact.db
USER aiact
EXPOSE 8000
CMD ["sh", "/app/scripts/start-workbench.sh"]
