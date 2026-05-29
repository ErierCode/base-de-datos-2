-- Módulos 3 y 4 — Slow Query Analyzer + Concurrencia / TX_LOG
-- Requiere PostgreSQL con shared_preload_libraries=pg_stat_statements (ver docker-compose).

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Módulo 3: clasificación obligatoria por duración (ms)
CREATE TYPE query_speed_t AS ENUM ('FAST', 'MEDIUM', 'SLOW', 'CRITICAL');

CREATE TABLE query_log (
    id              BIGSERIAL PRIMARY KEY,
    db_id           INTEGER NOT NULL REFERENCES connections (id) ON DELETE CASCADE,
    query_text      TEXT NOT NULL,
    duration_ms     NUMERIC(14, 3) NOT NULL,
    rows_returned   BIGINT,
    index_used      TEXT,
    execution_plan  TEXT,
    source_queryid  BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    speed_class     query_speed_t GENERATED ALWAYS AS (
        CASE
            WHEN duration_ms < 100 THEN 'FAST'::query_speed_t
            WHEN duration_ms < 500 THEN 'MEDIUM'::query_speed_t
            WHEN duration_ms < 2000 THEN 'SLOW'::query_speed_t
            ELSE 'CRITICAL'::query_speed_t
        END
    ) STORED
);

CREATE INDEX ix_query_log_db_time ON query_log (db_id, created_at DESC);
CREATE INDEX ix_query_log_speed ON query_log (speed_class, created_at DESC);

COMMENT ON TABLE query_log IS 'Módulo 3: consultas muestreadas (p. ej. desde pg_stat_statements + EXPLAIN).';
COMMENT ON COLUMN query_log.duration_ms IS 'Tiempo medio o medido de ejecución en ms (según origen del muestreo).';

-- Módulo 4: registro de transacciones / contención
CREATE TYPE tx_operation_t AS ENUM ('INSERT', 'UPDATE', 'DELETE', 'SELECT');
CREATE TYPE lock_type_t AS ENUM ('SHARED', 'EXCLUSIVE', 'DEADLOCK', 'TIMEOUT');

CREATE TABLE tx_log (
    id          BIGSERIAL PRIMARY KEY,
    db_id       INTEGER NOT NULL REFERENCES connections (id) ON DELETE CASCADE,
    session     VARCHAR(128) NOT NULL,
    operacion   tx_operation_t NOT NULL,
    inicio      TIMESTAMPTZ NOT NULL,
    fin         TIMESTAMPTZ NOT NULL,
    wait_time   INTEGER NOT NULL CHECK (wait_time >= 0),
    lock_type   lock_type_t NOT NULL,
    CONSTRAINT ck_tx_log_fin_ge_inicio CHECK (fin >= inicio)
);

CREATE INDEX ix_tx_log_db_fin ON tx_log (db_id, fin DESC);
CREATE INDEX ix_tx_log_lock ON tx_log (lock_type);

COMMENT ON COLUMN tx_log.wait_time IS 'Latencia total de la operación (incluye espera por bloqueos y post-abort en deadlocks), ms.';

-- Tablas de carga para demostrar concurrencia y deadlocks (misma BD de control)
CREATE SCHEMA IF NOT EXISTS workload;

CREATE TABLE workload.accounts (
    id          INTEGER PRIMARY KEY,
    balance     NUMERIC(14, 2) NOT NULL DEFAULT 0,
    label       TEXT
);

CREATE TABLE workload.op_queue (
    id BIGSERIAL PRIMARY KEY,
    payload TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO workload.accounts (id, balance, label) VALUES
    (1, 10000.00, 'cuenta-a'),
    (2, 10000.00, 'cuenta-b')
ON CONFLICT (id) DO NOTHING;

CREATE OR REPLACE VIEW v_slow_queries_recent AS
SELECT id, db_id, speed_class, duration_ms, rows_returned, index_used,
       left(query_text, 200) AS query_preview, created_at
FROM query_log
WHERE speed_class IN ('SLOW', 'CRITICAL')
ORDER BY created_at DESC;

CREATE OR REPLACE VIEW v_tx_deadlocks AS
SELECT * FROM tx_log WHERE lock_type = 'DEADLOCK' ORDER BY fin DESC;
