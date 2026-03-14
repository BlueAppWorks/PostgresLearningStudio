"""
Schema initialization for metrics storage in Postgres.
Creates the metrics schema and all required tables (idempotent).
"""

import os

from db import get_connection

SCHEMA_SQL = """
-- Metrics schema
CREATE SCHEMA IF NOT EXISTS metrics;

-- Connection targets
CREATE TABLE IF NOT EXISTS metrics.pg_targets (
    target_id       SERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    host            TEXT NOT NULL,
    port            INTEGER DEFAULT 5432,
    dbname          TEXT DEFAULT 'postgres',
    username        TEXT NOT NULL,
    password        TEXT NOT NULL,
    is_primary      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Benchmark runs
CREATE TABLE IF NOT EXISTS metrics.benchmark_runs (
    run_id          BIGSERIAL PRIMARY KEY,
    queue_id        BIGINT,
    run_name        TEXT,
    tool            TEXT NOT NULL DEFAULT 'pgbench',
    parameters      JSONB NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT DEFAULT 'running',
    summary         JSONB,
    pg_version      TEXT,
    pg_settings     JSONB,
    db_spec         JSONB,
    target_name     TEXT
);

-- Add columns if upgrading
DO $$
BEGIN
    ALTER TABLE metrics.benchmark_runs ADD COLUMN IF NOT EXISTS pg_version TEXT;
    ALTER TABLE metrics.benchmark_runs ADD COLUMN IF NOT EXISTS pg_settings JSONB;
    ALTER TABLE metrics.benchmark_runs ADD COLUMN IF NOT EXISTS db_spec JSONB;
    ALTER TABLE metrics.benchmark_runs ADD COLUMN IF NOT EXISTS target_name TEXT;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

-- pgbench progress (from -P output)
CREATE TABLE IF NOT EXISTS metrics.pgbench_progress (
    run_id          BIGINT REFERENCES metrics.benchmark_runs(run_id),
    elapsed_sec     NUMERIC NOT NULL,
    tps             NUMERIC,
    latency_avg_ms  NUMERIC,
    latency_stddev  NUMERIC,
    PRIMARY KEY (run_id, elapsed_sec)
);

-- Monitoring snapshots
CREATE TABLE IF NOT EXISTS metrics.snapshots (
    snapshot_id     BIGSERIAL PRIMARY KEY,
    run_id          BIGINT REFERENCES metrics.benchmark_runs(run_id),
    collected_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- pg_stat_activity snapshots
CREATE TABLE IF NOT EXISTS metrics.stat_activity (
    snapshot_id     BIGINT REFERENCES metrics.snapshots(snapshot_id),
    pid             INTEGER,
    state           TEXT,
    wait_event_type TEXT,
    wait_event      TEXT,
    query           TEXT,
    backend_start   TIMESTAMPTZ,
    xact_start      TIMESTAMPTZ,
    query_start     TIMESTAMPTZ
);

-- pg_stat_database snapshots
CREATE TABLE IF NOT EXISTS metrics.stat_database (
    snapshot_id       BIGINT REFERENCES metrics.snapshots(snapshot_id),
    datname           TEXT,
    xact_commit       BIGINT,
    xact_rollback     BIGINT,
    blks_read         BIGINT,
    blks_hit          BIGINT,
    tup_returned      BIGINT,
    tup_fetched       BIGINT,
    tup_inserted      BIGINT,
    tup_updated       BIGINT,
    tup_deleted       BIGINT,
    deadlocks         BIGINT,
    temp_files        BIGINT,
    temp_bytes        BIGINT
);

-- User-registered SQL sample scripts
CREATE TABLE IF NOT EXISTS metrics.user_sql_samples (
    sample_id   SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'User Scripts',
    description TEXT DEFAULT '',
    sql_content TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- User-registered benchmark scenarios (write + read script pair)
CREATE TABLE IF NOT EXISTS metrics.user_bench_scenarios (
    scenario_id   SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT DEFAULT '',
    write_script  TEXT NOT NULL,
    read_script   TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);
"""


def _register_primary_target(conn):
    """Auto-register the primary connection as a target."""
    host = os.environ.get("PGHOST", "localhost")
    port = int(os.environ.get("PGPORT", "5432"))
    dbname = os.environ.get("PGDATABASE", "benchmark")
    user = os.environ.get("PGUSER", "postgres")
    password = os.environ.get("PGPASSWORD", "")

    conn.execute(
        """INSERT INTO metrics.pg_targets (name, host, port, dbname, username, password, is_primary)
           VALUES (%s, %s, %s, %s, %s, %s, TRUE)
           ON CONFLICT (name) DO UPDATE
           SET host = EXCLUDED.host, port = EXCLUDED.port, dbname = EXCLUDED.dbname,
               username = EXCLUDED.username, password = EXCLUDED.password, is_primary = TRUE""",
        ("Primary Database", host, port, dbname, user, password),
    )


def init_schema():
    """Initialize the metrics schema in Postgres."""
    with get_connection() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()
        _register_primary_target(conn)
        conn.commit()
    print("Metrics schema initialized.")


if __name__ == "__main__":
    init_schema()
