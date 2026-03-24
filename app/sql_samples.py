"""Built-in SQL sample queries for the SQL Client learning interface."""

_SAMPLES = [
    # ── System ──
    {
        "id": "basic_version",
        "category": "System",
        "title": "PostgreSQL version",
        "description": "Check the PostgreSQL server version.",
        "sql": "SELECT version();",
    },
    {
        "id": "basic_databases",
        "category": "System",
        "title": "List databases",
        "description": "Show all databases on the server.",
        "sql": "SELECT datname, pg_size_pretty(pg_database_size(datname)) AS size\nFROM pg_database\nORDER BY pg_database_size(datname) DESC;",
    },
    {
        "id": "basic_tables",
        "category": "System",
        "title": "List tables",
        "description": "Show all user tables in the current database.",
        "sql": "SELECT schemaname, tablename,\n       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS size\nFROM pg_tables\nWHERE schemaname NOT IN ('pg_catalog', 'information_schema')\nORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;",
    },
    {
        "id": "admin_extensions",
        "category": "System",
        "title": "Installed extensions",
        "description": "List all installed PostgreSQL extensions.",
        "sql": "SELECT extname, extversion, extnamespace::regnamespace AS schema\nFROM pg_extension\nORDER BY extname;",
    },

    # ══════════════════════════════════════════
    # SQL Basics (SQL初心者向け)
    # ══════════════════════════════════════════
    {
        "id": "learn_setup",
        "category": "SQL Basics",
        "title": "Demo Data Setup",
        "description": "Create learning schema with prod/customer/orders tables and sample data. Run this first.",
        "sql": """-- ============================================
-- Learning Demo Data Setup
-- Based on OSS-DB Standard Textbook (LPI-Japan)
-- ============================================

-- Clean up if exists
DROP SCHEMA IF EXISTS learning CASCADE;
CREATE SCHEMA learning;

-- Product table
CREATE TABLE learning.prod (
    prod_id   INTEGER PRIMARY KEY,
    prod_name TEXT    NOT NULL,
    price     INTEGER NOT NULL
);

-- Customer table
CREATE TABLE learning.customer (
    customer_id   INTEGER PRIMARY KEY,
    customer_name TEXT    NOT NULL
);

-- Orders table (with foreign keys)
CREATE TABLE learning.orders (
    order_id    INTEGER PRIMARY KEY,
    order_date  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    customer_id INTEGER REFERENCES learning.customer(customer_id),
    prod_id     INTEGER REFERENCES learning.prod(prod_id),
    qty         INTEGER NOT NULL
);

-- Insert sample data
INSERT INTO learning.prod VALUES
    (1, 'みかん', 50), (2, 'りんご', 70), (3, 'メロン', 100),
    (4, 'バナナ', 30), (5, 'すいか', 500);

INSERT INTO learning.customer VALUES
    (1, '佐藤商事'), (2, '鈴木物産'), (3, '高橋商店'), (4, '藤原流通');

INSERT INTO learning.orders VALUES
    (1, CURRENT_TIMESTAMP - interval '5 days', 1, 1, 10),
    (2, CURRENT_TIMESTAMP - interval '4 days', 2, 2, 5),
    (3, CURRENT_TIMESTAMP - interval '3 days', 3, 3, 8),
    (4, CURRENT_TIMESTAMP - interval '3 days', 2, 1, 3),
    (5, CURRENT_TIMESTAMP - interval '2 days', 3, 2, 4),
    (6, CURRENT_TIMESTAMP - interval '2 days', 1, 4, 20),
    (7, CURRENT_TIMESTAMP - interval '1 day',  4, 5, 2),
    (8, CURRENT_TIMESTAMP,                     2, 3, 6);

-- Verify
SELECT 'prod' AS table_name, count(*) AS rows FROM learning.prod
UNION ALL
SELECT 'customer', count(*) FROM learning.customer
UNION ALL
SELECT 'orders', count(*) FROM learning.orders;""",
    },
    {
        "id": "learn_select_basic",
        "category": "SQL Basics",
        "title": "SELECT Basics",
        "description": "WHERE, ORDER BY, LIMIT, DISTINCT, BETWEEN — basic query patterns.",
        "sql": """-- All products
SELECT * FROM learning.prod;

-- Filter by price
SELECT prod_name, price FROM learning.prod
WHERE price >= 70
ORDER BY price DESC;

-- BETWEEN
SELECT * FROM learning.prod
WHERE price BETWEEN 50 AND 100;

-- DISTINCT customer_ids that have ordered
SELECT DISTINCT customer_id FROM learning.orders;

-- LIMIT
SELECT * FROM learning.orders ORDER BY order_date DESC LIMIT 3;""",
    },
    {
        "id": "learn_select_calc",
        "category": "SQL Basics",
        "title": "Calculated Columns & CASE",
        "description": "Arithmetic, aliases, CASE WHEN for conditional values.",
        "sql": """-- 10% price increase (display only, not saved)
SELECT prod_name, price,
       price * 1.1 AS price_with_tax
FROM learning.prod;

-- Price category using CASE
SELECT prod_name, price,
       CASE
           WHEN price >= 100 THEN 'Premium'
           WHEN price >= 50  THEN 'Standard'
           ELSE 'Budget'
       END AS category
FROM learning.prod
ORDER BY price DESC;""",
    },
    {
        "id": "learn_aggregate",
        "category": "SQL Basics",
        "title": "Aggregation & GROUP BY",
        "description": "COUNT, SUM, AVG, MIN, MAX with GROUP BY and HAVING.",
        "sql": """-- Basic aggregation
SELECT count(*) AS order_count,
       sum(qty) AS total_qty,
       avg(qty)::numeric(5,1) AS avg_qty,
       min(qty) AS min_qty,
       max(qty) AS max_qty
FROM learning.orders;

-- Orders per customer
SELECT c.customer_name,
       count(*) AS order_count,
       sum(o.qty) AS total_qty
FROM learning.orders o
JOIN learning.customer c ON o.customer_id = c.customer_id
GROUP BY c.customer_name
ORDER BY total_qty DESC;

-- HAVING: only customers with 2+ orders
SELECT c.customer_name, count(*) AS order_count
FROM learning.orders o
JOIN learning.customer c ON o.customer_id = c.customer_id
GROUP BY c.customer_name
HAVING count(*) >= 2;""",
    },
    {
        "id": "learn_join",
        "category": "SQL Basics",
        "title": "JOIN",
        "description": "INNER JOIN, LEFT JOIN, 3-table join with order details.",
        "sql": """-- INNER JOIN: orders with product names
SELECT o.order_id, o.order_date, p.prod_name, o.qty
FROM learning.orders o
JOIN learning.prod p ON o.prod_id = p.prod_id
ORDER BY o.order_date DESC;

-- LEFT JOIN: all customers, even those without orders
SELECT c.customer_name, o.order_id, o.qty
FROM learning.customer c
LEFT JOIN learning.orders o ON c.customer_id = o.customer_id
ORDER BY c.customer_name;

-- 3-table JOIN: full order details with amounts
SELECT o.order_id, o.order_date,
       c.customer_name,
       p.prod_name, p.price,
       o.qty,
       p.price * o.qty AS amount
FROM learning.orders o
JOIN learning.customer c ON o.customer_id = c.customer_id
JOIN learning.prod p ON o.prod_id = p.prod_id
ORDER BY o.order_date DESC;""",
    },
    {
        "id": "learn_subquery",
        "category": "SQL Basics",
        "title": "Subqueries",
        "description": "IN, EXISTS, scalar subquery, FROM-clause subquery.",
        "sql": """-- IN: customers who ordered メロン
SELECT customer_name FROM learning.customer
WHERE customer_id IN (
    SELECT customer_id FROM learning.orders
    WHERE prod_id = (SELECT prod_id FROM learning.prod WHERE prod_name = 'メロン')
);

-- EXISTS: products that have been ordered
SELECT prod_name FROM learning.prod p
WHERE EXISTS (
    SELECT 1 FROM learning.orders o WHERE o.prod_id = p.prod_id
);

-- Scalar subquery: each product vs average price
SELECT prod_name, price,
       price - (SELECT avg(price) FROM learning.prod)::integer AS diff_from_avg
FROM learning.prod
ORDER BY diff_from_avg DESC;

-- FROM-clause subquery: top customer by total amount
SELECT * FROM (
    SELECT c.customer_name,
           sum(p.price * o.qty) AS total_amount
    FROM learning.orders o
    JOIN learning.customer c ON o.customer_id = c.customer_id
    JOIN learning.prod p ON o.prod_id = p.prod_id
    GROUP BY c.customer_name
) AS summary
ORDER BY total_amount DESC
LIMIT 1;""",
    },
    {
        "id": "learn_dml",
        "category": "SQL Basics",
        "title": "INSERT / UPDATE / DELETE",
        "description": "Data manipulation: add, modify, remove rows. Includes price-update exercise.",
        "sql": """-- INSERT a new product
INSERT INTO learning.prod VALUES (6, 'ぶどう', 200);
SELECT * FROM learning.prod ORDER BY prod_id;

-- UPDATE: 10% price increase for all products (textbook exercise 1-1)
UPDATE learning.prod SET price = price * 1.1;
SELECT * FROM learning.prod ORDER BY prod_id;

-- UPDATE with WHERE: reset products over 100 (exercise 1-2)
UPDATE learning.prod
SET price = CASE prod_id
    WHEN 1 THEN 50 WHEN 2 THEN 70 WHEN 3 THEN 100
    WHEN 4 THEN 30 WHEN 5 THEN 500 WHEN 6 THEN 200
END;
SELECT * FROM learning.prod ORDER BY prod_id;

-- DELETE: remove the added product
DELETE FROM learning.prod WHERE prod_id = 6;
SELECT * FROM learning.prod ORDER BY prod_id;""",
    },
    {
        "id": "learn_ddl",
        "category": "SQL Basics",
        "title": "DDL (CREATE / ALTER / DROP)",
        "description": "Table creation, constraints, ALTER TABLE, DROP TABLE.",
        "sql": """-- CREATE TABLE with constraints
CREATE TABLE learning.inventory (
    inv_id    SERIAL PRIMARY KEY,
    prod_id   INTEGER NOT NULL REFERENCES learning.prod(prod_id),
    warehouse TEXT    NOT NULL DEFAULT 'Tokyo',
    quantity  INTEGER NOT NULL CHECK (quantity >= 0),
    updated   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INSERT data
INSERT INTO learning.inventory (prod_id, warehouse, quantity) VALUES
    (1, 'Tokyo', 100), (2, 'Tokyo', 50), (3, 'Osaka', 30),
    (1, 'Osaka', 80), (4, 'Tokyo', 200);

SELECT * FROM learning.inventory;

-- ALTER TABLE: add a column
ALTER TABLE learning.inventory ADD COLUMN min_stock INTEGER DEFAULT 10;
SELECT * FROM learning.inventory;

-- DROP TABLE
DROP TABLE learning.inventory;""",
    },
    {
        "id": "learn_view",
        "category": "SQL Basics",
        "title": "Views",
        "description": "CREATE VIEW for reusable queries.",
        "sql": """-- Create a view: order summary with amounts
CREATE OR REPLACE VIEW learning.order_summary AS
SELECT o.order_id, o.order_date,
       c.customer_name, p.prod_name,
       o.qty, p.price * o.qty AS amount
FROM learning.orders o
JOIN learning.customer c ON o.customer_id = c.customer_id
JOIN learning.prod p ON o.prod_id = p.prod_id;

-- Query the view
SELECT * FROM learning.order_summary ORDER BY order_date DESC;

-- Aggregation on the view
SELECT customer_name, sum(amount) AS total_spent
FROM learning.order_summary
GROUP BY customer_name
ORDER BY total_spent DESC;""",
    },

    # ══════════════════════════════════════════
    # OLTP Database (OLTPデータベース初心者向け)
    # ══════════════════════════════════════════
    {
        "id": "learn_large_data_setup",
        "category": "OLTP Database",
        "title": "Large Data Setup (100K rows)",
        "description": "Create a 100,000-row table for EXPLAIN, index, and VACUUM exercises.",
        "sql": """-- Create large table for performance exercises
DROP TABLE IF EXISTS learning.large_orders CASCADE;
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

ANALYZE learning.large_orders;

SELECT count(*) AS rows,
       pg_size_pretty(pg_total_relation_size('learning.large_orders')) AS total_size
FROM learning.large_orders;""",
    },
    {
        "id": "learn_explain_basic",
        "category": "OLTP Database",
        "title": "EXPLAIN Basics",
        "description": "Read execution plans: Seq Scan vs Index Scan, cost, rows, width.",
        "sql": """-- Seq Scan (no index on region)
EXPLAIN SELECT * FROM learning.large_orders WHERE region = 'Tokyo';

-- Index Scan (primary key)
EXPLAIN SELECT * FROM learning.large_orders WHERE id = 42;

-- EXPLAIN ANALYZE: actual execution time
EXPLAIN ANALYZE SELECT * FROM learning.large_orders WHERE id = 42;

-- Read the output:
-- cost=0.00..N: estimated startup and total cost
-- rows=N: estimated number of rows
-- actual time=N..N: real execution time (ANALYZE only)
-- Seq Scan: reads every row in the table
-- Index Scan: uses an index to find rows directly""",
    },
    {
        "id": "learn_index_tuning",
        "category": "OLTP Database",
        "title": "Index Tuning",
        "description": "Create indexes and compare EXPLAIN before/after.",
        "sql": """-- BEFORE: Seq Scan on region (no index)
EXPLAIN ANALYZE SELECT count(*) FROM learning.large_orders WHERE region = 'Tokyo';

-- Create an index
CREATE INDEX IF NOT EXISTS idx_large_orders_region ON learning.large_orders (region);

-- AFTER: Index Scan (or Bitmap Index Scan)
EXPLAIN ANALYZE SELECT count(*) FROM learning.large_orders WHERE region = 'Tokyo';

-- Composite index for range + equality
CREATE INDEX IF NOT EXISTS idx_large_orders_date_region
    ON learning.large_orders (region, order_date);

-- Uses the composite index
EXPLAIN ANALYZE SELECT * FROM learning.large_orders
WHERE region = 'Tokyo' AND order_date >= CURRENT_TIMESTAMP - interval '30 days';""",
    },
    {
        "id": "learn_index_selectivity",
        "category": "OLTP Database",
        "title": "Index Selectivity",
        "description": "Why low-cardinality columns don't benefit from indexes.",
        "sql": """-- Status has only 4 distinct values (low cardinality)
SELECT status, count(*) FROM learning.large_orders GROUP BY status;

-- Create index on status
CREATE INDEX IF NOT EXISTS idx_large_orders_status ON learning.large_orders (status);

-- Planner still chooses Seq Scan! (index is not selective enough)
EXPLAIN ANALYZE SELECT * FROM learning.large_orders WHERE status = 'completed';

-- Compare with high-selectivity query (single row by ID)
EXPLAIN ANALYZE SELECT * FROM learning.large_orders WHERE id = 42;

-- Lesson: indexes are most effective when they select a small fraction of rows.
-- The planner considers selectivity, not just whether an index exists.""",
    },
    {
        "id": "learn_txn_basic",
        "category": "OLTP Database",
        "title": "Transaction Basics (BEGIN/COMMIT/ROLLBACK)",
        "description": "Turn off Auto Commit first! Then run each statement one at a time.",
        "sql": """-- !! IMPORTANT: Turn OFF "Auto Commit" toggle above !!
-- Then execute each statement one by one (select + Ctrl+Enter)

-- 1. Start transaction
BEGIN;

-- 2. Insert a row
INSERT INTO learning.prod VALUES (99, 'テスト商品', 999);

-- 3. Verify it exists (visible within this transaction)
SELECT * FROM learning.prod ORDER BY prod_id;

-- 4. Rollback (undo the insert)
ROLLBACK;

-- 5. Verify: the row is gone
SELECT * FROM learning.prod ORDER BY prod_id;

-- Now try with COMMIT:
BEGIN;
INSERT INTO learning.prod VALUES (99, 'テスト商品', 999);
COMMIT;
-- The row now persists
SELECT * FROM learning.prod ORDER BY prod_id;
-- Clean up
DELETE FROM learning.prod WHERE prod_id = 99;""",
    },
    {
        "id": "learn_mvcc",
        "category": "OLTP Database",
        "title": "MVCC Observation",
        "description": "See PostgreSQL's row versioning with xmin, xmax, ctid system columns.",
        "sql": """-- PostgreSQL keeps old row versions (MVCC)
-- System columns reveal internal versioning:
--   xmin: transaction ID that created this row version
--   xmax: transaction ID that deleted/updated it (0 = still live)
--   ctid: physical location (page, offset)

SELECT ctid, xmin, xmax, * FROM learning.prod;

-- After UPDATE, the row gets a new ctid (new physical location)
-- and xmax of the old version is set to the updating transaction ID
UPDATE learning.prod SET price = price + 1 WHERE prod_id = 1;
SELECT ctid, xmin, xmax, * FROM learning.prod WHERE prod_id = 1;

-- Reset
UPDATE learning.prod SET price = 50 WHERE prod_id = 1;""",
    },
    {
        "id": "learn_lock_observation",
        "category": "OLTP Database",
        "title": "Lock Observation",
        "description": "View current locks and active sessions via pg_locks and pg_stat_activity.",
        "sql": """-- Current locks held by other sessions
SELECT l.pid, l.locktype, l.relation::regclass, l.mode, l.granted,
       a.usename, a.state,
       left(a.query, 60) AS query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE l.pid != pg_backend_pid()
  AND l.locktype = 'relation'
ORDER BY l.pid;

-- My own session info
SELECT pg_backend_pid() AS my_pid,
       current_user, current_database(),
       now() AS current_time;

-- Lock types explained:
-- AccessShareLock: SELECT (weakest, compatible with almost everything)
-- RowShareLock: SELECT FOR UPDATE
-- RowExclusiveLock: INSERT/UPDATE/DELETE
-- AccessExclusiveLock: DDL like DROP TABLE (blocks everything)""",
    },

    # ══════════════════════════════════════════
    # PostgreSQL (PostgreSQL初心者向け)
    # ══════════════════════════════════════════
    {
        "id": "learn_datetime",
        "category": "PostgreSQL",
        "title": "Date/Time Functions",
        "description": "now(), age(), date_trunc(), extract(), interval arithmetic, to_char().",
        "sql": """-- Current timestamp
SELECT now(), current_date, current_time;

-- Interval arithmetic
SELECT now() - interval '7 days' AS one_week_ago,
       now() + interval '1 month' AS next_month;

-- date_trunc: truncate to day/month/year
SELECT date_trunc('month', now()) AS month_start,
       date_trunc('year', now()) AS year_start;

-- extract: get specific parts
SELECT extract(year FROM now()) AS year,
       extract(month FROM now()) AS month,
       extract(dow FROM now()) AS day_of_week;  -- 0=Sunday

-- age: difference between timestamps
SELECT age(CURRENT_TIMESTAMP, '2025-01-01'::timestamp) AS since_2025;

-- to_char: format output
SELECT to_char(now(), 'YYYY-MM-DD HH24:MI:SS') AS formatted,
       to_char(now(), 'Day, DD Month YYYY') AS readable;

-- Orders in the last 3 days
SELECT * FROM learning.orders
WHERE order_date >= now() - interval '3 days'
ORDER BY order_date DESC;""",
    },
    {
        "id": "learn_string",
        "category": "PostgreSQL",
        "title": "String Functions",
        "description": "concat, substring, position, length, regexp_matches, format().",
        "sql": """-- String concatenation
SELECT customer_name || ' (ID: ' || customer_id || ')' AS label
FROM learning.customer;

-- format() — safer concatenation
SELECT format('Customer %s has ID %s', customer_name, customer_id) AS label
FROM learning.customer;

-- Length and position
SELECT prod_name,
       length(prod_name) AS name_length,
       position('ん' IN prod_name) AS pos_n
FROM learning.prod;

-- substring
SELECT substring('PostgreSQL' FROM 1 FOR 8);  -- 'PostgreS'
SELECT substring('Hello-World' FROM '[A-Z][a-z]+');  -- 'Hello'

-- Regular expression matching
SELECT prod_name FROM learning.prod
WHERE prod_name ~ '^[ぁ-ん]+$';  -- Hiragana-only names""",
    },
    {
        "id": "learn_cast_coalesce",
        "category": "PostgreSQL",
        "title": "Type Casting & COALESCE",
        "description": "CAST, ::, COALESCE, NULLIF — handling types and NULLs.",
        "sql": """-- :: casting (PostgreSQL shorthand)
SELECT '42'::integer, '2025-01-01'::date, 3.14::text;

-- CAST (standard SQL)
SELECT CAST('42' AS integer), CAST(now() AS date);

-- COALESCE: first non-NULL value
SELECT COALESCE(NULL, NULL, 'default') AS result;

-- Practical: handle missing data
SELECT c.customer_name,
       COALESCE(sum(o.qty), 0) AS total_qty
FROM learning.customer c
LEFT JOIN learning.orders o ON c.customer_id = o.customer_id
GROUP BY c.customer_name
ORDER BY total_qty DESC;

-- NULLIF: return NULL if two values are equal
SELECT NULLIF(1, 1) AS is_null,
       NULLIF(1, 2) AS is_one;""",
    },
    {
        "id": "learn_system_catalog",
        "category": "PostgreSQL",
        "title": "System Catalogs",
        "description": "Explore database internals via pg_class, pg_namespace, pg_stat_user_tables.",
        "sql": """-- All schemas
SELECT nspname AS schema_name,
       pg_catalog.pg_get_userbyid(nspowner) AS owner
FROM pg_namespace
WHERE nspname NOT LIKE 'pg_%' AND nspname != 'information_schema'
ORDER BY nspname;

-- Tables with details (pg_class)
SELECT n.nspname AS schema, c.relname AS table_name,
       c.relkind AS type,  -- r=table, v=view, i=index, S=sequence
       c.reltuples::bigint AS est_rows,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'learning'
ORDER BY pg_total_relation_size(c.oid) DESC;

-- Table activity statistics
SELECT relname,
       seq_scan, idx_scan,
       n_tup_ins AS inserts, n_tup_upd AS updates, n_tup_del AS deletes,
       n_live_tup AS live_rows, n_dead_tup AS dead_rows,
       last_vacuum, last_autovacuum, last_analyze
FROM pg_stat_user_tables
WHERE schemaname = 'learning'
ORDER BY relname;""",
    },
    {
        "id": "learn_vacuum",
        "category": "PostgreSQL",
        "title": "VACUUM & Dead Tuples",
        "description": "Delete rows, observe dead tuples, run VACUUM, compare sizes.",
        "sql": """-- 1. Check current state
SELECT relname, n_live_tup, n_dead_tup,
       pg_size_pretty(pg_total_relation_size('learning.large_orders')) AS size
FROM pg_stat_user_tables
WHERE relname = 'large_orders';

-- 2. Delete half the rows (creates dead tuples)
DELETE FROM learning.large_orders WHERE id % 2 = 0;

-- 3. Check dead tuples (may need a moment to update stats)
SELECT relname, n_live_tup, n_dead_tup,
       pg_size_pretty(pg_total_relation_size('learning.large_orders')) AS size
FROM pg_stat_user_tables
WHERE relname = 'large_orders';

-- 4. VACUUM: reclaim space from dead tuples
VACUUM learning.large_orders;

-- 5. Check again: dead tuples should be 0
SELECT relname, n_live_tup, n_dead_tup,
       pg_size_pretty(pg_total_relation_size('learning.large_orders')) AS size
FROM pg_stat_user_tables
WHERE relname = 'large_orders';

-- Note: VACUUM marks space as reusable but doesn't shrink the file.
-- VACUUM FULL physically compacts the table (requires exclusive lock).
-- In production, autovacuum handles this automatically.""",
    },
    {
        "id": "learn_analyze",
        "category": "PostgreSQL",
        "title": "ANALYZE & Statistics",
        "description": "Run ANALYZE, inspect pg_stats to see what the planner knows.",
        "sql": """-- Run ANALYZE to update statistics
ANALYZE learning.large_orders;

-- View planner statistics for the 'region' column
SELECT tablename, attname,
       n_distinct,
       most_common_vals,
       most_common_freqs
FROM pg_stats
WHERE tablename = 'large_orders' AND attname = 'region';

-- View histogram for 'amount' column
SELECT tablename, attname,
       n_distinct,
       histogram_bounds
FROM pg_stats
WHERE tablename = 'large_orders' AND attname = 'amount';

-- The planner uses these statistics to estimate row counts
-- and choose between Seq Scan, Index Scan, Hash Join, etc.
-- Stale statistics → bad estimates → suboptimal plans.
-- This is exactly what the pg_hint_plan demo demonstrates.""",
    },
    {
        "id": "learn_table_bloat",
        "category": "PostgreSQL",
        "title": "Table Bloat Check",
        "description": "Detect and measure table bloat from dead tuples.",
        "sql": """-- Bloat estimation: compare live tuples vs table size
SELECT relname,
       n_live_tup,
       n_dead_tup,
       CASE WHEN n_live_tup > 0
           THEN round(n_dead_tup::numeric / n_live_tup * 100, 1)
           ELSE 0
       END AS dead_pct,
       pg_size_pretty(pg_relation_size(relid)) AS table_size,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       last_vacuum,
       last_autovacuum
FROM pg_stat_user_tables
WHERE schemaname = 'learning'
ORDER BY n_dead_tup DESC;

-- If dead_pct is high (>20%), consider VACUUM.
-- If table_size is much larger than expected for live rows,
-- VACUUM FULL may help (but locks the table).""",
    },
    {
        "id": "learn_config",
        "category": "PostgreSQL",
        "title": "PostgreSQL Configuration",
        "description": "View key server parameters and their contexts.",
        "sql": """-- Key performance parameters
SELECT name, setting, unit, short_desc, context
FROM pg_settings
WHERE name IN (
    'shared_buffers', 'work_mem', 'maintenance_work_mem',
    'effective_cache_size', 'max_connections',
    'random_page_cost', 'seq_page_cost',
    'default_statistics_target', 'statement_timeout'
)
ORDER BY name;

-- context column meanings:
-- internal: cannot be changed
-- postmaster: requires restart
-- sighup: requires reload (SELECT pg_reload_conf())
-- superuser: can be SET by superuser
-- user: can be SET by any user in their session

-- Autovacuum settings
SELECT name, setting, short_desc
FROM pg_settings
WHERE name LIKE 'autovacuum%'
ORDER BY name;""",
    },

    # ══════════════════════════════════════════
    # Performance (既存 — 維持)
    # ══════════════════════════════════════════
    {
        "id": "perf_active_queries",
        "category": "Performance",
        "title": "Active queries",
        "description": "Show currently running queries.",
        "sql": "SELECT pid, usename, state, query_start, now() - query_start AS duration, query\nFROM pg_stat_activity\nWHERE state = 'active'\nORDER BY query_start;",
    },
    {
        "id": "perf_table_stats",
        "category": "Performance",
        "title": "Table statistics",
        "description": "Show sequential vs index scan ratios for tables.",
        "sql": "SELECT relname,\n       seq_scan, seq_tup_read,\n       idx_scan, idx_tup_fetch,\n       n_tup_ins, n_tup_upd, n_tup_del,\n       n_live_tup, n_dead_tup\nFROM pg_stat_user_tables\nORDER BY seq_scan DESC\nLIMIT 20;",
    },
    {
        "id": "perf_index_usage",
        "category": "Performance",
        "title": "Index usage",
        "description": "Show index usage statistics.",
        "sql": "SELECT schemaname, relname, indexrelname,\n       idx_scan, idx_tup_read, idx_tup_fetch,\n       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size\nFROM pg_stat_user_indexes\nORDER BY idx_scan DESC\nLIMIT 20;",
    },
    {
        "id": "perf_cache_hit",
        "category": "Performance",
        "title": "Cache hit ratio",
        "description": "Check buffer cache hit ratio.",
        "sql": "SELECT\n  sum(heap_blks_read) AS heap_read,\n  sum(heap_blks_hit) AS heap_hit,\n  CASE WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0\n    THEN round(sum(heap_blks_hit)::numeric / (sum(heap_blks_hit) + sum(heap_blks_read)) * 100, 2)\n    ELSE 0\n  END AS hit_ratio_pct\nFROM pg_statio_user_tables;",
    },
    {
        "id": "admin_locks",
        "category": "Performance",
        "title": "Current locks",
        "description": "Show current lock activity.",
        "sql": "SELECT l.pid, l.locktype, l.mode, l.granted,\n       a.usename, a.query_start, a.state,\n       left(a.query, 80) AS query\nFROM pg_locks l\nJOIN pg_stat_activity a ON l.pid = a.pid\nWHERE l.pid != pg_backend_pid()\nORDER BY l.pid;",
    },
    {
        "id": "admin_settings",
        "category": "Performance",
        "title": "Key settings",
        "description": "Show important PostgreSQL configuration parameters.",
        "sql": "SELECT name, setting, unit, short_desc\nFROM pg_settings\nWHERE name IN (\n  'shared_buffers', 'work_mem', 'maintenance_work_mem',\n  'effective_cache_size', 'max_connections',\n  'checkpoint_completion_target', 'wal_buffers',\n  'random_page_cost', 'effective_io_concurrency'\n)\nORDER BY name;",
    },
]


def get_samples() -> list[dict]:
    """Return all built-in SQL samples."""
    return list(_SAMPLES)


def get_sample_by_id(sample_id: str) -> dict | None:
    """Return a single sample by ID, or None if not found."""
    for s in _SAMPLES:
        if s["id"] == sample_id:
            return dict(s)
    return None
