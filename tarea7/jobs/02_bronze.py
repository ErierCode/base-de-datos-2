"""Bronze: ingesta CSV, JSON y XML sin transformaciones de negocio."""

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

import xml.etree.ElementTree as ET

from pyspark.sql import Row

from jobs.paths import (
    BRONZE_CSV,
    BRONZE_JSON,
    BRONZE_XML,
    RAW_CSV,
    RAW_JSON,
    RAW_XML,
)
from jobs.spark_session import get_spark


def ingest_csv(spark) -> None:
    df = (
        spark.read
        .option("header", True)
        .option("inferSchema", True)
        .csv(RAW_CSV)
    )
    df.write.format("delta").mode("overwrite").save(BRONZE_CSV)
    print(f"Bronze CSV -> {BRONZE_CSV} | registros: {df.count()}")


def ingest_json(spark) -> None:
    df = spark.read.json(RAW_JSON)
    df.write.format("delta").mode("overwrite").save(BRONZE_JSON)
    print(f"Bronze JSON -> {BRONZE_JSON} | registros: {df.count()}")


def ingest_xml(spark) -> None:
    tree = ET.parse(RAW_XML)
    rows = []
    for venta in tree.findall(".//venta"):
        rows.append(
            Row(
                id_venta=int(venta.findtext("id_venta")),
                fecha=venta.findtext("fecha"),
                id_cliente=int(venta.findtext("id_cliente")),
                pais=venta.findtext("pais"),
                producto=venta.findtext("producto"),
                categoria=venta.findtext("categoria"),
                cantidad=int(venta.findtext("cantidad")),
                precio_unitario=float(venta.findtext("precio_unitario")),
                monto=float(venta.findtext("monto")),
                vehiculo_id=venta.findtext("vehiculo_id"),
                lat=float(venta.findtext("lat")),
                lon=float(venta.findtext("lon")),
            )
        )
    df = spark.createDataFrame(rows)
    df.write.format("delta").mode("overwrite").save(BRONZE_XML)
    print(f"Bronze XML -> {BRONZE_XML} | registros: {df.count()}")


def main() -> None:
    spark = get_spark("RetailX Bronze")
    ingest_csv(spark)
    ingest_json(spark)
    ingest_xml(spark)
    spark.stop()


if __name__ == "__main__":
    main()
