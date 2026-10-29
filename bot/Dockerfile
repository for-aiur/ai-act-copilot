FROM ghcr.io/astral-sh/uv:0.13.6 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home bot \
    && mkdir /data && chown bot:bot /data
WORKDIR /app
COPY engine/ /app/engine/
RUN uv sync --project engine --extra bot --locked --no-dev
ENV PATH="/app/engine/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 AIACT_BOT_DATABASE=/data/reviews.sqlite3
USER bot
EXPOSE 8787
CMD ["aiact-bot", "serve", "--config", "/config/bot.toml", "--host", "0.0.0.0", "--port", "8787"]
