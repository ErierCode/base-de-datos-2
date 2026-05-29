"""Demuestra versionado y time travel de Delta Lake sin alterar Silver productivo."""

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from delta.tables import DeltaTable
from pyspark.sql import functions as F

from jobs.paths import SILVER_PATH
from jobs.spark_session import get_spark

DEMO_PATH = "delta/lab/silver_time_travel_demo"


def main() -> None:
    spark = get_spark("RetailX Delta Time Travel")
    source = spark.read.format("delta").load(SILVER_PATH)

    print("\n--- Versión 0: copia inicial en tabla de demostración ---")
    source.write.format("delta").mode("overwrite").save(DEMO_PATH)
    v0_count = spark.read.format("delta").option("versionAsOf", 0).load(DEMO_PATH).count()
    print("Registros v0:", v0_count)

    print("\n--- Versión 1: actualización (filtro de calidad) ---")
    source.filter(F.col("cantidad") <= 8).write.format("delta").mode("overwrite").save(DEMO_PATH)
    v1_count = spark.read.format("delta").load(DEMO_PATH).count()
    print("Registros v1:", v1_count)

    print("\n--- Time travel versionAsOf(0) ---")
    spark.read.format("delta").option("versionAsOf", 0).load(DEMO_PATH).agg(
        F.count("id_venta").alias("registros_recuperados_v0")
    ).show()

    print("\n--- Historial de versiones (_delta_log) ---")
    DeltaTable.forPath(spark, DEMO_PATH).history().select(
        "version", "timestamp", "operation"
    ).show(truncate=False)

    spark.stop()


if __name__ == "__main__":
    main()
