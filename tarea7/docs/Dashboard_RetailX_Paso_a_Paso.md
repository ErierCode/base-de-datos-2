# Dashboard RetailX — de simple a ejecutivo (15 min)

## Paso 1: Tema profesional

1. En Power BI: **Vista → Temas → Examinar temas**.
2. Abre: `powerbi/themes/RetailX_Executive.json`.
3. El reporte adoptará colores, fondo gris claro y tarjetas con borde/sombra.

## Paso 2: Título del reporte

1. **Insertar → Cuadro de texto**.
2. Escribe: **RetailX DataOps — Panel Gold (Lakehouse)**.
3. Fuente 22–24 pt, negrita, color `#1B1F24`.
4. Colócalo arriba a lo ancho de la página.

## Paso 3: Mejorar las tarjetas KPI (recomendado)

En lugar de 5 tarjetas sueltas, usa **Tarjeta de varias filas**:

1. Elimina las tarjetas actuales (selección múltiple + Supr).
2. Inserta **Tarjeta de varias filas** (icono con varias líneas).
3. De `kpis_generales` arrastra **todos** los campos a *Valores*.
4. **Formato → Etiquetas**: activa *Etiqueta de categoría* = Activado.
5. Verás nombre + número (ej. `ingresos_totales` y el valor).

O mantén 4 tarjetas pero en cada una:
- **Formato → General → Título**: activar y poner "Ingresos totales", "Transacciones", etc.
- **Formato → Etiquetas de llamada**: tamaño 28–32.
- **Formato → Efectos**: sombra suave.

## Paso 4: Fila de gráficos (debajo de KPIs)

### A) Ventas por categoría
- Visual: **Gráfico de barras agrupadas**.
- Eje Y: `ventas_por_categoria[categoria]`
- Eje X: `ventas_por_categoria[total_vendido]`
- Ordenar por `total_vendido` descendente.
- Título: "Ventas por categoría".

### B) Ventas por país
- Visual: **Gráfico de barras** o **mapa coroplético** (si tienes código ISO; si no, barras).
- Eje: `pais` · Valores: `total_vendido`.
- Título: "Ventas por país".

### C) Tendencia mensual
- Visual: **Gráfico de líneas**.
- Eje X: `ventas_por_mes[mes]` · Valores: `total_vendido` · Leyenda: `anio`.
- Título: "Evolución mensual de ventas".

## Paso 5: Tabla Top productos (abajo a la derecha)

- Visual: **Tabla**.
- Campos: `producto`, `categoria`, `unidades_vendidas`, `total_vendido`.
- Formato → Valores: formato moneda en `total_vendido`.
- Título: "Top 10 productos".

## Paso 6: Formato de números

Selecciona cada visual con montos → **Formato → Valores**:
- `ingresos_totales`, `total_vendido`: **Moneda** o **Número** con separador de miles.
- Evita notación científica (`8.19E+07` → muestra `81,921,612`).

## Paso 7: Alineación

1. Selecciona todos los visuales (Ctrl + clic).
2. **Formato → Alinear** → distribuir y alinear a cuadrícula.
3. Deja márgenes uniformes (16–24 px).

## Layout sugerido (1280 × 720)

```text
┌─────────────────────────────────────────────────────────────┐
│  Título: RetailX DataOps — Panel Gold                        │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│ KPI 1    │ KPI 2    │ KPI 3    │ KPI 4    │  (5 opcional)  │
├──────────────────────┬──────────────────────┬───────────────┤
│ Barras categoría     │ Barras país          │ Top productos │
├──────────────────────┴──────────────────────┴───────────────┤
│              Línea ventas por mes (ancho completo)            │
└─────────────────────────────────────────────────────────────┘
```

## Paso 8: Guardar

**Archivo → Guardar** y captura pantalla del resultado final.
