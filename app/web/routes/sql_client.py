"""SQL Client routes - execute SQL, psql meta-commands, sample scripts."""

import json
import re
import time

from flask import Blueprint, jsonify, render_template, request

from db import get_connection, get_target_connection, get_targets, get_user_sql_sample, get_user_sql_samples
from sql_samples import get_sample_by_id, get_samples

sql_bp = Blueprint("sql_client", __name__, url_prefix="/sql")

MAX_ROWS = 500
STATEMENT_TIMEOUT = "30s"


# ── psql meta-command translation ──


def translate_psql_command(cmd: str):
    """Translate a psql backslash command to equivalent SQL.
    Returns (sql, description) or (None, None) if not recognized.
    """
    cmd = cmd.strip()

    # \dt or \dt+
    if re.match(r"^\\dt\+?\s*$", cmd):
        return (
            "SELECT table_schema, table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
            "ORDER BY table_schema, table_name",
            "List of relations",
        )

    # \d tablename
    m = re.match(r"^\\d\s+(\S+)$", cmd)
    if m:
        tbl = m.group(1).replace("'", "''")
        # Split schema.table if present
        parts = tbl.split(".", 1)
        if len(parts) == 2:
            schema_filter = f"AND c.table_schema = '{parts[0]}'"
            tbl_name = parts[1]
        else:
            schema_filter = ""
            tbl_name = parts[0]
        return (
            f"SELECT c.column_name, c.data_type, c.is_nullable, c.column_default "
            f"FROM information_schema.columns c "
            f"WHERE c.table_name = '{tbl_name}' {schema_filter} "
            f"ORDER BY c.ordinal_position",
            f"Table \"{tbl}\"",
        )

    # \di - indexes
    if re.match(r"^\\di\+?\s*$", cmd):
        return (
            "SELECT schemaname, tablename, indexname, indexdef "
            "FROM pg_indexes "
            "WHERE schemaname NOT IN ('pg_catalog','information_schema') "
            "ORDER BY schemaname, tablename, indexname",
            "List of indexes",
        )

    # \l - databases
    if re.match(r"^\\l\+?\s*$", cmd):
        return (
            "SELECT datname, pg_catalog.pg_get_userbyid(datdba) AS owner, "
            "pg_catalog.pg_encoding_to_char(encoding) AS encoding "
            "FROM pg_catalog.pg_database ORDER BY datname",
            "List of databases",
        )

    # \du - roles
    if re.match(r"^\\du\+?\s*$", cmd):
        return (
            "SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolcanlogin "
            "FROM pg_catalog.pg_roles ORDER BY rolname",
            "List of roles",
        )

    # \dn - schemas
    if re.match(r"^\\dn\+?\s*$", cmd):
        return (
            "SELECT schema_name, schema_owner "
            "FROM information_schema.schemata "
            "ORDER BY schema_name",
            "List of schemas",
        )

    # \dv - views
    if re.match(r"^\\dv\+?\s*$", cmd):
        return (
            "SELECT table_schema, table_name, view_definition "
            "FROM information_schema.views "
            "WHERE table_schema NOT IN ('pg_catalog','information_schema') "
            "ORDER BY table_schema, table_name",
            "List of views",
        )

    # \df - functions
    if re.match(r"^\\df\+?\s*$", cmd):
        return (
            "SELECT n.nspname AS schema, p.proname AS name, "
            "pg_catalog.pg_get_function_result(p.oid) AS result_type, "
            "pg_catalog.pg_get_function_arguments(p.oid) AS arguments "
            "FROM pg_catalog.pg_proc p "
            "JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname NOT IN ('pg_catalog','information_schema') "
            "ORDER BY schema, name",
            "List of functions",
        )

    # \conninfo
    if re.match(r"^\\conninfo\s*$", cmd):
        return (
            "SELECT current_database() AS database, current_user AS user, "
            "inet_server_addr() AS host, inet_server_port() AS port, "
            "version() AS version",
            "Connection info",
        )

    # \? help
    if re.match(r"^\\[?h]", cmd):
        return None, "help"

    return None, None


# ── Routes ──


@sql_bp.route("/")
def sql_editor():
    builtin_samples = get_samples()
    user_samples_raw = get_user_sql_samples()

    # Convert user samples to same dict format, with prefixed IDs
    user_samples = [
        {
            "id": f"user_{us['sample_id']}",
            "category": us["category"],
            "title": us["title"],
            "description": us["description"],
            "sql": us["sql_content"],
        }
        for us in user_samples_raw
    ]

    samples = builtin_samples + user_samples

    # Rebuild categories preserving order
    seen = set()
    categories = []
    for s in samples:
        c = s["category"]
        if c not in seen:
            seen.add(c)
            categories.append(c)

    targets = get_targets()
    return render_template(
        "sql_client.html",
        samples=samples,
        categories=categories,
        targets=targets,
        samples_json=json.dumps(
            [{"id": s["id"], "title": s["title"], "category": s["category"]} for s in samples]
        ),
    )


@sql_bp.route("/execute", methods=["POST"])
def sql_execute():
    data = request.get_json(silent=True) or {}
    sql_text = (data.get("sql") or "").strip()
    mode = data.get("mode", "plain")  # plain, explain, analyze, buffers

    if not sql_text:
        return jsonify({"error": "No SQL provided."}), 400

    # Handle psql meta-commands
    if sql_text.startswith("\\"):
        translated_sql, desc = translate_psql_command(sql_text)
        if desc == "help":
            return jsonify({
                "columns": ["command", "description"],
                "rows": [
                    ["\\dt", "List tables"],
                    ["\\d TABLE", "Describe table columns"],
                    ["\\di", "List indexes"],
                    ["\\l", "List databases"],
                    ["\\du", "List roles"],
                    ["\\dn", "List schemas"],
                    ["\\dv", "List views"],
                    ["\\df", "List functions"],
                    ["\\conninfo", "Connection info"],
                ],
                "row_count": 9,
                "execution_time_ms": 0,
                "is_meta": True,
                "meta_description": "Available psql commands",
            })
        if translated_sql is None:
            return jsonify({"error": f"Unsupported psql command: {sql_text}"}), 400
        sql_text = translated_sql
        # Meta-commands always run in plain mode
        mode = "plain"

    # Apply EXPLAIN prefix based on mode
    if mode == "explain":
        sql_text = f"EXPLAIN\n{sql_text}"
    elif mode == "analyze":
        sql_text = f"EXPLAIN ANALYZE\n{sql_text}"
    elif mode == "buffers":
        sql_text = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)\n{sql_text}"

    # Use target connection if specified
    target_id = data.get("target_id")

    try:
        start = time.monotonic()
        conn_func = get_target_connection(int(target_id)) if target_id else get_connection()
        with conn_func as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'")
                cur.execute(sql_text)

                elapsed_ms = round((time.monotonic() - start) * 1000, 2)

                # Check if query returns rows
                if cur.description:
                    columns = [d.name for d in cur.description]
                    rows = cur.fetchmany(MAX_ROWS + 1)
                    truncated = len(rows) > MAX_ROWS
                    if truncated:
                        rows = rows[:MAX_ROWS]

                    # Convert to serializable types
                    clean_rows = []
                    for row in rows:
                        clean_rows.append(
                            [str(v) if v is not None else None for v in row]
                        )

                    return jsonify({
                        "columns": columns,
                        "rows": clean_rows,
                        "row_count": len(clean_rows),
                        "truncated": truncated,
                        "execution_time_ms": elapsed_ms,
                    })
                else:
                    # DDL/DML with no result set
                    rowcount = cur.rowcount
                    return jsonify({
                        "message": f"Query executed successfully. {rowcount} row(s) affected.",
                        "row_count": rowcount if rowcount >= 0 else 0,
                        "execution_time_ms": elapsed_ms,
                    })
    except Exception as e:
        elapsed_ms = round((time.monotonic() - start) * 1000, 2)
        error_msg = str(e).strip()
        return jsonify({
            "error": error_msg,
            "execution_time_ms": elapsed_ms,
        }), 400


@sql_bp.route("/samples")
def sql_samples_list():
    return jsonify(get_samples())


@sql_bp.route("/samples/<sample_id>")
def sql_sample_detail(sample_id):
    if sample_id.startswith("user_"):
        user_id = int(sample_id.replace("user_", ""))
        us = get_user_sql_sample(user_id)
        if not us:
            return jsonify({"error": "Sample not found"}), 404
        return jsonify({
            "id": sample_id,
            "title": us["title"],
            "category": us["category"],
            "description": us["description"],
            "sql": us["sql_content"],
        })
    sample = get_sample_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404
    return jsonify(sample)
