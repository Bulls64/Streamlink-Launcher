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


class GuiBase(TempData):
    """Fenêtre réelle dans un dossier de données temporaire, sans réseau ni zone de notification.

    Real window in a temporary data folder, without network nor notification area."""

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
            # Tâches différées encore prévues (vérifications de démarrage…) : annulées avant de fermer
            # Delayed tasks still planned (start-up checks…): cancelled before closing
            for job in self.app.tk.splitlist(self.app.tk.call("after", "info")):
                self.app.after_cancel(job)
            self.app.destroy()
        finally:
            for p in self.extra:
                p.stop()
            super().tearDown()


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestGuiSmoke(GuiBase):
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

    def test_open_the_chats_of_all_live_favorites(self):
        from launcher import app_launch
        app, core = self.app, app_launch.core
        app.toast = mock.Mock()
        for fav in ({"platform": "twitch", "channel": "Eslcs"}, {"platform": "kick", "channel": "xqc"},
                    {"platform": "twitch", "channel": "off"}, {"platform": "youtube", "channel": "dQw4w9WgXcQ"}):
            app.store.add_favorite(fav)
        self.assertFalse(app.open_live_chats())
        self.assertEqual(app.toast.call_args[0][:2], (app.t("toast_no_live_chats"), "warn"))
        app.live = {("eslcs", "twitch"): {"live": True}, ("xqc", "kick"): {"live": True},
                    ("off", "twitch"): {"live": False}}
        # Dans l'ordre des favoris (les nouveaux en tête) / in favorites order (newest first)
        self.assertEqual(app.live_chat_targets(), [("kick", "xqc"), ("twitch", "Eslcs")])
        with mock.patch.object(core, "find_chat", return_value="/opt/StreamlinkChat.AppImage"), \
                mock.patch.object(app_launch.subprocess, "Popen") as popen:
            self.assertTrue(app.open_live_chats())
        self.assertEqual(popen.call_count, 1)  # une seule fenêtre, un onglet par chaîne / one window, one tab each
        self.assertEqual(popen.call_args[0][0], ["/opt/StreamlinkChat.AppImage", "--open", "kick:xqc",
                                                 "--open", "twitch:Eslcs"])
        app.toast.assert_called_with(app.t("toast_live_chats_opened", count=2, name="xqc"), "ok")
        app.open_favorites()  # le panneau propose le bouton / the panel offers the button
        app.update()

    def test_watch_time_is_recorded_and_shown(self):
        from datetime import datetime, timedelta
        app = self.app
        stream = {"name": "eslcs", "label": "eslcs", "watch": {"channel": "eslcs", "platform": "twitch"},
                  "started": datetime.now() - timedelta(minutes=50)}
        app.record_watch(stream)
        app.record_watch(stream)  # une seule fois / only once
        self.assertEqual(len(app.watch.sessions), 1)
        self.assertGreaterEqual(app.watch.sessions[0]["seconds"], 50 * 60)
        app.open_history()
        app.update()
        app.open_stats()
        app.update()
        self.assertEqual(app.panel_kind, "stats")
        app.open_stats(0)
        app.update()
        app.watch.clear()
        app.open_stats(30)
        app.update()


if __name__ == "__main__":
    unittest.main()
