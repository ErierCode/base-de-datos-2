# Power BI — Si el lienzo sale vacío (pero hay datos en el panel Derecho)

Los datos **sí están** (tablas `v_pbi_*` con ✓). Los gráficos del `.pbip` generado a veces **no se dibujan** en Power BI Desktop; hay que crear el visual a mano (2 minutos).

## Paso a paso — Página «01 Rendimiento»

1. Clic en el **área blanca** grande (debajo del título).
2. Panel **Visualizaciones** → icono **Gráfico de líneas**.
3. En **Datos**, tabla **`v_pbi_rendimiento`**, arrastra:
   - **Eje X:** `capture_time`
   - **Eje Y:** `cpu_pct` (luego también `connections` y `locks` si quieres)
   - **Leyenda:** `motor`
4. **Inicio** → **Actualizar** (por si acaso).

Si ves solo el cuadro «motor» abajo: **selecciónalo y Supr** (el segmentador vacío a veces oculta todo).

## Otras páginas

| Pestaña | Visual | Campos |
|---------|--------|--------|
| 02 Heatmap | **Matriz** | Filas `dia_nombre`, Columnas `hora`, Valores `operaciones` |
| 03 Top Queries | **Tabla** | columnas de `v_pbi_top_slow` |
| 04 Backups | **Tabla** | `v_pbi_backups` |
| 05 Disponibilidad | **Tarjeta** o **Medidor** | Ver sección abajo (no uses la columna suelta en el medidor) |

## Página 05 — Medidor en blanco «(En blanco)»

La tabla muestra **33 %** y **75 %** por motor, pero el **medidor** necesita **un solo número** (promedio), no la columna con varias filas.

1. Clic en el medidor → quita `disponibilidad_pct` del campo **Valor**.
2. **Modelado** → **Nueva medida** → pega:

```dax
Disponibilidad Promedio = AVERAGE(v_pbi_disponibilidad[disponibilidad_pct])
```

3. Arrastra **Disponibilidad Promedio** al **Valor** del medidor.
4. Formato del visual (icono rodillo): **Mín.** `0`, **Máx.** `100`, **Objetivo** `99.9`.

Alternativa más simple: borra el medidor y usa visual **Tarjeta** con la misma medida.

## Comprobar datos en Postgres

```powershell
docker exec dcc-postgres-control psql -U dcc_admin -d dcc_control -c "SELECT COUNT(*) FROM v_pbi_rendimiento;"
```

Debe ser **> 0**. Conexión Power BI: **`localhost:5433`**, `dcc_admin`, contraseña del `.env`.

## Regenerar el PBIP (opcional)

```powershell
cd practica_final\powerbi
python generate_pbip.py
```

Cierra Power BI y vuelve a abrir `DataOps-Control-Center.pbip`.
