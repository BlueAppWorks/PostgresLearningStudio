# ================================================================
# Stage 1: Extract pgbench binary and its runtime dependencies
# ================================================================
# postgresql-17 (server package) is installed only in this builder
# stage — only the pgbench binary and its shared libraries are
# carried forward to the runtime image.
# ================================================================
FROM python:3.11-slim AS pgbench-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-17 \
    && rm -rf /var/lib/apt/lists/*

# Collect pgbench binary + every shared library it links against.
# The runtime image already has libc/libm/libpthread, but copying
# them again is harmless and guarantees nothing is missing.
RUN mkdir -p /pgbench-dist/bin /pgbench-dist/lib && \
    cp /usr/lib/postgresql/17/bin/pgbench /pgbench-dist/bin/ && \
    ldd /usr/lib/postgresql/17/bin/pgbench | \
    awk '/=>/ && $3 != "" { print $3 }' | sort -u | \
    while read lib; do cp --dereference "$lib" /pgbench-dist/lib/; done

# ================================================================
# Stage 2: Runtime — minimal application image
# ================================================================
# Removed from runtime vs. the previous single-stage build:
#   - postgresql-17  (server + all PG binaries)  → pgbench only
#   - dnsutils       (dig/nslookup — unused)     → removed
#   - curl           (HEALTHCHECK only)           → Python urllib
#   - psql           (entrypoint DB init)         → Python psycopg
# ================================================================
FROM python:3.11-slim

# Apply security patches
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*

# pgbench binary and its shared libraries from builder stage
COPY --from=pgbench-builder /pgbench-dist/bin/pgbench /usr/local/bin/pgbench
COPY --from=pgbench-builder /pgbench-dist/lib/ /usr/local/lib/
RUN ldconfig && pgbench --version

# Python dependencies
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Application code
COPY app/ /app/

WORKDIR /app

# Entrypoint and utility scripts (copy while still root)
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/init_db.py /init_db.py
COPY docker/healthcheck.py /healthcheck.py
RUN chmod +x /entrypoint.sh

# Run as non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser && \
    chown -R appuser:appuser /app && \
    chown appuser:appuser /entrypoint.sh /init_db.py /healthcheck.py
USER appuser

# Ensure Python output is not buffered (critical for SPCS log visibility)
ENV PYTHONUNBUFFERED=1

# Health check endpoint (uses Python instead of curl)
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 /healthcheck.py || exit 1

ENTRYPOINT ["/entrypoint.sh"]
