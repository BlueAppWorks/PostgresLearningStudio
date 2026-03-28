"""
PostgreSQL parameter collector.
Auto-collects version and key performance settings at benchmark start time.
"""

BENCHMARK_PG_SETTINGS = [
    # Memory
    "shared_buffers",
    "effective_cache_size",
    "work_mem",
    "maintenance_work_mem",
    "wal_buffers",
    "huge_pages",
    # WAL
    "max_wal_size",
    "min_wal_size",
    "wal_level",
    "checkpoint_completion_target",
    "synchronous_commit",
    # Parallelism
    "max_worker_processes",
    "max_parallel_workers",
    "max_parallel_workers_per_gather",
    # I/O
    "effective_io_concurrency",
    "random_page_cost",
    "seq_page_cost",
    # Connections
    "max_connections",
]


def _format_bytes(setting: str, unit: str | None) -> str:
    """Convert pg_settings value to human-readable size string."""
    try:
        val = int(setting)
    except (ValueError, TypeError):
        return setting

    if unit == "8kB":
        total_bytes = val * 8 * 1024
    elif unit == "kB":
        total_bytes = val * 1024
    elif unit == "MB":
        total_bytes = val * 1024 * 1024
    elif unit == "B":
        total_bytes = val
    else:
        return setting

    if total_bytes >= 1024 * 1024 * 1024:
        return f"{total_bytes / (1024**3):.1f}GB"
    elif total_bytes >= 1024 * 1024:
        return f"{total_bytes / (1024**2):.0f}MB"
    elif total_bytes >= 1024:
        return f"{total_bytes / 1024:.0f}KB"
    return f"{total_bytes}B"


def collect_pg_info(conn) -> dict:
    """
    Collect PostgreSQL version and key performance settings.

    Args:
        conn: psycopg connection to the target database

    Returns:
        dict with 'version' and 'settings' keys
    """
    result = {"version": "", "settings": {}}

    try:
        cur = conn.execute("SELECT version()")
        result["version"] = cur.fetchone()[0]
    except Exception as e:
        result["version"] = f"Error: {e}"

    try:
        placeholders = ",".join(["%s"] * len(BENCHMARK_PG_SETTINGS))
        cur = conn.execute(
            f"SELECT name, setting, unit, short_desc "
            f"FROM pg_settings WHERE name IN ({placeholders})",
            BENCHMARK_PG_SETTINGS,
        )
        for row in cur.fetchall():
            name, setting, unit, desc = row
            is_memory = unit in ("8kB", "kB", "MB", "B")
            display = _format_bytes(setting, unit) if is_memory else setting
            result["settings"][name] = {
                "setting": setting,
                "unit": unit or "",
                "display": display,
                "description": desc or "",
            }
    except Exception as e:
        print(f"Error collecting pg_settings: {e}")

    return result
