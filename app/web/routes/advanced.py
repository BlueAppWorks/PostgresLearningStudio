"""Advanced extension demos - PostGIS, pg_hint_plan, pgvector, pg_lake."""

import time

from flask import Blueprint, jsonify, render_template, request

from db import get_connection

advanced_bp = Blueprint("advanced", __name__, url_prefix="/advanced")


# ── Page routes ──


@advanced_bp.route("/")
def index():
    extensions = {}
    try:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT name, installed_version, default_version "
                "FROM pg_available_extensions "
                "WHERE name IN ('postgis', 'pg_hint_plan', 'vector', 'pg_lake') "
                "ORDER BY name"
            )
            for row in cur.fetchall():
                extensions[row[0]] = {
                    "installed": row[1],
                    "available": row[2],
                }
    except Exception:
        pass
    return render_template("advanced_index.html", extensions=extensions)


@advanced_bp.route("/postgis")
def postgis():
    return render_template("advanced_postgis.html")


@advanced_bp.route("/hint-plan")
def hint_plan():
    return render_template("advanced_hint_plan.html")


@advanced_bp.route("/pgvector")
def pgvector_page():
    return render_template("advanced_pgvector.html")


@advanced_bp.route("/pg-lake")
def pg_lake():
    return render_template("advanced_pg_lake.html")


# ── Setup SQL preview ──


@advanced_bp.route("/setup-sql/<extension>")
def setup_sql(extension):
    """Return the setup SQL statements for preview and copy."""
    setup_map = {
        "postgis": _postgis_setup,
        "hint_plan": _hint_plan_setup,
        "pgvector": _pgvector_setup,
    }
    setup_fn = setup_map.get(extension)
    if not setup_fn:
        return jsonify({"error": f"Unknown extension: {extension}"}), 400

    steps = [{"label": label, "sql": sql.strip()} for label, sql in setup_fn()]
    return jsonify({"steps": steps})


# ── Setup endpoint ──


@advanced_bp.route("/setup/<extension>", methods=["POST"])
def setup(extension):
    setup_map = {
        "postgis": _postgis_setup,
        "hint_plan": _hint_plan_setup,
        "pgvector": _pgvector_setup,
    }
    setup_fn = setup_map.get(extension)
    if not setup_fn:
        return jsonify({"error": f"Unknown extension: {extension}"}), 400

    results = []
    try:
        with get_connection() as conn:
            conn.autocommit = True
            for label, sql in setup_fn():
                start = time.monotonic()
                try:
                    cur = conn.execute(sql)
                    elapsed = round((time.monotonic() - start) * 1000, 1)
                    entry = {"label": label, "status": "ok", "time_ms": elapsed}
                    # Capture SELECT / SHOW results for informational steps
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


# ── pg_hint_plan query endpoint (same-session LOAD + SET + query) ──


@advanced_bp.route("/hint-query", methods=["POST"])
def hint_query():
    """Execute a query with pg_hint_plan loaded in the same session."""
    data = request.get_json() or {}
    sql = (data.get("sql") or "").strip()
    load_hint = data.get("load_hint_plan", True)

    if not sql:
        return jsonify({"error": "No SQL provided"}), 400

    try:
        with get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                if load_hint:
                    try:
                        cur.execute("LOAD 'pg_hint_plan'")
                    except Exception:
                        pass  # Already loaded via session_preload_libraries
                cur.execute("SET max_parallel_workers_per_gather = 0")
                cur.execute("SET statement_timeout = '30s'")
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


# ── Setup SQL generators ──


def _postgis_setup():
    return [
        ("Install PostGIS", "CREATE EXTENSION IF NOT EXISTS postgis"),
        ("Create demo schema", "CREATE SCHEMA IF NOT EXISTS postgis_demo"),
        ("Drop existing tables",
         "DROP TABLE IF EXISTS postgis_demo.points, postgis_demo.lines, postgis_demo.polygons CASCADE"),
        ("Create points table", """
            CREATE TABLE postgis_demo.points (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                category TEXT DEFAULT 'landmark',
                geom GEOMETRY(Point, 4326)
            )
        """),
        ("Create lines table", """
            CREATE TABLE postgis_demo.lines (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                geom GEOMETRY(LineString, 4326)
            )
        """),
        ("Create polygons table", """
            CREATE TABLE postgis_demo.polygons (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                geom GEOMETRY(Polygon, 4326)
            )
        """),
    ]


def _hint_plan_setup():
    return [
        ("Install pg_hint_plan", "CREATE EXTENSION IF NOT EXISTS pg_hint_plan"),
        ("Check pg_available_extensions",
         "SELECT name, installed_version, default_version "
         "FROM pg_available_extensions WHERE name = 'pg_hint_plan'"),
        ("Check shared_preload_libraries", "SHOW shared_preload_libraries"),
        ("Check session_preload_libraries", "SHOW session_preload_libraries"),
        ("Test LOAD pg_hint_plan", "LOAD 'pg_hint_plan'"),
        ("Create demo schema", "CREATE SCHEMA IF NOT EXISTS hint_demo"),
        ("Drop existing table", "DROP TABLE IF EXISTS hint_demo.orders CASCADE"),
        ("Create orders table", """
            CREATE TABLE hint_demo.orders (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER,
                status TEXT NOT NULL,
                amount NUMERIC(10,2),
                order_date DATE,
                region TEXT
            )
        """),
        ("Insert 500K rows / 500K行を挿入 (status: shipped/processing/delivered/cancelled)", """
            INSERT INTO hint_demo.orders (customer_id, status, amount, order_date, region)
            SELECT
                (random() * 10000)::int,
                (ARRAY['shipped','processing','delivered','cancelled'])[1 + (i % 4)],
                (random() * 10000)::numeric(10,2),
                CURRENT_DATE - (random() * 365)::int,
                'Region_' || (i % 10)
            FROM generate_series(1, 500000) AS s(i)
        """),
        ("Create index on status / statusにインデックス作成", "CREATE INDEX idx_orders_status ON hint_demo.orders(status)"),
        ("ANALYZE (establish baseline statistics / 統計情報のベースラインを確立)", "ANALYZE hint_demo.orders"),
        ("Insert 200K rush rows without re-ANALYZE / rush行200Kを追加(再ANALYZEなし)", """
            INSERT INTO hint_demo.orders (customer_id, status, amount, order_date, region)
            SELECT
                (random() * 10000)::int,
                'rush',
                (random() * 100)::numeric(10,2),
                CURRENT_DATE - (random() * 30)::int,
                'Region_0'
            FROM generate_series(1, 200000) AS s(i)
        """),
    ]


def _pgvector_setup():
    return [
        ("Install pgvector", "CREATE EXTENSION IF NOT EXISTS vector"),
        ("Create demo schema", "CREATE SCHEMA IF NOT EXISTS vector_demo"),
        ("Drop existing table",
         "DROP TABLE IF EXISTS vector_demo.sales_diary CASCADE"),
        ("Drop existing function",
         "DROP FUNCTION IF EXISTS vector_demo.text_to_vector(TEXT)"),
        ("Create sales diary table", """
            CREATE TABLE vector_demo.sales_diary (
                id SERIAL PRIMARY KEY,
                diary_date DATE NOT NULL DEFAULT CURRENT_DATE,
                salesperson TEXT NOT NULL,
                company TEXT,
                content TEXT NOT NULL,
                embedding vector(20),
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """),
        ("Create keyword vectorization function / キーワードベクトル化関数を作成", r"""
            CREATE OR REPLACE FUNCTION vector_demo.text_to_vector(input_text TEXT)
            RETURNS vector(20) AS $$
            DECLARE
                -- Business keyword dictionary (20 dimensions)
                -- ビジネスキーワード辞書（20次元）
                keywords TEXT[] := ARRAY[
                    '商談', '契約', '提案', '見積', '受注',
                    '失注', '訪問', '電話', 'メール', '会議',
                    '新規', '既存', '競合', '価格', '納期',
                    '品質', 'サポート', '導入', '検討', '決裁'
                ];
                vec FLOAT[] := '{}';
                i INTEGER;
                cnt FLOAT;
                norm FLOAT := 0;
            BEGIN
                FOR i IN 1..20 LOOP
                    cnt := (length(input_text) - length(replace(input_text, keywords[i], '')))::float
                           / length(keywords[i]);
                    vec := array_append(vec, cnt);
                    norm := norm + cnt * cnt;
                END LOOP;
                IF norm > 0 THEN
                    norm := sqrt(norm);
                    FOR i IN 1..20 LOOP
                        vec[i] := vec[i] / norm;
                    END LOOP;
                END IF;
                RETURN vec::vector(20);
            END;
            $$ LANGUAGE plpgsql IMMUTABLE
        """),
        ("Insert sample diary entries / サンプル日報データを挿入", """
            -- Sample sales diary entries (Japanese business content for keyword-based vectorization demo)
            -- サンプル営業日報（キーワードベクトル化デモ用の日本語ビジネスコンテンツ）
            INSERT INTO vector_demo.sales_diary (diary_date, salesperson, company, content) VALUES
            ('2026-02-10', '田中太郎', 'A社', '新規商談の訪問。提案資料を持参し導入について説明。先方は前向きで来週見積を提出予定。'),
            ('2026-02-12', '田中太郎', 'B社', '既存顧客への定期訪問。サポート品質に満足との声。追加導入を検討中。'),
            ('2026-02-14', '佐藤花子', 'C社', '競合との比較会議。価格と納期が決裁のポイント。見積を再提出予定。'),
            ('2026-02-16', '佐藤花子', 'D社', '電話にて受注確認。契約書を来週送付。決裁完了。'),
            ('2026-02-18', '鈴木一郎', 'E社', 'メールで新規提案資料を送付。検討中との返信。来週訪問のアポイント取得。')
        """),
        ("Vectorize all entries / 全エントリをベクトル化", """
            UPDATE vector_demo.sales_diary
            SET embedding = vector_demo.text_to_vector(content)
            WHERE embedding IS NULL
        """),
        ("Create HNSW index / HNSWインデックス作成", """
            CREATE INDEX ON vector_demo.sales_diary
            USING hnsw (embedding vector_cosine_ops)
        """),
    ]
