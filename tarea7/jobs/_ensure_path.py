"""Añade la raíz del lakehouse a sys.path (permite `python jobs/xx.py`)."""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
