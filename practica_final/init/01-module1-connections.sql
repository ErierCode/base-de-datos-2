-- Módulo 1 — tabla CONNECTIONS (BD de control)
-- password_ciphertext + password_algo: credencial cifrada por la aplicación (nunca texto plano).

CREATE TYPE motor_t AS ENUM ('ORACLE', 'SQL_SERVER', 'POSTGRESQL');
CREATE TYPE connection_status_t AS ENUM ('ACTIVE', 'INACTIVE', 'ERROR');

CREATE TABLE connections (
    id              SERIAL PRIMARY KEY,
    nombre          VARCHAR(255) NOT NULL,
    motor           motor_t NOT NULL,
    host            VARCHAR(255) NOT NULL,
    port            INTEGER NOT NULL CHECK (port > 0 AND port <= 65535),
    database_name   VARCHAR(255) NOT NULL,
    user_name       VARCHAR(255) NOT NULL,
    -- Almacenamiento seguro (la app cifra antes de INSERT/UPDATE):
    password_ciphertext BYTEA NOT NULL,
    password_algo   VARCHAR(64) NOT NULL DEFAULT 'app-managed',
    password_updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status          connection_status_t NOT NULL DEFAULT 'INACTIVE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_connections_nombre UNIQUE (nombre)
);

CREATE INDEX ix_connections_status ON connections (status);
CREATE INDEX ix_connections_motor ON connections (motor);

COMMENT ON TABLE connections IS 'Motores registrados para DataOps Control Center (Módulo 1)';
COMMENT ON COLUMN connections.password_ciphertext IS 'Secreto cifrado por el backend (p. ej. AES-GCM); nunca texto plano.';
