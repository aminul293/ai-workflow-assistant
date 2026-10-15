# Disposable synthetic-data preview; no credentials belong in build arguments.
FROM node:22-bookworm-slim AS web-build
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim AS preview
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY --from=web-build --chown=node:node /build/frontend/.next ./frontend/.next
COPY --from=web-build --chown=node:node /build/frontend/node_modules ./frontend/node_modules
COPY --from=web-build --chown=node:node /build/frontend/package.json ./frontend/package.json
COPY --chown=node:node backend/app/ ./backend/app/
COPY --chown=node:node backend/migrations/ ./backend/migrations/
COPY --chown=node:node backend/alembic.ini ./backend/alembic.ini
COPY --chown=node:node scripts/start_preview.py ./scripts/start_preview.py
USER node
EXPOSE 10000
CMD ["python", "scripts/start_preview.py"]
