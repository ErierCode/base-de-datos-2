-- Módulo 9 — Motor de alertas configurable (sin redeploy) + ALERT_LOG

CREATE TYPE alert_severity_t AS ENUM ('WARNING', 'CRITICAL');
CREATE TYPE alert_action_t AS ENUM ('EMAIL', 'DASHBOARD', 'EMAIL_DASHBOARD');
CREATE TYPE alert_status_t AS ENUM ('OPEN', 'ACKNOWLEDGED', 'RESOLVED');

CREATE TABLE alert_rules (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(64) NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metric_source   VARCHAR(64) NOT NULL,
    threshold_num   DOUBLE PRECISION NOT NULL,
    window_minutes  INTEGER NOT NULL DEFAULT 60 CHECK (window_minutes > 0),
    severity        alert_severity_t NOT NULL,
    action          alert_action_t NOT NULL DEFAULT 'DASHBOARD',
    cooldown_sec    INTEGER NOT NULL DEFAULT 300 CHECK (cooldown_sec >= 0),
    description     TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE alert_log (
    id              BIGSERIAL PRIMARY KEY,
    rule_id         INTEGER REFERENCES alert_rules (id) ON DELETE SET NULL,
    db_id           INTEGER REFERENCES connections (id) ON DELETE SET NULL,
    severity        alert_severity_t NOT NULL,
    condition_text  TEXT NOT NULL,
    message         TEXT,
    status          alert_status_t NOT NULL DEFAULT 'OPEN',
    action_taken    alert_action_t,
    engine_name     VARCHAR(255),
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    detail          JSONB
);

CREATE INDEX ix_alert_log_status_time ON alert_log (status, triggered_at DESC);
CREATE INDEX ix_alert_log_rule ON alert_log (rule_id, triggered_at DESC);

COMMENT ON TABLE alert_rules IS 'Módulo 9: reglas editables en caliente (API/UI).';
COMMENT ON TABLE alert_log IS 'Módulo 9: historial de alertas disparadas.';

INSERT INTO alert_rules (code, name, metric_source, threshold_num, window_minutes, severity, action, description)
VALUES
    ('CPU_HIGH', 'CPU superior al umbral', 'cpu_pct', 85, 5, 'WARNING', 'EMAIL_DASHBOARD',
     'PDF: CPU > 85% → correo + dashboard'),
    ('DEADLOCKS', 'Deadlocks acumulados', 'deadlocks_window', 3, 60, 'CRITICAL', 'DASHBOARD',
     'PDF: Deadlocks > 3 → alerta crítica en dashboard'),
    ('BACKUP_FAIL', 'Backup / SLA en riesgo', 'backup_sla_fail', 1, 1440, 'CRITICAL', 'EMAIL_DASHBOARD',
     'PDF: Backup fallido / SLA no cumplido'),
    ('REPL_LAG', 'Lag de replicación', 'replication_lag_sec', 10, 5, 'WARNING', 'DASHBOARD',
     'PDF: Lag replicación > 10 s'),
    ('DISK_PRESSURE', 'Presión de disco / memoria', 'memory_pct', 90, 10, 'CRITICAL', 'EMAIL_DASHBOARD',
     'PDF: Disco > 90% (proxy: memory_pct en métricas)'),
    ('CONN_PRESSURE', 'Conexiones sobre umbral', 'conn_pressure_pct', 80, 10, 'WARNING', 'DASHBOARD',
     'PDF: Conexiones > umbral (%)')
ON CONFLICT (code) DO NOTHING;
