-- Módulo 8 — Vistas para Power BI (5 dashboards obligatorios del PDF)
-- Aplicar: Get-Content -Raw .\init\09-module8-powerbi-views.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control

-- 1) Rendimiento temporal (CPU, conexiones, bloqueos por motor)
CREATE OR REPLACE VIEW v_pbi_rendimiento AS
SELECT
    m.id,
    m.db_id,
    c.nombre AS motor,
    m.capture_time,
    m.cpu_pct::double precision AS cpu_pct,
    m.connections,
    m.locks,
    m.deadlocks,
    m.health_grade::text AS health_grade
FROM db_metrics m
JOIN connections c ON c.id = m.db_id;

-- 2) Heatmap de actividad (hora × día de semana)
CREATE OR REPLACE VIEW v_pbi_heatmap AS
SELECT
    t.db_id,
    c.nombre AS motor,
    EXTRACT(HOUR FROM t.inicio)::integer AS hora,
    EXTRACT(ISODOW FROM t.inicio)::integer AS dia_semana,
    TO_CHAR(t.inicio, 'Dy') AS dia_nombre,
    COUNT(*)::bigint AS operaciones
FROM tx_log t
JOIN connections c ON c.id = t.db_id
WHERE t.inicio >= NOW() - INTERVAL '30 days'
GROUP BY t.db_id, c.nombre, 3, 4, 5;

-- 3) Top 10 queries lentas (+ optimización si existe)
CREATE OR REPLACE VIEW v_pbi_top_slow AS
SELECT
    q.id,
    q.db_id,
    c.nombre AS motor,
    q.speed_class::text AS speed_class,
    q.duration_ms::double precision AS duration_ms,
    LEFT(q.query_text, 300) AS query_preview,
    q.index_used,
    LEFT(COALESCE(q.execution_plan, ''), 500) AS execution_plan_preview,
    o.duration_before_ms,
    o.duration_after_ms,
    o.improvement_pct,
    o.index_applied,
    q.created_at
FROM query_log q
LEFT JOIN connections c ON c.id = q.db_id
LEFT JOIN LATERAL (
    SELECT
        qo.duration_before_ms,
        qo.duration_after_ms,
        qo.improvement_pct,
        qo.index_applied
    FROM query_optimizations qo
    WHERE qo.query_log_id = q.id
    ORDER BY qo.id DESC
    LIMIT 1
) o ON TRUE
WHERE q.speed_class IN ('SLOW', 'CRITICAL')
   OR q.duration_ms >= 500
ORDER BY q.duration_ms DESC;

-- 4) Backups y SLA
CREATE OR REPLACE VIEW v_pbi_backups AS
SELECT
    h.id,
    h.kind::text AS kind,
    h.size_mb::double precision AS size_mb,
    h.duration_sec::double precision AS duration_sec,
    h.restore_point,
    h.sla_met,
    (h.remote_url IS NOT NULL AND h.remote_url <> '') AS subido_nube,
    h.created_at,
    COALESCE(h.notes, '') AS notes
FROM backup_history h
WHERE h.purged IS NOT TRUE;

CREATE OR REPLACE VIEW v_pbi_sla AS
SELECT
    s.seconds_since_full_restore_point,
    s.target_rpo_sec,
    s.target_rto_sec,
    s.meets_rpo_objective_vs_last_full_now AS cumple_rpo,
    s.last_full_restore_point
FROM v_backup_sla_last s;

-- 5) Disponibilidad global por motor (objetivo 99,9 %)
CREATE OR REPLACE VIEW v_pbi_disponibilidad AS
SELECT
    c.id AS db_id,
    c.nombre AS motor,
    COUNT(*) FILTER (WHERE m.health_grade = 'HEALTHY')::bigint AS muestras_sanas,
    COUNT(*)::bigint AS total_muestras,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE m.health_grade = 'HEALTHY')
        / NULLIF(COUNT(*), 0),
        2
    )::double precision AS disponibilidad_pct
FROM connections c
LEFT JOIN db_metrics m
    ON m.db_id = c.id
   AND m.capture_time >= NOW() - INTERVAL '30 days'
GROUP BY c.id, c.nombre;

COMMENT ON VIEW v_pbi_rendimiento IS 'Módulo 8 PDF: rendimiento temporal';
COMMENT ON VIEW v_pbi_heatmap IS 'Módulo 8 PDF: heatmap hora/día';
COMMENT ON VIEW v_pbi_top_slow IS 'Módulo 8 PDF: top queries lentas';
COMMENT ON VIEW v_pbi_backups IS 'Módulo 8 PDF: historial backups';
COMMENT ON VIEW v_pbi_disponibilidad IS 'Módulo 8 PDF: disponibilidad % por motor';

-- Una sola fila para medidor / tarjeta (promedio global)
CREATE OR REPLACE VIEW v_pbi_disponibilidad_global AS
SELECT
    ROUND(AVG(disponibilidad_pct)::numeric, 2)::double precision AS disponibilidad_promedio_pct,
    99.9::double precision AS objetivo_pct
FROM v_pbi_disponibilidad;
