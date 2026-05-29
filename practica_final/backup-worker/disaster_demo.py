#!/usr/bin/env python3
"""
Simulación tipo desastre: DROP TABLE accidental sobre workload.accounts.
Ejecutar: docker compose run --rm backup-worker python disaster_demo.py
"""
from __future__ import annotations

import os
import sys

import psycopg


def main() -> int:
    dsn = os.environ.get("BACKUP_REGISTRY_URL") or os.environ.get("DATABASE_DUMP_URL") or ""
    if not dsn.strip():
        print("Falta BACKUP_REGISTRY_URL o DATABASE_DUMP_URL", file=sys.stderr)
        return 2
    with psycopg.connect(dsn.strip(), autocommit=True) as cx:
        with cx.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS workload.accounts CASCADE;")
    print("OK: tabla workload.accounts eliminada (simulación)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
