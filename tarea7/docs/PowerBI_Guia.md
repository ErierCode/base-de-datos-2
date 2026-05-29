# Dashboard Power BI conectado a Gold vía Delta Lake

Este proyecto incluye un **Power BI Project (PBIP)** y consultas M listas para conectar las tablas Gold en `delta/gold/` usando el conector **Delta Lake** de Power BI Desktop.

## Requisitos

1. **Power BI Desktop** actualizado.
2. En **Archivo → Opciones → Características en versión preliminar**, activar:
   - Power BI Project (.pbip) save option
   - **Store semantic model using TMDL format**
3. Haber ejecutado el pipeline al menos una vez:

```bash
python jobs/run_pipeline.py --rows 10000
```

3. Ruta absoluta de tu carpeta `lakehouse` (ejemplo Windows):

```text
C:\Users\TU_USUARIO\Desktop\practicaBD\data-lakehouse\lakehouse
```

## Opción A — Abrir el proyecto PBIP (recomendado)

1. Abre Power BI Desktop (con **Power BI Project (.pbip)** habilitado en *Archivo → Opciones → Características en versión preliminar*).
2. **Archivo → Abrir → Examinar informes**.
3. Selecciona `powerbi/RetailX_Gold_Dashboard.pbip`.
4. Si Power BI pide actualizar el parámetro **LakehouseRoot**, escribe la ruta absoluta de la carpeta `lakehouse` (ej. `C:\Users\erira\OneDrive\Desktop\practicaBD\data-lakehouse\lakehouse`).
5. **Inicio → Actualizar** para cargar las tablas Gold desde Delta.

**Si falla al abrir el `.pbip`:** abre directamente  
`powerbi/RetailX_Gold_Dashboard/RetailX_Gold_Dashboard.Report/definition.pbir`  
(atajo válido según Microsoft; carga reporte + modelo semántico).

El modelo incluye 5 tablas Gold y un reporte con visuales básicos (KPIs, barras por categoría/país, tendencia mensual).

## Opción B — Conector Delta Lake manual

1. **Obtener datos → Más... → Delta Lake → Delta Lake**.
2. Ruta de carpeta (ejemplo):

```text
...\lakehouse\delta\gold\kpis_generales
```

3. Repite para cada tabla Gold:

| Tabla | Carpeta Delta |
|-------|----------------|
| KPIs | `delta/gold/kpis_generales` |
| Ventas por categoría | `delta/gold/ventas_por_categoria` |
| Ventas por país | `delta/gold/ventas_por_pais` |
| Ventas por mes | `delta/gold/ventas_por_mes` |
| Top productos | `delta/gold/top_productos` |

4. Copia las consultas de `powerbi/queries/*.pq` en **Transformar datos → Editor avanzado** si prefieres parametrizar la ruta.

## Fuente de datos del modelo (importante)

El modelo PBIP carga las tablas **Gold** desde `output/` (CSV exportados por `04_gold.py` desde `delta/gold/`).  
Así evitas el error *"No se puede convertir el valor 'C:/...' al tipo Table"*, que ocurre cuando `DeltaLake.Table` no existe en tu Power BI.

Para la entrega puedes explicar: *Gold en Delta Lake → export CSV en `output/` → Power BI consume la capa Gold.*

## Opción C — Solo CSV manual (sin PBIP)

Si prefieres no usar el proyecto, importa cada carpeta en `output/` con **Obtener datos → Texto/CSV**.

## Script de ayuda (Windows)

```powershell
cd powerbi
.\Abrir_Dashboard.ps1
```

## Hacer el dashboard más profesional

Guía paso a paso: [Dashboard_RetailX_Paso_a_Paso.md](Dashboard_RetailX_Paso_a_Paso.md)

1. **Vista → Temas → Examinar temas** → `powerbi/themes/RetailX_Executive.json`
2. **Cuadro de texto** arriba: "RetailX DataOps — Panel Gold"
3. Cambia las tarjetas por **Tarjeta de varias filas** (`kpis_generales` completa) o activa **título** en cada tarjeta
4. Añade **barras** (categoría, país), **línea** (mes) y **tabla** (top productos)
5. Formato **moneda** en `ingresos_totales` y `total_vendido` (sin notación científica)

## Evidencias para la entrega

Capturas de:

1. Power BI con las 5 tablas cargadas desde Delta.
2. Panel de KPIs y gráficos del reporte.
3. Vista de **Transformar datos** mostrando el origen Delta Lake.

## Nota sobre Docker

Las rutas Delta deben apuntar a la carpeta en tu **host Windows** (donde está el volumen montado), no a rutas internas del contenedor (`/app`).

## Errores comunes

| Error | Causa | Solución |
|-------|--------|----------|
| `Property 'dataset' has not been defined` | El `.pbip` listaba el modelo como artifact separado (inválido) | Ya corregido: el `.pbip` solo referencia el **reporte**; el modelo va en `definition.pbir` con `byPath` |
| `Property 'name' has not been defined` en `definition.pbism` | Campo `name` no válido en el esquema | Ya corregido: solo `$schema` + `version`; TMDL en carpeta `definition/` |
| No carga tablas Delta | Parámetro `LakehouseRoot` incorrecto o pipeline no ejecutado | Ejecuta `python jobs/run_pipeline.py --rows 10000` en Docker y actualiza la ruta absoluta de `lakehouse` |
| `No se puede convertir ... al tipo Table` | Conector Delta no disponible; la ruta se trata como texto | Ya corregido: el modelo lee CSV en `output/` (export de Gold) |
| Solo aparece **Recuento** en `total_vendido` | CSV con `4.7E7` → Power BI importa la columna como **texto** | **Transformar datos** → columna → **Número decimal**; o actualizar modelo PBIP y **Actualizar** |
