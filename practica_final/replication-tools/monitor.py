"""
Módulo 6 — muestrear lag streaming en el primario (pg_stat_replication)
y persistir en la BD de control con clasificación ACCEPTABLE / WARNING / CRITICAL.
"""
from __future__ import annotations

import logging
import os
import time

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("replication-monitor")

CONTROL_URL = os.environ["CONTROL_DATABASE_URL"].strip()
PRIMARY_URL = os.environ["PRIMARY_PG_URL"].strip()
POLL_SEC = float(os.environ.get("REPLICATION_POLL_SECONDS", "5"))


def read_thresholds(cur_ctl: psycopg.Cursor) -> tuple[float, float, float]:
    cur_ctl.execute(
        """
        SELECT acceptable_max_sec, warning_ceiling_sec, critical_min_sec
        FROM replication_lag_thresholds WHERE id = 1
        """
    )
    row = cur_ctl.fetchone()
    if row:
        return float(row[0]), float(row[1]), float(row[2])
    return 2.0, 19.999, 20.0


def classify(lag_sec: float, acceptable_max: float, crit_min: float) -> str:
    """Alineado al enunciado: ≤2 Aceptable, >2 y <20 Advertencia típica, ≥20 Crítico."""
    if lag_sec <= acceptable_max:
        return "ACCEPTABLE"
    if lag_sec >= crit_min:
        return "CRITICAL"
    return "WARNING"


def latest_scenario(cur_pri: psycopg.Cursor) -> str | None:
    try:
        cur_pri.execute(
            """
            SELECT scenario::text FROM ha_stress.events
            ORDER BY id DESC LIMIT 1
            """
        )
        row = cur_pri.fetchone()
        return str(row[0]) if row else None
    except psycopg.Error:
        return None


def sample_primary(conn_pri: psycopg.Connection) -> dict[str, object | None]:
    with conn_pri.cursor() as cur:
        cur.execute(
            """
            SELECT
                state::text AS st,
                write_lsn::text,
                flush_lsn::text,
                replay_lsn::text,
                COALESCE(split_part(client_addr::text, '/', 1), 'unknown') AS host_txt,
                COALESCE(EXTRACT(EPOCH FROM replay_lag)::float, 0.0) AS replay_lag_s
            FROM pg_stat_replication
            ORDER BY replay_lag DESC NULLS LAST
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return {
                "lag_s": 0.0,
                "replay": None,
                "flush": None,
                "write": None,
                "state": "no_standby",
                "host": None,
            }
        state, wl, fl, rl, host, lag = row
        return {
            "lag_s": float(lag or 0.0),
            "replay": rl,
            "flush": fl,
            "write": wl,
            "state": state,
            "host": host,
        }


def persist_sample(
    *,
    lag_s: float,
    grade: str,
    scenario: str | None,
    meta: dict[str, object | None],
) -> None:
    with psycopg.connect(CONTROL_URL, autocommit=True) as ctl:
        with ctl.cursor() as cur:
            cur.execute(
                """
                INSERT INTO replication_lag_samples (
                    lag_seconds, grade, scenario_label,
                    primary_replay_lag, standby_state,
                    replay_lsn, flush_lsn, write_lsn, sender_host
                )
                VALUES (
                    %s, %s::replication_lag_grade_t, %s,
                    ((%s)::double precision * interval '1 second'),
                    %s::text,
                    %s::text,
                    %s::text,
                    %s::text,
                    %s::text
                )
                """,
                (
                    lag_s,
                    grade,
                    scenario,
                    lag_s,
                    meta.get("state"),
                    meta.get("replay"),
                    meta.get("flush"),
                    meta.get("write"),
                    meta.get("host"),
                ),
            )


def main() -> None:
    LOG.info("Monitor de lag; control=%s primary=%s", CONTROL_URL.split("@")[1:], PRIMARY_URL.split("@")[1:])
    while True:
        started = time.time()
        try:
            with psycopg.connect(CONTROL_URL) as conn_ctl:
                with conn_ctl.cursor() as cur_ctl:
                    acceptable_max, _warn_ceiling, critical_min = read_thresholds(cur_ctl)

            with psycopg.connect(PRIMARY_URL, autocommit=True) as conn_pri:
                with conn_pri.cursor() as cur_pri:
                    scenario = latest_scenario(cur_pri)
                meta = sample_primary(conn_pri)

            lag = float(meta["lag_s"])  # type: ignore[arg-type]
            grade = classify(lag, acceptable_max, critical_min)
            persist_sample(lag_s=lag, grade=grade, scenario=scenario, meta=meta)
            LOG.info(
                "lag=%.3fs grade=%s scenario=%s standby_state=%s",
                lag,
                grade,
                scenario,
                meta.get("state"),
            )
        except Exception as ex:
            LOG.warning("Ciclo monitor fallido: %s", ex)

        elapsed = time.time() - started
        sleep_for = max(0.25, POLL_SEC - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
