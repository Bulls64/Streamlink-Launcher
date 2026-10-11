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
        self.assertGreaterEqual(len(files), 2)
        keys = [set(json.loads(f.read_text(encoding="utf-8"))) for f in files]
        for f, k in zip(files[1:], keys[1:]):
            self.assertEqual(k, keys[0], f"{f.name} : {sorted(k ^ keys[0])}")

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
