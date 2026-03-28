"""Compare routes - overlay multiple benchmark results on the same chart."""

import json

from flask import Blueprint, jsonify, render_template

from db import get_connection

compare_bp = Blueprint("compare", __name__, url_prefix="/compare")

# Distinct colors for up to 8 overlaid runs
COLORS = [
    "#0d6efd",  # blue
    "#dc3545",  # red
    "#198754",  # green
    "#ffc107",  # yellow
    "#6f42c1",  # purple
    "#fd7e14",  # orange
    "#20c997",  # teal
    "#d63384",  # pink
]


@compare_bp.route("/")
def compare_view():
    runs = []
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT run_id, run_name, status, started_at,
                          (summary->>'tps')::numeric AS tps,
                          (summary->>'latency_avg_ms')::numeric AS latency_avg_ms,
                          (summary->>'num_transactions')::bigint AS num_transactions,
                          parameters->>'clients' AS clients,
                          parameters->>'duration' AS duration,
                          parameters->>'builtin_script' AS script,
                          pg_version
                   FROM metrics.benchmark_runs
                   WHERE status = 'completed' AND summary IS NOT NULL
                   ORDER BY run_id DESC
                   LIMIT 50"""
            )
            runs = [dict(zip([d.name for d in cur.description], row)) for row in cur.fetchall()]
    except Exception as e:
        print(f"Compare list error: {e}")

    return render_template("compare.html", runs=runs, colors=COLORS)


@compare_bp.route("/data")
def compare_data():
    """Return progress data for selected run IDs as JSON."""
    from flask import request

    run_ids_str = request.args.get("ids", "")
    if not run_ids_str:
        return jsonify({"runs": []})

    try:
        run_ids = [int(x) for x in run_ids_str.split(",") if x.strip().isdigit()]
    except ValueError:
        return jsonify({"runs": []})

    if not run_ids or len(run_ids) > 8:
        return jsonify({"runs": []})

    result = []
    try:
        with get_connection() as conn:
            for run_id in run_ids:
                # Get run metadata
                cur = conn.execute(
                    """SELECT run_id, run_name,
                              (summary->>'tps')::numeric AS tps,
                              (summary->>'latency_avg_ms')::numeric AS latency_avg_ms,
                              (summary->>'num_transactions')::bigint AS num_transactions,
                              (summary->>'num_failed')::bigint AS num_failed,
                              parameters->>'clients' AS clients,
                              parameters->>'duration' AS duration
                       FROM metrics.benchmark_runs WHERE run_id = %s""",
                    (run_id,),
                )
                row = cur.fetchone()
                if not row:
                    continue
                meta = dict(zip([d.name for d in cur.description], row))

                # Get progress data
                cur2 = conn.execute(
                    """SELECT elapsed_sec, tps, latency_avg_ms
                       FROM metrics.pgbench_progress
                       WHERE run_id = %s ORDER BY elapsed_sec""",
                    (run_id,),
                )
                progress = [
                    {
                        "elapsed_sec": float(r[0]),
                        "tps": float(r[1]) if r[1] else 0,
                        "latency_avg_ms": float(r[2]) if r[2] else 0,
                    }
                    for r in cur2.fetchall()
                ]

                # Convert Decimal to float for JSON serialization
                for key in ("tps", "latency_avg_ms"):
                    if meta.get(key) is not None:
                        meta[key] = float(meta[key])
                if meta.get("num_transactions") is not None:
                    meta["num_transactions"] = int(meta["num_transactions"])
                if meta.get("num_failed") is not None:
                    meta["num_failed"] = int(meta["num_failed"])

                result.append({"meta": meta, "progress": progress})
    except Exception as e:
        print(f"Compare data error: {e}")
        return jsonify({"error": str(e)}), 500

    return jsonify({"runs": result})
