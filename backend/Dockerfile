# Stage 1: Build dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies for asyncpg and other compiled packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production image
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (libpq for asyncpg)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --system app && \
    adduser --system --ingroup app app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/

# Switch to non-root user
USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
