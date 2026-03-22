"""Built-in SQL sample queries for the SQL Client learning interface."""

_SAMPLES = [
    {
        "id": "basic_select",
        "category": "Basics",
        "title": "SELECT all rows",
        "description": "Retrieve all rows from a table.",
        "sql": "SELECT * FROM pg_stat_activity LIMIT 20;",
    },
    {
        "id": "basic_version",
        "category": "Basics",
        "title": "PostgreSQL version",
        "description": "Check the PostgreSQL server version.",
        "sql": "SELECT version();",
    },
    {
        "id": "basic_databases",
        "category": "Basics",
        "title": "List databases",
        "description": "Show all databases on the server.",
        "sql": "SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size\nFROM pg_database\nORDER BY pg_database_size(datname) DESC;",
    },
    {
        "id": "basic_tables",
        "category": "Basics",
        "title": "List tables",
        "description": "Show all user tables in the current database.",
        "sql": "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS size\nFROM pg_tables\nWHERE schemaname NOT IN ('pg_catalog', 'information_schema')\nORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;",
    },
    {
        "id": "perf_active_queries",
        "category": "Performance",
        "title": "Active queries",
        "description": "Show currently running queries.",
        "sql": "SELECT pid, usename, state, query_start, now() - query_start AS duration, query\nFROM pg_stat_activity\nWHERE state = 'active'\nORDER BY query_start;",
    },
    {
        "id": "perf_table_stats",
        "category": "Performance",
        "title": "Table statistics",
        "description": "Show sequential vs index scan ratios for tables.",
        "sql": "SELECT relname,\n       seq_scan, seq_tup_read,\n       idx_scan, idx_tup_fetch,\n       n_tup_ins, n_tup_upd, n_tup_del,\n       n_live_tup, n_dead_tup\nFROM pg_stat_user_tables\nORDER BY seq_scan DESC\nLIMIT 20;",
    },
    {
        "id": "perf_index_usage",
        "category": "Performance",
        "title": "Index usage",
        "description": "Show index usage statistics.",
        "sql": "SELECT schemaname, relname, indexrelname,\n       idx_scan, idx_tup_read, idx_tup_fetch,\n       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size\nFROM pg_stat_user_indexes\nORDER BY idx_scan DESC\nLIMIT 20;",
    },
    {
        "id": "perf_cache_hit",
        "category": "Performance",
        "title": "Cache hit ratio",
        "description": "Check buffer cache hit ratio.",
        "sql": "SELECT\n  sum(heap_blks_read) AS heap_read,\n  sum(heap_blks_hit) AS heap_hit,\n  CASE WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0\n    THEN round(sum(heap_blks_hit)::numeric / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100, 2)\n    ELSE 0\n  END AS hit_ratio_pct\nFROM pg_statio_user_tables;",
    },
    {
        "id": "admin_locks",
        "category": "Admin",
        "title": "Current locks",
        "description": "Show current lock activity.",
        "sql": "SELECT l.pid, l.locktype, l.mode, l.granted,\n       a.usename, a.query_start, a.state,\n       left(a.query, 80) AS query\nFROM pg_locks l\nJOIN pg_stat_activity a ON l.pid = a.pid\nWHERE l.pid != pg_backend_pid()\nORDER BY l.pid;",
    },
    {
        "id": "admin_settings",
        "category": "Admin",
        "title": "Key settings",
        "description": "Show important PostgreSQL configuration parameters.",
        "sql": "SELECT name, setting, unit, short_desc\nFROM pg_settings\nWHERE name IN (\n  'shared_buffers', 'work_mem', 'maintenance_work_mem',\n  'effective_cache_size', 'max_connections',\n  'checkpoint_completion_target', 'wal_buffers',\n  'random_page_cost', 'effective_io_concurrency'\n)\nORDER BY name;",
    },
    {
        "id": "admin_extensions",
        "category": "Admin",
        "title": "Installed extensions",
        "description": "List all installed PostgreSQL extensions.",
        "sql": "SELECT extname, extversion, extnamespace::regnamespace AS schema\nFROM pg_extension\nORDER BY extname;",
    },
    {
        "id": "lake_iceberg_create",
        "category": "pg_lake",
        "title": "Create Iceberg table",
        "description": "Create an Iceberg table with day partitioning.",
        "sql": "CREATE TABLE lake_demo.access_logs (\n    log_time   TIMESTAMPTZ NOT NULL DEFAULT now(),\n    user_id    INT,\n    action     TEXT,\n    path       TEXT,\n    status     INT,\n    response_ms DOUBLE PRECISION\n) USING iceberg\n  WITH (partition_by = 'day(log_time)');",
    },
    {
        "id": "lake_copy_export",
        "category": "pg_lake",
        "title": "COPY TO S3 (Parquet)",
        "description": "Export a table to S3 as Parquet.",
        "sql": "-- Replace s3://your-bucket/ with your actual S3 path\nCOPY lake_demo.access_logs\n  TO 's3://your-bucket/demo/access_logs.parquet';",
    },
    {
        "id": "lake_foreign_table",
        "category": "pg_lake",
        "title": "Foreign Table (S3 Parquet)",
        "description": "Query S3 Parquet files directly without copying data.",
        "sql": "CREATE FOREIGN TABLE lake_demo.s3_logs ()\n    SERVER pg_lake\n    OPTIONS (path 's3://your-bucket/demo/access_logs.parquet');\n\nSELECT action, count(*) AS cnt,\n       avg(response_ms)::numeric(10,2) AS avg_ms\nFROM lake_demo.s3_logs\nGROUP BY action ORDER BY cnt DESC;",
    },
    {
        "id": "lake_iot_partition",
        "category": "pg_lake",
        "title": "IoT Hot/Cold partitioning",
        "description": "Time-series partitioned table for IoT sensor data with pg_partman.",
        "sql": "CREATE TABLE iot.sensor_data (\n    ts        TIMESTAMPTZ NOT NULL,\n    device_id INT         NOT NULL,\n    temp      DOUBLE PRECISION,\n    humidity  DOUBLE PRECISION,\n    pressure  DOUBLE PRECISION\n) PARTITION BY RANGE (ts);\n\n-- pg_partman: auto-manage daily partitions\nSELECT partman.create_parent(\n    p_parent_table := 'iot.sensor_data',\n    p_control      := 'ts',\n    p_interval     := 'daily',\n    p_premake      := 3\n);",
    },
]


def get_samples() -> list[dict]:
    """Return all built-in SQL samples."""
    return list(_SAMPLES)


def get_sample_by_id(sample_id: str) -> dict | None:
    """Return a single sample by ID, or None if not found."""
    for s in _SAMPLES:
        if s["id"] == sample_id:
            return dict(s)
    return None
