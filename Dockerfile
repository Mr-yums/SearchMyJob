FROM node:24-bookworm-slim AS node-base

FROM node-base AS assets
WORKDIR /build
COPY ui/package*.json ./ui/
RUN cd ui && npm ci
COPY ui ./ui
RUN cd ui && npm run build

FROM node-base AS mcp-dependencies
WORKDIR /build
COPY mcp/package*.json ./mcp/
RUN cd mcp && npm ci --omit=dev
COPY mcp ./mcp

FROM python:3.14-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend SEARCHMYJOB_STATE=/state SEARCHMYJOB_PORT=8935 SEARCHMYJOB_OAUTH_BIND=0.0.0.0
RUN apt-get update && apt-get install -y --no-install-recommends tini libatomic1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home app \
    && mkdir /state && chown app:app /state
COPY --from=node-base /usr/local/bin/node /usr/bin/node
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install -r requirements.lock.txt
COPY --chown=app:app backend ./backend
COPY --from=assets --chown=app:app /build/ui/dist ./ui/dist
COPY --from=mcp-dependencies --chown=app:app /build/mcp ./mcp
USER app
WORKDIR /app/backend
EXPOSE 8935
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "uvicorn", "searchmyjob.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8935", "--no-access-log"]
