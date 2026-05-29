"""Silver: unifica CSV/JSON/XML, limpia duplicados, tipos y fechas."""

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from pyspark.sql import functions as F

from jobs.paths import BRONZE_CSV, BRONZE_JSON, BRONZE_XML, SILVER_PATH
from jobs.spark_session import get_spark


def normalize_source(df, source_name: str):
  # Esquema común sin perder trazabilidad de origen
    base = (
        df
        .withColumn("fuente", F.lit(source_name))
        .withColumn("id_venta", F.col("id_venta").cast("long"))
        .withColumn("id_cliente", F.col("id_cliente").cast("long"))
        .withColumn("fecha", F.col("fecha").cast("string"))
        .withColumn("pais", F.col("pais").cast("string"))
        .withColumn("producto", F.col("producto").cast("string"))
        .withColumn("categoria", F.col("categoria").cast("string"))
        .withColumn("cantidad", F.col("cantidad").cast("int"))
        .withColumn("precio_unitario", F.col("precio_unitario").cast("double"))
    )
    if "sucursal" not in df.columns:
        base = base.withColumn("sucursal", F.lit(None).cast("string"))
    if "canal" not in df.columns:
        base = base.withColumn("canal", F.lit(None).cast("string"))
    if "metodo_pago" not in df.columns:
        base = base.withColumn("metodo_pago", F.lit(None).cast("string"))
    return base.select(
        "fuente", "id_venta", "fecha", "id_cliente", "pais", "sucursal",
        "producto", "categoria", "cantidad", "precio_unitario", "canal", "metodo_pago",
    )


def main() -> None:
    spark = get_spark("RetailX Silver")

    csv_df = normalize_source(spark.read.format("delta").load(BRONZE_CSV), "csv")
    json_df = normalize_source(spark.read.format("delta").load(BRONZE_JSON), "json")
    xml_df = normalize_source(spark.read.format("delta").load(BRONZE_XML), "xml")

    unified = csv_df.unionByName(json_df, allowMissingColumns=True).unionByName(
        xml_df, allowMissingColumns=True
    )

    clean = (
        unified.dropDuplicates(["id_venta"])
        .withColumn("fecha", F.to_date("fecha"))
        .withColumn("pais", F.initcap(F.trim(F.col("pais"))))
        .withColumn("sucursal", F.trim(F.col("sucursal")))
        .withColumn("producto", F.trim(F.col("producto")))
        .withColumn("categoria", F.initcap(F.trim(F.col("categoria"))))
        .withColumn("cantidad", F.col("cantidad").cast("int"))
        .withColumn("precio_unitario", F.col("precio_unitario").cast("double"))
        .withColumn("total_venta", F.round(F.col("cantidad") * F.col("precio_unitario"), 2))
        .withColumn("anio", F.year("fecha"))
        .withColumn("mes", F.month("fecha"))
        .filter(F.col("fecha").isNotNull())
        .filter(F.col("cantidad") > 0)
        .filter(F.col("precio_unitario") > 0)
    )

    clean.write.format("delta").mode("overwrite").save(SILVER_PATH)
    print("Capa Silver creada en:", SILVER_PATH)
    print("Registros Silver:", clean.count())
    clean.groupBy("fuente").count().show()
    spark.stop()


if __name__ == "__main__":
    main()
