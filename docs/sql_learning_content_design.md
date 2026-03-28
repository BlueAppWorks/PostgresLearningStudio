# SQL Learning Content Design — Postgres Learning Studio

## 背景

初期バージョンにあったインデックスチューニングやVACUUMの検証シナリオが英語化対応時にシンプルなシステムカタログ参照に縮小された。本改修で学習用コンテンツとして充実させる。

参考教材: `docs/osstext_ver3.0.2.pdf`（LPI-Japan オープンソースデータベース標準教科書 Ver.3.0.2）

## SQL Client の制約

| 機能 | 対応状況 | 備考 |
|---|---|---|
| 単一SQL実行 | OK | 1リクエスト = 1ステートメント |
| BEGIN/COMMIT | **未対応** | autocommit=True のため |
| SET パラメータ | 同一リクエスト内のみ | 次のクエリでリセット |
| 複数タブ別セッション | OK | ただしトランザクション維持不可 |

**トランザクション/ロックのデモ**: 現行では不可。将来 autocommit=false モード追加で対応可能。

## 実装方式

`sql_samples.py` の `_SAMPLES` リストにエントリを追加。SQL Client の Samples ドロップダウンから選択して実行する形式。

## デモデータ

教科書のデモデータ（prod / customer / orders）をベースに、Learning Studio 用に一括セットアップスクリプトを提供。

```sql
-- Demo data tables (from OSS-DB textbook)
CREATE SCHEMA IF NOT EXISTS learning;

CREATE TABLE learning.prod (
    prod_id   INTEGER PRIMARY KEY,
    prod_name TEXT    NOT NULL,
    price     INTEGER NOT NULL
);
CREATE TABLE learning.customer (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT    NOT NULL
);
CREATE TABLE learning.orders (
    order_id    INTEGER PRIMARY KEY,
    order_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER REFERENCES learning.customer(customer_id),
    prod_id     INTEGER REFERENCES learning.prod(prod_id),
    qty         INTEGER NOT NULL
);

INSERT INTO learning.prod VALUES
    (1,'みかん',50),(2,'りんご',70),(3,'メロン',100),(4,'バナナ',30),(5,'すいか',500);
INSERT INTO learning.customer VALUES
    (1,'佐藤商事'),(2,'鈴木物産'),(3,'高橋商店'),(4,'藤原流通');
INSERT INTO learning.orders VALUES
    (1,CURRENT_TIMESTAMP,1,1,10),(2,CURRENT_TIMESTAMP,2,2,5),
    (3,CURRENT_TIMESTAMP,3,3,8),(4,CURRENT_TIMESTAMP,2,1,3),
    (5,CURRENT_TIMESTAMP,3,2,4),(6,CURRENT_TIMESTAMP,1,4,20),
    (7,CURRENT_TIMESTAMP,4,5,2),(8,CURRENT_TIMESTAMP,2,3,6);
```

大量データ（EXPLAIN/VACUUM 演習用）: `generate_series` で10万行テーブルを作成。

```sql
CREATE TABLE learning.large_orders (
    id         SERIAL PRIMARY KEY,
    order_date TIMESTAMP NOT NULL,
    region     TEXT      NOT NULL,
    amount     NUMERIC(10,2) NOT NULL,
    status     TEXT      NOT NULL
);
INSERT INTO learning.large_orders (order_date, region, amount, status)
SELECT
    CURRENT_TIMESTAMP - (random() * interval '365 days'),
    (ARRAY['Tokyo','Osaka','Nagoya','Fukuoka','Sapporo'])[1 + (i % 5)],
    (random() * 10000)::numeric(10,2),
    (ARRAY['completed','pending','cancelled','shipped'])[1 + (i % 4)]
FROM generate_series(1, 100000) AS s(i);
```

## コンテンツ一覧

### カテゴリ: SQL Basics（SQL初心者向け）

| ID | タイトル | 説明 | 教科書参照 |
|---|---|---|---|
| `learn_setup` | Demo Data Setup | learning スキーマ + テーブル + データ一括作成 | 1章 |
| `learn_select_basic` | SELECT Basics | WHERE, ORDER BY, LIMIT, DISTINCT | 2.3-2.5節 |
| `learn_select_calc` | Calculated Columns | 算術演算, AS, CASE WHEN | 2.4節 |
| `learn_aggregate` | Aggregation | COUNT, SUM, AVG, MIN, MAX, GROUP BY, HAVING | 2.6節 |
| `learn_join` | JOIN | INNER JOIN, LEFT JOIN, 3テーブル結合 | 6.2節 |
| `learn_subquery` | Subqueries | IN, EXISTS, スカラーサブクエリ, FROM句サブクエリ | 6.3節 |
| `learn_dml` | INSERT / UPDATE / DELETE | 基本DML + 演習1の値上げシナリオ | 2.7-2.8節, 演習1 |
| `learn_ddl` | DDL (CREATE / ALTER / DROP) | テーブル作成・変更・削除, 制約 | 4章, 7章 |
| `learn_view` | Views | CREATE VIEW, ビュー経由のクエリ | 7.4節 |

### カテゴリ: OLTP Database（OLTPデータベース初心者向け）

| ID | タイトル | 説明 | 教科書参照 | 制約 |
|---|---|---|---|---|
| `learn_explain_basic` | EXPLAIN Basics | Seq Scan vs Index Scan, cost/rows の読み方 | 9.2節 | — |
| `learn_index_tuning` | Index Tuning | インデックス作成前後の EXPLAIN 比較, 複合インデックス | 9.1節 | — |
| `learn_index_selectivity` | Index Selectivity | カーディナリティが低い列ではインデックスが使われない例 | 9.2節 | — |
| `learn_lock_observation` | Lock Observation | pg_locks + pg_stat_activity でロック状態を観察 | 8.6節 | SELECTのみ |
| `learn_mvcc_observation` | MVCC Observation | xmin/xmax/ctid で行バージョンを観察 | 8.6節, 9.3節 | — |

**注**: トランザクション（BEGIN/COMMIT/ROLLBACK）とロック競合のデモは autocommit 制約により現行では不可。

### カテゴリ: PostgreSQL（PostgreSQL 初心者向け）

| ID | タイトル | 説明 | 教科書参照 |
|---|---|---|---|
| `learn_datetime` | Date/Time Functions | now(), age(), date_trunc(), extract(), interval 演算, to_char() | 3章 |
| `learn_string` | String Functions | concat, substring, position, length, regexp_matches, format() | — |
| `learn_cast_coalesce` | Type Casting & COALESCE | CAST, ::, COALESCE, NULLIF | 3章 |
| `learn_system_catalog` | System Catalogs | pg_stat_user_tables, pg_class, pg_namespace でDB内部を探索 | 9章 |
| `learn_vacuum` | VACUUM & Dead Tuples | 大量DELETE → n_dead_tup確認 → VACUUM → 再確認 | 9.3節 |
| `learn_analyze` | ANALYZE & Statistics | pg_stats の most_common_vals, histogram_bounds を観察 | 9.3節 |
| `learn_table_bloat` | Table Bloat Check | pg_stat_user_tables + pg_relation_size で肥大化を確認 | 9.3節 |
| `learn_config` | PostgreSQL Configuration | pg_settings から主要パラメータを確認, context 列の意味 | — |

## 除外項目

- ユーザー/権限管理（Snowflake Postgres での操作が教科書と異なる）
- pg_dump/restore（ファイル出力が扱いづらい）
- インストール/接続方法（Learning Studio が代替する部分）
- COPY TO/FROM ファイル（pg_lake の S3 COPY で代替済み）

## 実装手順

1. `sql_samples.py` に上記エントリを追加（各エントリに category, title, description, sql）
2. 既存の Basics / Performance / Admin / pg_lake カテゴリは維持
3. 新カテゴリ: `SQL Basics`, `OLTP Database`, `PostgreSQL`
4. Demo Data Setup は最初に実行する前提で、各サンプルの冒頭に依存関係を記載

## 将来の拡張

- [ ] SQL Client に autocommit=false モード追加 → トランザクション/ロックのデモが可能に
- [ ] 2セッション並行デモ（WebSocket ベースのセッション維持）
- [ ] 教科書 演習2（郵便番号12万件）の代替として pgbench テーブルを活用した大量データ演習
