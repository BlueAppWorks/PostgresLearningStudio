#!/usr/bin/env python3
"""Container health check — replaces curl to eliminate the curl package dependency."""

import sys
import urllib.request

try:
    urllib.request.urlopen("http://localhost:8080/health", timeout=5)
except Exception:
    sys.exit(1)
