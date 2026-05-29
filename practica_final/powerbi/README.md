# Módulo 8 — Power BI (DataOps Control Center)

El PDF pide **5 vistas obligatorias** en Power BI. La plataforma ya guarda los datos en PostgreSQL; este directorio incluye un **proyecto PBIP listo para abrir** en Power BI Desktop.

## Requisitos

- [Power BI Desktop](https://www.microsoft.com/power-platform/products/power-bi/desktop) (gratis)
- Docker con el stack levantado (`docker compose up -d` en `practica_final/`)
- Puerto **5433** en el host (`POSTGRES_PORT` en `.env`; evita conflicto con PostgreSQL local en Windows)

## Pasos rápidos

### 1. Aplicar vistas SQL (solo la primera vez o tras `docker compose down -v`)

```powershell
cd practica_final
Get-Content -Raw .\init\09-module8-powerbi-views.sql | docker exec -i dcc-postgres-control psql -U dcc_admin -d dcc_control
```

### 2. (Opcional) Regenerar el proyecto PBIP

```powershell
cd practica_final\powerbi
python generate_pbip.py
```

### 3. Abrir el informe

1. Abre **Power BI Desktop**.
2. **Archivo → Abrir → Examinar informes** (o doble clic).
3. Selecciona:

   `practica_final\powerbi\DataOps-Control-Center.pbip`

4. En el primer inicio te pedirá credenciales de PostgreSQL:

   | Campo | Valor |
   |-------|--------|
   | Servidor | `localhost` (puerto **5433** si Power BI lo pide aparte; o `localhost:5433`) |
   | Base de datos | `dcc_control` |
   | Usuario | `dcc_admin` |
   | Contraseña | `dcc_secret_change_me` (o la de tu `.env`) |

5. Pulsa **Actualizar** (o **Transformar datos → Cerrar y aplicar**) para cargar las 6 tablas.

## Páginas del informe (PDF Módulo 8)

| Página | Vista obligatoria |
|--------|-------------------|
| 01 Rendimiento | Líneas: CPU, conexiones, bloqueos por motor |
| 02 Heatmap | Matriz: operaciones por hora y día |
| 03 Top Queries | Tabla: queries lentas y optimización |
| 04 Backups SLA | Historial de backups + tarjeta SLA |
| 05 Disponibilidad | Medidor 99,9 % + tabla por motor |

## Exportar a `.pbix` (entrega del curso)

En Power BI Desktop: **Archivo → Guardar como** → `DataOps-Control-Center.pbix`

Puedes guardarlo en esta carpeta `powerbi/` para el repositorio o la entrega.

## Si no hay datos en los gráficos

1. Usa la app React (http://localhost:3000) unos minutos (workers de salud, queries, backups).
2. Comprueba filas:

   ```powershell
   docker exec dcc-postgres-control psql -U dcc_admin -d dcc_control -c "SELECT COUNT(*) FROM v_pbi_rendimiento;"
   ```

3. En Power BI: **Inicio → Actualizar**.

## Relación con Grafana

- **Grafana** (http://localhost:3001): monitoreo operativo (Prometheus).
- **Power BI**: BI ejecutivo sobre PostgreSQL (`dcc_control`), según el PDF.

Guía detallada manual: [../docs/MODULO-8-POWER-BI.md](../docs/MODULO-8-POWER-BI.md)
