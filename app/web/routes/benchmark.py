"""
Benchmark routes - configuration form, execution, SSE progress, cancellation.
"""

import json
import os
import shutil
import tempfile
import threading
import time

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    stream_with_context,
    url_for,
)

from benchmark_engine import PgBenchRunner
from db import get_connection, get_monitor_pool, get_target, get_targets, get_user_bench_scenario, get_user_bench_scenarios
from monitoring import MonitoringCollector
from pg_collector import collect_pg_info

benchmark_bp = Blueprint("benchmark", __name__, url_prefix="/benchmark")

# Single-run lock: only one benchmark at a time
_active_run_id = None
_active_runner = None
_lock = threading.Lock()


def _get_runner(target_id: int | None = None) -> PgBenchRunner:
    """Create a PgBenchRunner for the given target (or default env)."""
    if target_id:
        target = get_target(target_id)
        if target:
            return PgBenchRunner(
                target["dbname"], target["host"],
                str(target["port"]), target["username"],
                password=target["password"],
            )
    pg_host = os.environ["PGHOST"]
    pg_port = os.environ.get("PGPORT", "5432")
    pg_user = os.environ["PGUSER"]
    pg_db = os.environ.get("PGDATABASE", "benchmark")
    return PgBenchRunner(pg_db, pg_host, pg_port, pg_user)


@benchmark_bp.route("/new")
def new_benchmark():
    # Check if a benchmark is already running
    active = None
    with _lock:
        active = _active_run_id
    targets = get_targets()
    scenarios = get_user_bench_scenarios()
    return render_template("benchmark_new.html", active_run=active, targets=targets, scenarios=scenarios)


@benchmark_bp.route("/submit", methods=["POST"])
def submit_benchmark():
    global _active_run_id, _active_runner

    with _lock:
        if _active_run_id is not None:
            flash("A benchmark is already running. Wait for it to complete.", "warning")
            return redirect(url_for("benchmark.new_benchmark"))

    # Target selection
    target_id = request.form.get("target_id", type=int)

    # Parse form parameters
    scenario_mode = request.form.get("scenario_mode", "builtin")
    params = {
        "run_name": request.form.get("run_name", "").strip(),
        "clients": int(request.form.get("clients", 10)),
        "threads": int(request.form.get("threads", 2)),
        "duration": int(request.form.get("duration", 60)),
        "protocol": request.form.get("protocol", "simple"),
        "progress_interval": int(request.form.get("progress_interval", 5)),
        "initialize": request.form.get("initialize") == "on",
        "scale_factor": int(request.form.get("scale_factor", 10)),
    }

    if scenario_mode == "custom":
        scenario_id = int(request.form.get("custom_scenario_id", 0))
        scenario = get_user_bench_scenario(scenario_id)
        if not scenario:
            flash("Selected scenario not found.", "danger")
            return redirect(url_for("benchmark.new_benchmark"))

        custom_ratio = int(request.form.get("custom_read_ratio", 50))
        write_weight = 100 - custom_ratio
        read_weight = custom_ratio

        # Write scripts to temp files
        tmp_dir = tempfile.mkdtemp(prefix="pgbench_custom_")
        write_path = os.path.join(tmp_dir, "write.sql")
        read_path = os.path.join(tmp_dir, "read.sql")
        with open(write_path, "w") as f:
            f.write(scenario["write_script"])
        with open(read_path, "w") as f:
            f.write(scenario["read_script"])

        custom_scripts = []
        if write_weight > 0:
            custom_scripts.append({"path": write_path, "weight": write_weight})
        if read_weight > 0:
            custom_scripts.append({"path": read_path, "weight": read_weight})

        params["custom_scripts"] = custom_scripts
        params["custom_scenario_name"] = scenario["name"]
        params["_tmp_dir"] = tmp_dir
    elif scenario_mode == "mixer":
        ratio = int(request.form.get("read_ratio", 50))
        params["read_weight"] = ratio
        params["write_weight"] = 100 - ratio
    else:
        params["builtin_script"] = request.form.get("builtin_script", "tpcb-like")

    # DB spec (manual input, optional)
    db_spec = {}
    for field in ("cpu_cores", "memory_gb", "iops", "notes"):
        val = request.form.get(f"spec_{field}", "").strip()
        if val:
            db_spec[field] = val
    if db_spec:
        params["db_spec"] = db_spec

    # Resolve target name for record
    target_name = None
    if target_id:
        t = get_target(target_id)
        if t:
            target_name = t["name"]

    # Collect PG info
    pg_conn = get_connection()
    pg_info = collect_pg_info(pg_conn)

    # Create run record (exclude internal keys from stored params)
    stored_params = {k: v for k, v in params.items() if not k.startswith("_") and k != "custom_scripts"}
    if params.get("custom_scenario_name"):
        stored_params["custom_scenario_name"] = params["custom_scenario_name"]
    cur = pg_conn.execute(
        """INSERT INTO metrics.benchmark_runs
           (run_name, parameters, status, pg_version, pg_settings, db_spec, target_name)
           VALUES (%s, %s, 'running', %s, %s, %s, %s)
           RETURNING run_id""",
        (
            params.get("run_name", ""),
            json.dumps(stored_params),
            pg_info.get("version", ""),
            json.dumps(pg_info.get("settings", {})),
            json.dumps(db_spec) if db_spec else None,
            target_name,
        ),
    )
    run_id = cur.fetchone()[0]
    pg_conn.commit()
    pg_conn.close()

    with _lock:
        _active_run_id = run_id
        _active_runner = _get_runner(target_id)

    # Start benchmark in background thread
    thread = threading.Thread(
        target=_run_benchmark,
        args=(run_id, params),
        daemon=True,
    )
    thread.start()

    return redirect(url_for("benchmark.run_progress", run_id=run_id))


def _run_benchmark(run_id: int, params: dict):
    """Execute benchmark in background thread."""
    global _active_run_id, _active_runner

    runner = _active_runner
    monitor_interval = params.get("progress_interval", 5)
    monitor = MonitoringCollector(run_id, monitor_interval)
    monitor.start()

    pg_conn = get_connection()

    try:
        # Initialize if requested
        if params.get("initialize", False):
            scale = params.get("scale_factor", 10)
            print(f"  [Run {run_id}] Initializing pgbench data (scale={scale})...")
            init_result = runner.initialize(scale)
            if not init_result["success"]:
                raise RuntimeError(f"pgbench -i failed: {init_result['stderr'][:500]}")
            print(f"  [Run {run_id}] Initialization complete.")

        # Progress callback
        def on_progress(elapsed, tps, lat_avg, lat_std):
            try:
                with get_monitor_pool().connection() as conn:
                    conn.execute(
                        """INSERT INTO metrics.pgbench_progress
                           (run_id, elapsed_sec, tps, latency_avg_ms, latency_stddev)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (run_id, elapsed_sec) DO NOTHING""",
                        (run_id, elapsed, tps, lat_avg, lat_std),
                    )
                    conn.commit()
            except Exception as e:
                print(f"    Progress write error: {e}")

        print(f"  [Run {run_id}] Running pgbench (clients={params.get('clients', 10)}, "
              f"duration={params.get('duration', 60)}s)...")
        result = runner.run(params, on_progress=on_progress)

        summary = result["summary"]
        status = "completed" if result["success"] else "failed"

        pg_conn.execute(
            """UPDATE metrics.benchmark_runs
               SET status = %s, finished_at = now(), summary = %s
               WHERE run_id = %s""",
            (status, json.dumps(summary), run_id),
        )
        pg_conn.commit()

        tps = summary.get("tps", "N/A")
        lat = summary.get("latency_avg_ms", "N/A")
        print(f"  [Run {run_id}] Completed: TPS={tps}, Latency={lat}ms")

    except Exception as e:
        print(f"  [Run {run_id}] Failed: {e}")
        pg_conn.execute(
            """UPDATE metrics.benchmark_runs
               SET status = 'failed', finished_at = now(), summary = %s
               WHERE run_id = %s""",
            (json.dumps({"error": str(e)}), run_id),
        )
        pg_conn.commit()
    finally:
        monitor.stop()
        pg_conn.close()
        # Cleanup custom script temp files
        tmp_dir = params.get("_tmp_dir")
        if tmp_dir and os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        with _lock:
            _active_run_id = None
            _active_runner = None


@benchmark_bp.route("/run/<int:run_id>")
def run_progress(run_id):
    run = None
    try:
        with get_connection() as conn:
            cur = conn.execute(
                """SELECT run_id, run_name, status, parameters, started_at
                   FROM metrics.benchmark_runs WHERE run_id = %s""",
                (run_id,),
            )
            row = cur.fetchone()
            if row:
                run = dict(zip([d.name for d in cur.description], row))
    except Exception as e:
        print(f"Error loading run: {e}")

    if not run:
        flash("Run not found.", "danger")
        return redirect(url_for("index.dashboard"))

    return render_template("benchmark_run.html", run=run)


@benchmark_bp.route("/run/<int:run_id>/stream")
def run_stream(run_id):
    """SSE endpoint for real-time benchmark progress."""

    def generate():
        last_count = 0
        keepalive_counter = 0

        while True:
            try:
                with get_connection() as conn:
                    # Check run status
                    cur = conn.execute(
                        "SELECT status FROM metrics.benchmark_runs WHERE run_id = %s",
                        (run_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        yield f"event: error\ndata: Run not found\n\n"
                        return
                    status = row[0]

                    # Fetch new progress rows
                    cur2 = conn.execute(
                        """SELECT elapsed_sec, tps, latency_avg_ms, latency_stddev
                           FROM metrics.pgbench_progress
                           WHERE run_id = %s
                           ORDER BY elapsed_sec""",
                        (run_id,),
                    )
                    rows = cur2.fetchall()

                    if len(rows) > last_count:
                        for r in rows[last_count:]:
                            data = json.dumps({
                                "elapsed_sec": float(r[0]),
                                "tps": float(r[1]) if r[1] else 0,
                                "latency_avg_ms": float(r[2]) if r[2] else 0,
                                "latency_stddev": float(r[3]) if r[3] else 0,
                            })
                            yield f"event: progress\ndata: {data}\n\n"
                        last_count = len(rows)

                    if status in ("completed", "failed"):
                        # Send final summary
                        cur3 = conn.execute(
                            """SELECT summary, status FROM metrics.benchmark_runs
                               WHERE run_id = %s""",
                            (run_id,),
                        )
                        final = cur3.fetchone()
                        data = json.dumps({
                            "status": final[1],
                            "summary": json.loads(final[0]) if final[0] else {},
                        })
                        yield f"event: complete\ndata: {data}\n\n"
                        return

            except Exception as e:
                yield f"event: error\ndata: {str(e)}\n\n"
                return

            # Keep-alive
            keepalive_counter += 1
            if keepalive_counter % 6 == 0:
                yield ": keepalive\n\n"

            time.sleep(2)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@benchmark_bp.route("/cancel/<int:run_id>", methods=["POST"])
def cancel_benchmark(run_id):
    global _active_run_id, _active_runner

    with _lock:
        if _active_run_id == run_id and _active_runner:
            _active_runner.cancel()
            flash("Benchmark cancellation requested.", "info")
        else:
            flash("No active benchmark with that ID.", "warning")

    return redirect(url_for("benchmark.run_progress", run_id=run_id))
