"""Results routes - list, detail, DB spec editing."""

import json
from collections import OrderedDict

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import get_connection

results_bp = Blueprint("results", __name__, url_prefix="/results")


@results_bp.route("/")
def results_list():
    runs = []
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT run_id, run_name, tool, status, started_at, finished_at,
                          pg_version, target_name,
                          (summary->>'tps')::numeric AS tps,
                          (summary->>'latency_avg_ms')::numeric AS latency_avg_ms,
                          parameters->>'duration' AS duration
                   FROM metrics.benchmark_runs
                   ORDER BY run_id DESC
                   LIMIT 100"""
            )
            runs = [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"Results list error: {e}")

    return render_template("results_list.html", runs=runs)


@results_bp.route("/<int:run_id>")
def results_detail(run_id):
    run = None
    progress = []
    pg_settings = {}
    wait_events = {"timestamps": [], "event_types": {}}
    wait_summary = []

    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT run_id, run_name, tool, status, started_at, finished_at,
                          parameters, summary, pg_version, pg_settings, db_spec
                   FROM metrics.benchmark_runs WHERE run_id = %s""",
                (run_id,),
            )
            row = cur.fetchone()
            if row:
                run = dict(zip([d.name for d in cur.description], row))
                # Parse JSON fields
                for field in ("parameters", "summary", "pg_settings", "db_spec"):
                    val = run.get(field)
                    if isinstance(val, str):
                        try:
                            run[field] = json.loads(val)
                        except (json.JSONDecodeError, TypeError):
                            pass

                pg_settings = run.get("pg_settings") or {}

            # Load progress data
            cur2 = conn.execute(
                """SELECT elapsed_sec, tps, latency_avg_ms, latency_stddev
                   FROM metrics.pgbench_progress
                   WHERE run_id = %s ORDER BY elapsed_sec""",
                (run_id,),
            )
            progress = [
                {
                    "elapsed_sec": float(r[0]),
                    "tps": float(r[1]) if r[1] else 0,
                    "latency_avg_ms": float(r[2]) if r[2] else 0,
                    "latency_stddev": float(r[3]) if r[3] else 0,
                }
                for r in cur2.fetchall()
            ]

            # Load wait event time series (stacked area chart)
            cur3 = conn.execute(
                """SELECT
                       ROUND(EXTRACT(EPOCH FROM (s.collected_at - r.started_at))::numeric, 1)
                           AS elapsed_sec,
                       sa.wait_event_type,
                       COUNT(*) AS process_count
                   FROM metrics.snapshots s
                   JOIN metrics.benchmark_runs r ON r.run_id = s.run_id
                   JOIN metrics.stat_activity sa ON sa.snapshot_id = s.snapshot_id
                   WHERE s.run_id = %s
                     AND sa.wait_event_type IS NOT NULL
                   GROUP BY elapsed_sec, sa.wait_event_type
                   ORDER BY elapsed_sec, sa.wait_event_type""",
                (run_id,),
            )
            wait_rows = cur3.fetchall()

            if wait_rows:
                time_map = OrderedDict()
                all_types = set()
                for r in wait_rows:
                    elapsed = float(r[0])
                    evt_type = r[1]
                    count = int(r[2])
                    all_types.add(evt_type)
                    if elapsed not in time_map:
                        time_map[elapsed] = {}
                    time_map[elapsed][evt_type] = count

                timestamps = list(time_map.keys())
                sorted_types = sorted(all_types)
                event_types = {}
                for t in sorted_types:
                    event_types[t] = [time_map[ts].get(t, 0) for ts in timestamps]

                wait_events = {"timestamps": timestamps, "event_types": event_types}

            # Load wait event summary (table)
            cur4 = conn.execute(
                """SELECT sa.wait_event_type, sa.wait_event, COUNT(*) AS total_count
                   FROM metrics.snapshots s
                   JOIN metrics.stat_activity sa ON sa.snapshot_id = s.snapshot_id
                   WHERE s.run_id = %s
                     AND sa.wait_event_type IS NOT NULL
                   GROUP BY sa.wait_event_type, sa.wait_event
                   ORDER BY COUNT(*) DESC""",
                (run_id,),
            )
            wait_summary = [
                {
                    "wait_event_type": r[0],
                    "wait_event": r[1],
                    "total_count": int(r[2]),
                }
                for r in cur4.fetchall()
            ]
    except Exception as e:
        print(f"Results detail error: {e}")

    if not run:
        flash("Run not found.", "danger")
        return redirect(url_for("results.results_list"))

    return render_template(
        "results_detail.html",
        run=run,
        progress=progress,
        progress_json=json.dumps(progress),
        pg_settings=pg_settings,
        wait_events_json=json.dumps(wait_events),
        wait_summary=wait_summary,
    )


@results_bp.route("/delete", methods=["POST"])
def delete_results():
    run_ids = request.form.getlist("run_ids")
    if not run_ids:
        flash("No runs selected.", "warning")
        return redirect(url_for("results.results_list"))

    try:
        ids = [int(rid) for rid in run_ids]
    except ValueError:
        flash("Invalid run IDs.", "danger")
        return redirect(url_for("results.results_list"))

    try:
        with get_connection() as conn:
            placeholders = ",".join(["%s"] * len(ids))
            # Delete related data first (foreign key constraints)
            conn.execute(
                f"DELETE FROM metrics.stat_activity WHERE snapshot_id IN "
                f"(SELECT snapshot_id FROM metrics.snapshots WHERE run_id IN ({placeholders}))",
                ids,
            )
            conn.execute(
                f"DELETE FROM metrics.stat_database WHERE snapshot_id IN "
                f"(SELECT snapshot_id FROM metrics.snapshots WHERE run_id IN ({placeholders}))",
                ids,
            )
            conn.execute(
                f"DELETE FROM metrics.snapshots WHERE run_id IN ({placeholders})", ids
            )
            conn.execute(
                f"DELETE FROM metrics.pgbench_progress WHERE run_id IN ({placeholders})",
                ids,
            )
            conn.execute(
                f"DELETE FROM metrics.benchmark_runs WHERE run_id IN ({placeholders})",
                ids,
            )
            conn.commit()
        flash(f"Deleted {len(ids)} benchmark run(s).", "success")
    except Exception as e:
        flash(f"Error deleting runs: {e}", "danger")

    return redirect(url_for("results.results_list"))


@results_bp.route("/<int:run_id>/spec", methods=["POST"])
def update_spec(run_id):
    db_spec = {}
    for field in ("cpu_cores", "memory_gb", "iops", "notes"):
        val = request.form.get(field, "").strip()
        if val:
            db_spec[field] = val

    try:
        with get_connection() as conn:
            conn.execute(
                "UPDATE metrics.benchmark_runs SET db_spec = %s WHERE run_id = %s",
                (json.dumps(db_spec), run_id),
            )
            conn.commit()
        flash("Database spec updated.", "success")
    except Exception as e:
        flash(f"Error updating spec: {e}", "danger")

    return redirect(url_for("results.results_detail", run_id=run_id))
