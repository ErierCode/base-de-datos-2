"""Rutas compartidas del lakehouse RetailX."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DATA_DIR = "data"
DELTA_DIR = "delta"
OUTPUT_DIR = "output"

RAW_CSV = f"{DATA_DIR}/sales_raw.csv"
RAW_JSON = f"{DATA_DIR}/sales_events.json"
RAW_XML = f"{DATA_DIR}/fleet_telemetry.xml"

BRONZE_CSV = f"{DELTA_DIR}/bronze/sales_csv"
BRONZE_JSON = f"{DELTA_DIR}/bronze/sales_json"
BRONZE_XML = f"{DELTA_DIR}/bronze/sales_xml"

SILVER_PATH = f"{DELTA_DIR}/silver/sales_clean"
GOLD_BASE = f"{DELTA_DIR}/gold"
OUTPUT_BASE = OUTPUT_DIR
