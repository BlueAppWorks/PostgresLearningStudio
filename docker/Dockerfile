FROM python:3.11-slim AS base

# Install PostgreSQL (pgbench is in the server package, not client-only)
# Apply all security patches to minimize CVEs
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    postgresql-17 \
    dnsutils \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && /usr/lib/postgresql/17/bin/pgbench --version

# Make pgbench directly accessible
ENV PATH="/usr/lib/postgresql/17/bin:${PATH}"

# Python dependencies
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Application code
COPY app/ /app/

WORKDIR /app

# Entrypoint (copy while still root to ensure correct permissions)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Run as non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser && \
    chown -R appuser:appuser /app && \
    chown appuser:appuser /entrypoint.sh
USER appuser

# Ensure Python output is not buffered (critical for SPCS log visibility)
ENV PYTHONUNBUFFERED=1

# Health check endpoint
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
