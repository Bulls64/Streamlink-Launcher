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


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestChatGuiSmoke(TempData):
    """Streamlink Chat : la fenêtre se construit, un chat s'ouvre et affiche des messages (connexion factice)."""

    def setUp(self):
        super().setUp()
        from chat import app as chat_app
        from chat import config as chat_config
        from chat import instance
        self.mod = chat_app
        tmp = self.tmp
        self.patches = [mock.patch.object(chat_config, "CONFIG_FILE", tmp / "chat.json"),
                        mock.patch.object(chat_config, "CACHE_DIR", tmp / "cache"),
                        mock.patch.object(instance, "serve", lambda *a, **k: None),
                        mock.patch.object(chat_app.emotes, "fetch_global", lambda *a, **k: {})]
        for p in self.patches:
            p.start()

        class Dummy:
            can_send = False

            def __init__(self, emit, *a, **k):
                self.emit = emit

            def start(self):
                return self

            def join(self, ch):
                self.emit(("status", "twitch", ch, "connected", "ro"))

            def part(self, ch):
                pass

            def stop(self):
                pass
        self.patches.append(mock.patch.object(chat_app, "TwitchConnection", Dummy))
        self.patches[-1].start()
        self.app = chat_app.ChatApp()
        self.app.update()

    def tearDown(self):
        try:
            self.app.on_close()
        finally:
            for p in self.patches:
                p.stop()
            super().tearDown()

    def test_open_chat_and_show_messages(self):
        from chat.common import ChatMessage, split_words
        self.app.add_var.set("https://www.twitch.tv/eslcs")
        self.app._add_from_field()
        self.assertEqual([t.key for t in self.app.tabs], [("twitch", "eslcs")])
        msg = ChatMessage("twitch", "eslcs", text="salut @tous", user="ann", display_name="Ann",
                          badges=[("moderator", "Mod")], fragments=split_words("salut @tous"))
        self.app.events.put(("message", msg))
        for _ in range(10):
            self.app.update()
            self.app.after(30)
        view = self.app.current.view
        self.assertEqual(len(view.lines), 1)
        self.assertIn("Ann: salut @tous", view.text.get("1.0", "end"))
        self.assertEqual(self.app.current.status, "connected")
        self.app.open_settings()
        self.app.update()
        self.assertEqual(self.app.panel_kind, "settings")
