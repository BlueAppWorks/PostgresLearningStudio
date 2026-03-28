#!/bin/bash
set -e

echo "=== Postgres Learning Studio ==="
echo "Starting at $(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ============================================================
# Load database credentials from Snowflake Secrets
# ============================================================
SECRET_PATH="/snowflake/session/secrets/postgres_secret"

if [ -f "${SECRET_PATH}/username" ]; then
    export PGUSER=$(cat "${SECRET_PATH}/username")
    export PGPASSWORD=$(cat "${SECRET_PATH}/password")
    echo "Credentials loaded from Snowflake Secret"
else
    echo "Using credentials from environment variables"
fi

# PostgreSQL connection settings
export PGHOST=${PGHOST:?PGHOST is required}
export PGPORT=${PGPORT:-5432}
export PGDATABASE=${PGDATABASE:-benchmark}
export PGSSLMODE=${PGSSLMODE:-require}

echo "Target: ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE} (ssl=${PGSSLMODE})"

# ============================================================
# Wait for DNS resolution (SPCS EAI activation delay)
# ============================================================
echo ""
echo "Waiting for DNS resolution of ${PGHOST}..."
MAX_RETRIES=30
RETRY_COUNT=0
while true; do
    if getent hosts "${PGHOST}" > /dev/null 2>&1; then
        RESOLVED_IP=$(getent hosts "${PGHOST}" | awk '{print $1}')
        echo "DNS resolved: ${PGHOST} -> ${RESOLVED_IP}"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ ${RETRY_COUNT} -ge ${MAX_RETRIES} ]; then
        echo "WARNING: DNS resolution failed after ${MAX_RETRIES} retries (150s)"
        echo "Proceeding anyway (psycopg may resolve independently)..."
        break
    fi
    echo "  DNS not ready, retrying in 5s (${RETRY_COUNT}/${MAX_RETRIES})..."
    sleep 5
done

# ============================================================
# Wait for TCP connectivity to Postgres
# ============================================================
echo ""
echo "Testing TCP connectivity to ${PGHOST}:${PGPORT}..."
RETRY_COUNT=0
while true; do
    if timeout 5 bash -c "echo > /dev/tcp/${PGHOST}/${PGPORT}" 2>/dev/null; then
        echo "TCP connection to ${PGHOST}:${PGPORT} succeeded"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ ${RETRY_COUNT} -ge 10 ]; then
        echo "WARNING: TCP connectivity check timed out after 10 retries (50s)"
        echo "Proceeding anyway..."
        break
    fi
    echo "  TCP not ready, retrying in 5s (${RETRY_COUNT}/10)..."
    sleep 5
done

# ============================================================
# Auto-create benchmark database if needed
# ============================================================
echo ""
echo "Checking if database '${PGDATABASE}' exists..."
DB_EXISTS=$(PGDATABASE=postgres psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" \
    -tAc "SELECT 1 FROM pg_database WHERE datname='${PGDATABASE}'" 2>/dev/null || echo "0")

if [ "${DB_EXISTS}" != "1" ]; then
    echo "Creating database '${PGDATABASE}'..."
    PGDATABASE=postgres psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" \
        -c "CREATE DATABASE ${PGDATABASE};" 2>&1 || echo "WARNING: Database creation failed (Postgres may still be starting)"
else
    echo "Database '${PGDATABASE}' already exists"
fi

echo "NOTE: If Postgres is still starting, the Web UI will be available but DB operations may fail until Postgres is ready."

# ============================================================
# Initialize metrics schema
# ============================================================
echo ""
echo "Initializing metrics schema..."
cd /app
python3 schema.py || echo "WARNING: schema initialization failed (Postgres may still be starting). Will retry on first request."

# ============================================================
# Start application
# ============================================================
echo ""
echo "Starting Postgres Learning Studio..."
exec python3 main.py
