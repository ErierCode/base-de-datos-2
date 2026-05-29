"""
Generador de carga WAL contra el HA primario.
Rota NORMAL / MEDIUM / HIGH para mover el lag de replay hacia zonas típicas (2s / 5s / 20s).
"""
from __future__ import annotations

import logging
import os
import random
import string
import time

import psycopg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
LOG = logging.getLogger("replication-load")

PRIMARY_URL = os.environ["PRIMARY_PG_URL"].strip()
SCENARIO_HOLD_SEC = float(os.environ.get("SCENARIO_HOLD_SEC", "120"))


def rand_payload(n: int = 4096) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def burst(conn: psycopg.Connection, scenario: str, batch_rows: int) -> None:
    payload = rand_payload()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO ha_stress.events(scenario,payload) SELECT %s, %s FROM generate_series(1,%s)",
            (scenario, payload, batch_rows),
        )
    conn.commit()


def workload_for(scenario: str) -> tuple[int, int]:
    mapping = {
        # rounds, rows_per_round
        "NORMAL": (1, 200),
        "MEDIUM": (3, 2000),
        "HIGH": (8, 4000),
    }
    return mapping.get(scenario, (1, 200))


def main() -> None:
    sequence = os.environ.get("SCENARIO_SEQUENCE", "NORMAL,MEDIUM,HIGH,MEDIUM,NORMAL,HIGH").split(",")
    sequence = [s.strip().upper() for s in sequence if s.strip()]
    if not sequence:
        sequence = ["NORMAL", "MEDIUM", "HIGH"]

    idx = 0
    LOG.info(
        "Carga WAL activa contra %s. Secuencia=%s ciclo cada %ss",
        PRIMARY_URL.split("@")[1:],
        sequence,
        SCENARIO_HOLD_SEC,
    )
    try:
        with psycopg.connect(PRIMARY_URL, connect_timeout=20) as conn:
            conn.autocommit = False
            tick = time.time()
            while True:
                scenario = sequence[idx % len(sequence)]
                idx += 1
                rounds, batch = workload_for(scenario)
                burst_start = time.time()
                for _ in range(rounds):
                    burst(conn, scenario, batch)
                LOG.info(
                    "Escenario=%s bursts=%sx rows_each=%s en %.3fs",
                    scenario,
                    rounds,
                    batch,
                    time.time() - burst_start,
                )
                # Mantener etiqueta estable durante ventana grande
                elapsed = time.time() - tick
                sleep_remain = SCENARIO_HOLD_SEC - elapsed if SCENARIO_HOLD_SEC > 0 else 0
                tick = time.time()
                if sleep_remain > 0:
                    time.sleep(sleep_remain)
    except KeyboardInterrupt:
        LOG.info("Interrumpido por usuario.")


if __name__ == "__main__":
    main()
