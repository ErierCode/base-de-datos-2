import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str]) -> None:
    print("\n>>> Ejecutando:", " ".join(command))
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline RetailX DataOps Lakehouse")
    parser.add_argument("--rows", type=int, default=1_000_000, help="Registros CSV principales")
    parser.add_argument(
        "--skip-lab",
        action="store_true",
        help="Omitir laboratorio Spark (01b y 02b)",
    )
    args = parser.parse_args()

    for folder in ("data", "delta", "output"):
        (ROOT / folder).mkdir(exist_ok=True)

    steps = [
        [sys.executable, "jobs/01_generate_dataset.py", "--rows", str(args.rows)],
    ]
    if not args.skip_lab:
        steps.append([sys.executable, "jobs/01b_generate_spark_dataset.py", "--rows", str(args.rows)])

    steps.append([sys.executable, "jobs/02_bronze.py"])

    if not args.skip_lab:
        steps.append([sys.executable, "jobs/02b_spark_sql_delta_lab.py"])

    steps.extend(
        [
            [sys.executable, "jobs/03_silver.py"],
            [sys.executable, "jobs/04_gold.py"],
            [sys.executable, "jobs/05_queries.py"],
            [sys.executable, "jobs/06_analisis_negocio.py"],
            [sys.executable, "jobs/07_delta_time_travel.py"],
        ]
    )

    for step in steps:
        run(step)

    print("\nPipeline finalizado correctamente.")
    print("Capas: delta/bronze (csv,json,xml) -> silver -> gold")
    print("Power BI: abre powerbi/RetailX_Gold_Dashboard.pbip (ver docs/PowerBI_Guia.md)")


if __name__ == "__main__":
    main()
