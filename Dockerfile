# ── Stage 1: Build React frontend ─────────────────────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend

# Install deps first (better layer caching)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python runtime ────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY api/ ./api/
COPY config.yaml ./

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create runtime directories
RUN mkdir -p downloads logs /secrets

EXPOSE 8080

# SERVICE_ACCOUNT_PATH: override for local dev; default is Cloud Run secret mount path
ENV SERVICE_ACCOUNT_PATH=/secrets/service_account.json
ENV PORT=8080

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8080"]
