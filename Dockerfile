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

# Install runtime deps (Pillow needs libjpeg, etc.) + tzdata for TZ env
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libfreetype6-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend
COPY api/ ./api/
COPY main.py ./
COPY src/ ./src/

# Copy frontend build
COPY --from=frontend-builder /app/frontend/dist ./frontend_dist

# Copy required assets (fonts, demo post backgrounds)
COPY fonts/ ./fonts/
COPY ["demo post", "demo post/"]

# Output dir - will be volume-mounted
ENV OUTPUT_DIR=/app/output
ENV FRONTEND_DIST_PATH=/app/frontend_dist

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
