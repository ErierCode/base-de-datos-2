"""
Módulo 7 — capa Redis de caché con instrumentación hit/miss (cache_event_log)
y vistas agregadas (v_cache_hit_ratio_24h) en la BD de control.
Endpoints adicionales leen último lag de réplica desde la tabla de muestras.
"""
from __future__ import annotations

import json
import os
import time
from decimal import Decimal
from typing import Any

import psycopg
import redis
from fastapi import FastAPI, Query

app = FastAPI(title="DataOps Control Center Gateway", version="0.1")

CONTROL_URL = os.environ["CONTROL_DATABASE_URL"].strip()
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis-cache:6379/0").strip()
CACHE_KEY = os.environ.get("CACHE_SUMMARY_KEY", "dcc:dashboard:summary:v1").strip()
TTL_SEC = int(os.environ.get("CACHE_TTL_SECONDS", "45"))

# Ejercicio práctico: simula coste de cómputo ~400 ms en miss vs ~40 ms en hit tras Redis
MISS_SLEEP_SEC = float(os.environ.get("CACHE_MISS_LATENCY_SEC", "0.4"))
HIT_SLEEP_SEC = float(os.environ.get("CACHE_HIT_LATENCY_SEC", "0.04"))


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def log_cache_event(*, cache_key: str, outcome: str, latency_ms: float, detail: str | None = None) -> None:
    with psycopg.connect(CONTROL_URL, autocommit=True) as cx:
        with cx.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cache_event_log (cache_key, outcome, latency_ms, detail)
                VALUES (%s, %s::cache_event_outcome_t, %s, %s)
                """,
                (cache_key, outcome, latency_ms, detail),
            )


def serialize(obj: dict[str, Any]) -> str:
    def _conv(v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v)
        return v

    return json.dumps({k: _conv(v) for k, v in obj.items()})


def compute_summary_slow() -> dict[str, Any]:
    time.sleep(MISS_SLEEP_SEC)
    out: dict[str, Any] = {}
    with psycopg.connect(CONTROL_URL, autocommit=False) as cx:
        with cx.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::bigint AS samples,
                    COALESCE(AVG(lag_seconds), 0)::float AS avg_lag_recent,
                    MAX(captured_at) AS latest_capture
                FROM replication_lag_samples
                WHERE captured_at > NOW() - INTERVAL '6 hours';
                """
            )
            samples, avg_lag, latest = cur.fetchone()
            out["recent_replication_samples_6h"] = int(samples or 0)
            out["avg_lag_recent_seconds"] = float(avg_lag or 0.0)
            out["latest_sample_at"] = latest.isoformat() if latest else None

            cur.execute("SELECT hits, misses, hit_ratio FROM v_cache_hit_ratio_24h LIMIT 1;")
            ch = cur.fetchone()
            if ch:
                out["cache_hit_ratio_24h"] = {
                    "hits": int(ch[0] or 0),
                    "misses": int(ch[1] or 0),
                    "hit_ratio": float(ch[2] or 0.0),
                }

    out["scenario"] = "computed_from_db"
    return out


@app.get("/api/v1/dashboard/summary")
def dashboard_summary(force_refresh: bool = Query(False, description="true → invalidación lógica (no usa Redis)")):
    rc = redis_client()
    t0 = time.perf_counter()

    if not force_refresh:
        cached = rc.get(CACHE_KEY)
        if cached:
            time.sleep(HIT_SLEEP_SEC)
            ms = (time.perf_counter() - t0) * 1000.0
            body = json.loads(cached)
            log_cache_event(cache_key=CACHE_KEY, outcome="HIT", latency_ms=ms, detail="redis")
            return {"source": "redis", **body}

    body = compute_summary_slow()
    payload_txt = serialize(body)
    rc.setex(CACHE_KEY, TTL_SEC, payload_txt)
    ms = (time.perf_counter() - t0) * 1000.0
    log_cache_event(cache_key=CACHE_KEY, outcome="MISS", latency_ms=ms, detail=f"TTL={TTL_SEC}s")
    return {"source": "database", **body}


@app.post("/api/v1/cache/invalidate")
def invalidate_cache(namespace: str = Query("dashboard", description="Solo marca invalidación Redis")):
    rc = redis_client()
    deleted = rc.delete(CACHE_KEY)
    return {"ok": True, "removed_keys": int(deleted or 0), "namespace": namespace}


@app.get("/api/v1/replication/latest")
def replication_latest():
    with psycopg.connect(CONTROL_URL) as cx:
        with cx.cursor() as cur:
            cur.execute("SELECT lag_seconds::float, grade::text, scenario_label::text, captured_at FROM replication_lag_samples ORDER BY captured_at DESC LIMIT 1")
            row = cur.fetchone()
            if not row:
                return {"ok": False, "detail": "sin muestras aún"}
            lag, grade, scenario, cap = row
            return {"ok": True, "lag_seconds": float(lag), "grade": grade, "scenario": scenario, "captured_at": cap}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
