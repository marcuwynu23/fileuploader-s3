# Multi-stage, multi-environment Dockerfile for fileuploader-s3
ARG PYTHON_VERSION=3.10
ARG BUILD_ENV=production

# Base stage
FROM python:${PYTHON_VERSION}-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Builder stage (for dependencies)
FROM base AS builder
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system -e .

# Development stage
FROM base AS development
ENV FLASK_DEBUG=true
ENV FLASK_ENV=development
COPY --from=builder /usr/local /usr/local
COPY . .
EXPOSE 2424
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:2424/health || exit 1
CMD ["uv", "run", "app"]

# Production stage
FROM base AS production
ENV FLASK_DEBUG=false
ENV FLASK_ENV=production
COPY --from=builder /usr/local /usr/local
COPY . .
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser
EXPOSE 2424
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:2424/health || exit 1
CMD ["uv", "run", "waitress-serve", "--host=0.0.0.0", "--port=2424", "--call", "fileuploader_s3.main:app"]
