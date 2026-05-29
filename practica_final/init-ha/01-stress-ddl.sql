-- Tablas de estrés WAL en la instancia HA (primario replica a la réplica)
CREATE SCHEMA IF NOT EXISTS ha_stress;
CREATE TABLE IF NOT EXISTS ha_stress.events (
    id BIGSERIAL PRIMARY KEY,
    scenario TEXT NOT NULL DEFAULT 'NORMAL',
    payload TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ha_stress_created ON ha_stress.events (created_at DESC);
