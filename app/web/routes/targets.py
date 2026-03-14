"""Target connection management routes."""

import psycopg
from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import get_connection, get_target

targets_bp = Blueprint("targets", __name__, url_prefix="/targets")


@targets_bp.route("/")
def targets_list():
    targets = []
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM metrics.pg_targets ORDER BY is_primary DESC, name"
            )
            targets = [
                dict(zip([d.name for d in cur.description], row))
                for row in cur.fetchall()
            ]
    except Exception as e:
        flash(f"Error loading targets: {e}", "danger")

    return render_template("targets.html", targets=targets)


@targets_bp.route("/add", methods=["POST"])
def add_target():
    name = request.form.get("name", "").strip()
    host = request.form.get("host", "").strip()
    port = int(request.form.get("port", 5432))
    dbname = request.form.get("dbname", "postgres").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not name or not host or not username or not password:
        flash("Name, Host, Username, Password are required.", "danger")
        return redirect(url_for("targets.targets_list"))

    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO metrics.pg_targets (name, host, port, dbname, username, password)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (name) DO UPDATE
                   SET host = EXCLUDED.host, port = EXCLUDED.port,
                       dbname = EXCLUDED.dbname, username = EXCLUDED.username,
                       password = EXCLUDED.password""",
                (name, host, port, dbname, username, password),
            )
            conn.commit()
        flash(f"Target '{name}' added.", "success")
    except Exception as e:
        flash(f"Error adding target: {e}", "danger")

    return redirect(url_for("targets.targets_list"))


@targets_bp.route("/<int:target_id>/test", methods=["POST"])
def test_target(target_id):
    target = get_target(target_id)
    if not target:
        flash("Target not found.", "danger")
        return redirect(url_for("targets.targets_list"))

    conninfo = (
        f"host={target['host']} "
        f"port={target['port']} "
        f"dbname={target['dbname']} "
        f"user={target['username']} "
        f"password={target['password']} "
        f"sslmode=require connect_timeout=10"
    )
    try:
        conn = psycopg.connect(conninfo)
        cur = conn.execute("SELECT version()")
        version = cur.fetchone()[0]
        conn.close()
        flash(f"Connection OK: {version[:80]}", "success")
    except Exception as e:
        flash(f"Connection failed: {e}", "danger")

    return redirect(url_for("targets.targets_list"))


@targets_bp.route("/<int:target_id>/delete", methods=["POST"])
def delete_target(target_id):
    try:
        with get_connection() as conn:
            # Prevent deleting primary target
            cur = conn.execute(
                "SELECT is_primary, name FROM metrics.pg_targets WHERE target_id = %s",
                (target_id,),
            )
            row = cur.fetchone()
            if not row:
                flash("Target not found.", "danger")
                return redirect(url_for("targets.targets_list"))

            if row[0]:
                flash("Cannot delete the primary (metrics) target.", "warning")
                return redirect(url_for("targets.targets_list"))

            conn.execute(
                "DELETE FROM metrics.pg_targets WHERE target_id = %s", (target_id,)
            )
            conn.commit()
            flash(f"Target '{row[1]}' deleted.", "success")
    except Exception as e:
        flash(f"Error deleting target: {e}", "danger")

    return redirect(url_for("targets.targets_list"))
