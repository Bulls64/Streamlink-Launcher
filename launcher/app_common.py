"""Constantes partagées par la fenêtre principale et ses mixins.

Constants shared by the main window and its mixins."""
import os
import re

from . import core

LOG_LIMIT = 500
RECENTS = 3
FAV_SLOTS = 3
APP_COLOR = "#7C4DFF"
GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)([+-]-?\d+)([+-]-?\d+)$")
ICON_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.ico")
if not os.path.isfile(ICON_FILE):
    ICON_FILE = str(core.RES_DIR / "launcher" / "app.ico")
