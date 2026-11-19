"""Ubicación de recursos para ejecución desde fuentes y distribuciones congeladas."""
from pathlib import Path
import sys

RESOURCE_ROOT = Path(sys._MEIPASS) if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
