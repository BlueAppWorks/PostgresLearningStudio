"""
Monitoring collector - collects pg_stat_* metrics during benchmark execution.
Runs as a background thread, collecting snapshots at configurable intervals.
"""

import threading

from db import get_monitor_pool


class MonitoringCollector:
    """Collects PostgreSQL statistics snapshots during benchmark runs."""

    def __init__(self, run_id: int, interval_sec: int = 2):
        self.run_id = run_id
        self.interval_sec = interval_sec
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.snapshot_count = 0

    def start(self):
        """Start collecting metrics in a background thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._thread.start()
        print(f"  Monitoring started (run_id={self.run_id}, interval={self.interval_sec}s)")

    def stop(self):
        """Stop collecting metrics and wait for thread to finish."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        print(f"  Monitoring stopped ({self.snapshot_count} snapshots collected)")

    def _collect_loop(self):
        """Main collection loop - runs until stop_event is set."""
        pool = get_monitor_pool()
        while not self._stop_event.is_set():
            try:
                with pool.connection() as conn:
                    self._collect_snapshot(conn)
                    self.snapshot_count += 1
            except Exception as e:
                print(f"  Monitoring error: {e}")
            self._stop_event.wait(self.interval_sec)

    def _collect_snapshot(self, conn):
        """Collect one snapshot of all available metrics."""
        # Create snapshot record
        cur = conn.execute(
            "INSERT INTO metrics.snapshots (run_id) VALUES (%s) RETURNING snapshot_id",
            (self.run_id,),
        )
        snapshot_id = cur.fetchone()[0]

        self._collect_stat_activity(conn, snapshot_id)
        self._collect_stat_database(conn, snapshot_id)

        conn.commit()

    def _collect_stat_activity(self, conn, snapshot_id: int):
        """Collect pg_stat_activity snapshot."""
        try:
            conn.execute(
                """
                INSERT INTO metrics.stat_activity
                    (snapshot_id, pid, state, wait_event_type, wait_event,
                     query, backend_start, xact_start, query_start)
                SELECT %s, pid, state, wait_event_type, wait_event,
                       left(query, 500), backend_start, xact_start, query_start
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid != pg_backend_pid()
                """,
                (snapshot_id,),
            )
        except Exception as e:
            print(f"    stat_activity collection failed: {e}")

    def _collect_stat_database(self, conn, snapshot_id: int):
        """Collect pg_stat_database snapshot."""
        try:
            conn.execute(
                """
                INSERT INTO metrics.stat_database
                    (snapshot_id, datname, xact_commit, xact_rollback,
                     blks_read, blks_hit, tup_returned, tup_fetched,
                     tup_inserted, tup_updated, tup_deleted,
                     deadlocks, temp_files, temp_bytes)
                SELECT %s, datname, xact_commit, xact_rollback,
                       blks_read, blks_hit, tup_returned, tup_fetched,
                       tup_inserted, tup_updated, tup_deleted,
                       deadlocks, temp_files, temp_bytes
                FROM pg_stat_database
                WHERE datname = current_database()
                """,
                (snapshot_id,),
            )
        except Exception as e:
            print(f"    stat_database collection failed: {e}")
