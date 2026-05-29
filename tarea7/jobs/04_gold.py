import shutil
from pathlib import Path

exec(Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from pyspark.sql import functions as F
from pyspark.sql.types import DecimalType, DoubleType, FloatType

from jobs.paths import GOLD_BASE, OUTPUT_BASE, SILVER_PATH
from jobs.spark_session import get_spark


def _csv_friendly(df):
    """Decimal en CSV evita notación científica (4.7E7) que Power BI lee como texto."""
    for field in df.schema.fields:
        if isinstance(field.dataType, (DoubleType, FloatType)):
            df = df.withColumn(field.name, F.col(field.name).cast(DecimalType(18, 2)))
    return df


def save_gold(df, name: str) -> None:
    """Guarda Delta Gold y un CSV único para Power BI (sin archivos .crc de Spark)."""
    delta_path = f"{GOLD_BASE}/{name}"
    csv_file = Path(OUTPUT_BASE) / f"{name}.csv"
    tmp_dir = Path(OUTPUT_BASE) / f"_{name}_tmp"

    df.write.format("delta").mode("overwrite").save(delta_path)
    df = _csv_friendly(df)
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(str(tmp_dir))

    part = next(tmp_dir.glob("part-*.csv"))
    shutil.copy(part, csv_file)
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"Gold: {delta_path} | Power BI: {csv_file}")


def main() -> None:
    spark = get_spark("RetailX Gold")
    df = spark.read.format("delta").load(SILVER_PATH)

    ventas_categoria = (
        df.groupBy("categoria")
        .agg(
            F.count("id_venta").alias("cantidad_ventas"),
            F.round(F.sum("total_venta"), 2).alias("total_vendido"),
            F.round(F.avg("total_venta"), 2).alias("ticket_promedio"),
        )
        .orderBy(F.desc("total_vendido"))
    )

    ventas_pais = (
        df.groupBy("pais")
        .agg(
            F.count("id_venta").alias("cantidad_ventas"),
            F.round(F.sum("total_venta"), 2).alias("total_vendido"),
        )
        .orderBy(F.desc("total_vendido"))
    )

    ventas_mes = (
        df.groupBy("anio", "mes")
        .agg(F.round(F.sum("total_venta"), 2).alias("total_vendido"))
        .orderBy("anio", "mes")
    )

    top_productos = (
        df.groupBy("producto", "categoria")
        .agg(
            F.sum("cantidad").alias("unidades_vendidas"),
            F.round(F.sum("total_venta"), 2).alias("total_vendido"),
        )
        .orderBy(F.desc("total_vendido"))
        .limit(10)
    )

    kpis = df.agg(
        F.count("id_venta").alias("total_transacciones"),
        F.round(F.sum("total_venta"), 2).alias("ingresos_totales"),
        F.round(F.avg("total_venta"), 2).alias("ticket_promedio"),
        F.countDistinct("id_cliente").alias("clientes_unicos"),
        F.countDistinct("producto").alias("productos_unicos"),
    )

    save_gold(ventas_categoria, "ventas_por_categoria")
    save_gold(ventas_pais, "ventas_por_pais")
    save_gold(ventas_mes, "ventas_por_mes")
    save_gold(top_productos, "top_productos")
    save_gold(kpis, "kpis_generales")

    print("Resumen de KPIs:")
    kpis.show(truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
