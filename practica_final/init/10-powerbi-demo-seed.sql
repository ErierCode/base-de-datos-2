-- Datos de demostración para Power BI (ejecutar si las tablas están vacías tras recrear Docker)
-- Get-Content -Raw .\init\10-powerbi-demo-seed.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control

INSERT INTO connections (nombre, motor, host, port, database_name, user_name, password_ciphertext, status)
VALUES (
    'postgres-control',
    'POSTGRESQL',
    'postgres-control',
    5432,
    'dcc_control',
    'dcc_admin',
    '\x00'::bytea,
    'ACTIVE'
)
ON CONFLICT (nombre) DO UPDATE SET status = 'ACTIVE'
RETURNING id;

-- Usar el id de la conexión (normalmente 1)
DO $$
DECLARE
    cid INTEGER;
    t   TIMESTAMPTZ;
    i   INTEGER;
BEGIN
    SELECT id INTO cid FROM connections WHERE nombre = 'postgres-control' LIMIT 1;
    IF cid IS NULL THEN
        RAISE EXCEPTION 'No hay conexión postgres-control';
    END IF;

    -- Métricas últimos 7 días (cada 2 h)
    FOR i IN 0..83 LOOP
        t := NOW() - (i * INTERVAL '2 hours');
        INSERT INTO db_metrics (db_id, cpu_pct, memory_pct, connections, locks, deadlocks, disk_usage_mb, health_grade, capture_time)
        VALUES (
            cid,
            25 + (random() * 55)::numeric(5,2),
            30 + (random() * 40)::numeric(5,2),
            (5 + floor(random() * 40))::int,
            floor(random() * 15)::int,
            CASE WHEN random() < 0.05 THEN 1 ELSE 0 END,
            120 + random() * 80,
            CASE
                WHEN random() < 0.85 THEN 'HEALTHY'::health_grade_t
                WHEN random() < 0.95 THEN 'WARNING'::health_grade_t
                ELSE 'CRITICAL'::health_grade_t
            END,
            t
        );
    END LOOP;

    -- Transacciones para heatmap (últimos 14 días)
    FOR i IN 1..500 LOOP
        t := NOW() - (floor(random() * 14) || ' days')::interval
             - (floor(random() * 24) || ' hours')::interval;
        INSERT INTO tx_log (db_id, session, operacion, inicio, fin, wait_time, lock_type)
        VALUES (
            cid,
            'sess-' || i,
            (ARRAY['INSERT','UPDATE','DELETE','SELECT'])[1 + floor(random()*4)::int]::tx_operation_t,
            t,
            t + (random() * 500 || ' ms')::interval,
            floor(random() * 200)::int,
            'SHARED'::lock_type_t
        );
    END LOOP;

    -- Queries lentas
    INSERT INTO query_log (db_id, query_text, duration_ms, rows_returned, index_used, execution_plan)
    SELECT
        cid,
        'SELECT * FROM workload.accounts WHERE balance > ' || g,
        (600 + g * 180)::numeric(14,3),
        10 + g,
        CASE WHEN g % 3 = 0 THEN NULL ELSE 'ix_accounts_balance' END,
        '{"Node Type":"Seq Scan","Plan Rows":' || g || '}'
    FROM generate_series(1, 12) g;

    RAISE NOTICE 'Seed Power BI OK para connection id %', cid;
END $$;
