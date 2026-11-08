"""Tests de l'intégration au bureau, du mode mini et de la mise à jour intégrée, avec des imitations des appels Windows.

La zone de notification (wintray), le glisser-déposer (windrop) et le remplacement de l'exécutable passent par des
API Windows : ici, l'icône est un faux objet qui note ce qu'on lui demande, les dépôts sont des événements écrits
comme ceux de windrop, et le téléchargement, la vérification et le redémarrage de la mise à jour sont simulés.
Ce qui est testé, c'est la logique du lanceur autour de ces appels. Lancement : xvfb-run -a python -m unittest.

Tests of the desktop integration, the mini mode and the built-in update, with imitations of the Windows calls.

The notification area (wintray), drag and drop (windrop) and replacing the executable go through Windows APIs:
here, the icon is a fake object that records what it is asked, drops are events written like windrop's, and the
update's download, check and restart are simulated. What is tested is the launcher's logic around those calls.
Run: xvfb-run -a python -m unittest.
"""
import os
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tests.test_gui import HAVE_DISPLAY, GuiBase  # noqa: E402


class FakeTray:
    """Imite wintray.Tray : note les appels, renvoie le choix de menu demandé.

    Imitates wintray.Tray: records the calls, returns the requested menu choice."""

    def __init__(self, hotkey_ok=True, choice=0):
        self.icon_shown, self.hotkey, self.hotkey_error = False, False, 0
        self.hotkey_ok, self.choice = hotkey_ok, choice
        self.calls, self.menus, self.tooltip = [], [], None

    def show_icon(self):
        self.icon_shown = True

    def hide_icon(self):
        self.icon_shown = False

    def register_hotkey(self, combo=None):
        self.calls.append(("hotkey", combo))
        self.hotkey = self.hotkey_ok
        self.hotkey_error = 0 if self.hotkey_ok else 1409  # ERROR_HOTKEY_ALREADY_REGISTERED
        return self.hotkey_ok

    def unregister_hotkey(self):
        self.hotkey = False
        self.calls.append(("unhotkey",))

    def set_tooltip(self, text):
        self.tooltip = text

    def notify(self, title, body):
        self.calls.append(("notify", title, body))
        return True

    def show_menu(self, items):
        self.menus.append(items)
        return self.choice

    def stop(self):
        self.calls.append(("stop",))


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestTray(GuiBase):
    def setUp(self):
        super().setUp()
        self.app.toast = mock.Mock()
        self.tray = self.app.tray = FakeTray()

    def tearDown(self):
        self.app.tray = None
        super().tearDown()

    def test_settings_show_icon_and_register_hotkey(self):
        app, tray = self.app, self.tray
        app.cfg.update(tray=True, hotkey=True)
        app.apply_tray_settings()
        self.assertTrue(app.tray_active)
        self.assertEqual(tray.calls[-1][0], "hotkey")
        app.toast.assert_not_called()
        app.cfg.update(tray=False, hotkey=False)
        app.apply_tray_settings()
        self.assertFalse(app.tray_active)
        self.assertEqual(tray.calls[-1], ("unhotkey",))

    def test_taken_hotkey_is_reported(self):
        app = self.app
        app.tray = FakeTray(hotkey_ok=False)
        app.cfg.update(tray=True, hotkey=True)
        app.apply_tray_settings()
        self.assertEqual(app.toast.call_args[0][1], "warn")
        self.assertIn("1409", str(app.log_lines[-1]))

    def test_tooltip_counts_live_favorites(self):
        app, tray = self.app, self.tray
        tray.icon_shown = True
        app.store.add_favorite({"platform": "twitch", "channel": "eslcs"})
        app.update_tray_tooltip()
        self.assertEqual(tray.tooltip, "Streamlink Launcher")
        app.live = {("eslcs", "twitch"): {"live": True}}
        app.update_tray_tooltip()
        self.assertEqual(tray.tooltip, "Streamlink Launcher — " + app.t("toast_live_summary_one"))

    def test_menu_lists_live_favorites_and_their_chats(self):
        app, tray = self.app, self.tray
        tray.icon_shown = True
        app.store.add_favorite({"platform": "twitch", "channel": "eslcs"})
        app.live = {("eslcs", "twitch"): {"live": True, "viewers": 1500}}
        tray.choice = 100
        with mock.patch.object(app, "launch_favorite") as launch:
            app.tray_menu()
        labels = [i[1] for i in tray.menus[-1] if i]
        self.assertTrue(any("eslcs" in label for label in labels))
        self.assertIn(app.t("menu_open_live_chats", count=1), labels)
        self.assertEqual(launch.call_args[0][0]["channel"], "eslcs")
        tray.choice = 4
        with mock.patch.object(app, "open_live_chats") as chats:
            app.tray_menu()
        chats.assert_called_once()
        tray.choice = 2
        with mock.patch.object(app.mini, "show") as mini:
            app.tray_menu()
        mini.assert_called_once()

    def test_events_from_the_icon_and_the_hotkey(self):
        app = self.app
        with mock.patch.object(app, "show_main") as show, mock.patch.object(app, "tray_menu") as menu, \
                mock.patch.object(app.mini, "toggle") as toggle, mock.patch.object(app, "launch_favorite") as launch:
            app._tray_events.extend(["open", "menu", "hotkey", "balloon"])
            app._balloon_fav = {"platform": "twitch", "channel": "eslcs"}
            app._tray_events.append("balloon")
            app._poll_win_events()
        self.assertEqual(show.call_count, 1 + 1)   # open, puis balloon sans favori / then balloon without a favorite
        menu.assert_called_once()
        toggle.assert_called_once()
        launch.assert_called_once()
        self.assertFalse(app._tray_events)

    def test_an_event_error_does_not_stop_the_polling(self):
        app = self.app
        with mock.patch.object(app, "show_main", side_effect=RuntimeError("boom")):
            app._tray_events.extend(["open", "open"])
            app._poll_win_events()
        self.assertFalse(app._tray_events)

    def test_close_hides_to_the_tray_once_with_a_hint(self):
        app, tray = self.app, self.tray
        tray.icon_shown = True
        app.cfg["tray_hint_shown"] = False
        app.on_close()
        self.assertEqual(app.state(), "withdrawn")
        app.on_close()
        self.assertEqual([c[0] for c in tray.calls].count("notify"), 1)
        app.show_main()
        self.assertEqual(app.state(), "normal")

    def test_update_found_while_hidden_notifies_from_the_tray(self):
        app, tray = self.app, self.tray
        tray.icon_shown = True
        app.withdraw()
        app._update_checked({"path": "/usr/bin/streamlink", "installed": "7.0.0", "latest": "8.0.0",
                             "update": True, "kind": "pip"}, manual=False)
        self.assertEqual(tray.calls[-1][0], "notify")


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestDropAndClipboard(GuiBase):
    def setUp(self):
        super().setUp()
        self.app.toast = mock.Mock()

    def test_dropped_link_fills_the_field(self):
        app = self.app
        app.handle_drop(("enter",))
        self.assertIsNotNone(app._drop_overlay)
        app.handle_drop(("leave",))
        self.assertIsNone(app._drop_overlay)
        app.handle_drop(("text", "regarde https://kick.com/xqc ce soir"))
        self.assertEqual(app.target, ("platform", "kick"))
        self.assertIn("xqc", app.query.get())
        self.assertEqual(app.toast.call_args[0][1], "ok")

    def test_dropped_files(self):
        app = self.app
        folder = Path(tempfile.mkdtemp())
        url = folder / "stream.url"
        url.write_text("[InternetShortcut]\nURL=https://www.twitch.tv/eslcs\n", encoding="utf-8")
        app.handle_drop(("files", [str(folder / "image.png"), str(url)]))
        self.assertEqual(app.target, ("platform", "twitch"))
        self.assertIn("eslcs", app.query.get())
        app.handle_drop(("files", [str(folder / "image.png")]))
        self.assertEqual(app.toast.call_args[0][:2], (app.t("toast_drop_unknown"), "warn"))

    def test_drop_events_go_through_the_queue(self):
        app = self.app
        app._drop_events = deque([("text", "https://www.twitch.tv/ibai")])
        app._poll_win_events()
        self.assertIn("ibai", app.query.get())

    def test_copied_link_is_offered_once(self):
        app = self.app
        app.cfg["clipboard_watch"] = True
        app.clipboard_clear()
        app.clipboard_append("https://www.twitch.tv/eslcs")
        self.assertEqual(app.clipboard_offer(), ("twitch", "https://www.twitch.tv/eslcs"))
        self.assertIsNone(app.clipboard_offer())  # même contenu : déjà proposé / same content: already offered
        app._clip_seen = None
        app.offer_clipboard()
        self.assertEqual(app.toast.call_args[0][1], "info")
        with mock.patch.object(app, "launch") as launch:
            app.toast.call_args[1]["action"][1]()
        launch.assert_called_once()
        app.cfg["clipboard_watch"] = False
        app._clip_seen = None
        self.assertIsNone(app.clipboard_offer())


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestMiniBar(GuiBase):
    def setUp(self):
        super().setUp()
        self.mini = self.app.mini
        self.app.cfg["clipboard_watch"] = False
        self.app.toast = mock.Mock()
        self.app.store.add_favorite({"platform": "twitch", "channel": "eslcs"})
        self.app.store.add_favorite({"platform": "kick", "channel": "xqc"})

    def tearDown(self):
        self.mini.hide()
        super().tearDown()

    def test_open_switch_platform_and_close(self):
        mini, app = self.mini, self.app
        mini.toggle()
        app.update()
        self.assertTrue(mini.visible)
        self.assertEqual(mini.pid, "twitch")
        self.assertEqual(len(mini.items()), 2)  # les favoris quand rien n'est tapé / favorites when nothing is typed
        app.live = {("xqc", "kick"): {"live": True}}
        self.assertEqual(mini.items()[0]["value"]["channel"], "xqc")  # en direct en tête / live ones first
        mini.next_platform()
        self.assertEqual(mini.pid, app.platforms[1]["id"])
        mini.next_platform(-1)
        self.assertEqual(mini.pid, "twitch")
        mini.query.set("https://kick.com/adinross")  # un lien Kick choisit Kick / a Kick link picks Kick
        self.assertEqual(mini.pid, "kick")
        mini.show()  # déjà ouverte : reprend le focus / already open: takes the focus back
        self.assertTrue(mini.visible)
        mini.hide()
        self.assertFalse(mini.visible)
        self.assertEqual(mini.query.get(), "")

    def test_launch_errors_stay_in_the_bar(self):
        mini, app = self.mini, self.app
        mini.show()
        mini.query.set("eslcs")
        from launcher import app_launch
        with mock.patch.object(app_launch.core, "find_streamlink", return_value=None):
            mini.launch()
        self.assertTrue(mini.visible)
        self.assertIsNotNone(mini.message)
        with mock.patch.object(app_launch.core, "find_streamlink", return_value="/usr/bin/streamlink"), \
                mock.patch.object(app.streams, "start") as start:
            mini._enter()
        start.assert_called_once()
        self.assertFalse(mini.visible)

    def test_opens_filled_with_a_copied_link(self):
        mini, app = self.mini, self.app
        app.cfg["clipboard_watch"] = True
        app._clip_seen = None
        app.clipboard_clear()
        app.clipboard_append("https://kick.com/xqc")
        mini.show()
        app.update()
        self.assertEqual(mini.pid, "kick")
        self.assertEqual(mini.query.get(), "https://kick.com/xqc")


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestAppUpdate(GuiBase):
    """Mise à jour du lanceur : téléchargement, vérification, remplacement et redémarrage simulés.

    Launcher update: simulated download, check, replacement and restart."""

    RELEASE = {"version": "9.9.9", "page": "https://github.com/Bulls64/Streamlink-Launcher/releases/tag/v9.9.9",
               "asset": {"name": "StreamlinkLauncher-9.9.9.exe", "size": 1000, "url": "https://x/y.exe"}}

    def setUp(self):
        super().setUp()
        app = self.app
        app.toast = mock.Mock()
        from launcher import app_updates
        self.mod = app_updates
        # run_in_thread sans thread : le travail puis la suite, tout de suite / without a thread: work then done, now
        def run_now(work, done):
            try:
                result = work()
            except Exception as e:
                result = e
            done(result)
        app.run_in_thread = run_now
        app.open_settings()
        app.update()

    def found(self, **extra):
        return {"update": True, "current": "1.7.0", "latest": "9.9.9", "release": self.RELEASE, **extra}

    def test_check_shows_the_update(self):
        app, up = self.app, self.mod.updater
        with mock.patch.object(up, "check_app_update", return_value=self.found()), \
                mock.patch.object(up, "should_auto_update", return_value=False):
            app.check_app_update(manual=True)
        self.assertEqual(app.app_update["latest"], "9.9.9")
        self.assertEqual(app.toast.call_args[0][1], "warn")
        with mock.patch.object(up, "check_app_update", side_effect=OSError("offline")):
            app.check_app_update(manual=True)
        self.assertEqual((app._app_state, app._app_error), ("error", "app_err_network"))

    def test_install_downloads_checks_replaces_and_restarts(self):
        app, up = self.app, self.mod.updater
        app.app_update = self.found()
        with mock.patch.object(up, "can_self_update", return_value=True), \
                mock.patch.object(up, "download_update", return_value="/tmp/new.exe") as dl, \
                mock.patch.object(up, "check_signature", return_value=None), \
                mock.patch.object(up, "install_update") as install, \
                mock.patch.object(up, "relaunch", return_value=True) as relaunch, \
                mock.patch.object(app, "_shutdown") as shutdown, \
                mock.patch.object(self.mod.messagebox, "askyesno", return_value=True):
            app.install_app_update()
        dl.assert_called_once()
        install.assert_called_once()
        self.assertEqual(relaunch.call_args[1]["old_version"], __import__("launcher").__version__)
        shutdown.assert_called_once()

    def test_bad_signature_is_refused_and_the_file_removed(self):
        app, up = self.app, self.mod.updater
        app.app_update = self.found()
        bad = Path(tempfile.mkdtemp()) / "new.exe"
        bad.write_bytes(b"MZ")
        with mock.patch.object(up, "can_self_update", return_value=True), \
                mock.patch.object(up, "download_update", return_value=str(bad)), \
                mock.patch.object(up, "check_signature", return_value="app_err_signature"), \
                mock.patch.object(up, "install_update") as install:
            app.install_app_update(auto=True)
        install.assert_not_called()
        self.assertEqual((app._app_state, app._app_error), ("error", "app_err_signature"))
        self.assertFalse(bad.exists())

    def test_cannot_restart_asks_for_a_manual_restart(self):
        app, up = self.app, self.mod.updater
        app.app_update = self.found()
        with mock.patch.object(up, "can_self_update", return_value=True), \
                mock.patch.object(up, "download_update", return_value="/tmp/new.exe"), \
                mock.patch.object(up, "check_signature", return_value=None), \
                mock.patch.object(up, "install_update"), \
                mock.patch.object(up, "relaunch", return_value=False):
            app.install_app_update(auto=True)
        self.assertEqual(app._app_state, "restart")

    def test_without_a_replaceable_exe_the_release_page_opens(self):
        app, up = self.app, self.mod.updater
        app.app_update = self.found()
        with mock.patch.object(up, "can_self_update", return_value=False), \
                mock.patch.object(app, "open_url") as open_url:
            app.install_app_update()
        open_url.assert_called_once_with(self.RELEASE["page"])

    def test_auto_update_waits_for_running_streams(self):
        app, up = self.app, self.mod.updater
        with mock.patch.object(up, "should_auto_update", return_value=True), \
                mock.patch.object(app.streams, "running", return_value=[{"name": "x"}]), \
                mock.patch.object(app, "install_app_update") as install:
            app._app_update_checked(self.found(), manual=False)
        install.assert_not_called()

    def test_streamlink_update_card(self):
        app = self.app
        app._update_checked({"path": "/usr/bin/streamlink", "installed": "7.0.0", "latest": "8.0.0",
                             "update": True, "kind": "pip"}, manual=True)
        app.open_update()  # installation pip : commande copiée / pip install: command copied
        self.assertIn("streamlink", app.clipboard_get())
        app._update_checked(OSError("offline"), manual=True)
        self.assertEqual(app.toast.call_args[0][:2], (app.t("toast_update_check_failed"), "warn"))


@unittest.skipUnless(HAVE_DISPLAY, "pas d'écran ou de Tk disponible")
class TestLiveFlow(GuiBase):
    """Vérification en direct côté interface : résumé, notification d'un début de live, aperçus.

    Live check on the interface side: summary, notification when a live starts, previews."""

    def setUp(self):
        super().setUp()
        app = self.app
        app.toast = mock.Mock()
        app.cfg.update(live_check=True, live_previews=True, live_notify=True)

        def run_now(work, done):
            try:
                result = work()
            except Exception as e:
                result = e
            done(result)
        app.run_in_thread = run_now
        app.store.add_favorite({"platform": "twitch", "channel": "eslcs"})
        app.store.add_favorite({"platform": "kick", "channel": "xqc"})
        from launcher import app_favorites
        self.mod = app_favorites

    def tearDown(self):
        self.app.tray = None
        super().tearDown()

    def info(self, live, preview=None):
        return {"live": live, "title": "T" if live else None, "game": "G" if live else None,
                "viewers": 10 if live else None, "preview": preview}

    def test_summary_then_notification_when_a_live_starts(self):
        app, mod = self.app, self.mod
        app.tray = FakeTray()
        app.tray.icon_shown = True
        first = {("eslcs", "twitch"): self.info(True), ("xqc", "kick"): self.info(False)}
        with mock.patch.object(mod.live, "check_live", return_value=first), \
                mock.patch.object(mod.live, "fetch_previews", return_value={}):
            app._run_live()
        self.assertEqual(app.toast.call_args[0][0], app.t("toast_live_summary_one"))
        self.assertIsNotNone(app._live_job)  # prochaine vérification prévue / next check planned
        second = {("eslcs", "twitch"): None, ("xqc", "kick"): self.info(True)}  # None : état gardé / state kept
        with mock.patch.object(mod.live, "check_live", return_value=second), \
                mock.patch.object(mod.live, "fetch_previews", return_value={}), \
                mock.patch.object(mod.winnotify, "flash_taskbar"):
            app._run_live()
        self.assertTrue(app.live[("eslcs", "twitch")]["live"])
        self.assertEqual(app.toast.call_args[0][0], app.t("toast_live_started", name="xqc", platform="Kick"))
        self.assertEqual(app.tray.calls[-1][0], "notify")
        self.assertEqual(app._balloon_fav["channel"], "xqc")
        with mock.patch.object(mod.live, "check_live", side_effect=OSError("offline")):
            app._run_live()  # une erreur ne change rien / an error changes nothing
        self.assertTrue(app.live[("xqc", "kick")]["live"])

    def test_without_the_tray_a_windows_notification_is_used(self):
        app, mod = self.app, self.mod
        app.live = {("xqc", "kick"): self.info(False)}
        app._live_first = False
        with mock.patch.object(mod.live, "check_live", return_value={("xqc", "kick"): self.info(True)}), \
                mock.patch.object(mod.live, "fetch_previews", return_value={}), \
                mock.patch.object(mod.winnotify, "toast") as toast, \
                mock.patch.object(mod.winnotify, "flash_taskbar"):
            app._run_live()
        toast.assert_called_once()

    def test_previews_are_downloaded_and_drawn(self):
        app, mod = self.app, self.mod
        from launcher import thumb
        url = "https://static-cdn.jtvnw.net/previews-ttv/live_user_eslcs-640x360.jpg"
        app.live = {("eslcs", "twitch"): self.info(True, url)}
        key = ("eslcs", "twitch")
        with mock.patch.object(mod.live, "fetch_previews", return_value={key: b"\xff\xd8jpeg"}) as fetch:
            app.refresh_previews()
        self.assertIn(key, fetch.call_args[0][0])
        self.assertEqual(app.previews[key]["data"], b"\xff\xd8jpeg")
        png = thumb.png_rgba(4, 3, b"\x80\x40\x20\xff" * 12)
        self.assertIsNone(app.preview_image(key, 4, 3))  # pas encore à la bonne taille / not at the right size yet
        with mock.patch.object(mod.thumb, "render", return_value=png):
            app._render_preview(key)
        self.assertIsNotNone(app.preview_image(key, 4, 3))
        with mock.patch.object(mod.thumb, "render", return_value=None):  # décodage impossible / cannot decode
            app.previews[key]["stale"] = True
            app.preview_image(key, 8, 6)
            app._render_preview(key)
        self.assertEqual(app.previews[key]["failed"], (8, 6))
        app.live = {}
        app.refresh_previews()
        self.assertEqual(app.previews, {})


@unittest.skipUnless(os.name == "nt", "API Windows réelles : seulement sous Windows")
class TestWindowsApis(unittest.TestCase):
    """Sous Windows (CI), les vrais appels : icône cachée, raccourci, démarrage automatique (commande seulement).

    On Windows (CI), the real calls: hidden icon, shortcut, automatic start (command only)."""

    def test_tray_window_and_hotkey(self):
        from launcher import wintray
        events = []
        tray = wintray.Tray(events.append)
        if not tray.start():
            self.skipTest("fenêtre de la zone de notification indisponible sur ce poste")
        try:
            # Une combinaison peu courante, pour ne pas gêner le poste / an unusual combination
            if tray.register_hotkey("ctrl+alt+shift+f12"):
                self.assertTrue(tray.hotkey)
            tray.unregister_hotkey()
            self.assertFalse(tray.hotkey)
        finally:
            tray.stop()

    def test_drop_target_registers_on_a_window(self):
        import tkinter as tk

        from launcher import windrop
        root = tk.Tk()
        try:
            root.update()
            target = windrop.DropTarget(windrop.toplevel_hwnd(root), [].append)
            if target.register():
                target.revoke()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
