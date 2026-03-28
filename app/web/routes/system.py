"""System info route - shows current PG version and settings."""

from flask import Blueprint, render_template

from db import get_connection
from pg_collector import BENCHMARK_PG_SETTINGS, collect_pg_info

system_bp = Blueprint("system", __name__, url_prefix="/system")


@system_bp.route("/")
def system_info():
    pg_info = {"version": "", "settings": {}}

    try:
        with get_connection() as conn:
            pg_info = collect_pg_info(conn)
    except Exception as e:
        print(f"System info error: {e}")

    # Ordered by the BENCHMARK_PG_SETTINGS list
    ordered_settings = []
    for name in BENCHMARK_PG_SETTINGS:
        if name in pg_info["settings"]:
            ordered_settings.append((name, pg_info["settings"][name]))

    return render_template(
        "system.html",
        pg_version=pg_info["version"],
        settings=ordered_settings,
    )
