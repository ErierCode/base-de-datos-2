"""Laboratorio Canva paso 4: 1M ventas con SparkSession 'RetailX' (id_venta, id_cliente, monto)."""

from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

import argparse
import shutil
from pathlib import Path

from pyspark.sql import functions as F

from jobs.paths import DATA_DIR
from jobs.spark_session import get_spark

LAB_CSV = f"{DATA_DIR}/ventas_spark_lab.csv"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=1_000_000)
    parser.add_argument("--output", default=LAB_CSV)
    args = parser.parse_args()

    spark = get_spark("RetailX")
    print(f"Generando {args.rows:,} tuplas con SparkSession RetailX...")

    df = (
        spark.range(1, args.rows + 1)
        .withColumnRenamed("id", "id_venta")
        .withColumn("id_cliente", (F.rand(seed=42) * 119999 + 1).cast("int"))
        .withColumn("monto", F.round(F.rand(seed=7) * 5000 + 50, 2))
        .select("id_venta", "id_cliente", "monto")
    )

    tmp_dir = args.output + "_tmp"
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(tmp_dir)

    part = next(Path(tmp_dir).glob("part-*.csv"))
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(part), args.output)
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print(f"CSV laboratorio guardado en: {args.output}")
    spark.read.option("header", True).csv(args.output).show(5)
    spark.stop()


if __name__ == "__main__":
    main()
