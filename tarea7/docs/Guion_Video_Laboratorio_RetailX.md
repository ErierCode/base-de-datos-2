# Guión para video — Laboratorio Data Lakehouse RetailX

**Basado en:** [Presentación Canva — Data Lakehouse + Delta Lake + Apache Spark](https://www.canva.com/design/DAHKhY4CADc/eGKJqJH8PbN62bVg0-Eowg/view?embed)  
**Proyecto:** `data-lakehouse/lakehouse` (RetailX DataOps Lakehouse)  
**Duración sugerida del video:** 12–18 minutos

---

## Cómo usar este documento

- **TEXTO PARA DECIR:** léelo o adáptalo con tus palabras.
- **MOSTRAR EN PANTALLA:** abre exactamente lo indicado mientras hablas.
- **TIEMPO:** orientativo por bloque.

---

# BLOQUE 0 — Introducción (1 min)

## TEXTO PARA DECIR

> Hola. En este video presento el laboratorio de **Data Lakehouse con Apache Spark y Delta Lake**, aplicado al caso empresarial **RetailX**.  
> Implementé un pipeline completo con arquitectura **Medallion** (Bronze, Silver y Gold), procesamiento a escala con **PySpark**, persistencia en **Delta Lake** y un **dashboard en Power BI** conectado a la capa Gold.

## MOSTRAR EN PANTALLA

1. Diapositiva 1 de Canva (portada) **o** carpeta del proyecto en el explorador de archivos.
2. Ruta: `practicaBD/data-lakehouse/lakehouse`

---

# BLOQUE 1 — Contexto y objetivos (2 min)

## TEXTO PARA DECIR — Problema RetailX (Canva, diapositiva 3)

> RetailX es una empresa retail con **fuentes heterogéneas**: transacciones del ERP/POS en CSV, eventos web en **JSON**, telemetría IoT/GPS en **XML**, y además datos manuales o de redes.  
> Eso genera reportes lentos, duplicados que distorsionan KPIs y una arquitectura difícil de escalar.  
> La solución que implementamos es un **Lakehouse moderno**: almacenamiento económico + procesamiento distribuido + calidad por capas.

## MOSTRAR EN PANTALLA

- Diapositiva 3 de Canva (**El problema: Empresa RetailX**).
- Opcional: carpeta `data/` con `sales_raw.csv`, `sales_events.json`, `fleet_telemetry.xml`.

## TEXTO PARA DECIR — Objetivos (Canva, diapositiva 2)

> Los objetivos del laboratorio son cuatro:  
> **1)** Diferenciar Data Warehouse, Data Lake y Lakehouse.  
> **2)** Diseñar un pipeline **Medallion** Bronze → Silver → Gold.  
> **3)** Procesar datos con **Spark** a escala de millones de registros.  
> **4)** Usar **Delta Lake** con propiedades ACID y versionado.

## MOSTRAR EN PANTALLA

- Diapositiva 2 de Canva (Objetivos de aprendizaje).

---

# BLOQUE 2 — Teoría: DW vs Lake vs Lakehouse (1,5 min)

## TEXTO PARA DECIR (Canva, diapositiva 4)

> Un **Data Warehouse** es rígido y costoso, optimizado para BI pero poco flexible con datos crudos.  
> Un **Data Lake** guarda todo en bruto pero le faltan transacciones y gobernanza.  
> El **Lakehouse** combina lo mejor de ambos: almacenamiento barato tipo lago, con una capa como **Delta Lake** que añade **ACID, versionado y time travel** sobre archivos Parquet.

## MOSTRAR EN PANTALLA

- Diapositiva 4 de Canva (**DW vs Data Lake vs Lakehouse**).
- Carpeta `delta/` mostrando `_delta_log` en alguna tabla (ej. `delta/gold/kpis_generales/_delta_log`).

---

# BLOQUE 3 — Arquitectura Medallion (2 min)

## TEXTO PARA DECIR (Canva, diapositiva 5)

> La arquitectura **Medallion** tiene tres capas:  
> **Bronze:** ingestión en crudo, sin transformar. En nuestro caso: CSV, JSON y XML tal como llegan.  
> **Silver:** limpieza, tipos correctos, deduplicación y reglas de calidad.  
> **Gold:** agregados de negocio — KPIs, ventas por categoría, país, mes y top productos — listos para Power BI.

## MOSTRAR EN PANTALLA

- Diapositiva 5 de Canva (Medallion Bronze → Silver → Gold).
- Explorador con:
  - `delta/bronze/sales_csv`, `sales_json`, `sales_xml`
  - `delta/silver/sales_clean`
  - `delta/gold/` (kpis_generales, ventas_por_categoria, etc.)
- README.md sección "Capas Medallion" (opcional).

---

# BLOQUE 4 — Apache Spark (1 min)

## TEXTO PARA DECIR (Canva, diapositiva 6)

> **Apache Spark** procesa en memoria y en paralelo. Usamos **PySpark** para transformar millones de filas.  
> En el proyecto, cada capa es un job: Bronze, Silver, Gold, más análisis de negocio y demostración de **time travel** en Delta.

## MOSTRAR EN PANTALLA

- Diapositiva 6 de Canva (Apache Spark).
- Carpeta `jobs/` con archivos `02_bronze.py`, `03_silver.py`, `04_gold.py`, `06_analisis_negocio.py`, `07_delta_time_travel.py`.

---

# BLOQUE 5 — Laboratorio: entorno Docker y datos (2,5 min)

## TEXTO PARA DECIR (Canva, diapositiva 7 — pasos 1 a 4)

> **Paso 1–2:** Levantamos el entorno con **Docker Compose** y red `lakehouse-net`. El contenedor `retailx_dataops_spark` incluye Python, Java y PySpark.  
> **Paso 3:** Entramos al contenedor con `docker exec`.  
> **Paso 4:** Generamos datos — en nuestro caso hasta **un millón de ventas** en CSV, más muestras en JSON y XML. También hay un job con **SparkSession "RetailX"** para el millón de tuplas de laboratorio.

## MOSTRAR EN PANTALLA

1. Terminal: `docker compose build` y `docker compose up -d` (captura o en vivo).
2. Terminal: `docker ps` mostrando `retailx_dataops_spark`.
3. Terminal dentro del contenedor:
   ```bash
   python jobs/run_pipeline.py --rows 10000
   ```
   (usa 10000 en el video si 1M tarda mucho; menciona que la entrega final usa 1M).
4. Carpeta `data/` con los tres archivos fuente.
5. Salida en consola: "CSV generado", "Bronze", "Silver", "Gold".

---

# BLOQUE 6 — Laboratorio: Delta Lake y consultas (2 min)

## TEXTO PARA DECIR (Canva, diapositiva 8 — pasos 5 a 7)

> **Paso 5:** Consultamos con **Spark SQL** — por ejemplo gasto por cliente con `groupBy` y `sum`.  
> **Paso 6:** Persistimos en **Delta Lake**; se crea la carpeta `_delta_log` con transacciones ACID.  
> **Paso 7:** Leemos de nuevo desde Delta y podemos hacer **time travel** a versiones anteriores.

## MOSTRAR EN PANTALLA

1. Ejecución o salida de `jobs/02b_spark_sql_delta_lab.py` (SQL por cliente).
2. Carpeta `delta/lab/delta_ventas/_delta_log`.
3. Ejecución de `jobs/07_delta_time_travel.py` mostrando historial de versiones en consola.
4. Diapositiva 8 de Canva.

---

# BLOQUE 7 — Proyecto final: análisis gerencial (2 min)

## TEXTO PARA DECIR (Canva, diapositiva 9 — preguntas de análisis)

> El proyecto final pide responder con PySpark sobre el dataset:  
> 1. ¿Qué **cliente** tiene mayor volumen de compra?  
> 2. ¿Cuáles son las **10 ventas** de mayor importe?  
> 3. ¿Cuál es el **promedio de venta por cliente**?  
> 4. ¿Qué clientes concentran el **80% del ingreso** (Pareto)?  
> Esto lo resuelve el job `06_analisis_negocio.py`.

## MOSTRAR EN PANTALLA

- Diapositiva 9 de Canva (preguntas de análisis).
- Terminal con salida de:
  ```bash
  python jobs/06_analisis_negocio.py
  ```
- Resaltar en consola las 4 respuestas.

---

# BLOQUE 8 — Proyecto final: Lakehouse completo + Power BI (3 min)

## TEXTO PARA DECIR (Canva, diapositiva 9 — proyecto final)

> El **Lakehouse completo** integra:  
> - **Bronze** con CSV, JSON y XML sin transformar.  
> - **Silver** unificado y limpio.  
> - **Gold** con KPIs y agregados.  
> - **Dashboard Power BI** sobre la capa Gold (exportada a CSV en `output/` para compatibilidad).  
> Procesamos más de **11 mil transacciones** en la demo (o 1 millón en la versión final), en **3 capas Medallion**.

## MOSTRAR EN PANTALLA

1. `jobs/run_pipeline.py` (orquestador completo).
2. Carpeta `output/` con `kpis_generales.csv`, `ventas_por_categoria.csv`, etc.
3. **Power BI Desktop:**
   - Panel Datos con las 5 tablas.
   - Vista de tabla `ventas_por_pais` (como ya tienes).
   - Dashboard con tarjetas KPI + gráficos (si ya los armaste).
4. Diapositiva 9 de Canva (cifras 1M, 3 capas, 120 min).

---

# BLOQUE 9 — Cierre (1 min)

## TEXTO PARA DECIR

> En resumen: implementé un **Lakehouse RetailX** con fuentes heterogéneas, pipeline **Medallion**, **Spark + Delta Lake** a escala, consultas de negocio, **time travel** y consumo en **Power BI**.  
> El código está en el repositorio `data-lakehouse/lakehouse`, con Docker, jobs documentados y guías en `docs/`.  
> Gracias por ver el video.

## MOSTRAR EN PANTALLA

- Diagrama mental o diapositiva 5 de Canva de nuevo.
- Árbol del proyecto completo.
- Tu dashboard Power BI final.

---

# ANEXO — Mapa rápido Canva → Tu proyecto

| Diapositiva Canva | Evidencia en tu repo |
|-------------------|----------------------|
| Problema RetailX | `data/sales_raw.csv`, `.json`, `.xml` |
| Medallion | `delta/bronze`, `silver`, `gold` |
| Spark 1M | `01_generate_dataset.py`, `01b_generate_spark_dataset.py` |
| Delta SQL | `02b_spark_sql_delta_lab.py` |
| Time travel | `07_delta_time_travel.py` |
| 4 preguntas | `06_analisis_negocio.py` |
| Power BI Gold | `powerbi/RetailX_Gold_Dashboard.pbip` + `output/*.csv` |

---

# ANEXO — Comandos útiles para grabar

```powershell
cd data-lakehouse\lakehouse
docker compose up -d
docker exec -it retailx_dataops_spark bash
python jobs/run_pipeline.py --rows 10000
python jobs/06_analisis_negocio.py
python jobs/07_delta_time_travel.py
```

---

*Documento generado para exposición en video del laboratorio académico RetailX.*
