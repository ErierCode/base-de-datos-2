"""
DataOps Control Center — Módulo 2
Job cada POLL_SECONDS (por defecto 60): lee conexiones ACTIVE,
muestrea métricas en PostgreSQL de destino y escribe db_metrics + health_grade.
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("health-worker")

CONTROL_URL = os.environ["CONTROL_DATABASE_URL"].strip()
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "60"))
# Solo desarrollo: password_ciphertext = UTF-8 sin cifrar, password_algo = UTF8_PLAIN_DEV
PLAIN_DEV_ALGO = "UTF8_PLAIN_DEV"
AES_GCM_ALGO = "AES-GCM-v1"
# Alias guardado en BD por defecto (init) o registros antiguos
AES_GCM_ALIASES = frozenset({AES_GCM_ALGO.upper(), "APP-MANAGED"})
_CRED_KEY: bytes | None = None


def is_aes_gcm_algo(algo: str) -> bool:
    return algo.strip().upper() in AES_GCM_ALIASES


def _credential_key() -> bytes:
    global _CRED_KEY
    if _CRED_KEY is not None:
        return _CRED_KEY
    b64 = os.environ.get("CREDENTIAL_ENCRYPTION_KEY_BASE64", "").strip()
    if b64:
        _CRED_KEY = bytes.fromhex(b64) if len(b64) == 64 and all(c in "0123456789abcdef" for c in b64.lower()) else __import__("base64").b64decode(b64)
    else:
        seed = os.environ.get("JWT_KEY", "dcc-jwt-dev-key-change-in-production-min-32-chars!!")
        _CRED_KEY = hashlib.sha256(seed.encode("utf-8")).digest()
    return _CRED_KEY


@dataclass
class Thresholds:
    cpu_warning_pct: float
    cpu_critical_pct: float
    memory_warning_pct: float
    memory_critical_pct: float
    conn_warning_pct: float
    conn_critical_pct: float
    locks_warning: int
    locks_critical: int
    deadlocks_warning: int
    deadlocks_critical: int


def load_thresholds(cur: psycopg.Cursor) -> Thresholds:
    cur.execute(
        """
        SELECT cpu_warning_pct, cpu_critical_pct, memory_warning_pct, memory_critical_pct,
               conn_warning_pct, conn_critical_pct, locks_warning, locks_critical,
               deadlocks_warning, deadlocks_critical
        FROM health_thresholds WHERE nombre = 'global' LIMIT 1
        """
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Falta fila global en health_thresholds")
    return Thresholds(
        float(row[0]),
        float(row[1]),
        float(row[2]),
        float(row[3]),
        float(row[4]),
        float(row[5]),
        int(row[6]),
        int(row[7]),
        int(row[8]),
        int(row[9]),
    )


def password_from_row(algo: str, ciphertext: memoryview | bytes | None) -> str | None:
    if ciphertext is None:
        return None
    raw = bytes(ciphertext)
    if algo.upper() == PLAIN_DEV_ALGO:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            LOG.warning("Contraseña UTF8_PLAIN_DEV inválida (no UTF-8)")
            return None
    if is_aes_gcm_algo(algo):
        try:
            if len(raw) < 28:
                return None
            nonce, tag, cipher = raw[:12], raw[12:28], raw[28:]
            plain = AESGCM(_credential_key()).decrypt(nonce, cipher + tag, None)
            return plain.decode("utf-8")
        except Exception as ex:
            LOG.warning("No se pudo descifrar AES-GCM-v1: %s", ex)
            return None
    LOG.warning("Omitiendo conexión id: algoritmo %s no soportado", algo)
    return None


def build_conninfo(host: str, port: int, db: str, user: str, password: str) -> str:
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db)}"
    )


def classify(
    thresholds: Thresholds,
    cpu_pct: float,
    memory_pct: float,
    conn_pressure_pct: float,
    locks: int,
    deadlocks_delta: int,
) -> str:
    tiers: list[int] = []

    def add(metric: float, w: float, c: float) -> None:
        if metric >= c:
            tiers.append(3)
        elif metric >= w:
            tiers.append(2)

    add(cpu_pct, thresholds.cpu_warning_pct, thresholds.cpu_critical_pct)
    add(memory_pct, thresholds.memory_warning_pct, thresholds.memory_critical_pct)
    add(conn_pressure_pct, thresholds.conn_warning_pct, thresholds.conn_critical_pct)
    add(float(locks), float(thresholds.locks_warning), float(thresholds.locks_critical))
    add(float(deadlocks_delta), float(thresholds.deadlocks_warning), float(thresholds.deadlocks_critical))
    if 3 in tiers:
        return "CRITICAL"
    if 2 in tiers:
        return "WARNING"
    return "HEALTHY"


def sample_postgres_targets(conninfo: str) -> tuple[dict[str, Any], str | None]:
    """
    Métricas heurísticas coherentes con comentarios en db_metrics del SQL.
    """
    try:
        with psycopg.connect(conninfo, connect_timeout=8) as tconn:
            tconn.autocommit = True
            with tconn.cursor() as tc:
                tc.execute(
                    """
                    SELECT
                        d.blks_hit,
                        d.blks_read,
                        d.numbackends,
                        d.deadlocks,
                        pg_database_size(d.datname) AS dsize
                    FROM pg_stat_database d
                    WHERE d.datname = current_database()
                    """
                )
                row = tc.fetchone()
                if not row:
                    return {}, "pg_stat_database vacío para esta base"
                blks_hit = int(row[0] or 0)
                blks_read = int(row[1] or 0)
                deadlocks_cum = int(row[3] or 0)
                disk_bytes = int(row[4] or 0)

                tc.execute("SELECT setting::int FROM pg_settings WHERE name = %s", ("max_connections",))
                max_conn = int((tc.fetchone() or (100,))[0])
                tc.execute(
                    """
                    SELECT count(*)::int FROM pg_stat_activity
                    WHERE datname = current_database()
                    """
                )
                conn_count = int((tc.fetchone() or (0,))[0])
                tc.execute(
                    """
                    SELECT count(*)::int FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND state ILIKE 'idle in transaction%'
                    """
                )
                idle_tx = int((tc.fetchone() or (0,))[0])
                tc.execute(
                    """
                    SELECT count(*)::int
                    FROM pg_locks k
                    JOIN pg_database d ON k.database = d.oid
                    WHERE d.datname = current_database()
                    """
                )
                lock_count = int((tc.fetchone() or (0,))[0])

        denom = blks_hit + blks_read
        cpu_pct = round(100.0 - (100.0 * blks_hit / denom), 2) if denom > 0 else 0.0
        cpu_pct = max(0.0, min(100.0, cpu_pct))
        mem_pct = round(100.0 * idle_tx / max_conn, 2) if max_conn > 0 else 0.0
        mem_pct = max(0.0, min(100.0, mem_pct))
        conn_pressure = round(100.0 * conn_count / max_conn, 2) if max_conn > 0 else 0.0
        conn_pressure = max(0.0, min(100.0, conn_pressure))

        disk_mb = round(disk_bytes / (1024.0 * 1024.0), 2)

        return {
            "cpu_pct": cpu_pct,
            "memory_pct": mem_pct,
            "connections": conn_count,
            "locks": lock_count,
            "deadlocks_cumulative": deadlocks_cum,
            "disk_usage_mb": disk_mb,
            "conn_pressure_pct": conn_pressure,
        }, None
    except Exception as ex:
        return {}, f"{type(ex).__name__}: {ex}"


_last_deadlocks: dict[int, int] = {}


def deadlocks_delta(db_id: int, cumulative: int) -> int:
    prev = _last_deadlocks.get(db_id)
    _last_deadlocks[db_id] = cumulative
    if prev is None:
        return 0
    if cumulative < prev:
        return cumulative
    return cumulative - prev


def insert_metric(
    cur: psycopg.Cursor,
    db_id: int,
    grade: str,
    payload: dict[str, Any],
    error: str | None,
) -> None:
    cur.execute(
        """
        INSERT INTO db_metrics (
            db_id, cpu_pct, memory_pct, connections, locks, deadlocks,
            disk_usage_mb, health_grade, collect_error
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s::health_grade_t, %s
        )
        """,
        (
            db_id,
            payload.get("cpu_pct", 0),
            payload.get("memory_pct", 0),
            int(payload.get("connections", 0)),
            int(payload.get("locks", 0)),
            int(payload.get("deadlocks", 0)),
            float(payload.get("disk_usage_mb", 0)),
            grade,
            error,
        ),
    )


def run_cycle() -> None:
    with psycopg.connect(CONTROL_URL) as ctrl:
        ctrl.autocommit = True
        with ctrl.cursor() as cur:
            th = load_thresholds(cur)

            cur.execute(
                """
                SELECT id, motor::text, host, port, database_name, user_name,
                       password_ciphertext, password_algo, status::text
                FROM connections WHERE status::text IN ('ACTIVE')
                ORDER BY id
                """
            )
            rows = cur.fetchall()

        success_ids: list[int] = []
        failed_ids: list[int] = []

        with ctrl.cursor() as cur:
            for (
                cid,
                motor,
                host,
                port,
                dbname,
                user_name,
                pw_cipher,
                pw_algo,
                status,
            ) in rows:
                _ = status
                if motor != "POSTGRESQL":
                    insert_metric(
                        cur,
                        int(cid),
                        "CRITICAL",
                        {},
                        f"Motor {motor}: colector no implementado en esta versión",
                    )
                    continue

                pwd = password_from_row(str(pw_algo), pw_cipher)
                if pwd is None:
                    insert_metric(
                        cur,
                        int(cid),
                        "CRITICAL",
                        {},
                        f"Sin credencial usable (password_algo debe ser {PLAIN_DEV_ALGO} en dev)",
                    )
                    failed_ids.append(int(cid))
                    continue

                conninfo = build_conninfo(host, int(port), dbname, user_name, pwd)
                sample, err = sample_postgres_targets(conninfo)
                if err:
                    insert_metric(cur, int(cid), "CRITICAL", {}, err)
                    failed_ids.append(int(cid))
                    continue

                dlt = deadlocks_delta(int(cid), int(sample["deadlocks_cumulative"]))
                sample_clean = dict(sample)
                sample_clean.pop("deadlocks_cumulative", None)
                sample_clean["deadlocks"] = dlt

                grade = classify(
                    th,
                    float(sample_clean["cpu_pct"]),
                    float(sample_clean["memory_pct"]),
                    float(sample["conn_pressure_pct"]),
                    int(sample_clean["locks"]),
                    int(sample_clean["deadlocks"]),
                )
                insert_metric(cur, int(cid), grade, sample_clean, None)
                success_ids.append(int(cid))
                LOG.info(
                    "id=%s %s métricas ok grade=%s cpu=%s mem=%s conns=%s locks=%s deadlocksΔ=%s",
                    cid,
                    dbname,
                    grade,
                    sample_clean["cpu_pct"],
                    sample_clean["memory_pct"],
                    sample_clean["connections"],
                    sample_clean["locks"],
                    sample_clean["deadlocks"],
                )

        with ctrl.cursor() as cur:
            if success_ids:
                cur.execute(
                    "UPDATE connections SET status = 'ACTIVE'::connection_status_t WHERE id = ANY(%s)",
                    (success_ids,),
                )
            if failed_ids:
                cur.execute(
                    "UPDATE connections SET status = 'ERROR'::connection_status_t WHERE id = ANY(%s)",
                    (failed_ids,),
                )
                LOG.warning("Marcadas ERROR conexiones: %s", failed_ids)


def main() -> None:
    LOG.info("Control DB: inicializando job cada %ss", POLL_SECONDS)
    run_cycle()
    sched = BlockingScheduler()
    sched.add_job(run_cycle, "interval", seconds=POLL_SECONDS, id="dcc_health_cycle")
    sched.start()


if __name__ == "__main__":
    main()
