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
1. pg_lake で `CREATE TABLE ... USING iceberg` → S3 に Parquet + Iceberg metadata を書き出し
2. Snowflake 側で同じ S3 パスの Iceberg テーブルを外部管理テーブルとして READ
3. ETL パイプライン不要の "Zero ETL" アプローチ

### pg_partman 連携
**Snowflake 公式ブログで推奨パターンとして紹介済み:**

推奨スタック: `pg_partman` + `pg_incremental` + `pg_lake`
1. `pg_partman` で時系列パーティションテーブル（heap）を作成 → Hot/Warm データ
2. `pg_incremental` で継続的に Iceberg テーブルへ追記（約1分間隔）
3. `pg_partman` で古いローカルパーティションを自動 DROP → Cold データは S3 の Iceberg のみ
4. 必要に応じて warm（heap）と cold（Iceberg）の両方をクエリ

### 現在の制約（Snowflake Postgres 環境）
- `pg_extension_base` が `shared_preload_libraries` に必要 → 現在 SF Postgres 未設定
- `pgduck_server` プロセスが必要（ポート5332）→ SF Postgres で起動可能か要確認
- マルチライター非対応（Snowflake側からの書き込みは不可、Issue #41）

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

#### Demo 4: パーティションアーカイブ（pg_partman + pg_lake）
**目的:** 時系列データの自動アーカイブ戦略を体験
**★ 最優先: Postgres → Iceberg、Snowflake から READ できるところまで**

```sql
-- === Step 1: Create partitioned heap table (Hot data) ===
-- === Step 1: パーティション付きヒープテーブル作成（ホットデータ） ===
CREATE TABLE lake_demo.metrics (
    ts   TIMESTAMPTZ NOT NULL,
    host TEXT,
    cpu  DOUBLE PRECISION,
    mem  DOUBLE PRECISION
) PARTITION BY RANGE (ts);

-- Create partitions with pg_partman / pg_partman でパーティション作成
SELECT partman.create_parent(
    p_parent_table := 'lake_demo.metrics',
    p_control := 'ts',
    p_interval := 'daily'
);

-- === Step 2: Create Iceberg archive table (Cold data on S3) ===
-- === Step 2: Iceberg アーカイブテーブル作成（S3 上のコールドデータ） ===
CREATE TABLE lake_demo.metrics_archive (
    ts   TIMESTAMPTZ NOT NULL,
    host TEXT,
    cpu  DOUBLE PRECISION,
    mem  DOUBLE PRECISION
) USING iceberg
  WITH (partition_by = 'day(ts)');

-- === Step 3: Archive old partitions to Iceberg ===
-- === Step 3: 古いパーティションを Iceberg にアーカイブ ===
INSERT INTO lake_demo.metrics_archive
SELECT * FROM lake_demo.metrics
WHERE ts < now() - interval '7 days';

-- Drop archived heap partitions / アーカイブ済みヒープパーティションを削除
-- (pg_partman retention handles this automatically)
-- (pg_partman の retention 設定で自動化可能)

-- === Step 4: Query across hot + cold ===
-- === Step 4: ホット + コールドを横断クエリ ===
SELECT date_trunc('day', ts) AS day,
       avg(cpu)::numeric(5,2) AS avg_cpu
FROM (
    SELECT ts, cpu FROM lake_demo.metrics          -- hot (heap)
    UNION ALL
    SELECT ts, cpu FROM lake_demo.metrics_archive  -- cold (iceberg/S3)
) combined
GROUP BY 1 ORDER BY 1;
```

**Snowflake から READ する手順（情報パネルで表示）:**
```sql
-- === On Snowflake side: Read Iceberg table from S3 ===
-- === Snowflake 側: S3 上の Iceberg テーブルを読み取り ===
CREATE OR REPLACE ICEBERG TABLE analytics.metrics_from_pg
    CATALOG = 'SNOWFLAKE'
    EXTERNAL_VOLUME = 'pg_lake_s3_vol'
    BASE_LOCATION = 's3://bucket/lake_demo/metrics_archive/'
    CATALOG_TABLE_NAME = 'metrics_archive';

-- Query in Snowflake / Snowflake でクエリ
SELECT * FROM analytics.metrics_from_pg
WHERE ts >= '2026-03-01';
```

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
| `shared_preload_libraries` に `pg_extension_base` 必要 | SF Postgres 未設定 | Setup で自動チェック、未設定時は SQL プレビューのみモード |
| `pgduck_server` プロセス必要 | SF Postgres での挙動未確認 | ヘルスチェックエンドポイントで検出 |
| S3 バケット必要 | ユーザー設定依存 | 設定パネル追加、MinIO ローカルもサポート |
| Snowflake Internal Stage 非対応 | pg_lake 側で未実装 | S3 経由のワークフローを案内 |
| pg_partman 必要（Demo 4） | SF Postgres で利用可能か要確認 | CREATE EXTENSION で検出、不可時はスキップ |

---

### 補足: Snowflake ブログで推奨された時系列スタック

Snowflake 公式エンジニアリングブログ記事:
"Building a High-Performance Postgres Time Series Stack with Iceberg"

推奨構成:
- **pg_partman**: パーティション管理（作成・保持期間・自動 DROP）
- **pg_incremental**: 継続的 Iceberg 同期（約1分間隔で差分追記）
- **pg_lake**: Iceberg テーブル・S3 書き出し

`pg_incremental` は pg_cron ベースの差分処理フレームワーク。
Demo 4 では簡略化して手動アーカイブとするが、
pg_incremental の存在と自動化の可能性を情報パネルで言及する。
