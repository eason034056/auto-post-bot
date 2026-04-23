# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.13-slim
WORKDIR /app

# tzdata for TZ env
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Chromium + system deps for Playwright HTML renderer
# 💡 --with-deps 會自動 apt-get install 所有 Chromium 需要的 lib（libnss3 等）
RUN playwright install --with-deps chromium

# Copy backend
COPY api/ ./api/
COPY main.py ./
COPY src/ ./src/

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist

# Copy required assets (fonts for CJK rendering via HTML templates)
COPY fonts/ ./fonts/

# Output dir - will be volume-mounted
ENV OUTPUT_DIR=/app/output
ENV FRONTEND_DIST_PATH=/app/frontend_dist

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
