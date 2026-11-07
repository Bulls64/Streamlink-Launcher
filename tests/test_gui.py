"""Test de fumée de l'interface : la fenêtre se construit, les réglages s'ouvrent, le thème change.

Ignoré s'il n'y a pas d'écran ou de Tk (sous Linux : xvfb-run -a python -m unittest tests.test_gui).
Tout est redirigé vers un dossier temporaire ; aucun réseau (vérifications de mise à jour désactivées).

Interface smoke test: the window builds, the settings open, the theme changes.

Skipped if there is no screen or Tk (on Linux: xvfb-run -a python -m unittest tests.test_gui).
Everything is redirected to a temporary folder; no network (update checks disabled).
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
                   # no Tk or no screen
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


    def test_open_chat_from_favorite_and_with_stream(self):
        from launcher import app_launch
        app, core = self.app, app_launch.core
        app.toast = mock.Mock()
        with mock.patch.object(core, "find_chat", return_value=None):
            self.assertFalse(app.open_chat("twitch", "eslcs"))
        self.assertEqual(app.toast.call_args[0][:2], (app.t("toast_no_chat"), "warn"))
        with mock.patch.object(core, "find_chat", return_value="/opt/StreamlinkChat.AppImage"), \
                mock.patch.object(app_launch.subprocess, "Popen") as popen:
            self.assertTrue(app.open_chat("kick", "xqc"))
            self.assertEqual(popen.call_args[0][0], ["/opt/StreamlinkChat.AppImage", "--open", "kick:xqc"])
            app.toast.assert_called_with(app.t("toast_chat_opened", name="xqc"), "ok")
            # Lancer un stream Twitch avec l'option : le chat s'ouvre aussi
            # Starting a Twitch stream with the option: the chat opens too
            app.cfg["chat_with_stream"] = True
            p = app.platform_by_id("twitch")
            with mock.patch.object(core, "find_streamlink", return_value="/usr/bin/streamlink"), \
                    mock.patch.object(app.streams, "start"):
                self.assertTrue(app.launch_platform(p, "eslcs"))
            self.assertEqual(popen.call_args[0][0][-2:], ["--open", "twitch:eslcs"])
            popen.reset_mock()
            yt = app.platform_by_id("youtube")
            with mock.patch.object(core, "find_streamlink", return_value="/usr/bin/streamlink"), \
                    mock.patch.object(app.streams, "start"):
                app.launch_platform(yt, "dQw4w9WgXcQ")
            popen.assert_not_called()                               # YouTube : pas de chat / no chat

    def test_favorite_menu_offers_the_chat(self):
        app = self.app
        entries = []

        class FakeMenu:
            def __init__(self, *a, **k):
                pass

            def add_command(self, label, command):
                entries.append(label)

            def add_separator(self):
                pass

            def tk_popup(self, x, y):
                pass

            def grab_release(self):
                pass
        from types import SimpleNamespace
        event = SimpleNamespace(x_root=10, y_root=10)
        with mock.patch("tkinter.Menu", FakeMenu):
            app.favorite_menu(event, {"platform": "twitch", "channel": "eslcs"})
            self.assertIn(app.t("menu_open_chat"), entries)
            entries.clear()
            app.favorite_menu(event, {"platform": "youtube", "channel": "dQw4w9WgXcQ"})
            self.assertNotIn(app.t("menu_open_chat"), entries)
            entries.clear()
            app.favorite_menu(event, {"channel": "old"})                # ancien favori : Twitch / old favorite
            self.assertIn(app.t("menu_open_chat"), entries)

if __name__ == "__main__":
    unittest.main()
