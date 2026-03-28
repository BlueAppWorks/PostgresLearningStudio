# Postgres Learning Studio

An interactive learning and benchmarking platform for PostgreSQL, delivered as a Snowflake Native App on SPCS (Snowflake Container Services).

## What is this app?

Postgres Learning Studio is designed for anyone learning PostgreSQL — from SQL beginners to database administrators exploring advanced extensions. It provides a browser-based environment where you can execute SQL, run benchmarks, and experience PostgreSQL's powerful features hands-on, without installing anything locally.

This app also serves as a **reference implementation** for building business applications on Snowflake Postgres as a Snowflake Native App. The entire source code — including Snowflake Postgres connectivity, SPCS container deployment, and the setup wizard — is publicly available on GitHub as a reference for building your own applications.

## Key Features

### Learning Content

- **SQL Basics**: SELECT, JOIN, aggregation, subqueries, DML, DDL, views — with pre-loaded sample data based on the OSS-DB Standard Textbook (LPI-Japan)
- **OLTP Database**: Execution plans (EXPLAIN), index tuning, transactions (BEGIN/COMMIT/ROLLBACK), MVCC observation, lock monitoring
- **PostgreSQL Internals**: VACUUM, ANALYZE, system catalogs, date/time functions, type casting, configuration parameters, table bloat detection
- **Transaction Mode**: Toggle Auto Commit off to experience BEGIN/COMMIT/ROLLBACK interactively
- **SQL Editor**: All learning content runs in the built-in SQL Client — a general-purpose SQL editor where you can also write and execute any SQL freely

### Benchmark

- **pgbench Integration**: Run standard TPC-B Like, Simple Update, and Select Only workloads with configurable clients, threads, and duration
- **Workload Mixing**: Combine built-in workloads with custom ratios using pgbench's `-b script@weight` syntax
- **Custom Scenarios**: Register your own write/read transaction scripts and run them as benchmark scenarios with `-f script@weight`
- **Multi-Target Comparison**: Connect to multiple PostgreSQL instances (Snowflake Postgres, Amazon RDS, AlloyDB, self-hosted) and compare performance side-by-side with charts
- **Real-Time Monitoring**: Collect pg_stat_activity and pg_stat_database snapshots during benchmark runs

### Advanced Extensions

- **PostGIS**: Store coordinates, calculate distances, check polygon containment — with map visualization
- **pgvector**: Semantic search with vector embeddings — vectorize text and find similar documents
- **pg_hint_plan**: Control query planner behavior with SQL comment hints (requires external PostgreSQL — not yet available on Snowflake Postgres)

### pg_lake (Iceberg & Data Lake)

- **Iceberg Tables**: Create tables with `USING iceberg` — data stored as Parquet on S3 with Iceberg metadata
- **Execution Plans**: Compare DuckDB query pushdown behavior across different date ranges
- **Hot + Archive Pattern**: Real-time sync from heap (hot) to Iceberg (archive) using pg_incremental + pg_cron
- **Snowflake Integration**: Read the same Iceberg data from Snowflake — Zero ETL
- **Getting Started Guide**: Step-by-step S3/IAM/Storage Integration setup with dynamic SQL generation

## Architecture

- **Snowflake Native App**: Deployed as an Application Package with setup wizard (Streamlit)
- **SPCS Container**: Flask Web UI with pgbench, SQL client, and monitoring tools
- **Snowflake Postgres**: Connects to Snowflake's managed PostgreSQL service (also supports external PostgreSQL)

This app works standalone as a Snowflake Native App. It also conforms to the **Gallery Compatible v3** specification, which means it can be managed by Blue App Gallery for automated compute pool lifecycle (start/stop via time-based leases) when deployed alongside the Gallery platform.

## Source Code

The full source code of this application is publicly available on GitHub. If you are building your own Snowflake Native App on Snowflake Postgres, feel free to use it as a reference for SPCS container deployment, Streamlit setup wizards, and PostgreSQL connectivity patterns.

**Repository**: [github.com/BlueAppWorks/PostgresLearningStudio](https://github.com/BlueAppWorks/PostgresLearningStudio)
