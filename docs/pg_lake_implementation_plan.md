# pg_lake 学習コンテンツ実装計画

## 調査結果サマリー

### pg_lake とは
- Snowflake が 2025年11月にオープンソース化（元 Crunchy Data 開発、Apache 2.0）
- PostgreSQL をスタンドアロン Lakehouse に変える拡張機能群
- Iceberg テーブル / Foreign Table / COPY TO/FROM S3 の3本柱
- 内部で `pgduck_server`（DuckDB ベースの列指向エンジン）を利用

### Snowflake Internal Stage 対応状況
**結論: 未対応。ドキュメント・GitHub Issues・Discussions のいずれにも言及なし。**

対応ストレージ:
- S3 / S3互換（MinIO等）: ◎ 主要バックエンド
- GCS: △ DuckDB credential chain 経由で可能だがバグ報告あり (#169)
- Azure Blob: △ 要望あり (#133) だが未完
- HTTP/HTTPS: ○ 読み取り専用
- Hugging Face (`hf://`): ○ MLデータセット用
- **Snowflake Internal Stage: ✗ 未対応**

### Postgres → Iceberg → Snowflake のデータフロー

**2つの連携パス:**

**Path A — Direct S3 access (External Iceberg Tables):**
1. pg_lake で `CREATE TABLE ... USING iceberg` → S3 に Parquet + Iceberg metadata を書き出し
2. Snowflake 側で External Volume + Catalog Integration を作成し、同じ S3 の Iceberg テーブルを READ
3. ETL パイプライン不要の "Zero ETL" アプローチ
4. 公式ガイド: [Build a Lakehouse with Snowflake Postgres and pg_lake](https://www.snowflake.com/en/developers/guides/build-a-lakehouse-with-snowflake-postgres-and-pg-lake/)

**Path B — REST Catalog (Polaris / Open Catalog):**
- 実験的サポート（Issue #94）
- 読み取りパスは「ほぼ完成」、書き込みパスも任意トランザクション・DDL・パーティションをサポート
- **制約:** シングルライターモデル前提（Postgres のみが書き込み側）
- Credential vending は未実装
- 現時点では Path A の Direct S3 方式を推奨

### pg_partman + pg_incremental + pg_lake 連携
**Snowflake 公式ブログで推奨パターンとして紹介済み:**

推奨スタック: `pg_partman` + `pg_incremental` + `pg_lake`
1. `pg_partman` で日次パーティションテーブル（heap）を作成 → Hot データ（直近7日）
2. `pg_incremental` で継続的に Iceberg テーブルへ差分追記（約1分間隔、pg_cron ベース）
3. Day 8 に heap パーティションを DETACH → FDW foreign table として再 ATTACH → Cold データ
4. 親パーティションテーブルへの単一クエリで hot + cold を透過的にアクセス
5. パーティションプルーニングにより Cold パーティション（S3）への不要なアクセスを実行計画レベルで排除
6. Snowflake は S3 上の Iceberg テーブルを READ（ALTER ICEBERG TABLE ... REFRESH で1分鮮度）

**FDW パーティション方式の根拠:**
- PostgreSQL は PG11 以降、foreign table をパーティション子テーブルとして ATTACH 可能（公式サポート）
- パーティションプルーニングが range 境界に基づいて動作するため、UNION ALL ビューより確実
- INSERT は heap パーティションにのみルーティングされる（Cold への書き込みは意図通り発生しない）
- 制約: 親テーブルに UNIQUE INDEX は不可（IoT 時系列データでは問題なし）

### Snowflake Postgres での有効化
Snowflake Postgres はマネージドサービスのため、`shared_preload_libraries` や `pg_extension_base` の
手動設定は**不要**。以下のみで有効化できる:
```sql
CREATE EXTENSION pg_lake CASCADE;
```
前提条件は S3 ストレージ統合の設定（IAM ロール + Storage Integration + ALTER POSTGRES INSTANCE）。
詳細: https://docs.snowflake.com/en/user-guide/snowflake-postgres/postgres-pg_lake

### 現在の制約
- マルチライター非対応（Snowflake側からの書き込みは不可、Issue #41）
- S3 バケットは Snowflake アカウントと同じ AWS リージョンに必要

---

## 実装計画

### Demo 構成: 4つのインタラクティブデモ

#### Demo 1: Iceberg テーブルの作成と基本 DML
**目的:** Iceberg テーブルの作成・INSERT・SELECT・UPDATE・DELETE を体験

```sql
-- Create Iceberg table with time partitioning
-- 時系列パーティション付き Iceberg テーブルを作成
CREATE TABLE lake_demo.access_logs (
    log_time   TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id    INT,
    action     TEXT,
    path       TEXT,
    status     INT,
    response_ms DOUBLE PRECISION
) USING iceberg
  WITH (partition_by = 'day(log_time)');

-- Insert sample data / サンプルデータの INSERT
INSERT INTO lake_demo.access_logs (log_time, user_id, action, path, status, response_ms)
SELECT
    now() - (random() * interval '30 days'),
    (random() * 1000)::int,
    (ARRAY['GET','POST','PUT','DELETE'])[1 + (i % 4)],
    '/api/v1/' || (ARRAY['users','orders','products','health'])[1 + (i % 4)],
    (ARRAY[200, 200, 200, 201, 301, 404, 500])[1 + (i % 7)],
    random() * 500
FROM generate_series(1, 10000) AS s(i);

-- Query with partition pruning / パーティションプルーニング付きクエリ
SELECT date_trunc('day', log_time) AS day,
       count(*) AS requests,
       avg(response_ms)::numeric(10,2) AS avg_ms
FROM lake_demo.access_logs
WHERE log_time >= now() - interval '7 days'
GROUP BY 1 ORDER BY 1;
```

**UIポイント:**
- Setup ボタンで自動セットアップ
- テーブル作成 → データ INSERT → 集計クエリの3ステップ
- EXPLAIN で partition pruning の効果を確認

#### Demo 2: COPY TO/FROM — S3 エクスポート・インポート
**目的:** PostgreSQL テーブルを S3 に Parquet で書き出し、読み戻す体験

```sql
-- Export to S3 as Parquet / S3 に Parquet 形式でエクスポート
COPY lake_demo.access_logs TO 's3://bucket/demo/access_logs.parquet';

-- Export with filter / フィルタ付きエクスポート
COPY (
    SELECT * FROM lake_demo.access_logs
    WHERE status >= 400
) TO 's3://bucket/demo/errors.parquet';

-- Import from S3 / S3 からインポート
CREATE TABLE lake_demo.imported_errors (LIKE lake_demo.access_logs);
COPY lake_demo.imported_errors FROM 's3://bucket/demo/errors.parquet';

-- Verify / 確認
SELECT count(*) AS imported_rows FROM lake_demo.imported_errors;
```

**注意:** S3 バケットの設定が必要。SF Postgres 環境では EAI 経由のネットワーク許可が必要。

#### Demo 3: Foreign Table — S3 の Parquet を直接クエリ
**目的:** データをコピーせず S3 上のファイルを直接 SQL で問い合わせる

```sql
-- Create foreign table pointing to S3 Parquet files
-- S3 上の Parquet ファイルを Foreign Table として登録
CREATE FOREIGN TABLE lake_demo.s3_logs ()
    SERVER pg_lake
    OPTIONS (path 's3://bucket/demo/access_logs.parquet');

-- Query foreign table directly (no data copy needed)
-- Foreign Table を直接クエリ（データコピー不要）
SELECT action, count(*) AS cnt, avg(response_ms)::numeric(10,2) AS avg_ms
FROM lake_demo.s3_logs
GROUP BY action ORDER BY cnt DESC;

-- List files in S3 / S3 上のファイル一覧
SELECT path FROM lake_file.list('s3://bucket/demo/**/*.parquet');
```

#### Demo 4: IoT Hot/Cold パーティションライフサイクル（pg_partman + pg_incremental + pg_lake）
**目的:** IoT センサーデータの日次パーティションで、Hot（ローカル heap）→ Cold（S3 Iceberg FDW）の
ライフサイクル全体を体験。パーティションプルーニングにより Cold 期間の S3 アクセスを実行計画レベルで排除。
**★ 最優先: Postgres → Iceberg、Snowflake から READ できるところまで**

**アーキテクチャ概要:**
```
iot.sensor_data (PARTITION BY RANGE(ts))    ← 親テーブル（単一の入口）
  │
  ├── p_2026_03_22 (heap)     ← 今日、アクティブ書き込み
  ├── p_2026_03_21 (heap)     ← 昨日
  ├── ...
  ├── p_2026_03_16 (heap)     ← 7日前
  │       ↓ pg_incremental（毎分）
  │       ↓ INSERT INTO iceberg_archive SELECT * FROM heap WHERE ts > last_processed
  │
  ├── p_2026_03_15 (FOREIGN TABLE → S3 Iceberg)  ← 8日前、FDW 経由
  ├── p_2026_03_14 (FOREIGN TABLE → S3 Iceberg)
  └── ...

Snowflake → S3 Iceberg を READ（ALTER ICEBERG TABLE ... REFRESH で1分鮮度）
```

**パーティション切り替えライフサイクル:**
```
Day 0:   pg_partman が p_YYYY_MM_DD を heap で作成
Day 0~7: IoT データが INSERT される
         pg_incremental が毎分 Iceberg archive テーブルに差分追記
         Snowflake は Iceberg を READ（1分鮮度）
Day 8:   パーティション切り替え自動化:
         ① DETACH PARTITION p_old（heap）
         ② DROP TABLE p_old（データは既に S3 Iceberg にある）
         ③ CREATE FOREIGN TABLE p_old (...) SERVER pg_lake_server
              OPTIONS (path 's3://bucket/iot/archive/day=YYYY-MM-DD/')
         ④ ATTACH PARTITION p_old FOR VALUES FROM (...) TO (...)
```

```sql
-- ========================================================
-- Step 1: 親テーブル + pg_partman による日次パーティション
-- ========================================================
CREATE SCHEMA IF NOT EXISTS iot;

CREATE TABLE iot.sensor_data (
    ts        TIMESTAMPTZ NOT NULL,
    device_id INT         NOT NULL,
    temp      DOUBLE PRECISION,
    humidity  DOUBLE PRECISION,
    pressure  DOUBLE PRECISION
) PARTITION BY RANGE (ts);

-- pg_partman: 日次パーティションを自動管理
SELECT partman.create_parent(
    p_parent_table := 'iot.sensor_data',
    p_control      := 'ts',
    p_interval     := 'daily',
    p_premake      := 3          -- 3日先まで事前作成
);

-- retention 設定（後で FDW に切り替えるため、ここでは自動 DROP しない）
UPDATE partman.part_config
SET retention          = NULL,   -- 自動 DROP は使わない（手動で FDW に切り替える）
    retention_keep_table = TRUE
WHERE parent_table = 'iot.sensor_data';

-- ========================================================
-- Step 2: Iceberg アーカイブテーブル（pg_incremental の同期先）
-- ========================================================
CREATE TABLE iot.sensor_archive (
    ts        TIMESTAMPTZ NOT NULL,
    device_id INT         NOT NULL,
    temp      DOUBLE PRECISION,
    humidity  DOUBLE PRECISION,
    pressure  DOUBLE PRECISION
) USING iceberg
  WITH (partition_by = 'day(ts)');

-- ========================================================
-- Step 3: pg_incremental で毎分 Iceberg に差分追記
-- ========================================================
-- pg_incremental は pg_cron ベースの差分処理フレームワーク
-- シーケンスパイプライン or 時間間隔パイプラインで差分を追跡

-- 時間間隔パイプラインの例（1分間隔）
SELECT incremental.create_pipeline(
    pipeline_name := 'iot_to_iceberg',
    query         := $$
        INSERT INTO iot.sensor_archive (ts, device_id, temp, humidity, pressure)
        SELECT ts, device_id, temp, humidity, pressure
        FROM iot.sensor_data
        WHERE ts >= $1 AND ts < $2
    $$,
    interval      := '1 minute'::interval
);

-- パイプラインの状態確認
SELECT * FROM incremental.pipelines;

-- ========================================================
-- Step 4: サンプルデータ投入（過去14日分の IoT データ）
-- ========================================================
INSERT INTO iot.sensor_data (ts, device_id, temp, humidity, pressure)
SELECT
    now() - (random() * interval '14 days'),
    (random() * 100)::int,
    20.0 + random() * 15.0,            -- 20~35°C
    40.0 + random() * 40.0,            -- 40~80%
    1000.0 + (random() - 0.5) * 50.0   -- 975~1025 hPa
FROM generate_series(1, 100000) AS s(i);

-- pg_incremental を手動実行（デモ用。本番では pg_cron が自動実行）
CALL incremental.execute_pipeline('iot_to_iceberg');

-- Iceberg 側にデータが同期されたことを確認
SELECT date_trunc('day', ts) AS day, count(*) AS rows
FROM iot.sensor_archive
GROUP BY 1 ORDER BY 1;

-- ========================================================
-- Step 5: 8日前のパーティションを FDW に切り替え
-- ========================================================
-- 切り替え対象日を算出
DO $$
DECLARE
    target_date DATE := current_date - 8;
    part_name   TEXT := 'iot.sensor_data_p' || to_char(target_date, 'YYYY_MM_DD');
    fdw_name    TEXT := 'iot.sensor_cold_p' || to_char(target_date, 'YYYY_MM_DD');
    s3_path     TEXT := 's3://bucket/iot/sensor_archive/day=' || target_date || '/';
    range_start TIMESTAMPTZ := target_date::timestamptz;
    range_end   TIMESTAMPTZ := (target_date + 1)::timestamptz;
BEGIN
    -- ① Detach the heap partition
    EXECUTE format('ALTER TABLE iot.sensor_data DETACH PARTITION %I', part_name);

    -- ② Drop the heap partition (data already in S3 Iceberg)
    EXECUTE format('DROP TABLE IF EXISTS %I', part_name);

    -- ③ Create foreign table pointing to S3 Iceberg data
    EXECUTE format(
        'CREATE FOREIGN TABLE %I (
            ts        TIMESTAMPTZ NOT NULL,
            device_id INT         NOT NULL,
            temp      DOUBLE PRECISION,
            humidity  DOUBLE PRECISION,
            pressure  DOUBLE PRECISION
        ) SERVER pg_lake_server OPTIONS (path %L)',
        fdw_name, s3_path
    );

    -- ④ Attach as partition
    EXECUTE format(
        'ALTER TABLE iot.sensor_data ATTACH PARTITION %I FOR VALUES FROM (%L) TO (%L)',
        fdw_name, range_start, range_end
    );

    RAISE NOTICE 'Switched % from heap to FDW (S3: %)', part_name, s3_path;
END $$;

-- ========================================================
-- Step 6: パーティションプルーニングの確認
-- ========================================================
-- 直近2日のクエリ → Cold パーティション（FDW）はスキャンされない
EXPLAIN (COSTS OFF)
SELECT avg(temp), avg(humidity)
FROM iot.sensor_data
WHERE ts >= now() - interval '2 days';

-- 期待される実行計画:
-- Append
--   → Seq Scan on sensor_data_p2026_03_22   ← heap（スキャン）
--   → Seq Scan on sensor_data_p2026_03_21   ← heap（スキャン）
--   → Foreign Scan on sensor_cold_p2026_03_14 ... (never executed)  ← プルーニング!

-- 全期間クエリも単一テーブルとして透過的にアクセス
SELECT date_trunc('day', ts) AS day,
       avg(temp)::numeric(5,2)     AS avg_temp,
       avg(humidity)::numeric(5,2) AS avg_hum,
       count(*)                    AS rows
FROM iot.sensor_data   -- ← 単一テーブル名で hot + cold を横断
GROUP BY 1 ORDER BY 1;

-- ========================================================
-- Step 7: 過去データの修正（稀な UPDATE/DELETE）
-- ========================================================
-- FDW パーティション経由の書き込み可否は pg_lake_table FDW の実装に依存。
-- 確実に対応するには Iceberg アーカイブテーブルを直接操作:
UPDATE iot.sensor_archive
SET temp = 25.0
WHERE device_id = 42 AND ts = '2026-03-14 10:00:00+09';

-- ========================================================
-- 自動化: pg_cron で Day 8 切り替えをスケジュール
-- ========================================================
-- 本番では以下のように pg_cron で毎日実行:
-- SELECT cron.schedule('partition_to_fdw', '0 2 * * *',
--     $$SELECT iot.switch_partition_to_fdw(current_date - 8)$$);
-- （switch_partition_to_fdw は Step 5 の DO ブロックを関数化したもの）
```

**Snowflake から READ する手順（情報パネルで表示）:**
```sql
-- === On Snowflake side: Read Iceberg table from S3 ===
-- === Snowflake 側: S3 上の Iceberg テーブルを読み取り ===

-- 1. External Volume の作成
CREATE OR REPLACE EXTERNAL VOLUME pg_lake_vol
    STORAGE_LOCATIONS = (
        (
            NAME = 'pg_lake_s3'
            STORAGE_BASE_URL = 's3://bucket/iot/'
            STORAGE_PROVIDER = 'S3'
            STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/pg-lake-access'
        )
    );

-- 2. Catalog Integration の作成
CREATE OR REPLACE CATALOG INTEGRATION pg_lake_catalog
    CATALOG_SOURCE = OBJECT_STORE
    TABLE_FORMAT = ICEBERG
    ENABLED = TRUE;

-- 3. Iceberg テーブル登録（pg_incremental が毎分同期した最新データを含む）
CREATE OR REPLACE ICEBERG TABLE analytics.sensor_from_pg
    EXTERNAL_VOLUME = 'pg_lake_vol'
    CATALOG = 'pg_lake_catalog'
    METADATA_FILE_PATH = 'sensor_archive/metadata/v1.metadata.json';

-- 4. クエリ（1分鮮度のデータが参照可能）
SELECT date_trunc('hour', ts) AS hour,
       avg(temp) AS avg_temp,
       count(*) AS readings
FROM analytics.sensor_from_pg
GROUP BY 1 ORDER BY 1;

-- 5. メタデータ更新（新しいスナップショットを認識させる）
ALTER ICEBERG TABLE analytics.sensor_from_pg REFRESH;
```

**FDW パーティションの利点（UNION ALL ビュー比較）:**
| 観点 | FDW パーティション | UNION ALL ビュー |
|------|-------------------|-----------------|
| パーティションプルーニング | ✅ 実行計画レベルで保証 | ⚠️ プランナ依存、保証なし |
| クエリ透過性 | ✅ `SELECT * FROM sensor_data` のみ | ❌ ビュー名を使う必要 |
| INSERT routing | ✅ 親テーブルに INSERT → heap に自動ルーティング | ❌ アプリが宛先を意識 |
| pg_partman 統合 | ✅ パーティション情報を pg_partman が認識 | ❌ 手動管理 |
| 書き込み（Cold） | ⚠️ FDW の書き込み対応に依存 | ✅ Iceberg テーブル直接操作 |

**未検証事項（実装時に確認）:**
1. `pg_lake_server` に対する FDW foreign table が `ATTACH PARTITION` に対応するか
2. FDW パーティションの `OPTIONS (path)` に Iceberg メタデータパスを指定できるか、Parquet 直指定が必要か
3. pg_incremental の `create_pipeline` API のパラメータ仕様（$1, $2 が正確に何を示すか）
4. FDW パーティション経由の UPDATE/DELETE 可否

---

### UI 実装詳細

#### ページ構成の変更
現在の pg_lake ページは「Coming Soon」の情報ページ。これを以下に変更:

1. **ステータスバナー**: pg_lake の利用可否を自動検出
   - 利用可能 → 各デモの Setup/Run ボタンが有効
   - 利用不可 → 情報パネル（現在の内容）+ SQL プレビューのみ
2. **4つのデモカード**: 各デモは Setup + Run ボタン付き
3. **Snowflake 連携パネル**: Snowflake 側で実行する SQL のリファレンス（コピー可能）

#### バックエンド変更 (`advanced.py`)

```python
# 新しいセットアップ関数
def _pg_lake_setup():
    return [
        ("Install pg_lake", "CREATE EXTENSION IF NOT EXISTS pg_lake CASCADE"),
        ("Create demo schema", "CREATE SCHEMA IF NOT EXISTS lake_demo"),
        ("Set S3 prefix", "ALTER SYSTEM SET pg_lake_iceberg.default_location_prefix = 's3://...'"),
        # ... テーブル作成、サンプルデータ投入
    ]
```

#### 設定画面の追加
S3 バケット設定が必要なため、pg_lake デモ用の設定パネルを追加:
- S3 Bucket URL
- AWS Access Key / Secret Key（または IAM ロール）
- Snowflake External Volume 名（参考情報として表示）

---

### ファイル変更一覧

| ファイル | 変更内容 |
|---------|---------|
| `app/web/templates/advanced_pg_lake.html` | 全面書き換え: 4デモ構成のインタラクティブページ |
| `app/web/templates/advanced_index.html` | "Coming Soon" バッジを条件付き表示に変更 |
| `app/web/routes/advanced.py` | `_pg_lake_setup()` 関数追加、pg_lake 関連ルート追加 |
| `app/i18n.py` | pg_lake 関連の翻訳キー追加（約30キー） |

### 実装順序

1. **Phase 1**: Demo 1 (Iceberg テーブル基本) + Demo 2 (COPY TO/FROM)
2. **Phase 2**: Demo 3 (Foreign Table) + Demo 4 (パーティションアーカイブ)
3. **Phase 3**: Snowflake 連携リファレンスパネル + S3 設定 UI

### 前提条件・リスク

| 項目 | 状況 | 対策 |
|------|------|------|
| pg_lake インストール | `CREATE EXTENSION pg_lake CASCADE` で有効化 | Setup ボタンで自動実行 |
| S3 Storage Integration | ユーザー設定依存（IAM ロール + S3 バケット） | ドキュメントで手順案内 |
| S3 バケット必要 | Snowflake と同リージョンのみ | 設定パネル追加、MinIO ローカルもサポート |
| Snowflake Internal Stage 非対応 | pg_lake 側で未実装 | S3 経由のワークフローを案内 |
| pg_partman 必要（Demo 4） | SF Postgres で利用可能か要確認 | CREATE EXTENSION で検出、不可時はスキップ |

---

### 補足: Snowflake ブログで推奨された時系列スタック

Snowflake 公式エンジニアリングブログ記事:
"Building a High-Performance Postgres Time Series Stack with Iceberg"

推奨構成:
- **pg_partman**: パーティション管理（日次パーティション作成・事前作成・ライフサイクル）
- **pg_incremental**: 継続的 Iceberg 同期（約1分間隔で差分追記、pg_cron ベース）
- **pg_lake**: Iceberg テーブル作成・S3 書き出し + FDW での S3 読み取り

`pg_incremental` のパイプラインタイプ:
- **シーケンスパイプライン**: 数値 ID レンジで差分追跡
- **時間間隔パイプライン**: 時間レンジ（$1=開始、$2=終了）で差分追跡 → IoT に最適
- **ファイルリストパイプライン**: S3 上の新規ファイル検出

exactly-once セマンティクス: 進捗追跡とコマンド実行が同一トランザクション内で行われる。

Demo 4 では pg_incremental を使った自動同期を実装し、
手動実行（CALL incremental.execute_pipeline）でデモ中の即時確認も可能にする。

---

### 補足: Snowflake 側の Iceberg テーブル読み取り設定

Snowflake 公式ガイドに基づく設定手順:

```sql
-- 1. External Volume の作成（S3 バケットへのアクセス）
CREATE OR REPLACE EXTERNAL VOLUME pg_lake_vol
    STORAGE_LOCATIONS = (
        (
            NAME = 'pg_lake_s3'
            STORAGE_BASE_URL = 's3://your-bucket/pg_lake/'
            STORAGE_PROVIDER = 'S3'
            STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::123456789012:role/pg-lake-access'
        )
    );

-- 2. Catalog Integration の作成
CREATE OR REPLACE CATALOG INTEGRATION pg_lake_catalog
    CATALOG_SOURCE = OBJECT_STORE
    TABLE_FORMAT = ICEBERG
    ENABLED = TRUE;

-- 3. Iceberg テーブルの登録（Postgres 側で作成済みのテーブルを参照）
CREATE OR REPLACE ICEBERG TABLE analytics.metrics_from_pg
    EXTERNAL_VOLUME = 'pg_lake_vol'
    CATALOG = 'pg_lake_catalog'
    METADATA_FILE_PATH = 'lake_demo/metrics_archive/metadata/v1.metadata.json';

-- 4. クエリ
SELECT date_trunc('day', ts) AS day, avg(cpu) AS avg_cpu
FROM analytics.metrics_from_pg
GROUP BY 1 ORDER BY 1;

-- メタデータの更新（Postgres 側で新しいデータを書き込んだ後）
ALTER ICEBERG TABLE analytics.metrics_from_pg REFRESH;
```

### 補足: プロジェクト沿革

| 時期 | イベント |
|------|---------|
| 2024年初 | Crunchy Data で開発開始 |
| 2024年中 | Crunchy Bridge for Analytics としてリリース |
| 2025年6月 | Snowflake が Crunchy Data を買収（$250M） |
| 2025年11月 | pg_lake v3.0 として OSS 化（Snowflake BUILD 2025） |
| 2026年2月 | Snowflake BUILD London で Snowflake Postgres 拡張を発表、GA タイムライン提示 |

### 補足: 参考リンク集

- [pg_lake GitHub](https://github.com/Snowflake-Labs/pg_lake)
- [Iceberg Tables ドキュメント](https://github.com/Snowflake-Labs/pg_lake/blob/main/docs/iceberg-tables.md)
- [Data Lake Import/Export ドキュメント](https://github.com/Snowflake-Labs/pg_lake/blob/main/docs/data-lake-import-export.md)
- [Foreign Table ドキュメント](https://github.com/Snowflake-Labs/pg_lake/blob/main/docs/query-data-lake-files.md)
- [Snowflake 公式: pg_lake 設定](https://docs.snowflake.com/en/user-guide/snowflake-postgres/postgres-pg_lake)
- [Snowflake ブログ: pg_lake 紹介](https://www.snowflake.com/en/engineering-blog/pg-lake-postgres-lakehouse-integration/)
- [Snowflake ブログ: 時系列スタック](https://www.snowflake.com/en/engineering-blog/postgres-time-series-iceberg/)
- [Snowflake ガイド: Lakehouse 構築](https://www.snowflake.com/en/developers/guides/build-a-lakehouse-with-snowflake-postgres-and-pg-lake/)
- [Snowflake ガイド: IoT パイプライン](https://www.snowflake.com/en/developers/guides/snowflake-postgres-pg-lake-iot/)
- [REST Catalog ロードマップ - Issue #94](https://github.com/Snowflake-Labs/pg_lake/issues/94)
- [GCS バグ - Issue #169](https://github.com/Snowflake-Labs/pg_lake/issues/169)
