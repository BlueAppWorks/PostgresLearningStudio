"""pg_lake — Getting Started guide, demos, and API endpoints."""

import os
import time

from flask import Blueprint, jsonify, redirect, render_template, request

from db import get_connection, get_postgres_db_connection

pg_lake_bp = Blueprint("pg_lake", __name__, url_prefix="/pg-lake")


# ── Helper ──


def _get_pg_lake_status() -> dict:
    """Detect pg_lake availability and installation status."""
    status = {"available": False, "installed": False, "version": ""}
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT installed_version, default_version "
                "FROM pg_available_extensions WHERE name = 'pg_lake'"
            )
            row = cur.fetchone()
            if row:
                status["available"] = True
                status["installed"] = row[0] is not None
                status["version"] = row[0] or row[1]
    except Exception:
        pass
    return status


def _get_instance_name() -> str:
    """Get Postgres instance name from environment variable."""
    return os.environ.get("PG_INSTANCE_NAME", "")


def _get_connection_type() -> str:
    """Get Postgres connection type (snowflake_postgres / external)."""
    return os.environ.get("PG_CONNECTION_TYPE", "")


# ── Page routes ──


@pg_lake_bp.route("/")
def overview():
    status = _get_pg_lake_status()
    return render_template("pg_lake_index.html", pg_lake_status=status)


@pg_lake_bp.route("/setup")
def setup_guide():
    status = _get_pg_lake_status()
    instance_name = _get_instance_name()
    connection_type = _get_connection_type()
    return render_template(
        "pg_lake_setup.html",
        pg_lake_status=status,
        instance_name=instance_name,
        connection_type=connection_type,
    )


@pg_lake_bp.route("/demos")
def demos():
    status = _get_pg_lake_status()
    return render_template("pg_lake_demos.html", pg_lake_status=status)


# ── API endpoints ──


@pg_lake_bp.route("/setup-info")
def setup_info():
    """Return dynamic setup context for the Getting Started wizard."""
    status = _get_pg_lake_status()
    instance_name = _get_instance_name()
    connection_type = _get_connection_type()
    pg_database = os.environ.get("PGDATABASE", "benchmark")

    # Check if default_location_prefix is already set
    location_prefix = ""
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "SHOW pg_lake_iceberg.default_location_prefix"
            )
            row = cur.fetchone()
            if row:
                location_prefix = str(row[0]) if row[0] else ""
    except Exception:
        pass

    return jsonify({
        "status": status,
        "instance_name": instance_name,
        "connection_type": connection_type,
        "pg_database": pg_database,
        "location_prefix": location_prefix,
    })


@pg_lake_bp.route("/lake-query", methods=["POST"])
def lake_query():
    """Execute a pg_lake related query."""
    data = request.get_json() or {}
    sql = (data.get("sql") or "").strip()

    if not sql:
        return jsonify({"error": "No SQL provided"}), 400

    try:
        with get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '60s'")
                cur.execute(sql)

                if cur.description:
                    columns = [d.name for d in cur.description]
                    rows = cur.fetchall()
                    clean_rows = [
                        [str(v) if v is not None else None for v in row]
                        for row in rows
                    ]
                    return jsonify({
                        "columns": columns,
                        "rows": clean_rows,
                        "row_count": len(clean_rows),
                    })
                else:
                    return jsonify({
                        "message": f"OK. {cur.rowcount} row(s) affected.",
                        "row_count": max(cur.rowcount, 0),
                    })
    except Exception as e:
        return jsonify({"error": str(e).strip()[:500]}), 500


@pg_lake_bp.route("/run-setup", methods=["POST"])
def run_setup():
    """Run pg_lake extension setup steps."""
    data = request.get_json(silent=True) or {}
    s3_prefix = (data.get("s3_prefix") or "").strip().rstrip("/")

    results = []
    try:
        with get_connection() as conn:
            conn.autocommit = True

            # Set default_location_prefix if provided
            if s3_prefix:
                start = time.monotonic()
                try:
                    conn.execute(
                        f"SET pg_lake_iceberg.default_location_prefix = '{s3_prefix}/'"
                    )
                    elapsed = round((time.monotonic() - start) * 1000, 1)
                    results.append({
                        "label": f"Set location prefix: {s3_prefix}/",
                        "status": "ok", "time_ms": elapsed,
                    })
                except Exception as e:
                    elapsed = round((time.monotonic() - start) * 1000, 1)
                    results.append({
                        "label": "Set location prefix", "status": "error",
                        "error": str(e).strip()[:200], "time_ms": elapsed,
                    })

            for label, sql in _pg_lake_setup_steps():
                start = time.monotonic()
                try:
                    cur = conn.execute(sql)
                    elapsed = round((time.monotonic() - start) * 1000, 1)
                    entry = {"label": label, "status": "ok", "time_ms": elapsed}
                    if cur.description:
                        cols = [d.name for d in cur.description]
                        row = cur.fetchone()
                        if row:
                            if len(cols) > 1:
                                entry["value"] = ", ".join(
                                    f"{c}={v}" for c, v in zip(cols, row)
                                    if v is not None
                                )
                            else:
                                entry["value"] = str(row[0])
                    results.append(entry)
                except Exception as e:
                    elapsed = round((time.monotonic() - start) * 1000, 1)
                    results.append({
                        "label": label, "status": "error",
                        "error": str(e).strip()[:200], "time_ms": elapsed,
                    })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"results": results})


@pg_lake_bp.route("/redistribute-partitions", methods=["POST"])
def redistribute_partitions():
    """Move rows from default partition to correct daily partitions.
    Returns progress after each batch so the frontend can animate."""
    try:
        with get_connection() as conn:
            conn.autocommit = True
            rounds = []
            for i in range(200):  # safety limit
                cur = conn.execute(
                    "SELECT partition_data_time('iot.sensor_data')"
                )
                moved = cur.fetchone()[0]

                # Get current counts
                cur2 = conn.execute(
                    "SELECT "
                    "(SELECT count(*) FROM iot.sensor_data_default) AS default_rows, "
                    "(SELECT count(*) FROM iot.sensor_data) AS total_rows"
                )
                row = cur2.fetchone()
                rounds.append({
                    "round": i + 1,
                    "moved": moved,
                    "default_remaining": row[0],
                    "total": row[1],
                })

                if moved == 0 or row[0] == 0:
                    break

            return jsonify({"rounds": rounds, "done": True})
    except Exception as e:
        return jsonify({"error": str(e).strip()[:500]}), 500


# ── Setup SQL generators ──


@pg_lake_bp.route("/setup-cron", methods=["POST"])
def setup_cron():
    """Install pg_cron in the postgres database and schedule the sync pipeline."""
    results = []
    try:
        with get_postgres_db_connection() as conn:
            conn.autocommit = True

            # Install pg_cron
            start = time.monotonic()
            try:
                conn.execute("CREATE EXTENSION IF NOT EXISTS pg_cron CASCADE")
                elapsed = round((time.monotonic() - start) * 1000, 1)
                results.append({"label": "Install pg_cron (postgres db)", "status": "ok", "time_ms": elapsed})
            except Exception as e:
                elapsed = round((time.monotonic() - start) * 1000, 1)
                results.append({"label": "Install pg_cron", "status": "error",
                                "error": str(e).strip()[:200], "time_ms": elapsed})
                return jsonify({"results": results}), 500

            # Get target database name
            pg_database = os.environ.get("PGDATABASE", "benchmark")

            # Schedule the pipeline job (every 1 minute)
            start = time.monotonic()
            try:
                conn.execute(
                    "SELECT cron.schedule_in_database("
                    "  'events_to_archive',"
                    "  '* * * * *',"
                    "  $$CALL incremental.execute_pipeline('events_to_archive')$$,"
                    f" '{pg_database}'"
                    ")"
                )
                elapsed = round((time.monotonic() - start) * 1000, 1)
                results.append({"label": f"Schedule pipeline (every 1 min → {pg_database})",
                                "status": "ok", "time_ms": elapsed})
            except Exception as e:
                elapsed = round((time.monotonic() - start) * 1000, 1)
                results.append({"label": "Schedule pipeline", "status": "error",
                                "error": str(e).strip()[:200], "time_ms": elapsed})

            # List current jobs
            start = time.monotonic()
            cur = conn.execute("SELECT jobid, schedule, command, database FROM cron.job")
            jobs = cur.fetchall()
            elapsed = round((time.monotonic() - start) * 1000, 1)
            job_info = ", ".join(f"#{j[0]} {j[1]} → {j[3]}" for j in jobs)
            results.append({"label": "Active cron jobs", "status": "ok",
                            "value": job_info or "(none)", "time_ms": elapsed})

    except Exception as e:
        return jsonify({"error": str(e).strip()[:500]}), 500

    return jsonify({"results": results})


@pg_lake_bp.route("/remove-cron", methods=["POST"])
def remove_cron():
    """Remove the sync pipeline cron job."""
    try:
        with get_postgres_db_connection() as conn:
            conn.autocommit = True
            conn.execute("SELECT cron.unschedule('events_to_archive')")
        return jsonify({"message": "Cron job 'events_to_archive' removed."})
    except Exception as e:
        return jsonify({"error": str(e).strip()[:500]}), 500


def _pg_lake_setup_steps():
    return [
        ("Install pg_lake", "CREATE EXTENSION IF NOT EXISTS pg_lake CASCADE"),
        ("Install pg_incremental", "CREATE EXTENSION IF NOT EXISTS pg_incremental CASCADE"),
        ("Check pg_lake version",
         "SELECT name, installed_version, default_version "
         "FROM pg_available_extensions WHERE name = 'pg_lake'"),
        ("Clean up pg_incremental pipelines",
         "DELETE FROM incremental.time_interval_pipelines WHERE pipeline_name = 'events_to_archive'"),
        ("Clean up pg_incremental pipelines (2)",
         "DELETE FROM incremental.pipelines WHERE pipeline_name = 'events_to_archive'"),
        ("Drop demo schema (full reset)", "DROP SCHEMA IF EXISTS demo CASCADE"),
        ("Create demo schema", "CREATE SCHEMA demo"),
        ("Create Iceberg table (events_hot)", """
            CREATE TABLE demo.events_hot (
                event_id    BIGSERIAL,
                event_date  TIMESTAMPTZ NOT NULL DEFAULT now(),
                region      TEXT NOT NULL,
                category    TEXT NOT NULL,
                amount      NUMERIC(10,2) NOT NULL,
                status      TEXT NOT NULL DEFAULT 'active'
            ) USING iceberg
              WITH (partition_by = 'day(event_date)')
        """),
        ("Insert 50,000 sample events (60 days)", """
            INSERT INTO demo.events_hot
                (event_date, region, category, amount, status)
            SELECT
                now() - (random() * interval '60 days'),
                (ARRAY['Tokyo','Osaka','Nagoya','Fukuoka','Sapporo'])[1 + (i % 5)],
                (ARRAY['purchase','refund','subscription','cancellation'])[1 + (i % 4)],
                (random() * 10000)::numeric(10,2),
                (ARRAY['active','completed','pending','cancelled'])[1 + (i % 4)]
            FROM generate_series(1, 50000) AS s(i)
        """),
    ]
