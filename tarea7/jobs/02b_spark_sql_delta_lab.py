"""Laboratorio Canva pasos 5-7: Spark SQL, Delta /tmp/delta_ventas y lectura."""

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from pyspark.sql import functions as F

from jobs.paths import DATA_DIR
from jobs.spark_session import get_spark

LAB_CSV = f"{DATA_DIR}/ventas_spark_lab.csv"
DELTA_LAB = "delta/lab/delta_ventas"


def main() -> None:
    spark = get_spark("RetailX Lab SQL")

    print("\n--- Paso 5: Consultar CSV con Spark SQL (gasto por cliente) ---")
    df = spark.read.option("header", True).option("inferSchema", True).csv(LAB_CSV)
    df.createOrReplaceTempView("ventas")
    spark.sql(
        """
        SELECT id_cliente, ROUND(SUM(monto), 2) AS total_monto
        FROM ventas
        GROUP BY id_cliente
        ORDER BY total_monto DESC
        LIMIT 10
        """
    ).show(truncate=False)

    print("\n--- Paso 6: Escribir en Delta Lake ---")
    df.write.format("delta").mode("overwrite").save(DELTA_LAB)
    print(f"Tabla Delta creada en: {DELTA_LAB} (_delta_log incluido)")

    print("\n--- Paso 7: Leer desde Delta ---")
    spark.read.format("delta").load(DELTA_LAB).select(
        "id_venta", "id_cliente", "monto"
    ).orderBy(F.desc("monto")).show(10, truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
