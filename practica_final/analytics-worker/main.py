"""
Módulo 3 — Slow Query Analyzer
Muestrea pg_stat_statements en cada conexión ACTIVE (PostgreSQL),
inserta en query_log con duration_ms (media en ms) y opcionalmente EXPLAIN (FORMAT JSON).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any
from urllib.parse import quote_plus

import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from apscheduler.schedulers.blocking import BlockingScheduler
from psycopg import errors as pg_errors

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("analytics-worker")

CONTROL_URL = os.environ["CONTROL_DATABASE_URL"].strip()
POLL_SECONDS = int(os.environ.get("QUERY_POLL_SECONDS", "120"))
TOP_N = int(os.environ.get("QUERY_TOP_N", "40"))
EXPLAIN_SAMPLES = max(0, int(os.environ.get("EXPLAIN_SAMPLES", "5")))
MIN_MEAN_MS = float(os.environ.get("MIN_MEAN_MS", "0"))
PLAIN_DEV_ALGO = "UTF8_PLAIN_DEV"
AES_GCM_ALGO = "AES-GCM-v1"
AES_GCM_ALIASES = frozenset({AES_GCM_ALGO.upper(), "APP-MANAGED"})


def is_aes_gcm_algo(algo: str) -> bool:
    return algo.strip().upper() in AES_GCM_ALIASES


def _credential_key() -> bytes:
    b64 = os.environ.get("CREDENTIAL_ENCRYPTION_KEY_BASE64", "").strip()
    if b64:
        import base64

        return base64.b64decode(b64)
    seed = os.environ.get("JWT_KEY", "dcc-jwt-dev-key-change-in-production-min-32-chars!!")
    return hashlib.sha256(seed.encode("utf-8")).digest()


def password_from_row(algo: str, ciphertext: memoryview | bytes | None) -> str | None:
    if ciphertext is None:
        return None
    raw = bytes(ciphertext)
    if algo.upper() == PLAIN_DEV_ALGO:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if is_aes_gcm_algo(algo):
        try:
            if len(raw) < 28:
                return None
            nonce, tag, cipher = raw[:12], raw[12:28], raw[28:]
            plain = AESGCM(_credential_key()).decrypt(nonce, cipher + tag, None)
            return plain.decode("utf-8")
        except Exception as ex:
            LOG.warning("AES-GCM-v1 falló: %s", ex)
            return None
    LOG.warning("analytics: algoritmo %s no soportado", algo)
    return None


_FORBIDDEN_HINT = re.compile(
    r"\b(EXECUTE|COMMIT|BEGIN|ROLLBACK|LISTEN|COPY|VACUUM|ALTER|DROP)\b",
    re.IGNORECASE,
)


def build_conninfo(host: str, port: int, db: str, user: str, password: str) -> str:
    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(db)}"
    )


def first_index_name(plan_node: dict[str, Any]) -> str | None:
    if not plan_node:
        return None
    if "Index Name" in plan_node and plan_node["Index Name"]:
        return str(plan_node["Index Name"])
    for key in ("Plans", "InitPlan", "SubPlans"):
        child = plan_node.get(key)
        if isinstance(child, list):
            for c in child:
                if isinstance(c, dict):
                    r = first_index_name(c)
                    if r:
                        return r
        elif isinstance(child, dict):
            r = first_index_name(child)
            if r:
                return r
    return None


def plan_to_index_and_text(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    try:
        root = json.loads(raw)
        blob = root[0] if isinstance(root, list) else root
        plan = blob.get("Plan")
        if isinstance(plan, dict):
            return first_index_name(plan), raw
        return None, raw
    except json.JSONDecodeError:
        return None, raw


def safe_explain(cur: psycopg.Cursor, sql_text: str) -> tuple[str | None, str | None]:
    q = (sql_text or "").strip()
    if not q or len(q) > 12_000:
        return None, None
    # EXPLAIN necesita valores concretos; las consultas normalizadas con $1.. fallan sin bind.
    if re.search(r"\$\d+", q):
        return None, None
    tok = q.lstrip().split(None, 1)
    first = tok[0].upper() if tok else ""
    if first not in ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE"):
        return None, None
    if _FORBIDDEN_HINT.search(q):
        return None, None
    try:
        cur.execute(f"EXPLAIN (FORMAT JSON) {q}")  # noqa: S608 trusted source from pg_stat_statements
        row = cur.fetchone()
        if not row:
            return None, None
        text = row[0]
        idx, plan_txt = plan_to_index_and_text(text if isinstance(text, str) else str(text))
        return idx, plan_txt
    except (pg_errors.UndefinedTable, pg_errors.SyntaxError, pg_errors.PostgresError):
        return None, None


def ensure_extension(conn: psycopg.Connection) -> bool:
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
        conn.autocommit = False
        return True
    except pg_errors.InsufficientPrivilege as ex:
        LOG.warning("pg_stat_statements no disponible: %s", ex)
        conn.autocommit = False
        return False


def ingest_for_target(control_cur: psycopg.Cursor, db_id: int, conninfo: str) -> int:
    inserted = 0
    explain_budget = EXPLAIN_SAMPLES
    candidates: list[tuple[Any, ...]] = []
    try:
        with psycopg.connect(conninfo, connect_timeout=10) as tconn:
            if not ensure_extension(tconn):
                return 0
            tconn.autocommit = True
            with tconn.cursor() as tc:
                tc.execute(
                    """
                    SELECT queryid::bigint, query::text, calls::bigint,
                           rows::bigint, mean_exec_time::double precision,
                           total_exec_time::double precision
                    FROM pg_stat_statements
                    WHERE dbid = (
                        SELECT oid FROM pg_database WHERE datname = current_database()
                    )
                      AND userid = (SELECT oid FROM pg_roles WHERE rolname = CURRENT_USER)
                      AND mean_exec_time >= %s
                      AND LENGTH(query::text) < 8192
                      AND (
                          query ILIKE 'SELECT %%' OR query ILIKE 'WITH %%'
                          OR query ILIKE 'INSERT %%'
                          OR query ILIKE 'UPDATE %%'
                          OR query ILIKE 'DELETE %%'
                      )
                      AND query NOT ILIKE '%%pg_stat_statements%%'
                      AND query NOT ILIKE '%%EXPLAIN (FORMAT JSON)%%'
                      AND query NOT ILIKE '%%CREATE EXTENSION %%'
                      AND query NOT ILIKE '%%CREATE TABLE %%'
                    ORDER BY mean_exec_time DESC
                    LIMIT %s
                    """,
                    (MIN_MEAN_MS, TOP_N),
                )
                candidates = tc.fetchall()
    except Exception as ex:
        LOG.error("analytics db_id=%s conexión: %s", db_id, ex)
        return 0

    for row in candidates:
        qid, qtext, calls, total_rows, mean_ms, _total_ms = row
        calls = int(calls or 0)
        total_rows = int(total_rows or 0)
        mean_ms_f = float(mean_ms or 0.0)
        rows_hint = None
        if calls > 0:
            rows_hint = int(round(total_rows / float(calls)))

        idx_used = None
        explain_txt = None
        if explain_budget > 0:
            try:
                with psycopg.connect(conninfo, connect_timeout=10) as econn:
                    econn.autocommit = True
                    with econn.cursor() as ec:
                        idx_used, explain_txt = safe_explain(ec, qtext)
            except Exception as ex:
                LOG.debug("EXPLAIN omitido para queryid=%s: %s", qid, ex)
            explain_budget -= 1

        plan_str = explain_txt[:200_000] if explain_txt is not None and len(explain_txt) > 200_000 else explain_txt
        control_cur.execute(
            """
            INSERT INTO query_log (
                db_id, query_text, duration_ms, rows_returned,
                index_used, execution_plan, source_queryid
            ) VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                db_id,
                qtext[:50_000],
                round(mean_ms_f, 3),
                rows_hint,
                idx_used,
                plan_str,
                int(qid) if qid is not None else None,
            ),
        )
        inserted += 1

    return inserted


def run_cycle() -> None:
    with psycopg.connect(CONTROL_URL) as ctrl:
        ctrl.autocommit = True
        with ctrl.cursor() as cur:
            cur.execute(
                """
                SELECT id, motor::text, host, port, database_name,
                       user_name, password_ciphertext, password_algo, status::text
                FROM connections
                WHERE status::text IN ('ACTIVE') AND motor::text IN ('POSTGRESQL')
                ORDER BY id
                """
            )
            rows = cur.fetchall()

        total_inserted = 0
        with ctrl.cursor() as cur:
            for cid, motor, host, port, dbname, user_name, pw_cipher, pw_algo, _status in rows:
                _ = motor
                pwd = password_from_row(str(pw_algo), pw_cipher)
                if pwd is None:
                    continue
                conninfo = build_conninfo(host, int(port), dbname, user_name, pwd)
                n = ingest_for_target(cur, int(cid), conninfo)
                total_inserted += n
                if n:
                    LOG.info("db_id=%s insertados %s registros en query_log", cid, n)
        if total_inserted == 0:
            LOG.info("analytics: sin filas nuevas (sin stats o sin conexiones ACTIVE)")


def main() -> None:
    LOG.info("analytics-worker: primer ciclo y luego cada %ss", POLL_SECONDS)
    run_cycle()
    sched = BlockingScheduler()
    sched.add_job(run_cycle, "interval", seconds=POLL_SECONDS, id="dcc_query_cycle")
    sched.start()


if __name__ == "__main__":
    main()
