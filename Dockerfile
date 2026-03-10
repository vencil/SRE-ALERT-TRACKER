# ============================================================
# Stage 1: Frontend build
# ============================================================
FROM node:20-alpine AS frontend

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --production=false
COPY frontend/ ./
RUN npm run build

# ============================================================
# Stage 2: Backend (production)
# ============================================================
FROM python:3.12-slim AS production

# Labels
LABEL maintainer="sre-team" \
      description="SRE Alert Tracking System" \
      version="1.1.1"

WORKDIR /app

# Install dependencies first (cached layer)
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./

# Copy frontend build output into backend/static
COPY --from=frontend /app/frontend/dist ./static/

# Copy VERSION for runtime version reporting
COPY VERSION /app/VERSION

# Copy cluster config template
COPY config/ /app/config/

# Create data directory for SQLite + tmp for Python cache (readOnlyRootFilesystem)
RUN mkdir -p /data /tmp/app-cache

# Security: non-root user
RUN useradd -m -r -s /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app /data /tmp/app-cache

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
