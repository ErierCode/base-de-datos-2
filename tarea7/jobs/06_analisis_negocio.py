"""Preguntas de análisis gerencial (diapositiva 9) sobre el dataset RetailX."""

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from pyspark.sql import Window
from pyspark.sql import functions as F

from jobs.paths import SILVER_PATH
from jobs.spark_session import get_spark


def main() -> None:
    spark = get_spark("RetailX Analisis Negocio")
    df = spark.read.format("delta").load(SILVER_PATH)

    print("\n" + "=" * 80)
    print("1) Cliente con mayor volumen de compra total")
    df.groupBy("id_cliente").agg(
        F.round(F.sum("total_venta"), 2).alias("total_compra")
    ).orderBy(F.desc("total_compra")).show(1, truncate=False)

    print("\n" + "=" * 80)
    print("2) Top 10 ventas de mayor importe individual")
    df.select("id_venta", "id_cliente", "producto", "total_venta", "fecha").orderBy(
        F.desc("total_venta")
    ).show(10, truncate=False)

    print("\n" + "=" * 80)
    print("3) Monto promedio de venta por cliente")
    df.groupBy("id_cliente").agg(
        F.round(F.avg("total_venta"), 2).alias("promedio_venta"),
        F.count("id_venta").alias("num_transacciones"),
    ).orderBy(F.desc("promedio_venta")).show(10, truncate=False)

    print("\n" + "=" * 80)
    print("4) Pareto: clientes que concentran el 80% del ingreso")
    ingreso_total = df.agg(F.sum("total_venta")).collect()[0][0]
    objetivo = ingreso_total * 0.80

    por_cliente = (
        df.groupBy("id_cliente")
        .agg(F.round(F.sum("total_venta"), 2).alias("total_cliente"))
        .orderBy(F.desc("total_cliente"))
    )

    w = Window.orderBy(F.desc("total_cliente"))
    pareto = (
        por_cliente
        .withColumn("acumulado", F.sum("total_cliente").over(w))
        .withColumn("pct_acumulado", F.round(F.col("acumulado") / ingreso_total * 100, 2))
    )

    hasta_80 = pareto.filter(F.col("acumulado") < objetivo).count()
    clientes_80 = max(1, hasta_80 + 1)

    print(f"Ingresos totales: {ingreso_total:,.2f}")
    print(f"Clientes que concentran ~80% del ingreso: {clientes_80:,}")
    print(f"Total clientes con ventas: {por_cliente.count():,}")
    pareto.show(15, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
