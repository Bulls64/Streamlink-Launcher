"""Tests de la logique sans interface (launcher/core.py).

Lancer depuis la racine du dépôt :  python -m unittest discover -s tests -v
Aucune dépendance : bibliothèque standard uniquement, pas besoin d'écran ni de Streamlink.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from launcher import core, __version__  # noqa: E402


class TempData(unittest.TestCase):
    """Redirige tous les fichiers de données vers un dossier temporaire."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        data = self.tmp / "streams"
        patches = {
            "CONFIG_FILE": self.tmp / "config.json",
            "DATA_FOLDER": data,
            "HISTORY_FILE": data / "history.json",
            "FAV_FILE": data / "favorites.json",
        }
        self._patches = [mock.patch.object(core, k, v) for k, v in patches.items()]
        for p in self._patches:
            p.start()
        core.DATA_ISSUES.clear()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        core.DATA_ISSUES.clear()


class TestVersion(unittest.TestCase):
    def test_version_matches_exe_metadata(self):
        info = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn(f"'FileVersion', '{__version__}'", info)
        self.assertIn(f"'ProductVersion', '{__version__}'", info)

    def test_changelog_has_current_version(self):
        self.assertIn(f"## [{__version__}]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_parse_version(self):
        self.assertEqual(core.parse_version("streamlink 7.1.3"), (7, 1, 3))
        self.assertEqual(core.parse_version("8.0"), (8, 0, 0))
        self.assertIsNone(core.parse_version("pas de version"))


class TestTranslations(unittest.TestCase):
    def test_same_keys_in_every_language(self):
        files = sorted((ROOT / "lang").glob("*.json"))
        self.assertEqual({f.stem for f in files}, {"fr", "en", "es", "de", "it"})
        keys = [set(json.loads(f.read_text(encoding="utf-8"))) for f in files]
        for f, k in zip(files[1:], keys[1:]):
            self.assertEqual(k, keys[0], f"{f.name} : {sorted(k ^ keys[0])}")

    def test_same_placeholders_in_every_language(self):
        import re
        data = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in (ROOT / "lang").glob("*.json")}
        for key, ref in data["fr"].items():
            if not isinstance(ref, str):
                continue
            for lang, strings in data.items():
                self.assertEqual(sorted(re.findall(r"{\w+}", strings[key])), sorted(re.findall(r"{\w+}", ref)),
                                 f"{lang}.json : {key}")

    def test_every_language_has_a_name_and_twelve_months(self):
        for f in (ROOT / "lang").glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            self.assertTrue(d.get("_language_name"), f.name)
            self.assertEqual(len(d["months_short"]), 12, f.name)

    def test_placeholder_named_key_is_allowed(self):
        t = core.I18n("fr")
        t.strings = {"x": "Raccourci {key}"}
        self.assertEqual(t("x", key="Ctrl+Alt+S"), "Raccourci Ctrl+Alt+S")


class TestInput(unittest.TestCase):
    def setUp(self):
        self.p = {p["id"]: p for p in core.DEFAULT_PLATFORMS}

    def test_channel_and_links(self):
        tw = self.p["twitch"]
        self.assertEqual(core.resolve_target(tw, "zerator"), ("https://www.twitch.tv/zerator", "zerator"))
        self.assertEqual(core.resolve_target(tw, "https://www.twitch.tv/zerator")[1], "zerator")
        self.assertEqual(core.resolve_target(tw, "twitch.tv/zerator")[1], "zerator")

    def test_youtube_forms(self):
        yt = self.p["youtube"]
        for text in ("dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ",
                     "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1", "youtube.com/shorts/dQw4w9WgXcQ"):
            self.assertEqual(core.resolve_target(yt, text)[1], "dQw4w9WgXcQ", text)

    def test_rejects_bad_input(self):
        for platform, text in (("twitch", ""), ("twitch", "a b"), ("twitch", "x;rm -rf"),
                               ("url", "ftp://x.y"), ("url", 'https://a.b/"x')):
            with self.assertRaises(core.InputError, msg=text):
                core.resolve_target(self.p[platform], text)

    def test_detect_platform(self):
        platforms = core.DEFAULT_PLATFORMS
        self.assertEqual(core.detect_platform_in_text(platforms, "kick.com/xqc"), "kick")
        self.assertEqual(core.detect_platform_in_text(platforms, "https://example.com/live"), "url")
        self.assertIsNone(core.detect_platform_in_text(platforms, "zerator"))


class TestSaveLoad(TempData):
    def test_atomic_save_keeps_backup(self):
        path = self.tmp / "a.json"
        self.assertTrue(core.save_json(path, {"v": 1}))
        self.assertTrue(core.save_json(path, {"v": 2}))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"v": 2})
        self.assertEqual(json.loads((self.tmp / "a.json.bak").read_text(encoding="utf-8")), {"v": 1})
        self.assertFalse((self.tmp / "a.json.tmp").exists())

    def test_truncated_file_is_restored_from_backup(self):
        path = self.tmp / "fav.json"
        core.save_json(path, {"favorites": [1, 2]})
        core.save_json(path, {"favorites": [1, 2, 3]})
        path.write_text(path.read_text(encoding="utf-8")[:12], encoding="utf-8")  # coupure en pleine écriture
        self.assertEqual(core.load_json(path, {}, recover=True), {"favorites": [1, 2]})
        self.assertEqual(core.DATA_ISSUES[0][0], "data_restored")
        self.assertEqual(len(list(self.tmp.glob("fav.json.*.corrupt"))), 1)

    def test_unreadable_file_without_backup_is_set_aside_not_overwritten(self):
        path = self.tmp / "fav.json"
        path.write_text('{"favorites": [', encoding="utf-8")
        self.assertEqual(core.load_json(path, {"favorites": []}, recover=True), {"favorites": []})
        self.assertEqual(core.DATA_ISSUES[0][0], "data_unreadable")
        corrupt = list(self.tmp.glob("fav.json.*.corrupt"))
        self.assertEqual(len(corrupt), 1)
        self.assertEqual(corrupt[0].read_text(encoding="utf-8"), '{"favorites": [')

    def test_without_recover_file_is_left_alone(self):
        path = self.tmp / "fr.json"
        path.write_text("{oups", encoding="utf-8")
        self.assertEqual(core.load_json(path, {}), {})
        self.assertTrue(path.exists())
        self.assertEqual(core.DATA_ISSUES, [])

    def test_save_failure_is_reported(self):
        target = self.tmp / "dossier" / "x.json"
        target.parent.write_text("pas un dossier", encoding="utf-8")
        self.assertFalse(core.save_json(target, {"a": 1}))
        self.assertEqual(core.DATA_ISSUES[0], ("save_failed", {"file": "x.json"}))

    def test_store_survives_truncated_favorites(self):
        store = core.Store()
        store.add_favorite({"channel": "a", "platform": "twitch"})
        store.add_favorite({"channel": "b", "platform": "kick"})
        core.FAV_FILE.write_text(core.FAV_FILE.read_text(encoding="utf-8")[:30], encoding="utf-8")
        again = core.Store()
        self.assertEqual([f["channel"] for f in again.favorites], ["a"])  # dernière version saine (.bak)


class TestLinks(unittest.TestCase):
    """Presse-papiers intelligent et glisser-déposer : reconnaissance des liens."""

    def setUp(self):
        self.platforms = core.DEFAULT_PLATFORMS
        self.tmp = Path(tempfile.mkdtemp())

    def test_link_in_text(self):
        f = lambda t: core.link_in_text(self.platforms, t)  # noqa: E731
        self.assertEqual(f("https://kick.com/xqc"), ("kick", "https://kick.com/xqc"))
        self.assertEqual(f("twitch.tv/zerator"), ("twitch", "twitch.tv/zerator"))
        self.assertEqual(f("Regarde ça : https://www.twitch.tv/zerator, vite !"),
                         ("twitch", "https://www.twitch.tv/zerator"))
        self.assertEqual(f("https://example.com/live")[0], "url")

    def test_known_platform_wins_over_generic_link(self):
        text = "https://example.com/a puis https://kick.com/xqc"
        self.assertEqual(core.link_in_text(self.platforms, text)[0], "kick")

    def test_ignores_plain_text(self):
        for text in ("", "   ", "bonjour", "du texte avec des mots", "zerator", None):
            self.assertIsNone(core.link_in_text(self.platforms, text), text)

    def test_ignores_huge_clipboard(self):
        self.assertIsNone(core.link_in_text(self.platforms, "https://kick.com/xqc " + "x" * core.CLIPBOARD_MAX))

    def test_url_shortcut_file(self):
        f = self.tmp / "lien.url"
        f.write_text("[InternetShortcut]\r\nURL=https://www.twitch.tv/zerator\r\n", encoding="utf-8")
        self.assertEqual(core.link_from_url_file(f), "https://www.twitch.tv/zerator")
        self.assertEqual(core.links_from_paths(self.platforms, [f]), ("twitch", "https://www.twitch.tv/zerator"))

    def test_url_shortcut_utf16_and_garbage(self):
        f = self.tmp / "u16.url"
        f.write_text("[InternetShortcut]\nURL=https://kick.com/xqc\n", encoding="utf-16")
        self.assertEqual(core.link_from_url_file(f), "https://kick.com/xqc")
        bad = self.tmp / "bad.url"
        bad.write_text("URL=javascript:alert(1)", encoding="utf-8")
        self.assertIsNone(core.link_from_url_file(bad))
        self.assertIsNone(core.link_from_url_file(self.tmp / "absent.url"))

    def test_dropped_files_skip_unsupported_types(self):
        img = self.tmp / "a.png"
        img.write_bytes(b"\x89PNG")
        txt = self.tmp / "n.txt"
        txt.write_text("à voir : https://kick.com/xqc", encoding="utf-8")
        self.assertIsNone(core.links_from_paths(self.platforms, [img]))
        self.assertEqual(core.links_from_paths(self.platforms, [img, txt]), ("kick", "https://kick.com/xqc"))

    def test_drop_module_is_inert_outside_windows(self):
        from launcher import windrop
        target = windrop.DropTarget(0, lambda event: None)
        if os.name != "nt":
            self.assertFalse(target.register())
        target.revoke()

    def test_clipboard_watch_is_on_by_default(self):
        self.assertTrue(core.DEFAULT_CONFIG["clipboard_watch"])


class TestBackup(TempData):
    LANGS = {"fr": "Français", "en": "English"}
    KEYS = ("ctrl+alt+s", "alt+shift+s")

    def parse(self, data):
        return core.parse_backup(data, self.LANGS, self.KEYS)

    def test_roundtrip_keeps_settings_and_favorites(self):
        cfg = dict(core.DEFAULT_CONFIG, language="en", theme="dark", live_interval=10,
                   qualities={"twitch": "720p,best"}, hotkey_combo="alt+shift+s")
        favs = [{"channel": "zerator", "platform": "twitch", "added": "2026-01-01 10:00:00"}]
        backup = core.make_backup(cfg, favs, "1.2.0")
        settings, got = self.parse(json.loads(json.dumps(backup)))
        self.assertEqual((settings["language"], settings["theme"], settings["live_interval"]), ("en", "dark", 10))
        self.assertEqual(settings["qualities"], {"twitch": "720p,best"})
        self.assertEqual(settings["hotkey_combo"], "alt+shift+s")
        self.assertEqual(got, favs)

    def test_machine_specific_paths_are_never_exported_or_imported(self):
        cfg = dict(core.DEFAULT_CONFIG, streamlink_path="C:/a.exe", player_path="C:/p.exe",
                   scripts_folder="C:/s", geometry="1x1+0+0")
        exported = core.make_backup(cfg, [], "1")["settings"]
        for key in core.MACHINE_KEYS:
            self.assertNotIn(key, exported)
        settings, _ = self.parse({"theme": "dark", "streamlink_path": "C:/evil.exe", "player_path": "x",
                                  "scripts_folder": "y", "geometry": "z"})
        self.assertEqual(settings, {"theme": "dark"})

    def test_invalid_values_are_dropped(self):
        settings, _ = self.parse({"theme": "dark", "language": "xx", "live_interval": 7, "hotkey_combo": "win+x",
                                  "player": "calc.exe", "player_args": "a\nb", "tray": "yes",
                                  "live_check": 1, "qualities": {"twitch": "best; rm"}, "unknown": 1})
        self.assertEqual(settings, {"theme": "dark"})

    def test_accepts_plain_config_and_favorites_files(self):
        self.assertEqual(self.parse({"theme": "light", "tray": False})[0], {"theme": "light", "tray": False})
        favs = self.parse({"favorites": [{"channel": "a", "platform": "kick"}, "oops", {"channel": "b"}]})[1]
        self.assertEqual(favs, [{"channel": "a", "platform": "kick"}])

    def test_unrecognised_content_is_refused(self):
        for data in ({}, [], "texte", {"foo": 1}, {"format": core.BACKUP_FORMAT}):
            with self.assertRaises(core.BackupError) as cm:
                self.parse(data)
            self.assertEqual(cm.exception.key, "err_backup_invalid")

    def test_read_backup_errors(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{pas du json", encoding="utf-8")
        with self.assertRaises(core.BackupError) as cm:
            core.read_backup(bad, self.LANGS, self.KEYS)
        self.assertEqual(cm.exception.key, "err_backup_read")
        with self.assertRaises(core.BackupError):
            core.read_backup(self.tmp / "absent.json", self.LANGS, self.KEYS)
        huge = self.tmp / "huge.json"
        huge.write_text('{"theme": "dark"}' + " " * core.BACKUP_MAX_BYTES, encoding="utf-8")
        with self.assertRaises(core.BackupError):
            core.read_backup(huge, self.LANGS, self.KEYS)

    def test_merge_favorites_skips_duplicates(self):
        current = [{"channel": "a", "platform": "twitch"}]
        incoming = [{"channel": "a", "platform": "twitch", "added": "x"}, {"channel": "a", "platform": "kick"},
                    {"channel": "b", "platform": "twitch"}]
        merged, added = core.merge_favorites(current, incoming)
        self.assertEqual(added, 2)
        self.assertEqual([(f["channel"], f["platform"]) for f in merged],
                         [("a", "twitch"), ("a", "kick"), ("b", "twitch")])

    def test_favorites_are_capped(self):
        many = [{"channel": f"c{i}", "platform": "twitch"} for i in range(core.FAVORITES_MAX + 50)]
        self.assertEqual(len(core.sanitize_favorites(many)), core.FAVORITES_MAX)


class TestDataFolder(unittest.TestCase):
    def test_writable_probe(self):
        tmp = Path(tempfile.mkdtemp())
        self.assertTrue(core._is_writable(tmp))
        self.assertEqual(list(tmp.iterdir()), [])
        self.assertFalse(core._is_writable(tmp / "absent"))

    @unittest.skipUnless(os.name == "nt", "Windows")
    def test_fallback_in_appdata(self):
        self.assertTrue(str(core._user_data_dir()).endswith("Streamlink Launcher"))

    def test_store_does_not_crash_when_folder_is_unusable(self):
        tmp = Path(tempfile.mkdtemp())
        blocker = tmp / "streams"
        blocker.write_text("fichier à la place du dossier", encoding="utf-8")
        with mock.patch.object(core, "DATA_FOLDER", blocker), \
                mock.patch.object(core, "HISTORY_FILE", blocker / "history.json"), \
                mock.patch.object(core, "FAV_FILE", blocker / "favorites.json"):
            store = core.Store()  # avant la 1.0.2 : exception au démarrage
            self.assertEqual(store.favorites, [])


if __name__ == "__main__":
    unittest.main()
