"""Scripts & Scenarios management routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for

from db import (
    add_user_bench_scenario,
    add_user_sql_sample,
    delete_user_bench_scenario,
    delete_user_sql_sample,
    get_user_bench_scenarios,
    get_user_sql_samples,
)

scripts_bp = Blueprint("scripts", __name__, url_prefix="/scripts")


@scripts_bp.route("/")
def scripts_list():
    sql_samples = get_user_sql_samples()
    bench_scenarios = get_user_bench_scenarios()
    return render_template(
        "scripts.html",
        sql_samples=sql_samples,
        bench_scenarios=bench_scenarios,
    )


@scripts_bp.route("/sql/add", methods=["POST"])
def add_sql_sample():
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "User Scripts").strip()
    description = request.form.get("description", "").strip()
    sql_content = request.form.get("sql_content", "").strip()

    # File upload takes precedence over textarea
    uploaded = request.files.get("sql_file")
    if uploaded and uploaded.filename:
        sql_content = uploaded.read().decode("utf-8", errors="replace").strip()

    if not title or not sql_content:
        flash("Title and SQL content are required.", "danger")
        return redirect(url_for("scripts.scripts_list"))

    add_user_sql_sample(title, category or "User Scripts", description, sql_content)
    flash(f"SQL sample '{title}' added.", "success")
    return redirect(url_for("scripts.scripts_list"))


@scripts_bp.route("/sql/<int:sample_id>/delete", methods=["POST"])
def remove_sql_sample(sample_id):
    delete_user_sql_sample(sample_id)
    flash("SQL sample deleted.", "success")
    return redirect(url_for("scripts.scripts_list"))


@scripts_bp.route("/scenario/add", methods=["POST"])
def add_scenario():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    write_script = request.form.get("write_script", "").strip()
    read_script = request.form.get("read_script", "").strip()

    # File upload takes precedence
    write_file = request.files.get("write_file")
    if write_file and write_file.filename:
        write_script = write_file.read().decode("utf-8", errors="replace").strip()

    read_file = request.files.get("read_file")
    if read_file and read_file.filename:
        read_script = read_file.read().decode("utf-8", errors="replace").strip()

    if not name or not write_script or not read_script:
        flash("Name, write script, and read script are required.", "danger")
        return redirect(url_for("scripts.scripts_list"))

    add_user_bench_scenario(name, description, write_script, read_script)
    flash(f"Scenario '{name}' added.", "success")
    return redirect(url_for("scripts.scripts_list"))


@scripts_bp.route("/scenario/<int:scenario_id>/delete", methods=["POST"])
def remove_scenario(scenario_id):
    delete_user_bench_scenario(scenario_id)
    flash("Scenario deleted.", "success")
    return redirect(url_for("scripts.scripts_list"))
