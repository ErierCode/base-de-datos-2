-- Módulos 6 y 7 — réplica (métricas de lag) + registro Redis hit/miss
-- Ejecutar en la BD de control (dcc_control) si ya existía el volumen:
-- docker exec -i dcc-postgres-control psql -U ... -d dcc_control < init/05-modules6-7.sql

-- Módulo 6 — umbral tipo laboratorio vs pg_stat_replication.replay_lag
CREATE TYPE replication_lag_grade_t AS ENUM ('ACCEPTABLE', 'WARNING', 'CRITICAL');

CREATE TABLE replication_lag_thresholds (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    acceptable_max_sec  DOUBLE PRECISION NOT NULL DEFAULT 2,
    warning_ceiling_sec DOUBLE PRECISION NOT NULL DEFAULT 5,
    critical_min_sec    DOUBLE PRECISION NOT NULL DEFAULT 20
);

INSERT INTO replication_lag_thresholds (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE replication_lag_samples (
    id                 BIGSERIAL PRIMARY KEY,
    lag_seconds        DOUBLE PRECISION NOT NULL,
    grade              replication_lag_grade_t NOT NULL,
    scenario_label     VARCHAR(40),
    primary_replay_lag INTERVAL,
    captured_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    standby_state      TEXT,
    replay_lsn         TEXT,
    flush_lsn          TEXT,
    write_lsn          TEXT,
    sender_host        TEXT
);

CREATE INDEX ix_replication_lag_time ON replication_lag_samples (captured_at DESC);

CREATE OR REPLACE VIEW v_replication_lag_latest AS
SELECT *
FROM (
    SELECT *
    FROM replication_lag_samples
    ORDER BY captured_at DESC
    LIMIT 1
) s;

COMMENT ON TABLE replication_lag_samples IS 'Módulo 6: muestras de lag de streaming desde el primario (pg_stat_replication).';

-- Módulo 7 — eventos Redis (hits/miss) + métricas de latencia
CREATE TYPE cache_event_outcome_t AS ENUM ('HIT', 'MISS');

CREATE TABLE cache_event_log (
    id          BIGSERIAL PRIMARY KEY,
    cache_key TEXT NOT NULL,
    outcome     cache_event_outcome_t NOT NULL,
    latency_ms  NUMERIC(14, 3) NOT NULL,
    detail      TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_cache_event_time ON cache_event_log (created_at DESC);

CREATE OR REPLACE VIEW v_cache_hit_ratio_24h AS
SELECT
    COUNT(*) FILTER (WHERE outcome = 'HIT') AS hits,
    COUNT(*) FILTER (WHERE outcome = 'MISS') AS misses,
    ROUND(
        COUNT(*) FILTER (WHERE outcome = 'HIT')::numeric
        / NULLIF(COUNT(*), 0),
        4
    ) AS hit_ratio,
    ROUND(AVG(latency_ms) FILTER (WHERE outcome = 'HIT'), 3) AS avg_latency_ms_hit,
    ROUND(AVG(latency_ms) FILTER (WHERE outcome = 'MISS'), 3) AS avg_latency_ms_miss
FROM cache_event_log
WHERE created_at > NOW() - INTERVAL '24 hours';
