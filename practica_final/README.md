# DataOps Control Center

Plataforma de monitoreo de bases de datos (práctica final). Stack alineado al PDF **Tecnologías sugeridas**.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | **.NET 8 Web API** — JWT, **Swagger** (`/swagger`) |
| Frontend | **React 18** + Vite + Recharts (responsive) |
| BD control | PostgreSQL 16 (`postgres-control`) |
| Caché | **Redis** (Módulo 7, vía API) |
| Monitoreo | **Prometheus**, **Grafana**, **Alertmanager**, exporters Postgres/Redis |
| Workers | Python (health, analytics, backup, replicación) |

## Arranque rápido

```powershell
cd proyectoBD
docker compose up -d --build
```

| Servicio | URL |
|----------|-----|
| UI React | http://localhost:3000 |
| API + Swagger | http://localhost:8080/swagger |
| Grafana | http://localhost:3001 (admin / admin) → carpeta **DataOps Control Center** → dashboard **Overview** |
| Prometheus | http://localhost:9090 |

**Login demo:** `admin` / `Admin123!`

## Módulos 3 y 4

Tras levantar el stack, aplica (si la BD ya existía):

```powershell
Get-Content -Raw .\init\06-module3-4-complete.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
```

**Módulo 3 (UI):** pestaña *Queries* → *Ejecutar baseline* → *Optimizar* → gráfico antes/después.

**Módulo 4:** servicio `dcc-concurrency-sim` (120+ hilos en bucle). Pestaña *Concurrencia* muestra `tx_log` y deadlocks resueltos.

## Módulo 5 — Backup, Recovery y nube (AWS S3)

| Requisito PDF | Implementación |
|---------------|----------------|
| FULL / DIFF / INC | `backup-worker` + `pg_dump`, marcas `backup_touch` |
| Metadatos `BACKUP_HISTORY` | `init/04-module5-backup.sql` |
| SHA-256 + URL remoto | Tras cada backup, subida boto3 → S3 |
| Retención | `RETENTION_DAYS` + job `PURGE_CRON` |
| Snapshots PRE_* | `docker compose run --rm backup-worker python main.py snapshot PRE_DEPLOY` |
| Desastre + restore RTO | `disaster_demo.py` + `restore_demo.py --measure-rto` |
| Dashboard SLA | Pestaña **Backup (5)** + `GET /api/backups/sla` |

### Configurar Amazon S3 (producción / demo AWS)

1. Crea un bucket en la región deseada (ej. `us-east-1`).
2. Usuario IAM con permisos `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket` sobre `arn:aws:s3:::tu-bucket/dcc-control/*`.
3. Copia `.env.example` → `.env` y define:

```env
S3_BUCKET=tu-bucket-dcc
S3_PREFIX=dcc-control/
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
# NO definir S3_ENDPOINT_URL en AWS real
FULL_BOOTSTRAP_ON_STARTUP=1
```

4. `docker compose up -d --build backup-worker api frontend`

La UI mostrará **Replicación nube: AWS/S3** y columna **Nube ✓** cuando `remote_url` esté registrado.

### Prueba de desastre (informe / defensa)

Script automático con evidencia en consola:

```powershell
.\scripts\verify-module5.ps1
# Otros snapshots: .\scripts\verify-module5.ps1 -SnapshotLabel PRE_DEPLOY
```

Manual (mismos pasos):

```powershell
docker compose run --rm backup-worker python main.py snapshot PRE_TEST
docker compose run --rm backup-worker python disaster_demo.py
docker compose run --rm backup-worker python restore_demo.py --measure-rto
```

`restore_demo` descarga desde S3 si el archivo local no existe (útil tras purga local).

## Módulos 6 y 7 — Replicación HA + Redis

| Requisito PDF | Implementación |
|---------------|----------------|
| Primario + réplica | `postgres-ha-primary` / `postgres-ha-replica` (Bitnami PG 16) |
| Lag 2s / 5s / 20s | `replication-load` (NORMAL/MEDIUM/HIGH) + `replication-monitor` |
| Visualización tiempo real | Pestaña **Replicación (6)** + gráfico (poll 5 s) |
| CAP (informe) | Texto guía en UI + análisis en informe |
| Redis hit/miss | `DashboardCacheService` + `cache_event_log` |
| ~400 ms sin / ~40 ms con caché | Demostración API `GET /api/cache/demo` |
| TTL + invalidación manual | `Redis:TtlSeconds` + `POST /api/cache/invalidate` |
| Hit ratio en dashboard | Pestaña **Caché (7)** |

Tras `docker compose up -d --build`, los servicios HA pueden tardar **2–3 min** en quedar healthy. Hasta entonces el gráfico de lag puede estar vacío.

```powershell
docker logs dcc-replication-monitor --tail 20
docker logs dcc-replication-load --tail 20
```

## Arranque completo (módulos 1–7) desde cero

```powershell
cd C:\Users\erira\OneDrive\Desktop\proyectoBD
# .env con AWS opcional para módulo 5
docker compose down -v
docker compose up -d --build
```

1. http://localhost:3000 → `admin` / `Admin123!`
2. **Motores (1)** → registrar `postgres-control` (host `postgres-control`, db `dcc_control`)
3. Esperar pestañas **Salud (2)** … **Caché (7)** (workers en background)

## Módulo 8 — Power BI

**Proyecto listo para abrir:** [powerbi/DataOps-Control-Center.pbip](powerbi/DataOps-Control-Center.pbip) (Power BI Desktop).

```powershell
cd practica_final\powerbi
.\aplicar-vistas.ps1          # vistas SQL en Postgres
# Abrir DataOps-Control-Center.pbip → credenciales dcc_admin / dcc_secret_change_me
```

Las 5 páginas del PDF (rendimiento, heatmap, top queries, backups/SLA, disponibilidad) vienen preconfiguradas. Detalle: **[powerbi/README.md](powerbi/README.md)**. Guía manual alternativa: **[docs/MODULO-8-POWER-BI.md](docs/MODULO-8-POWER-BI.md)**.

## Módulo 9 — Motor de alertas

| Regla PDF | Código | Configurable en UI |
|-----------|--------|-------------------|
| CPU > 85% | `CPU_HIGH` | Sí |
| Deadlocks > 3 | `DEADLOCKS` | Sí |
| Backup fallido / SLA | `BACKUP_FAIL` | Sí |
| Lag réplica > 10 s | `REPL_LAG` | Sí |
| Disco > 90% (proxy) | `DISK_PRESSURE` | Sí |
| Conexiones > umbral | `CONN_PRESSURE` | Sí |

- Worker: `AlertEngineService` (cada ~45 s)
- UI: pestaña **Alertas (9)** — activar/desactivar reglas, umbral, resolver alertas
- Tablas: `alert_rules`, `alert_log` (`init/08-module9-alerts.sql`)
- Webhook Alertmanager: `POST /api/alerts/webhook`
- Correo opcional: `Alerts:SmtpHost`, `Alerts:EmailTo` en `appsettings` o variables de entorno

```powershell
Get-Content -Raw .\init\08-module9-alerts.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
```

## Migraciones manuales (BD ya creada)

```powershell
Get-Content -Raw .\init\02-module2-health.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
Get-Content -Raw .\init\04-module5-backup.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
Get-Content -Raw .\init\05-modules6-7.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
Get-Content -Raw .\init\08-module9-alerts.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
```

## Variables útiles (`.env`)

```env
POSTGRES_PASSWORD=dcc_secret_change_me
JWT_KEY=dcc-jwt-dev-key-change-in-production-min-32-chars!!
DCC_ADMIN_USER=admin
DCC_ADMIN_PASSWORD=Admin123!
```
