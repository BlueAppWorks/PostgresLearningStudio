"""Internationalization support for Postgres Learning Studio."""

from flask import request
from markupsafe import Markup

TRANSLATIONS = {
    # ── Navbar / Layout ──
    "nav.home": {"en": "Home", "ja": "Home"},
    "nav.benchmark": {"en": "Benchmark", "ja": "Benchmark"},
    "nav.new_run": {"en": "New Run", "ja": "新規実行"},
    "nav.results": {"en": "Results", "ja": "結果一覧"},
    "nav.compare": {"en": "Compare", "ja": "比較"},
    "nav.playground": {"en": "Playground", "ja": "Playground"},
    "nav.sql_client": {"en": "SQL Client", "ja": "SQL Client"},
    "nav.scripts": {"en": "Scripts & Scenarios", "ja": "スクリプト & シナリオ"},
    "nav.advanced": {"en": "Advanced", "ja": "Advanced"},
    "nav.overview": {"en": "Overview", "ja": "概要"},
    "nav.settings": {"en": "Settings", "ja": "Settings"},
    "nav.connections": {"en": "Connections", "ja": "接続先"},
    "nav.system_info": {"en": "System Info", "ja": "システム情報"},
    "footer": {"en": "Postgres Learning Studio &mdash; Running on SPCS", "ja": "Postgres Learning Studio &mdash; Running on SPCS"},

    # ── Advanced Index ──
    "adv.title": {"en": "Advanced Extensions", "ja": "Advanced Extensions"},
    "adv.intro": {
        "en": "Interactive demo environment to experience powerful PostgreSQL extensions.<br>Learn setup methods, sample SQL, and actual behavior of each extension.",
        "ja": "PostgreSQL のパワフルなエクステンションを体験できるインタラクティブなデモ環境です。<br>各エクステンションのセットアップ方法、サンプル SQL、実際の動作を確認できます。",
    },
    "adv.postgis.desc": {
        "en": "An extension that adds <strong>geospatial data</strong> capabilities to PostgreSQL. Store coordinates (points, lines, polygons) in the DB and execute spatial queries like distance calculations and containment checks in SQL.",
        "ja": "PostgreSQL に<strong>地理空間データ</strong>の機能を追加するエクステンション。地図上の座標（ポイント・ライン・ポリゴン）を DB に格納し、距離計算や包含判定などの空間クエリを SQL で実行できます。",
    },
    "adv.postgis.feat1": {
        "en": "Store and render points, lines, and polygons",
        "ja": "ポイント・ライン・ポリゴンの格納と描画",
    },
    "adv.postgis.feat2": {
        "en": "Distance, area, and containment calculations",
        "ja": "距離計算・面積計算・包含判定",
    },
    "adv.postgis.feat3": {
        "en": "Fast search with GiST spatial index",
        "ja": "GiST 空間インデックスによる高速検索",
    },
    "adv.postgis.license": {
        "en": 'Developer: <a href="https://postgis.net/" target="_blank">PostGIS Project</a> (OSGeo) / License: GPL v2',
        "ja": '開発: <a href="https://postgis.net/" target="_blank">PostGIS Project</a> (OSGeo) / ライセンス: GPL v2',
    },
    "adv.hint.desc": {
        "en": "An extension that lets you control the PostgreSQL query planner by writing <strong>hints</strong> in SQL comments. Useful when statistics are stale or the planner chooses a suboptimal plan.",
        "ja": "SQL コメントに<strong>ヒント</strong>を書くことで、PostgreSQL のクエリプランナーに実行計画を指示できるエクステンション。統計情報が古い場合や、プランナーが最適でない計画を選ぶ場合に有効です。",
    },
    "adv.hint.feat1": {
        "en": "Force SeqScan / IndexScan",
        "ja": "SeqScan / IndexScan の強制指定",
    },
    "adv.hint.feat2": {
        "en": "Specify JOIN method (NestLoop / HashJoin / MergeJoin)",
        "ja": "JOIN 方式の指定（NestLoop / HashJoin / MergeJoin）",
    },
    "adv.hint.feat3": {
        "en": "Fix inefficient plans caused by stale statistics",
        "ja": "古い統計情報による非効率な計画の修正",
    },
    "adv.hint.license": {
        "en": 'Developer: <a href="https://github.com/ossc-db" target="_blank">NTT OSS Center DBMS Development and Support Team</a> / License: PostgreSQL License',
        "ja": '開発: <a href="https://github.com/ossc-db" target="_blank">NTT OSS Center DBMS Development and Support Team</a> / ライセンス: PostgreSQL License',
    },
    "adv.vector.desc": {
        "en": 'An extension that adds <strong>vector types</strong> and vector search to PostgreSQL. Convert text to numerical vectors and perform "semantic search" to find similar documents via SQL. A foundational technology for AI/RAG.',
        "ja": "PostgreSQL に<strong>ベクトル型</strong>とベクトル検索を追加するエクステンション。テキストを数値ベクトルに変換し、意味的に似た文書を検索する「セマンティック検索」を SQL で実現できます。AI/RAG の基盤技術です。",
    },
    "adv.vector.feat1": {
        "en": "Store vectors with the vector type",
        "ja": "vector 型によるベクトル格納",
    },
    "adv.vector.feat2": {
        "en": "Search by cosine similarity and L2 distance",
        "ja": "コサイン類似度・L2距離による検索",
    },
    "adv.vector.feat3": {
        "en": "Fast nearest-neighbor search with HNSW / IVFFlat index",
        "ja": "HNSW / IVFFlat インデックスで高速近傍検索",
    },
    "adv.vector.license": {
        "en": 'Developer: <a href="https://github.com/pgvector" target="_blank">Andrew Kane</a> / License: PostgreSQL License',
        "ja": '開発: <a href="https://github.com/pgvector" target="_blank">Andrew Kane</a> / ライセンス: PostgreSQL License',
    },
    "adv.lake.title_badge": {"en": "Coming Soon", "ja": "Coming Soon"},
    "adv.lake.desc": {
        "en": "A Snowflake-developed extension that adds <strong>Apache Iceberg</strong> and <strong>data lake</strong> access to PostgreSQL. Create Iceberg tables with <code>CREATE TABLE ... USING iceberg</code> and query Parquet/CSV on S3 directly.",
        "ja": "PostgreSQL に <strong>Apache Iceberg</strong> と<strong>データレイク</strong>アクセス機能を追加する Snowflake 製エクステンション。<code>CREATE TABLE ... USING iceberg</code> で Iceberg テーブルを作成し、S3 上の Parquet/CSV を直接クエリできます。",
    },
    "adv.lake.feat1": {
        "en": "Create and DML Iceberg tables",
        "ja": "Iceberg テーブルの作成・DML",
    },
    "adv.lake.feat2": {
        "en": "Query Parquet/CSV on S3/GCS via Foreign Tables",
        "ja": "S3/GCS 上の Parquet/CSV を Foreign Table で参照",
    },
    "adv.lake.feat3": {
        "en": "Read/write data lake via COPY TO/FROM",
        "ja": "COPY TO/FROM によるデータレイク読み書き",
    },
    "adv.lake.license": {
        "en": 'Developer: <a href="https://github.com/Snowflake-Labs" target="_blank">Snowflake Labs</a> / License: Apache License 2.0',
        "ja": '開発: <a href="https://github.com/Snowflake-Labs" target="_blank">Snowflake Labs</a> / ライセンス: Apache License 2.0',
    },

    # ── PostGIS Demo ──
    "postgis.title": {"en": "PostGIS Demo", "ja": "PostGIS Demo"},
    "postgis.intro": {
        "en": 'Experience storing, querying, and visualizing geospatial data. <a href="https://postgis.net/" target="_blank" rel="noopener">PostGIS</a> is an OSS extension that adds geospatial capabilities to PostgreSQL. (<a href="https://github.com/postgis/postgis" target="_blank" rel="noopener">GitHub</a>)',
        "ja": '地理空間データの格納・検索・地図描画を体験します。<a href="https://postgis.net/" target="_blank" rel="noopener">PostGIS</a> は PostgreSQL に地理空間機能を追加する OSS エクステンションです。(<a href="https://github.com/postgis/postgis" target="_blank" rel="noopener">GitHub</a>)',
    },
    "postgis.demo1.title": {
        "en": "Demo 1: INSERT Point and Map Display",
        "ja": "Demo 1: ポイントの INSERT と地図表示",
    },
    "postgis.demo1.desc": {
        "en": "INSERT the coordinates of the Snowflake Tokyo Office (Yaesu 2-2-1) and plot it on the map.",
        "ja": "Snowflake 東京オフィス（八重洲2-2-1）の座標を DB に INSERT し、地図上にプロットします。",
    },
    "postgis.demo2.title": {
        "en": "Demo 2: Plotting Multiple Points",
        "ja": "Demo 2: 複数ポイントのプロット",
    },
    "postgis.demo2.desc": {
        "en": "Add landmarks around Tokyo Station and plot all points on the map.",
        "ja": "東京駅周辺のランドマークを追加し、地図上に全ポイントをプロットします。",
    },
    "postgis.demo3.title": {
        "en": "Demo 3: Drawing Lines and Distance Calculation",
        "ja": "Demo 3: ラインの描画と距離計算",
    },
    "postgis.demo3.desc": {
        "en": "Create a line from start point through waypoint to Snowflake Office and calculate total distance with <code>ST_Length(geography)</code>.",
        "ja": "始点 → 中継点 → Snowflake Office を結ぶラインを作成し、<code>ST_Length(geography)</code> で総距離を計算します。",
    },
    "postgis.demo3.start": {"en": "Start Point", "ja": "始点"},
    "postgis.demo3.via": {"en": "Waypoint", "ja": "中継点"},
    "postgis.demo3.end": {"en": "End Point (fixed)", "ja": "終点（固定）"},
    "postgis.demo4.title": {
        "en": "Demo 4: Polygon Containment (ST_Contains)",
        "ja": "Demo 4: ポリゴンの包含判定 (ST_Contains)",
    },
    "postgis.demo4.desc": {
        "en": "Create a rectangular polygon around the Yaesu area and check which points are inside using <code>ST_Contains</code>.",
        "ja": "八重洲エリアを四角く囲うポリゴンを作成し、<code>ST_Contains</code> で各ポイントが中に入っているかを判定します。",
    },

    # ── pg_hint_plan Demo ──
    "hint.title": {"en": "pg_hint_plan Demo", "ja": "pg_hint_plan Demo"},
    "hint.intro": {
        "en": 'Reproduce a case where stale statistics cause an inefficient execution plan, and fix it with hints. <a href="https://github.com/ossc-db/pg_hint_plan" target="_blank" rel="noopener">pg_hint_plan</a> is a PostgreSQL extension that controls execution plans via SQL comments.',
        "ja": '統計情報の劣化により非効率な実行計画が選ばれるケースを再現し、ヒントで修正する体験をします。<a href="https://github.com/ossc-db/pg_hint_plan" target="_blank" rel="noopener">pg_hint_plan</a> は SQL コメントで実行計画を制御する PostgreSQL エクステンションです。',
    },
    "hint.intro_dev": {
        "en": 'Developer: <a href="https://github.com/ossc-db" target="_blank" rel="noopener">NTT OSS Center DBMS Development and Support Team</a> / License: PostgreSQL License',
        "ja": '開発: <a href="https://github.com/ossc-db" target="_blank" rel="noopener">NTT OSS Center DBMS Development and Support Team</a> / ライセンス: PostgreSQL License',
    },
    "hint.scenario.title": {"en": "Scenario Explanation", "ja": "シナリオ解説"},
    "hint.scenario.step1": {
        "en": '<code>hint_demo.orders</code> table: INSERT <strong>500,000 rows</strong><br><small class="text-muted">status = shipped / processing / delivered / cancelled (no \'rush\')</small>',
        "ja": '<code>hint_demo.orders</code> テーブルに <strong>500,000 行</strong>を INSERT<br><small class="text-muted">status = shipped / processing / delivered / cancelled の4種（\'rush\' は存在しない）</small>',
    },
    "hint.scenario.step2": {
        "en": "<code>ANALYZE</code> to collect statistics &rarr; planner doesn't know about 'rush'",
        "ja": "<code>ANALYZE</code> で統計情報を取得 → プランナーは 'rush' を知らない",
    },
    "hint.scenario.step3": {
        "en": "INSERT <strong>200,000</strong> additional rows with status=<strong>'rush'</strong> (without ANALYZE)",
        "ja": "追加で status=<strong>'rush'</strong> の行を <strong>200,000 行</strong> INSERT（ANALYZE しない）",
    },
    "hint.scenario.step4": {
        "en": "At this point, rush is actually <strong>200,000 rows (28% of total)</strong>, but statistics show zero",
        "ja": "この時点で rush は実際 <strong>200,000 行（全体の28%）</strong> だが、統計にはゼロ",
    },
    "hint.scenario.step5": {
        "en": 'Planner thinks "rush doesn\'t exist or is extremely rare" &rarr; chooses <strong>Index Scan</strong> &rarr; massive random I/O',
        "ja": "プランナーは「rush は存在しない or 極少数」と誤認 → <strong>Index Scan</strong> を選択 → 大量のランダム I/O",
    },
    "hint.scenario.step6": {
        "en": "<code>/*+ SeqScan(orders) */</code> hint forces Seq Scan &rarr; sequential access is more efficient for large result sets",
        "ja": "<code>/*+ SeqScan(orders) */</code> ヒントで Seq Scan を強制 → 大量行にはシーケンシャルが効率的",
    },
    "hint.scenario.note": {
        "en": '<strong>Note:</strong> This demo disables parallel queries with <code>max_parallel_workers_per_gather = 0</code> to clearly show the difference between Index Scan and Seq Scan in a single process.',
        "ja": '<strong>Note:</strong> このデモでは <code>max_parallel_workers_per_gather = 0</code> でパラレルクエリを無効化し、単一プロセスでの Index Scan vs Seq Scan の違いを明確にします。',
    },
    "hint.scenario.prereq": {
        "en": '<strong>Prerequisite:</strong> <code>session_preload_libraries</code> or <code>shared_preload_libraries</code> must include <code>pg_hint_plan</code>. Setup checks this automatically.',
        "ja": '<strong>前提条件:</strong> <code>session_preload_libraries</code> または <code>shared_preload_libraries</code> に <code>pg_hint_plan</code> が設定されている必要があります。Setup で自動チェックします。',
    },
    "hint.scenario.sf_note": {
        "en": '<strong>Snowflake Postgres:</strong> Currently <code>pg_hint_plan</code> cannot be set in <code>session_preload_libraries</code>, so this demo does not work (requires a feature request to Snowflake).',
        "ja": '<strong>Snowflake Postgres:</strong> 現時点では <code>session_preload_libraries</code> に <code>pg_hint_plan</code> を設定できないため、このデモは動作しません（Snowflake への機能リクエストが必要）。',
    },
    "hint.step1.title": {
        "en": "Step 1: Check Statistics",
        "ja": "Step 1: 統計情報の確認",
    },
    "hint.step1.desc": {
        "en": "Compare old statistics (after ANALYZE) vs actual row counts.",
        "ja": "ANALYZE 後の古い統計 vs 実際の行数を比較します。",
    },
    "hint.step2.title": {
        "en": "Step 2: Compare Execution Plans (without vs with hints)",
        "ja": "Step 2: 実行計画の比較（ヒントなし vs あり）",
    },
    "hint.step2.desc": {
        "en": "EXPLAIN ANALYZE the same query without and with hints to compare execution plans and timings.",
        "ja": "同じクエリをヒントなし・ありで EXPLAIN ANALYZE し、実行計画と所要時間を比較します。",
    },
    "hint.step2.no_hint": {
        "en": "<strong>Without Hints</strong> (planner decides)",
        "ja": "<strong>ヒントなし</strong>（プランナー任せ）",
    },
    "hint.step2.with_hint": {
        "en": "<strong>With Hints</strong> (force SeqScan)",
        "ja": "<strong>ヒントあり</strong>（SeqScan 強制）",
    },
    "hint.step3.title": {
        "en": "Step 3: Fix with ANALYZE",
        "ja": "Step 3: ANALYZE で統計を更新",
    },
    "hint.step3.desc": {
        "en": "Running ANALYZE updates the statistics so the planner can choose the correct plan.",
        "ja": "ANALYZE を実行して統計情報を最新化すると、プランナーが正しい計画を選ぶようになります。",
    },
    "hint.benchmark_tip": {
        "en": '<strong>Benchmark Integration:</strong> Register hint/no-hint SQL on the <a href="/scripts">Scripts & Scenarios</a> page, and run them as custom scenarios in <a href="/benchmark/new">Benchmark</a> to compare TPS and latency numerically.',
        "ja": '<strong>Benchmark 連携:</strong> ヒントあり/なしの SQL を <a href="/scripts">Scripts & Scenarios</a> に登録し、<a href="/benchmark/new">Benchmark</a> のカスタムシナリオで実行すると、TPS やレイテンシの違いを数値で比較できます。',
    },

    # ── pg_hint_plan JS messages ──
    "hint.js.actual_rows": {
        "en": "<strong>Actual Row Counts (COUNT):</strong>",
        "ja": "<strong>実際の行数 (COUNT):</strong>",
    },
    "hint.js.planner_stats": {
        "en": "<strong>Planner Statistics (pg_stats.most_common_vals):</strong>",
        "ja": "<strong>プランナーの統計情報 (pg_stats.most_common_vals):</strong>",
    },
    "hint.js.stats_warning": {
        "en": 'Statistics do not contain <code>rush</code>. The planner estimates nearly zero rows for rush.<br>In reality there are <strong>~200,000 rows</strong>, making Index Scan inefficient.',
        "ja": '統計情報には <code>rush</code> が存在しません。プランナーは rush の行数をほぼゼロと推定します。<br>実際には <strong>~200,000行</strong> あるため、Index Scan は非効率です。',
    },
    "hint.js.after_analyze": {
        "en": "<strong>Execution plan after ANALYZE (without hints):</strong>",
        "ja": "<strong>ANALYZE 後の実行計画（ヒントなし）:</strong>",
    },
    "hint.js.analyze_success": {
        "en": "ANALYZE updated the statistics, allowing the planner to correctly estimate rush = 200,000 rows.<br>The appropriate plan (Seq Scan) is now chosen even without hints.",
        "ja": "ANALYZE により統計情報が更新され、プランナーが rush = 200,000 行を正しく推定できるようになりました。<br>ヒントなしでも適切な実行計画（Seq Scan）が選択されます。",
    },
    "hint.js.load_success": {
        "en": "<code>LOAD 'pg_hint_plan'</code> succeeded. <strong>Hints are active.</strong><br>Click \"Run Both Plans\" in Step 2 to compare execution plans.",
        "ja": "<code>LOAD 'pg_hint_plan'</code> が成功しました。<strong>ヒントが有効です。</strong><br>Step 2 の「Run Both Plans」で実行計画の違いを確認できます。",
    },
    "hint.js.load_fail": {
        "en": '<strong>pg_hint_plan is available but library loading failed.</strong><br><code>session_preload_libraries</code> or <code>shared_preload_libraries</code> must include it.',
        "ja": '<strong>pg_hint_plan はインストール可能ですが、ライブラリのロードに失敗しました。</strong><br><code>session_preload_libraries</code> または <code>shared_preload_libraries</code> に追加が必要です。',
    },
    "hint.js.not_available": {
        "en": '<strong>pg_hint_plan is not available on this server.</strong><br>Not found in <code>pg_available_extensions</code>.',
        "ja": '<strong>pg_hint_plan はこのサーバーでは利用できません。</strong><br><code>pg_available_extensions</code> に含まれていません。',
    },

    # ── pgvector Demo ──
    "vector.title": {"en": "pgvector Demo", "ja": "pgvector Demo"},
    "vector.intro": {
        "en": 'Experience "semantic search" — converting text to vectors and finding similar documents. <a href="https://github.com/pgvector/pgvector" target="_blank" rel="noopener">pgvector</a> is an OSS extension that adds vector types and vector search to PostgreSQL.',
        "ja": 'テキストをベクトルに変換し、意味的に似た文書を検索する「セマンティック検索」を体験します。<a href="https://github.com/pgvector/pgvector" target="_blank" rel="noopener">pgvector</a> は PostgreSQL にベクトル型とベクトル検索を追加する OSS エクステンションです。',
    },
    "vector.how_title": {"en": "How It Works", "ja": "仕組み"},
    "vector.how_desc": {
        "en": 'This demo uses a simple keyword-based vectorization with a business keyword dictionary.<br><small class="text-muted">(In production, use AI models like OpenAI Embeddings or Snowflake Cortex for higher accuracy)</small>',
        "ja": 'このデモでは、ビジネス関連のキーワード辞書を使った簡易ベクトル化を行います。<br><small class="text-muted">（本番環境では OpenAI Embeddings や Snowflake Cortex などの AI モデルでより高精度なベクトルを生成します）</small>',
    },
    "vector.keywords_title": {
        "en": "<strong>Keyword Dictionary (20-dimensional vector):</strong>",
        "ja": "<strong>キーワード辞書（20次元ベクトル）:</strong>",
    },
    "vector.keywords_note": {
        "en": "Count occurrences of each keyword to vectorize, then L2-normalize.",
        "ja": "各キーワードの出現回数を数えてベクトル化し、L2正規化します。",
    },
    "vector.step1.title": {
        "en": "Step 1: View Existing Sales Diary",
        "ja": "Step 1: 既存の営業日報を確認",
    },
    "vector.step2.title": {
        "en": "Step 2: INSERT New Diary Entry",
        "ja": "Step 2: 新しい日報を INSERT",
    },
    "vector.step2.person": {"en": "Salesperson", "ja": "営業担当"},
    "vector.step2.company": {"en": "Company", "ja": "会社名"},
    "vector.step2.content": {"en": "Diary Content", "ja": "日報内容"},
    "vector.step3.title": {
        "en": "Step 3: Vectorize (UPDATE)",
        "ja": "Step 3: ベクトル化 (UPDATE)",
    },
    "vector.step3.desc": {
        "en": "Convert the text of inserted rows to vectors. Only rows with <code>embedding IS NULL</code> are processed.",
        "ja": "INSERT した行のテキストをベクトルに変換します。<code>embedding IS NULL</code> の行のみが対象です。",
    },
    "vector.step4.title": {
        "en": "Step 4: Semantic Search",
        "ja": "Step 4: セマンティック検索",
    },
    "vector.step4.desc": {
        "en": "Search with natural language and find similar diary entries.",
        "ja": "自然言語で検索し、意味的に近い日報を見つけます。",
    },
    "vector.step4.search_label": {"en": "Search Text", "ja": "検索テキスト"},
    "vector.step4.preset_label": {"en": "Preset", "ja": "プリセット"},
    "vector.step4.results_title": {
        "en": "<strong>Results (by cosine similarity):</strong>",
        "ja": "<strong>検索結果（コサイン類似度順）:</strong>",
    },

    # ── pg_lake ──
    "lake.title": {"en": "pg_lake", "ja": "pg_lake"},
    "lake.intro": {
        "en": 'A Snowflake-developed extension that adds Apache Iceberg and data lake access to PostgreSQL. <a href="https://github.com/Snowflake-Labs/pg_lake" target="_blank" rel="noopener">pg_lake</a> is an open-source project by Snowflake Labs.',
        "ja": 'PostgreSQL に Apache Iceberg とデータレイクアクセス機能を追加する Snowflake 製エクステンション。<a href="https://github.com/Snowflake-Labs/pg_lake" target="_blank" rel="noopener">pg_lake</a> は Snowflake Labs が開発するオープンソースプロジェクトです。',
    },
    "lake.unavailable": {
        "en": '<strong>Currently unavailable:</strong> pg_lake requires <code>pg_extension_base</code> in <code>shared_preload_libraries</code>, which is not yet configured in the current Snowflake Postgres environment. Waiting for Snowflake support.',
        "ja": '<strong>現在利用不可:</strong> pg_lake は <code>pg_extension_base</code> が <code>shared_preload_libraries</code> に登録されている必要がありますが、現在の Snowflake Postgres 環境ではまだ設定されていません。Snowflake 側の対応待ちです。',
    },
    "lake.overview": {"en": "Overview", "ja": "概要"},
    "lake.sql_samples": {
        "en": "SQL Samples (available in the future)",
        "ja": "SQL サンプル（将来利用可能）",
    },
    "lake.extensions": {"en": "Extension List", "ja": "エクステンション一覧"},

    # ── Scripts & Scenarios ──
    "scripts.title": {"en": "Scripts & Scenarios", "ja": "Scripts & Scenarios"},
    "scripts.sql_info": {
        "en": 'User-registered scripts appear in the SQL Client\'s <strong>Samples</strong> dropdown. Register PostgreSQL learning scripts or business-specific queries as samples.',
        "ja": 'SQL Client の <strong>Samples</strong> ドロップダウンにユーザー登録スクリプトが追加されます。PostgreSQL学習や業務固有のクエリをサンプルとして登録できます。',
    },
    "scripts.bench_info": {
        "en": 'Register custom scenarios for benchmarks. Each scenario consists of a <strong>Write Script</strong> (write transactions) and a <strong>Read Script</strong> (read transactions), with configurable execution ratios.<br>Uses pgbench\'s <code>-f script@weight</code> syntax.',
        "ja": 'ベンチマーク用のカスタムシナリオを登録します。<strong>Write Script</strong>（書き込みトランザクション）と<strong>Read Script</strong>（読み取りトランザクション）の2つを1組として登録し、ベンチマーク実行時にそれぞれの実行割合を指定できます。<br>pgbench の <code>-f script@weight</code> 構文を利用します。',
    },
}


def get_lang() -> str:
    """Get current language from cookie, defaulting to English."""
    return request.cookies.get("lang", "en")


def t(key: str) -> Markup:
    """Translate a key to the current language.

    Returns Markup so HTML in translations is rendered, not escaped.
    """
    lang = get_lang()
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return Markup(key)
    return Markup(entry.get(lang, entry.get("en", key)))
