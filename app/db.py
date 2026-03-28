"""
Database connection management.
Provides connection pools for the benchmark target Postgres
and helpers for pgbench subprocess invocation.
"""

import os

import psycopg
from psycopg_pool import ConnectionPool

# Build connection info from environment variables (set by entrypoint.sh)
PG_CONNINFO = (
    f"host={os.environ.get('PGHOST', 'localhost')} "
    f"port={os.environ.get('PGPORT', '5432')} "
    f"dbname={os.environ.get('PGDATABASE', 'benchmark')} "
    f"user={os.environ.get('PGUSER', 'postgres')} "
    f"password={os.environ.get('PGPASSWORD', '')} "
    f"sslmode={os.environ.get('PGSSLMODE', 'require')}"
)

_monitor_pool: ConnectionPool | None = None

# Session-held connections for transaction mode (keyed by session_id)
_txn_connections: dict[str, psycopg.Connection] = {}


def get_txn_connection(session_id: str, target_id: int | None = None) -> psycopg.Connection:
    """Get or create a persistent connection for transaction mode.
    The connection stays open across requests until COMMIT/ROLLBACK."""
    if session_id in _txn_connections:
        conn = _txn_connections[session_id]
        if conn.closed:
            del _txn_connections[session_id]
        else:
            return conn

    if target_id:
        target = get_target(target_id)
        if target:
            conninfo = (
                f"host={target['host']} "
                f"port={target['port']} "
                f"dbname={target['dbname']} "
                f"user={target['username']} "
                f"password={target['password']} "
                f"sslmode=require"
            )
        else:
            conninfo = PG_CONNINFO
    else:
        conninfo = PG_CONNINFO

    conn = psycopg.connect(conninfo, autocommit=False)
    _txn_connections[session_id] = conn
    return conn


def release_txn_connection(session_id: str):
    """Close and remove a transaction-mode connection."""
    conn = _txn_connections.pop(session_id, None)
    if conn and not conn.closed:
        try:
            conn.close()
        except Exception:
            pass


def get_txn_status(session_id: str) -> str:
    """Return transaction status for a session: 'idle', 'in_transaction', or 'none'."""
    conn = _txn_connections.get(session_id)
    if not conn or conn.closed:
        return "none"
    info = conn.info
    if info.transaction_status == psycopg.pq.TransactionStatus.IDLE:
        return "idle"
    elif info.transaction_status == psycopg.pq.TransactionStatus.INTRANS:
        return "in_transaction"
    elif info.transaction_status == psycopg.pq.TransactionStatus.INERROR:
        return "in_error"
    return "unknown"


def get_monitor_pool() -> ConnectionPool:
    """Get or create the connection pool for monitoring queries."""
    global _monitor_pool
    if _monitor_pool is None:
        _monitor_pool = ConnectionPool(
            PG_CONNINFO,
            min_size=1,
            max_size=3,
            open=True,
        )
    return _monitor_pool


def get_connection() -> psycopg.Connection:
    """Get a single connection for one-off operations (schema init, etc.)."""
    return psycopg.connect(PG_CONNINFO)


def get_postgres_db_connection() -> psycopg.Connection:
    """Get a connection to the 'postgres' database (same host, same credentials).
    Used for pg_cron which must be installed in the postgres database."""
    conninfo = (
        f"host={os.environ.get('PGHOST', 'localhost')} "
        f"port={os.environ.get('PGPORT', '5432')} "
        f"dbname=postgres "
        f"user={os.environ.get('PGUSER', 'postgres')} "
        f"password={os.environ.get('PGPASSWORD', '')} "
        f"sslmode={os.environ.get('PGSSLMODE', 'require')}"
    )
    return psycopg.connect(conninfo)


def get_pgbench_env(password_override: str | None = None) -> dict:
    """Return environment variables dict for pgbench subprocess."""
    env = os.environ.copy()
    env["PGPASSWORD"] = password_override or os.environ.get("PGPASSWORD", "")
    env["PGSSLMODE"] = os.environ.get("PGSSLMODE", "require")
    return env


def get_targets() -> list[dict]:
    """List all configured connection targets."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM metrics.pg_targets ORDER BY is_primary DESC, name"
        )
        return [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]


def get_target(target_id: int) -> dict | None:
    """Get a specific connection target by ID."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM metrics.pg_targets WHERE target_id = %s", (target_id,)
        )
        row = cur.fetchone()
        if row:
            return dict(zip([d.name for d in cur.description], row))
    return None


def get_user_sql_samples() -> list[dict]:
    """List all user-registered SQL samples."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM metrics.user_sql_samples ORDER BY category, title"
        )
        return [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]


def get_user_sql_sample(sample_id: int) -> dict | None:
    """Get a single user SQL sample by ID."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM metrics.user_sql_samples WHERE sample_id = %s", (sample_id,)
        )
        row = cur.fetchone()
        if row:
            return dict(zip([d.name for d in cur.description], row))
    return None


def add_user_sql_sample(title: str, category: str, description: str, sql_content: str) -> int:
    """Insert a user SQL sample. Returns sample_id."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO metrics.user_sql_samples (title, category, description, sql_content)
               VALUES (%s, %s, %s, %s) RETURNING sample_id""",
            (title, category, description, sql_content),
        )
        sample_id = cur.fetchone()[0]
        conn.commit()
        return sample_id


def delete_user_sql_sample(sample_id: int):
    """Delete a user SQL sample."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM metrics.user_sql_samples WHERE sample_id = %s", (sample_id,)
        )
        conn.commit()


def get_user_bench_scenarios() -> list[dict]:
    """List all user-registered benchmark scenarios."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM metrics.user_bench_scenarios ORDER BY name"
        )
        return [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]


def get_user_bench_scenario(scenario_id: int) -> dict | None:
    """Get a single benchmark scenario by ID."""
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT * FROM metrics.user_bench_scenarios WHERE scenario_id = %s",
            (scenario_id,),
        )
        row = cur.fetchone()
        if row:
            return dict(zip([d.name for d in cur.description], row))
    return None


def add_user_bench_scenario(name: str, description: str,
                            write_script: str, read_script: str) -> int:
    """Insert a benchmark scenario. Returns scenario_id."""
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO metrics.user_bench_scenarios
               (name, description, write_script, read_script)
               VALUES (%s, %s, %s, %s) RETURNING scenario_id""",
            (name, description, write_script, read_script),
        )
        scenario_id = cur.fetchone()[0]
        conn.commit()
        return scenario_id


def delete_user_bench_scenario(scenario_id: int):
    """Delete a benchmark scenario."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM metrics.user_bench_scenarios WHERE scenario_id = %s",
            (scenario_id,),
        )
        conn.commit()


def get_target_connection(target_id: int) -> psycopg.Connection:
    """Get a connection to a specific target database."""
    target = get_target(target_id)
    if not target:
        return get_connection()
    conninfo = (
        f"host={target['host']} "
        f"port={target['port']} "
        f"dbname={target['dbname']} "
        f"user={target['username']} "
        f"password={target['password']} "
        f"sslmode=require"
    )
    return psycopg.connect(conninfo)
