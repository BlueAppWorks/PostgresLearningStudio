#!/usr/bin/env python3
"""Check if the target database exists; create it if not.

Replaces the psql calls previously used in entrypoint.sh, eliminating the
need for the postgresql-client package in the runtime image.
"""

import os
import sys

import psycopg
from psycopg import sql


def main():
    dbname = os.environ.get("PGDATABASE", "benchmark")
    conninfo = (
        f"host={os.environ['PGHOST']} "
        f"port={os.environ.get('PGPORT', '5432')} "
        f"dbname=postgres "
        f"user={os.environ['PGUSER']} "
        f"password={os.environ.get('PGPASSWORD', '')} "
        f"sslmode={os.environ.get('PGSSLMODE', 'require')}"
    )

    try:
        conn = psycopg.connect(conninfo, autocommit=True)
        row = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)
        ).fetchone()

        if row:
            print(f"Database '{dbname}' already exists")
        else:
            print(f"Creating database '{dbname}'...")
            conn.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname))
            )
            print(f"Database '{dbname}' created")

        conn.close()
    except Exception as e:
        print(f"WARNING: Database init failed: {e}")
        print("Postgres may still be starting. Will retry on first request.")
        sys.exit(0)  # Non-fatal: app should start anyway


if __name__ == "__main__":
    main()
