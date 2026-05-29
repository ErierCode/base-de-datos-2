-- Completar Módulos 3 y 4 según PDF: optimización antes/después + detección/resolución deadlocks

CREATE TABLE IF NOT EXISTS query_optimizations (
    id                  BIGSERIAL PRIMARY KEY,
    query_log_id        BIGINT NOT NULL REFERENCES query_log (id) ON DELETE CASCADE,
    duration_before_ms  NUMERIC(14, 3) NOT NULL,
    duration_after_ms   NUMERIC(14, 3) NOT NULL,
    improvement_pct     NUMERIC(8, 2) GENERATED ALWAYS AS (
        CASE WHEN duration_before_ms > 0
             THEN ROUND(100.0 * (duration_before_ms - duration_after_ms) / duration_before_ms, 2)
             ELSE 0 END
    ) STORED,
    index_applied       TEXT,
    ddl_applied         TEXT,
    execution_plan_before TEXT,
    execution_plan_after  TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_query_opt_log ON query_optimizations (query_log_id);

ALTER TABLE query_log ADD COLUMN IF NOT EXISTS is_optimized BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE query_log ADD COLUMN IF NOT EXISTS optimized_query_text TEXT;

-- Laboratorio reproducible: consulta lenta sin índice → índice → comparativa
CREATE SCHEMA IF NOT EXISTS query_lab;

CREATE TABLE IF NOT EXISTS query_lab.orders (
    id           BIGSERIAL PRIMARY KEY,
    customer_id  INTEGER NOT NULL,
    amount       NUMERIC(12, 2) NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'OPEN',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_query_top_slow AS
SELECT q.id, q.db_id, q.speed_class::text, q.duration_ms, q.rows_returned,
       q.index_used, q.is_optimized, left(q.query_text, 300) AS query_preview,
       q.created_at,
       o.duration_before_ms, o.duration_after_ms, o.improvement_pct, o.index_applied
FROM query_log q
LEFT JOIN LATERAL (
    SELECT duration_before_ms, duration_after_ms, improvement_pct, index_applied
    FROM query_optimizations WHERE query_log_id = q.id ORDER BY id DESC LIMIT 1
) o ON TRUE
WHERE q.speed_class IN ('SLOW', 'CRITICAL')
ORDER BY q.duration_ms DESC, q.created_at DESC;

CREATE TABLE IF NOT EXISTS deadlock_events (
    id                BIGSERIAL PRIMARY KEY,
    db_id             INTEGER REFERENCES connections (id) ON DELETE SET NULL,
    tx_log_id         BIGINT REFERENCES tx_log (id) ON DELETE SET NULL,
    session_id        VARCHAR(128),
    detected_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolution_action TEXT NOT NULL DEFAULT 'POSTGRES_ROLLBACK_VICTIM',
    resolved_at       TIMESTAMPTZ,
    detail            TEXT,
    CONSTRAINT uq_deadlock_tx UNIQUE (tx_log_id)
);

CREATE OR REPLACE VIEW v_concurrency_summary AS
SELECT
    COUNT(*) FILTER (WHERE fin > NOW() - INTERVAL '24 hours') AS ops_24h,
    COUNT(*) FILTER (WHERE lock_type = 'DEADLOCK' AND fin > NOW() - INTERVAL '24 hours') AS deadlocks_24h,
    COUNT(*) FILTER (WHERE lock_type = 'TIMEOUT' AND fin > NOW() - INTERVAL '24 hours') AS timeouts_24h,
    ROUND(AVG(wait_time) FILTER (WHERE fin > NOW() - INTERVAL '24 hours'))::int AS avg_wait_ms_24h
FROM tx_log;

COMMENT ON TABLE query_optimizations IS 'Módulo 3: evidencia comparativa antes/después de optimización indexada.';
COMMENT ON TABLE deadlock_events IS 'Módulo 4: detección automática de deadlocks desde tx_log y resolución del motor.';
