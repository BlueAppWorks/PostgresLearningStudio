# pg_lake Demo Cleanup Guide

このデモで作成されたすべてのオブジェクトを削除する手順です。
環境ごとに独立しているので、必要な部分だけ実行してください。

---

## 1. PostgreSQL 側（SQL Client で実行）

```sql
-- pg_incremental パイプライン削除
DELETE FROM incremental.time_interval_pipelines WHERE pipeline_name = 'events_to_archive';
DELETE FROM incremental.pipelines WHERE pipeline_name = 'events_to_archive';

-- デモスキーマごと削除（全テーブル、VIEW、Iceberg テーブルを含む）
DROP SCHEMA IF EXISTS demo CASCADE;

-- 古いデモスキーマ（以前のバージョンで使用していた場合）
DROP SCHEMA IF EXISTS lake_demo CASCADE;
DROP SCHEMA IF EXISTS iot CASCADE;
```

## 2. pg_cron ジョブ（postgres データベースに接続して実行）

pg_cron は `postgres` データベースにインストールされています。
アプリの Demo 3 画面から「Disable Auto-Sync」ボタンで削除できます。

手動で削除する場合（postgres データベースに接続）：

```sql
-- ジョブ一覧を確認
SELECT jobid, jobname, schedule, command, database FROM cron.job;

-- デモ用ジョブを削除
SELECT cron.unschedule('events_to_archive');

-- pg_cron 自体を削除する場合（他で使っていなければ）
-- DROP EXTENSION pg_cron CASCADE;
```

## 3. S3 バケット（AWS Console または AWS CLI）

pg_lake が書き込んだ Iceberg データは `default_location_prefix` 配下にあります。

### AWS CLI

```bash
# default_location_prefix のパスを指定
aws s3 rm s3://your-bucket/pg_lake/your-prefix/ --recursive

# Replace with your actual bucket and prefix
aws s3 rm s3://your-bucket/pg_lake/your-prefix/ --recursive
```

### AWS Console

1. S3 → バケットを開く
2. `pg_lake/` フォルダに移動
3. デモ用プレフィックスフォルダを選択 → 削除

### 注意

- `frompg/` ディレクトリは pg_lake が自動生成したもの。中に `tables/benchmark/demo/...` がある
- バケット自体や IAM ロールは削除不要（再利用できる）
- Storage Integration も残しておいてよい

## 4. Snowflake 側（Snowflake Worksheet で実行）

```sql
USE ROLE ACCOUNTADMIN;

-- Iceberg テーブル削除
DROP ICEBERG TABLE IF EXISTS PG_LAKE_DEMO.ANALYTICS.EVENT_ARCHIVE;
DROP ICEBERG TABLE IF EXISTS PG_LAKE_DEMO.ANALYTICS.SENSOR_FROM_PG;

-- デモ用スキーマ・データベースを削除する場合
DROP SCHEMA IF EXISTS PG_LAKE_DEMO.ANALYTICS;
DROP DATABASE IF EXISTS PG_LAKE_DEMO;

-- External Volume・Catalog Integration を削除する場合（他で使っていなければ）
-- DROP CATALOG INTEGRATION IF EXISTS PG_LAKE_CATALOG;
-- DROP EXTERNAL VOLUME IF EXISTS PG_LAKE_VOL;
```

## 5. Snowflake Postgres 設定のリセット（必要な場合のみ）

```sql
USE ROLE ACCOUNTADMIN;

-- default_location_prefix をリセット
-- ALTER DATABASE benchmark RESET pg_lake_iceberg.default_location_prefix;

-- Storage Integration の紐付けを外す
-- ALTER POSTGRES INSTANCE <INSTANCE_NAME> UNSET STORAGE_INTEGRATION;

-- Compute Family を Burstable に戻す（コスト節約）
-- ALTER POSTGRES INSTANCE <INSTANCE_NAME> SET COMPUTE_FAMILY = 'BURST_S';

-- pg_lake エクステンション削除（postgres に接続して実行）
-- DROP EXTENSION pg_lake CASCADE;
-- DROP EXTENSION pg_incremental CASCADE;
```

## 6. AWS リソースの削除（完全撤去する場合のみ）

```
1. IAM > Roles > snowflake-pg-lake-access → 削除
2. IAM > Roles > snowflake-iceberg-read → 削除
3. IAM > Policies > SnowflakePgLakeS3Access → 削除
4. S3 > バケット → 空にしてから削除（または保持）
5. Snowflake > ACCOUNTADMIN > DROP STORAGE INTEGRATION PG_LAKE_S3_INTEGRATION;
```

---

## クイックリセット（デモデータだけ消して再実行したい場合）

```sql
-- PostgreSQL SQL Client で実行
DELETE FROM incremental.time_interval_pipelines WHERE pipeline_name = 'events_to_archive';
DELETE FROM incremental.pipelines WHERE pipeline_name = 'events_to_archive';
DROP SCHEMA IF EXISTS demo CASCADE;
```

```bash
# S3 データ削除
aws s3 rm s3://your-bucket/pg_lake/your-prefix/frompg/ --recursive
```

その後 Demo 1 の Setup ボタンからやり直せます。
