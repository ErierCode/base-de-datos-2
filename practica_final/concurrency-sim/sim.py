"""
Módulo 4 — Concurrencia: ≥100 hilos concurrentes, operaciones mixtas,
registro en tx_lock y disparo intencional de deadlocks en PostgreSQL.
La resolución del interbloqueo la realiza el motor (rollback de un backend);
aquí registramos lock_type DEADLOCK y seguimos con más operaciones.
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import psycopg
from psycopg import errors as pg_errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("concurrency-sim")

DSN = os.environ["DATABASE_URL"].strip()
DB_ID = int(os.environ.get("DB_CONNECTION_ID", "1"))
USERS = int(os.environ.get("SIM_USERS", "120"))
DURATION = float(os.environ.get("SIM_DURATION_SEC", "45"))
DEADLOCK_RATIO = float(os.environ.get("DEADLOCK_STRESS_RATIO", "0.18"))

_log_lock = threading.Lock()


def log_tx(session: str, operacion: str, inicio: datetime, fin: datetime, lock_type: str) -> None:
    wait_ms = max(0, int((fin - inicio).total_seconds() * 1000))
    with _log_lock:
        with psycopg.connect(DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tx_log (db_id, session, operacion, inicio, fin, wait_time, lock_type)
                    VALUES (%s,%s,%s::tx_operation_t,%s,%s,%s,%s::lock_type_t)
                    """,
                    (
                        DB_ID,
                        session,
                        operacion,
                        inicio,
                        fin,
                        wait_ms,
                        lock_type,
                    ),
                )


def do_select(conn: psycopg.Connection, session: str) -> None:
    inicio = datetime.now(timezone.utc)
    rid = random.choice([1, 2])
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM workload.accounts WHERE id = %s", (rid,))
            _ = cur.fetchone()
    fin = datetime.now(timezone.utc)
    log_tx(session, "SELECT", inicio, fin, "SHARED")


def do_update(conn: psycopg.Connection, session: str) -> None:
    inicio = datetime.now(timezone.utc)
    amt = random.randint(-8, 8)
    rid = random.choice([1, 2])
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE workload.accounts SET balance = balance + %s WHERE id = %s RETURNING balance",
                (amt, rid),
            )
            _ = cur.fetchone()
    fin = datetime.now(timezone.utc)
    log_tx(session, "UPDATE", inicio, fin, "EXCLUSIVE")


def do_insert(conn: psycopg.Connection, session: str) -> None:
    inicio = datetime.now(timezone.utc)
    payload = f"evt-{random.randint(1, 10**9)}"
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("INSERT INTO workload.op_queue (payload) VALUES (%s)", (payload,))
    fin = datetime.now(timezone.utc)
    log_tx(session, "INSERT", inicio, fin, "EXCLUSIVE")


def do_delete(conn: psycopg.Connection, session: str) -> None:
    inicio = datetime.now(timezone.utc)
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM workload.op_queue
                WHERE ctid IN (
                    SELECT ctid FROM workload.op_queue
                    ORDER BY id
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                """
            )
    fin = datetime.now(timezone.utc)
    log_tx(session, "DELETE", inicio, fin, "EXCLUSIVE")


def do_deadlock_prone(conn: psycopg.Connection, session: str) -> None:
    inicio = datetime.now(timezone.utc)
    a, b = 1, 2
    if random.random() < 0.5:
        a, b = b, a
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT balance FROM workload.accounts WHERE id = %s FOR UPDATE", (a,))
                _ = cur.fetchone()
                time.sleep(0.02 + random.random() * 0.08)
                cur.execute("SELECT balance FROM workload.accounts WHERE id = %s FOR UPDATE", (b,))
                _ = cur.fetchone()
    except pg_errors.DeadlockDetected:
        fin = datetime.now(timezone.utc)
        log_tx(session, "SELECT", inicio, fin, "DEADLOCK")
        return
    fin = datetime.now(timezone.utc)
    log_tx(session, "SELECT", inicio, fin, "SHARED")


def maybe_timeout(conn: psycopg.Connection, session: str) -> None:
    inicio = datetime.now(timezone.utc)
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET LOCAL statement_timeout = '3ms'")
                cur.execute("SELECT pg_sleep(0.05)")
    except pg_errors.QueryCanceled:
        fin = datetime.now(timezone.utc)
        log_tx(session, "SELECT", inicio, fin, "TIMEOUT")
        return
    fin = datetime.now(timezone.utc)
    log_tx(session, "SELECT", inicio, fin, "SHARED")


def worker(worker_id: int) -> None:
    deadline = time.time() + DURATION
    seq = 0
    while time.time() < deadline:
        seq += 1
        session = f"sim-{worker_id}-{seq}"
        roll = random.random()
        try:
            with psycopg.connect(DSN, connect_timeout=15) as conn:
                conn.autocommit = False
                if roll < DEADLOCK_RATIO:
                    do_deadlock_prone(conn, session)
                elif roll < DEADLOCK_RATIO + 0.025:
                    maybe_timeout(conn, session)
                elif roll < 0.55:
                    do_select(conn, session)
                elif roll < 0.82:
                    do_update(conn, session)
                elif roll < 0.93:
                    do_insert(conn, session)
                else:
                    do_delete(conn, session)
        except psycopg.Error as ex:
            LOG.debug("worker %s sesión %s error: %s", worker_id, session, ex)
        time.sleep(random.random() * 0.03)


def main() -> None:
    continuous = os.environ.get("SIM_CONTINUOUS", "1").strip().lower() in {"1", "true", "yes"}
    LOG.info(
        "Simulación Módulo 4: usuarios=%s duración=%ss deadlock_stress≈%.0f%% continuous=%s",
        USERS,
        DURATION,
        DEADLOCK_RATIO * 100,
        continuous,
    )

    while True:
        with ThreadPoolExecutor(max_workers=min(USERS, 256)) as pool:
            futures = [pool.submit(worker, wid) for wid in range(USERS)]
            for fut in as_completed(futures):
                fut.result()

        with psycopg.connect(DSN, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*), COALESCE(SUM(CASE WHEN lock_type='DEADLOCK'::lock_type_t THEN 1 ELSE 0 END),0)"
                    " FROM tx_log WHERE db_id=%s AND session LIKE 'sim-%%' AND fin > NOW() - INTERVAL '24 hours'",
                    (DB_ID,),
                )
                total, dl = cur.fetchone()
                LOG.info(
                    "Ciclo OK. tx_log (sim, 24h, db_id=%s): ops=%s deadlocks=%s",
                    DB_ID,
                    total,
                    dl,
                )

        if not continuous:
            break
        pause = float(os.environ.get("SIM_CYCLE_PAUSE_SEC", "30"))
        LOG.info("Pausa %ss antes del siguiente ciclo de carga...", pause)
        time.sleep(pause)


if __name__ == "__main__":
    main()
