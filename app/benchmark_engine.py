"""
Benchmark engine - pgbench subprocess wrapper.
Handles initialization, execution, output parsing, and result collection.
"""

import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Callable, Optional

from db import get_pgbench_env

# Regex for pgbench -P progress lines:
# "progress: 5.0 s, 1234.5 tps, lat 8.100 ms stddev 2.345, 0 failed"
PROGRESS_RE = re.compile(
    r"progress:\s+([\d.]+)\s+s,\s+([\d.]+)\s+tps,\s+"
    r"lat\s+([\d.]+)\s+ms\s+stddev\s+([\d.]+)"
)


class PgBenchRunner:
    """Manages pgbench execution as a subprocess."""

    def __init__(self, db_name: str, host: str, port: str, user: str,
                 password: str | None = None):
        self.db_name = db_name
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self._process: Optional[subprocess.Popen] = None
        self._cancelled = False

    def initialize(self, scale_factor: int = 10) -> dict:
        """Run pgbench -i to create/populate benchmark tables."""
        cmd = [
            "pgbench", "-i",
            "-s", str(scale_factor),
            "-h", self.host,
            "-p", self.port,
            "-U", self.user,
            self.db_name,
        ]
        print(f"  pgbench init: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=get_pgbench_env(self.password),
            timeout=600,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def run(
        self,
        params: dict,
        on_progress: Optional[Callable] = None,
    ) -> dict:
        """
        Execute pgbench with given parameters.

        Args:
            params: Benchmark parameters dict with keys:
                - builtin_script: str (tpcb-like, simple-update, select-only)
                - clients: int
                - threads: int
                - duration: int (seconds)
                - protocol: str (simple, extended, prepared)
                - progress_interval: int (seconds)
                - read_weight: int (optional, for workload mixer)
                - write_weight: int (optional, for workload mixer)
            on_progress: callback(elapsed_sec, tps, latency_avg, latency_stddev)
        """
        self._cancelled = False
        cmd = self._build_command(params)

        print(f"  pgbench run: {' '.join(cmd)}")
        started_at = datetime.now(timezone.utc)
        progress_data = []

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=get_pgbench_env(self.password),
        )

        full_output = []
        for line in self._process.stdout:
            full_output.append(line)
            if self._cancelled:
                self._process.terminate()
                break

            match = PROGRESS_RE.search(line)
            if match:
                elapsed = float(match.group(1))
                tps = float(match.group(2))
                lat_avg = float(match.group(3))
                lat_std = float(match.group(4))
                progress_data.append({
                    "elapsed_sec": elapsed,
                    "tps": tps,
                    "latency_avg_ms": lat_avg,
                    "latency_stddev": lat_std,
                })
                if on_progress:
                    on_progress(elapsed, tps, lat_avg, lat_std)

        self._process.wait()
        finished_at = datetime.now(timezone.utc)

        summary = self._parse_summary("".join(full_output))
        summary["started_at"] = started_at.isoformat()
        summary["finished_at"] = finished_at.isoformat()
        summary["progress_data"] = progress_data

        return {
            "success": self._process.returncode == 0 and not self._cancelled,
            "summary": summary,
            "full_output": "".join(full_output),
        }

    def cancel(self):
        """Cancel a running benchmark."""
        self._cancelled = True
        if self._process:
            self._process.terminate()

    def _build_command(self, params: dict) -> list:
        """Build pgbench command from parameters."""
        cmd = ["pgbench"]

        custom_scripts = params.get("custom_scripts")
        read_weight = params.get("read_weight")
        write_weight = params.get("write_weight")

        if custom_scripts:
            # Custom scenario mode: use -f path@weight
            for entry in custom_scripts:
                cmd.extend(["-f", f"{entry['path']}@{entry['weight']}"])
        elif read_weight is not None and write_weight is not None:
            # Workload mixer mode: use -b with @weight
            if read_weight > 0:
                cmd.extend(["-b", f"select-only@{read_weight}"])
            if write_weight > 0:
                cmd.extend(["-b", f"tpcb-like@{write_weight}"])
        else:
            # Single built-in script mode
            cmd.extend(["-b", params.get("builtin_script", "tpcb-like")])

        cmd.extend([
            "-c", str(params.get("clients", 10)),
            "-j", str(params.get("threads", 2)),
            "-T", str(params.get("duration", 60)),
            "-M", params.get("protocol", "simple"),
            "-P", str(params.get("progress_interval", 5)),
            "-h", self.host,
            "-p", self.port,
            "-U", self.user,
            self.db_name,
        ])
        return cmd

    def _parse_summary(self, output: str) -> dict:
        """Parse pgbench final output for TPS and latency metrics."""
        summary = {}

        patterns = [
            (r"number of transactions actually processed:\s*(\d+)",
             "num_transactions", int),
            (r"number of failed transactions:\s*(\d+)",
             "num_failed", int),
            (r"latency average\s*=\s*([\d.]+)\s*ms",
             "latency_avg_ms", float),
            (r"latency stddev\s*=\s*([\d.]+)\s*ms",
             "latency_stddev_ms", float),
            (r"initial connection time\s*=\s*([\d.]+)\s*ms",
             "initial_conn_time_ms", float),
            (r"tps\s*=\s*([\d.]+)\s*\(without initial connection time\)",
             "tps", float),
            (r"tps\s*=\s*([\d.]+)\s*\(including",
             "tps_including_conn", float),
        ]

        for pattern, key, cast in patterns:
            m = re.search(pattern, output)
            if m:
                summary[key] = cast(m.group(1))

        return summary
