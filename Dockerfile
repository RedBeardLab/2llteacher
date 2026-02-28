# Use Python 3.12 slim image as base
FROM python:3.12-slim AS base

# Declare volume for database persistence
VOLUME ["/data"]

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=llteacher.production \
    DATABASE_PATH=/data/llteacher.sqlite \
    OTEL_SERVICE_NAME=llteacher \
    OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io \
    OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf \
    OTEL_TRACES_EXPORTER=otlp \
    OTEL_METRICS_EXPORTER=none \
    OTEL_LOGS_EXPORTER=otlp \
    OTEL_PYTHON_LOGGING_AUTO_INSTRUMENTATION_ENABLED=true

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install uv

# Set work directory
WORKDIR /app

# Copy UV configuration files and README.md (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Copy workspace structure - apps and core components
COPY src/ ./src/

# Install dependencies using uv (workspace-aware)
RUN uv sync --frozen

# Copy remaining project files
COPY manage.py run_tests.py docker-entrypoint.sh ./
COPY templates/ ./templates/
COPY static/ ./static/

# Make entrypoint script executable
RUN chmod +x docker-entrypoint.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && \
    chown -R app:app /app && \
    mkdir -p /app/staticfiles /data && \
    chown -R app:app /app/staticfiles /data

# Collect static files as root first (before switching to app user)
RUN uv run python manage.py collectstatic --noinput

# Ensure proper ownership of static files
RUN chown -R app:app /app/staticfiles

USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Set entrypoint and default command
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uv", "run", "opentelemetry-instrument", \
                    "gunicorn", \
                    "--bind", "0.0.0.0:8000", \
                    "--workers", "8", \
                    "--timeout", "120", \
                    "--access-logfile", "-", \
                    "--access-logformat", "%(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\" %(D)s", \
                    "llteacher.wsgi:application"]
