from pathlib import Path as _Path

exec(_Path(__file__).resolve().parent.joinpath("_ensure_path.py").read_text(encoding="utf-8"))  # noqa: S102

from jobs.paths import GOLD_BASE
from jobs.spark_session import get_spark

TABLES = [
    f"{GOLD_BASE}/kpis_generales",
    f"{GOLD_BASE}/ventas_por_categoria",
    f"{GOLD_BASE}/ventas_por_pais",
    f"{GOLD_BASE}/top_productos",
    f"{GOLD_BASE}/ventas_por_mes",
]


def main() -> None:
    spark = get_spark("RetailX Queries")
    for path in TABLES:
        print("\n" + "=" * 80)
        print(f"Consulta Gold: {path}")
        spark.read.format("delta").load(path).show(20, truncate=False)
    spark.stop()


if __name__ == "__main__":
    main()
