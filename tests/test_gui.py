"""Test de fumée de l'interface : la fenêtre se construit, les réglages s'ouvrent, le thème change.

Ignoré s'il n'y a pas d'écran ou de Tk (sous Linux : xvfb-run -a python -m unittest tests.test_gui).
Tout est redirigé vers un dossier temporaire ; aucun réseau (vérifications de mise à jour désactivées).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:  # pas de Tk ou pas d'écran
    HAVE_DISPLAY = False

from tests.test_core import TempData  # noqa: E402


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestGuiSmoke(TempData):
    def setUp(self):
        super().setUp()
        from launcher import app as app_module
        core = app_module.core
        core.save_config({**core.DEFAULT_CONFIG, "update_check": False, "tray": False, "language": "en"})
        self.extra = [mock.patch.object(app_module.wintray, "acquire_single_instance", return_value=True)]
        for p in self.extra:
            p.start()
        self.app = app_module.App()
        self.app.update()

    def tearDown(self):
        try:
            self.app.destroy()
        finally:
            for p in self.extra:
                p.stop()
            super().tearDown()

    def test_window_is_built(self):
        self.assertTrue(self.app.winfo_exists())
        self.assertGreater(self.app.winfo_width(), 100)
        self.assertEqual(self.app.title(), "Streamlink Launcher")

    def test_settings_open_and_close(self):
        self.app.open_settings()
        self.app.update()
        self.assertEqual(self.app.panel_kind, "settings")

    def test_theme_switch(self):
        for theme in ("dark", "light"):
            self.app.cfg["theme"] = theme
            self.app.build()
            self.app.update()
            self.assertEqual(self.app.mode, theme)


if __name__ == "__main__":
    unittest.main()
