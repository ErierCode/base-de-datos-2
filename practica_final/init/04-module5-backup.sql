-- Módulo 5 — BACKUP_HISTORY, SLA, marcas DIFF/INC y triggers de cambio
-- Orden importante: crear backup_history antes de sembrar / disparadores.

CREATE TYPE backup_kind_t AS ENUM ('FULL', 'DIFF', 'INC');

CREATE TABLE backup_sla_targets (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    target_rpo_sec INTEGER NOT NULL DEFAULT 900 CHECK (target_rpo_sec > 0),
    target_rto_sec INTEGER NOT NULL DEFAULT 2700 CHECK (target_rto_sec > 0),
    description TEXT DEFAULT 'Ejemplo orientativo: RPO=15min, RTO=45min'
);

INSERT INTO backup_sla_targets (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE backup_touch (
    schema_name TEXT NOT NULL,
    table_name  TEXT NOT NULL,
    touched_since_full BOOLEAN NOT NULL DEFAULT false,
    touched_since_any BOOLEAN NOT NULL DEFAULT false,
    touched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_backup_touch PRIMARY KEY (schema_name, table_name),
    CONSTRAINT ck_backup_touch_schemas CHECK (schema_name IN ('public', 'workload'))
);

CREATE OR REPLACE FUNCTION backup_touch_after_change() RETURNS TRIGGER AS $$
BEGIN
    UPDATE backup_touch bt
       SET touched_since_full = TRUE,
           touched_since_any = TRUE,
           touched_at = NOW()
     WHERE bt.schema_name = TG_TABLE_SCHEMA
       AND bt.table_name = TG_TABLE_NAME;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TABLE backup_history (
    id BIGSERIAL PRIMARY KEY,
    kind backup_kind_t NOT NULL,
    size_mb NUMERIC(14, 4) NOT NULL,
    duration_sec NUMERIC(14, 4) NOT NULL,
    restore_point TIMESTAMPTZ NOT NULL,
    local_path TEXT,
    remote_url TEXT,
    cloud_object_key TEXT,
    checksum_sha256 CHAR(64) NOT NULL,
    checksum_algo TEXT NOT NULL DEFAULT 'SHA256',
    depends_on_id BIGINT REFERENCES backup_history (id),
    parent_full_id BIGINT REFERENCES backup_history (id),
    snapshot_label TEXT,
    notes TEXT,
    included_tables TEXT,
    rpo_estimate_sec DOUBLE PRECISION,
    rto_observed_sec DOUBLE PRECISION,
    sla_met BOOLEAN NOT NULL DEFAULT false,
    retention_until TIMESTAMPTZ,
    purged BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_snapshot_labels CHECK (
        snapshot_label IS NULL
        OR snapshot_label IN ('PRE_DEPLOY', 'PRE_TEST', 'PRE_IMPORT')
    )
);

CREATE INDEX ix_backup_hist_created ON backup_history (created_at DESC);
CREATE INDEX ix_backup_hist_kind_created ON backup_history (kind, created_at DESC);

INSERT INTO backup_touch (schema_name, table_name)
SELECT DISTINCT t.table_schema, t.table_name
FROM information_schema.tables t
WHERE t.table_type = 'BASE TABLE'
  AND t.table_schema IN ('public', 'workload')
ON CONFLICT DO NOTHING;

-- No exponer escrituras administrativas de backups como “datos mutables” para DIFF/INC
DELETE FROM backup_touch
WHERE schema_name = 'public'
  AND table_name IN ('backup_history', 'backup_touch', 'backup_sla_targets');

DO $$
DECLARE
    r RECORD;
    trig TEXT;
BEGIN
    FOR r IN SELECT schema_name, table_name FROM backup_touch LOOP
        trig := 'tbkt_' || md5(r.schema_name || ':' || r.table_name);
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I.%I;', trig, r.schema_name, r.table_name);
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON %I.%I
             FOR EACH ROW EXECUTE FUNCTION backup_touch_after_change();',
            trig,
            r.schema_name,
            r.table_name
        );
    END LOOP;
END $$;

CREATE OR REPLACE VIEW v_backup_latest AS
SELECT h.*
FROM (
    SELECT * FROM backup_history ORDER BY created_at DESC LIMIT 20
) AS h;

CREATE OR REPLACE VIEW v_backup_sla_last AS
SELECT
    CASE
        WHEN last_full.restore_point IS NULL THEN NULL::double precision
        ELSE EXTRACT(EPOCH FROM (NOW() - last_full.restore_point))
    END AS seconds_since_full_restore_point,
    t.target_rpo_sec,
    t.target_rto_sec,
    CASE
        WHEN last_full.restore_point IS NULL THEN false
        WHEN EXTRACT(EPOCH FROM (NOW() - last_full.restore_point)) <= t.target_rpo_sec
             THEN TRUE
        ELSE false
    END AS meets_rpo_objective_vs_last_full_now,
    last_full.restore_point AS last_full_restore_point
FROM backup_sla_targets t
LEFT JOIN LATERAL (
    SELECT bh.restore_point AS restore_point
    FROM backup_history bh
    WHERE bh.kind = 'FULL'
      AND bh.purged IS NOT TRUE
      AND bh.created_at >= NOW() - INTERVAL '30 days'
      AND bh.local_path IS NOT NULL
      AND bh.local_path <> ''
    ORDER BY bh.created_at DESC
    LIMIT 1
) AS last_full ON TRUE
WHERE t.id = 1;

COMMENT ON VIEW v_backup_sla_last IS 'Dashboard rápido: holgura de RPO contra el último FULL (métrica didáctica).';
COMMENT ON TABLE backup_touch IS 'Tablas tocadas: DIFF usa touched_since_full; INC usa touched_since_any. FULL resetea ambos.';
