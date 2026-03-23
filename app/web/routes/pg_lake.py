"""pg_lake — Getting Started guide, demos, and API endpoints."""

import os
import time

from flask import Blueprint, jsonify, redirect, render_template, request

from db import get_connection

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
    results = []
    try:
        with get_connection() as conn:
            conn.autocommit = True
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


# ── Setup SQL generators ──


def _pg_lake_setup_steps():
    return [
        ("Install pg_lake", "CREATE EXTENSION IF NOT EXISTS pg_lake CASCADE"),
        ("Check pg_lake version",
         "SELECT name, installed_version, default_version "
         "FROM pg_available_extensions WHERE name = 'pg_lake'"),
        ("Create demo schema", "CREATE SCHEMA IF NOT EXISTS lake_demo"),
        ("Drop existing demo tables",
         "DROP TABLE IF EXISTS lake_demo.access_logs CASCADE"),
        ("Create Iceberg table (access_logs)", """
            CREATE TABLE lake_demo.access_logs (
                log_time   TIMESTAMPTZ NOT NULL DEFAULT now(),
                user_id    INT,
                action     TEXT,
                path       TEXT,
                status     INT,
                response_ms DOUBLE PRECISION
            ) USING iceberg
              WITH (partition_by = 'day(log_time)')
        """),
        ("Insert 30,000 sample rows (60 days)", """
            INSERT INTO lake_demo.access_logs
                (log_time, user_id, action, path, status, response_ms)
            SELECT
                now() - (random() * interval '60 days'),
                (random() * 1000)::int,
                (ARRAY['GET','POST','PUT','DELETE'])[1 + (i % 4)],
                '/api/v1/' || (ARRAY['users','orders','products','health'])[1 + (i % 4)],
                (ARRAY[200, 200, 200, 201, 301, 404, 500])[1 + (i % 7)],
                random() * 500
            FROM generate_series(1, 30000) AS s(i)
        """),
    ]
