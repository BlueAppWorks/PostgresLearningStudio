"""Dashboard route - shows recent benchmark runs and quick actions."""

from flask import Blueprint, render_template

from db import get_connection

index_bp = Blueprint("index", __name__)


@index_bp.route("/")
def dashboard():
    runs = []
    active_run = None
    latest = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT run_id, run_name, tool, status, started_at, finished_at,
                          pg_version,
                          (summary->>'tps')::numeric AS tps,
                          (summary->>'latency_avg_ms')::numeric AS latency_avg_ms
                   FROM metrics.benchmark_runs
                   ORDER BY run_id DESC
                   LIMIT 20"""
            )
            runs = [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]

            # Check for active run
            cur2 = conn.execute(
                "SELECT run_id FROM metrics.benchmark_runs WHERE status = 'running' LIMIT 1"
            )
            row = cur2.fetchone()
            if row:
                active_run = row[0]

            # Latest completed run for summary cards
            cur3 = conn.execute(
                """SELECT run_id, run_name,
                          (summary->>'tps')::numeric AS tps,
                          (summary->>'latency_avg_ms')::numeric AS latency_avg_ms,
                          (summary->>'num_transactions')::bigint AS num_transactions,
                          (summary->>'num_failed')::bigint AS num_failed
                   FROM metrics.benchmark_runs
                   WHERE status = 'completed' AND summary IS NOT NULL
                   ORDER BY run_id DESC LIMIT 1"""
            )
            row3 = cur3.fetchone()
            if row3:
                latest = dict(zip([d.name for d in cur3.description], row3))
    except Exception as e:
        print(f"Dashboard query error: {e}")

    return render_template("index.html", runs=runs, active_run=active_run, latest=latest)
