# Postgres Learning Studio

PostgreSQL benchmark and learning tool running on Snowflake SPCS.

## Features

- **pgbench Benchmarking**: Run standard TPC-B and custom benchmarks against PostgreSQL
- **SQL Client**: Execute queries and explore PostgreSQL databases
- **Monitoring**: Real-time pg_stat_activity and pg_stat_database collection during benchmarks
- **Results Comparison**: Compare benchmark results side-by-side with charts
- **Multiple Targets**: Connect to multiple PostgreSQL instances (Snowflake Postgres, RDS, AlloyDB, etc.)
- **Advanced Labs**: pgvector, PostGIS, pg_hint_plan, and pg_lake exercises

## Architecture

- **Streamlit UI**: Setup and configuration interface (this app)
- **SPCS Container**: Flask Web UI with pgbench, SQL client, and monitoring tools
- **Gallery Compatible v3**: Service lifecycle managed by Gallery Operator
