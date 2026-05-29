-- Módulo 2 — Health check automático, métricas y umbrales configurables.
-- Si tu BD ya existía antes de este archivo: ejecutalo manualmente con psql o copia estos CREATE.

CREATE TYPE health_grade_t AS ENUM ('HEALTHY', 'WARNING', 'CRITICAL');

-- Umbrales globales (el dashboard clasifica HEALTHY/WARNING/CRITICAL con peor resultado por métrica).
CREATE TABLE health_thresholds (
    id SMALLSERIAL PRIMARY KEY,
    nombre              VARCHAR(100) NOT NULL DEFAULT 'global',
    cpu_warning_pct     NUMERIC(5, 2) NOT NULL DEFAULT 70.00 CHECK (cpu_warning_pct BETWEEN 0 AND 100),
    cpu_critical_pct    NUMERIC(5, 2) NOT NULL DEFAULT 85.00 CHECK (cpu_critical_pct BETWEEN 0 AND 100),
    memory_warning_pct  NUMERIC(5, 2) NOT NULL DEFAULT 70.00 CHECK (memory_warning_pct BETWEEN 0 AND 100),
    memory_critical_pct NUMERIC(5, 2) NOT NULL DEFAULT 85.00 CHECK (memory_critical_pct BETWEEN 0 AND 100),
    conn_warning_pct    NUMERIC(5, 2) NOT NULL DEFAULT 60.00 CHECK (conn_warning_pct BETWEEN 0 AND 100),
    conn_critical_pct   NUMERIC(5, 2) NOT NULL DEFAULT 80.00 CHECK (conn_critical_pct BETWEEN 0 AND 100),
    locks_warning       INTEGER NOT NULL DEFAULT 80 CHECK (locks_warning >= 0),
    locks_critical      INTEGER NOT NULL DEFAULT 250 CHECK (locks_critical >= locks_warning),
    deadlocks_warning   INTEGER NOT NULL DEFAULT 1 CHECK (deadlocks_warning >= 0),
    deadlocks_critical  INTEGER NOT NULL DEFAULT 3 CHECK (deadlocks_critical >= deadlocks_warning),
    CONSTRAINT uq_health_thresholds_nombre UNIQUE (nombre),
    CONSTRAINT ck_cpu_critical_ge_warning CHECK (cpu_critical_pct >= cpu_warning_pct),
    CONSTRAINT ck_memory_critical_ge_warning CHECK (memory_critical_pct >= memory_warning_pct),
    CONSTRAINT ck_conn_critical_ge_warning CHECK (conn_critical_pct >= conn_warning_pct)
);

INSERT INTO health_thresholds (nombre) VALUES ('global')
ON CONFLICT (nombre) DO NOTHING;

CREATE TABLE db_metrics (
    id              BIGSERIAL PRIMARY KEY,
    db_id           INTEGER NOT NULL REFERENCES connections (id) ON DELETE CASCADE,
    cpu_pct         NUMERIC(5, 2) NOT NULL,
    memory_pct      NUMERIC(5, 2) NOT NULL,
    connections     INTEGER NOT NULL DEFAULT 0,
    locks           INTEGER NOT NULL DEFAULT 0,
    deadlocks       INTEGER NOT NULL DEFAULT 0,
    disk_usage_mb   NUMERIC(14, 2) NOT NULL DEFAULT 0,
    health_grade    health_grade_t NOT NULL,
    capture_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    collect_error   TEXT
);

CREATE INDEX ix_db_metrics_db_capture ON db_metrics (db_id, capture_time DESC);
CREATE INDEX ix_db_metrics_health ON db_metrics (health_grade);

COMMENT ON TABLE db_metrics IS 'Serie temporal de métricas (Módulo 2). cpu/memory son heurísticas para PostgreSQL.';
COMMENT ON COLUMN db_metrics.cpu_pct IS 'Proxy de presión I/O: % de buffer miss (100 - hit ratio), acotado 0-100.';
COMMENT ON COLUMN db_metrics.memory_pct IS 'Proxy: % de sesiones idle-in-transaction respecto a max_connections.';
COMMENT ON COLUMN db_metrics.deadlocks IS 'Deadlocks detectados en el intervalo desde la captura anterior (delta).';

CREATE OR REPLACE VIEW v_connection_latest_health AS
SELECT DISTINCT ON (m.db_id)
    m.db_id,
    c.nombre,
    c.motor,
    c.host,
    c.port,
    c.status AS connection_status,
    m.cpu_pct,
    m.memory_pct,
    m.connections,
    m.locks,
    m.deadlocks,
    m.disk_usage_mb,
    m.health_grade,
    m.capture_time,
    m.collect_error
FROM db_metrics m
JOIN connections c ON c.id = m.db_id
ORDER BY m.db_id, m.capture_time DESC;
