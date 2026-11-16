"""Stable locations for portable application data and packaged resources."""

import sys
from pathlib import Path

APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
LANG_DIR = APP_DIR / "langs"
if not LANG_DIR.is_dir():
    LANG_DIR = RESOURCE_DIR / "langs"
CONFIG_PATH = APP_DIR / "po.ini"
