"""Tests de la logique sans interface (launcher/core.py).

Lancer depuis la racine du dépôt :  python -m unittest discover -s tests -v
Aucune dépendance : bibliothèque standard uniquement, pas besoin d'écran ni de Streamlink.

Tests of the logic without interface (launcher/core.py).

Run from the root of the repository:  python -m unittest discover -s tests -v
No dependency: standard library only, no need for a screen or Streamlink.
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

from launcher import __version__, backup, core, inputs, live, updater  # noqa: E402


class TempData(unittest.TestCase):
    """Redirige tous les fichiers de données vers un dossier temporaire.

    Redirects all the data files to a temporary folder."""

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


class TestSystemLanguage(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "variables d'environnement de langue : Linux")
    def test_language_from_environment(self):
        for env, expected in (({"LANG": "fr_FR.UTF-8"}, "fr"), ({"LC_ALL": "de_DE.UTF-8", "LANG": "fr_FR"}, "de"),
                              ({"LANG": "C"}, "en"), ({"LANG": "ja_JP.UTF-8"}, "en")):
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(core.locale, "getlocale", return_value=(None, None)):
                self.assertEqual(core.detect_system_language(), expected, env)


class TestPlatformsFile(TempData):
    def test_missing_file_is_seeded_from_bundled_copy(self):
        target = self.tmp / "user" / "platforms.json"
        with mock.patch.object(core, "PLATFORMS_FILE", target):
            platforms, error = core.load_platforms()
        self.assertIsNone(error)
        saved = json.loads(target.read_text(encoding="utf-8"))
        bundled = json.loads((ROOT / "platforms.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, bundled)  # avec son aide (_aide) et live_check
                                          # with its help (_aide) and live_check
        self.assertEqual([p["id"] for p in platforms], [p["id"] for p in bundled["platforms"]])

    def test_missing_file_without_bundled_copy_uses_defaults(self):
        target = self.tmp / "user" / "platforms.json"
        with mock.patch.object(core, "PLATFORMS_FILE", target), mock.patch.object(core, "BASE_DIR", self.tmp / "none"):
            core.load_platforms()
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"platforms": core.DEFAULT_PLATFORMS})


class TestVersion(unittest.TestCase):
    def test_version_matches_exe_metadata(self):
        info = (ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn(f"'FileVersion', '{__version__}'", info)
        self.assertIn(f"'ProductVersion', '{__version__}'", info)

    def test_changelog_has_current_version(self):
        self.assertIn(f"## [{__version__}]", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_parse_version(self):
        self.assertEqual(updater.parse_version("streamlink 7.1.3"), (7, 1, 3))
        self.assertEqual(updater.parse_version("8.0"), (8, 0, 0))
        self.assertIsNone(updater.parse_version("pas de version"))


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

    def test_no_unused_translation(self):
        code = "".join(f.read_text(encoding="utf-8") for f in (ROOT / "launcher").glob("*.py"))
        code += (ROOT / "platforms.json").read_text(encoding="utf-8")
        dynamic = ("ph_", "player_")  # clés construites : t("ph_" + type), t("player_" + lecteur)
                                      # built keys: t("ph_" + type), t("player_" + player)
        keys = json.loads((ROOT / "lang" / "fr.json").read_text(encoding="utf-8"))
        unused = [k for k in keys if not k.startswith("_") and not k.startswith(dynamic)
                  and f'"{k}"' not in code and f"'{k}'" not in code]
        self.assertEqual(unused, [])

    def test_every_language_has_a_name_and_twelve_months(self):
        for f in (ROOT / "lang").glob("*.json"):
            d = json.loads(f.read_text(encoding="utf-8"))
            self.assertTrue(d.get("_language_name"), f.name)
            self.assertEqual(len(d["months_short"]), 12, f.name)

    def test_format_date(self):
        from datetime import datetime
        t = core.I18n("fr")
        now = datetime(2026, 10, 12, 20, 0, 0)
        self.assertEqual(t.format_date("2026-10-12 08:05:00", now), "Aujourd’hui, 08:05")
        self.assertEqual(t.format_date("2026-10-11 23:59:59", now), "Hier, 23:59")
        self.assertEqual(t.format_date("2025-10-20 22:35:26", now), "20 oct. 2025")
        for odd in ("pas une date", "", None, ["liste"]):  # valeurs abîmées : rendues telles quelles
                                                           # damaged values: returned as they are
            self.assertEqual(t.format_date(odd, now), odd or "")

    def test_placeholder_named_key_is_allowed(self):
        t = core.I18n("fr")
        t.strings = {"x": "Raccourci {key}"}
        self.assertEqual(t("x", key="Ctrl+Alt+S"), "Raccourci Ctrl+Alt+S")


class TestInput(unittest.TestCase):
    def setUp(self):
        self.p = {p["id"]: p for p in core.DEFAULT_PLATFORMS}

    def test_channel_and_links(self):
        tw = self.p["twitch"]
        self.assertEqual(inputs.resolve_target(tw, "zerator"), ("https://www.twitch.tv/zerator", "zerator"))
        self.assertEqual(inputs.resolve_target(tw, "https://www.twitch.tv/zerator")[1], "zerator")
        self.assertEqual(inputs.resolve_target(tw, "twitch.tv/zerator")[1], "zerator")

    def test_youtube_forms(self):
        yt = self.p["youtube"]
        for text in ("dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ",
                     "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1", "youtube.com/shorts/dQw4w9WgXcQ"):
            self.assertEqual(inputs.resolve_target(yt, text)[1], "dQw4w9WgXcQ", text)

    def test_rejects_bad_input(self):
        for platform, text in (("twitch", ""), ("twitch", "a b"), ("twitch", "x;rm -rf"),
                               ("url", "ftp://x.y"), ("url", 'https://a.b/"x')):
            with self.assertRaises(inputs.InputError, msg=text):
                inputs.resolve_target(self.p[platform], text)

    def test_detect_platform(self):
        platforms = core.DEFAULT_PLATFORMS
        self.assertEqual(inputs.detect_platform_in_text(platforms, "kick.com/xqc"), "kick")
        self.assertEqual(inputs.detect_platform_in_text(platforms, "https://example.com/live"), "url")
        self.assertIsNone(inputs.detect_platform_in_text(platforms, "zerator"))


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
                                                                                  # power cut in the middle of a write
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
                                                                          # last healthy version (.bak)


class TestLinks(unittest.TestCase):
    """Presse-papiers intelligent et glisser-déposer : reconnaissance des liens.

    Smart clipboard and drag and drop: link recognition."""

    def setUp(self):
        self.platforms = core.DEFAULT_PLATFORMS
        self.tmp = Path(tempfile.mkdtemp())

    def test_link_in_text(self):
        f = lambda t: inputs.link_in_text(self.platforms, t)
        self.assertEqual(f("https://kick.com/xqc"), ("kick", "https://kick.com/xqc"))
        self.assertEqual(f("twitch.tv/zerator"), ("twitch", "twitch.tv/zerator"))
        self.assertEqual(f("Regarde ça : https://www.twitch.tv/zerator, vite !"),
                         ("twitch", "https://www.twitch.tv/zerator"))
        self.assertEqual(f("https://example.com/live")[0], "url")

    def test_known_platform_wins_over_generic_link(self):
        text = "https://example.com/a puis https://kick.com/xqc"
        self.assertEqual(inputs.link_in_text(self.platforms, text)[0], "kick")

    def test_ignores_plain_text(self):
        for text in ("", "   ", "bonjour", "du texte avec des mots", "zerator", None):
            self.assertIsNone(inputs.link_in_text(self.platforms, text), text)

    def test_ignores_huge_clipboard(self):
        self.assertIsNone(inputs.link_in_text(self.platforms, "https://kick.com/xqc " + "x" * inputs.CLIPBOARD_MAX))

    def test_url_shortcut_file(self):
        f = self.tmp / "lien.url"
        f.write_text("[InternetShortcut]\r\nURL=https://www.twitch.tv/zerator\r\n", encoding="utf-8")
        self.assertEqual(inputs.link_from_url_file(f), "https://www.twitch.tv/zerator")
        self.assertEqual(inputs.links_from_paths(self.platforms, [f]), ("twitch", "https://www.twitch.tv/zerator"))

    def test_url_shortcut_utf16_and_garbage(self):
        f = self.tmp / "u16.url"
        f.write_text("[InternetShortcut]\nURL=https://kick.com/xqc\n", encoding="utf-16")
        self.assertEqual(inputs.link_from_url_file(f), "https://kick.com/xqc")
        bad = self.tmp / "bad.url"
        bad.write_text("URL=javascript:alert(1)", encoding="utf-8")
        self.assertIsNone(inputs.link_from_url_file(bad))
        self.assertIsNone(inputs.link_from_url_file(self.tmp / "absent.url"))

    def test_dropped_files_skip_unsupported_types(self):
        img = self.tmp / "a.png"
        img.write_bytes(b"\x89PNG")
        txt = self.tmp / "n.txt"
        txt.write_text("à voir : https://kick.com/xqc", encoding="utf-8")
        self.assertIsNone(inputs.links_from_paths(self.platforms, [img]))
        self.assertEqual(inputs.links_from_paths(self.platforms, [img, txt]), ("kick", "https://kick.com/xqc"))

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
        return backup.parse_backup(data, self.LANGS, self.KEYS)

    def test_roundtrip_keeps_settings_and_favorites(self):
        cfg = dict(core.DEFAULT_CONFIG, language="en", theme="dark", live_interval=10,
                   qualities={"twitch": "720p,best"}, hotkey_combo="alt+shift+s")
        favs = [{"channel": "zerator", "platform": "twitch", "added": "2026-01-01 10:00:00"}]
        data = backup.make_backup(cfg, favs, "1.2.0")
        settings, got = self.parse(json.loads(json.dumps(data)))
        self.assertEqual((settings["language"], settings["theme"], settings["live_interval"]), ("en", "dark", 10))
        self.assertEqual(settings["qualities"], {"twitch": "720p,best"})
        self.assertEqual(settings["hotkey_combo"], "alt+shift+s")
        self.assertEqual(got, favs)

    def test_machine_specific_paths_are_never_exported_or_imported(self):
        cfg = dict(core.DEFAULT_CONFIG, streamlink_path="C:/a.exe", player_path="C:/p.exe",
                   scripts_folder="C:/s", geometry="1x1+0+0")
        exported = backup.make_backup(cfg, [], "1")["settings"]
        for key in backup.MACHINE_KEYS:
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
        for data in ({}, [], "texte", {"foo": 1}, {"format": backup.BACKUP_FORMAT}):
            with self.assertRaises(backup.BackupError) as cm:
                self.parse(data)
            self.assertEqual(cm.exception.key, "err_backup_invalid")

    def test_read_backup_errors(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{pas du json", encoding="utf-8")
        with self.assertRaises(backup.BackupError) as cm:
            backup.read_backup(bad, self.LANGS, self.KEYS)
        self.assertEqual(cm.exception.key, "err_backup_read")
        with self.assertRaises(backup.BackupError):
            backup.read_backup(self.tmp / "absent.json", self.LANGS, self.KEYS)
        huge = self.tmp / "huge.json"
        huge.write_text('{"theme": "dark"}' + " " * backup.BACKUP_MAX_BYTES, encoding="utf-8")
        with self.assertRaises(backup.BackupError):
            backup.read_backup(huge, self.LANGS, self.KEYS)

    def test_merge_favorites_skips_duplicates(self):
        current = [{"channel": "a", "platform": "twitch"}]
        incoming = [{"channel": "a", "platform": "twitch", "added": "x"}, {"channel": "a", "platform": "kick"},
                    {"channel": "b", "platform": "twitch"}]
        merged, added = backup.merge_favorites(current, incoming)
        self.assertEqual(added, 2)
        self.assertEqual([(f["channel"], f["platform"]) for f in merged],
                         [("a", "twitch"), ("a", "kick"), ("b", "twitch")])

    def test_favorites_are_capped(self):
        many = [{"channel": f"c{i}", "platform": "twitch"} for i in range(backup.FAVORITES_MAX + 50)]
        self.assertEqual(len(backup.sanitize_favorites(many)), backup.FAVORITES_MAX)


SMALL_JPEG = (
    "/9j/4AAQSkZJRgABAQAAAAAAAAD/2wBDAAMCAgMCAgMDAwMEAwMEBQgFBQQEBQoHBwYIDAoMDAsKCwsNDhIQDQ4RDgsLEBYQERMU"
    "FRUVDA8XGBYUGBIUFRT/wAALCAAJABABAREA/8QAFAABAAAAAAAAAAAAAAAAAAAAAP/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAI"
    "AQEAAD8AAP/Z"
)


class TestLivePreviews(unittest.TestCase):
    def test_viewer_counts_follow_the_language(self):
        fr, en = core.I18n("fr"), core.I18n("en")
        self.assertEqual([fr.format_number(n) for n in (0, 999, 1000, 1234, 12345, 99999, 123456, 2_560_000)],
                         ["0", "999", "1 k", "1,2 k", "12,3 k", "99,9 k", "123 k", "2,5 M"])
        self.assertEqual(en.format_number(12345), "12.3K")
        self.assertEqual(fr.viewers(1), "1 spectateur")
        self.assertEqual(en.viewers(0), "0 viewers")
        for lang in core.available_languages():
            t = core.I18n(lang)
            self.assertIn("2", t.viewers(2_000_000))
            self.assertNotIn("{", t.viewers(1) + t.viewers(5000))

    def test_twitch_request_asks_for_preview(self):
        sent = {}

        def fake_http(url, payload, headers, timeout):
            sent.update(payload)
            return {"data": {"users": [
                {"login": "On", "stream": {"title": "T", "viewersCount": 42, "game": {"displayName": "G"},
                                           "previewImageURL": "https://static-cdn.jtvnw.net/p-640x360.jpg"}},
                {"login": "off", "stream": None}]}}
        with mock.patch.object(live, "_http_json", fake_http):
            res = live.twitch_live(["On", "off", "absent"])
        self.assertIn("previewImageURL(width:640,height:360)", sent["query"])
        self.assertEqual(res["on"], {"live": True, "title": "T", "game": "G", "viewers": 42,
                                     "preview": "https://static-cdn.jtvnw.net/p-640x360.jpg"})
        self.assertEqual(res["off"], live._offline())
        self.assertEqual(res["absent"], live._offline())

    def test_preview_url_is_https_only_and_refreshed(self):
        base = "https://static-cdn.jtvnw.net/previews-ttv/live_user_x-640x360.jpg"
        self.assertEqual(live.preview_url(base, now=600), base + "?t=2")
        self.assertEqual(live.preview_url(base + "?a=1", now=0), base + "?a=1&t=0")
        self.assertNotEqual(live.preview_url(base, now=0), live.preview_url(base, now=300))
        for bad in (None, "", "http://example.com/x.jpg", "file:///c:/x.jpg", "https://" + "a" * 600):
            self.assertIsNone(live.preview_url(bad))

    def test_fetch_previews_survives_errors(self):
        def fake(url, timeout=8):
            if "bad" in url:
                raise OSError("boom")
            return b"\xff\xd8data"
        with mock.patch.object(live, "fetch_image", fake):
            self.assertEqual(live.fetch_previews({"a": "https://ok", "b": "https://bad"}),
                             {"a": b"\xff\xd8data", "b": None})

    def test_setting_is_on_by_default_and_importable(self):
        self.assertIs(core.DEFAULT_CONFIG["live_previews"], True)
        self.assertEqual(backup.sanitize_settings({"live_previews": False}), {"live_previews": False})
        self.assertEqual(backup.sanitize_settings({"live_previews": "yes"}), {})


class TestThumb(unittest.TestCase):
    def setUp(self):
        from launcher import thumb
        self.thumb = thumb

    def test_png_is_valid(self):
        import struct
        import zlib
        w, h = 3, 2
        png = self.thumb.png_rgba(w, h, bytes(range(24)))
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(struct.unpack(">II", png[16:24]), (w, h))
        idat = png.index(b"IDAT")
        size = struct.unpack(">I", png[idat - 4:idat])[0]
        raw = zlib.decompress(png[idat + 4:idat + 4 + size])
        self.assertEqual(raw, b"\0" + bytes(range(12)) + b"\0" + bytes(range(12, 24)))

    def test_rounded_corners_are_transparent_and_smooth(self):
        w, h, r = 40, 20, 8
        rgba = self.thumb.round_corners(bytearray(b"\x10\x20\x30\xff" * (w * h)), w, h, r)
        alpha = lambda x, y: rgba[(y * w + x) * 4 + 3]
        for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
            self.assertEqual(alpha(x, y), 0)
        self.assertEqual(alpha(w // 2, h // 2), 255)
        self.assertEqual(alpha(r, 0), 255)
        self.assertTrue(any(0 < alpha(x, 1) < 255 for x in range(r)))  # bord lissé
                                                                       # smoothed edge
        self.assertEqual(rgba[0:3], b"\x10\x20\x30")  # couleurs intactes
                                                      # colors untouched

    def test_cover_box_crops_without_distortion(self):
        cb = self.thumb.cover_box
        self.assertEqual(cb(640, 360, 192, 108), (0, 0, 640, 360))
        self.assertEqual(cb(640, 360, 100, 100), (140, 0, 360, 360))
        self.assertEqual(cb(640, 360, 300, 100), (0, 73, 640, 213))

    def test_bgra_to_rgba_with_padding(self):
        buf = bytes([1, 2, 3, 4, 9, 9, 9, 9,
                     5, 6, 7, 8, 9, 9, 9, 9])  # 1 pixel par ligne, 4 octets de remplissage
                                               # 1 pixel per row, 4 padding bytes
        self.assertEqual(bytes(self.thumb.bgra_to_rgba(buf, 1, 2, 8)), bytes([3, 2, 1, 4, 7, 6, 5, 8]))

    def test_render_refuses_bad_input(self):
        self.assertIsNone(self.thumb.render(b"", 100, 50, 8))
        self.assertIsNone(self.thumb.render(b"\xff\xd8xx", 4, 4, 8))
        with mock.patch.object(self.thumb, "decode_scaled", side_effect=OSError("bad")):
            self.assertIsNone(self.thumb.render(b"\xff\xd8xx", 100, 50, 8))
        with mock.patch.object(self.thumb, "decode_scaled", return_value=b"\0" * 10):
            self.assertIsNone(self.thumb.render(b"\xff\xd8xx", 100, 50, 8))  # taille incohérente
                                                                             # inconsistent size
        with mock.patch.object(self.thumb, "decode_scaled", return_value=b"\xff" * (100 * 50 * 4)):
            self.assertTrue(self.thumb.render(b"\xff\xd8xx", 100, 50, 8).startswith(b"\x89PNG"))

    @unittest.skipUnless(os.name == "nt", "GDI+ : Windows uniquement")
    def test_gdiplus_decodes_a_real_jpeg(self):
        # JPEG 16x9 gris généré une fois (aucune dépendance) puis réduit en 8x4
        # 16x9 grey JPEG generated once (no dependency), then reduced to 8x4
        import base64
        jpeg = base64.b64decode(SMALL_JPEG)
        rgba = self.thumb.decode_scaled(jpeg, 8, 4)
        self.assertEqual(len(rgba), 8 * 4 * 4)
        self.assertTrue(all(a == 255 for a in rgba[3::4]))


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
                                  # before 1.0.2: exception at start-up
            self.assertEqual(store.favorites, [])


class TestAppUpdate(unittest.TestCase):
    """Mise à jour du lanceur depuis les releases GitHub.

    Launcher update from the GitHub releases."""
    SIZE = 1_500_000

    def api(self, **over):
        v = "9.9.9"
        data = {"tag_name": f"v{v}", "draft": False, "prerelease": False, "assets": [{
            "name": f"StreamlinkLauncher-{v}.exe", "size": self.SIZE, "digest": "sha256:" + "a" * 64,
            "browser_download_url": f"{updater.REPO_URL}/releases/download/v{v}/StreamlinkLauncher-{v}.exe"}]}
        data.update(over)
        return data

    def test_parse_release_ok(self):
        r = updater.parse_release(self.api())
        self.assertEqual(r["version"], "9.9.9")
        self.assertEqual(r["asset"]["sha256"], "a" * 64)
        self.assertTrue(r["page"].endswith("/releases/tag/v9.9.9"))

    def test_parse_release_rejects(self):
        self.assertIsNone(updater.parse_release(None))
        self.assertIsNone(updater.parse_release(self.api(draft=True)))
        self.assertIsNone(updater.parse_release(self.api(prerelease=True)))
        self.assertIsNone(updater.parse_release(self.api(tag_name="v9.9")))
        self.assertIsNone(updater.parse_release(self.api(tag_name="release-9")))

    def test_parse_release_asset_checks(self):
        def asset(**kw):
            d = self.api()
            d["assets"][0].update(kw)
            return updater.parse_release(d)["asset"]
        self.assertIsNone(asset(browser_download_url="https://evil.example/StreamlinkLauncher-9.9.9.exe"))
        self.assertIsNone(asset(digest=None))
        self.assertIsNone(asset(digest="sha1:" + "a" * 40))
        self.assertIsNone(asset(size=10))
        self.assertIsNone(asset(size=updater.UPDATE_MAX_BYTES + 1))
        self.assertIsNone(asset(size=True))
        self.assertIsNone(asset(name="Other.exe"))
        self.assertIsNotNone(asset())

    def test_check_app_update(self):
        with mock.patch.object(updater, "_http_get_json", return_value=self.api()):
            r = updater.check_app_update("1.0.0")
            self.assertTrue(r["update"])
            self.assertEqual(r["latest"], "9.9.9")
            self.assertFalse(updater.check_app_update("9.9.9")["update"])
            self.assertFalse(updater.check_app_update("10.0.0")["update"])

    def test_check_app_update_errors(self):
        import urllib.error
        e404 = urllib.error.HTTPError("u", 404, "nf", {}, None)
        with mock.patch.object(updater, "_http_get_json", side_effect=e404):
            self.assertEqual(updater.check_app_update("1.0.0")["error"], "release")
        with mock.patch.object(updater, "_http_get_json", side_effect=OSError("down")):
            r = updater.check_app_update("1.0.0")
            self.assertEqual((r["error"], r["update"]), ("network", None))
        with mock.patch.object(updater, "_http_get_json", return_value={"tag_name": "x"}):
            self.assertEqual(updater.check_app_update("1.0.0")["error"], "release")

    def test_safe_redirects(self):
        import urllib.error
        h = [x for x in updater._safe_opener().handlers if x.__class__.__name__ == "Redirect"][0]
        import urllib.request
        req = urllib.request.Request("https://github.com/x")
        for ok in ("https://objects.githubusercontent.com/a", "https://github.com/b", "https://api.github.com/c"):
            self.assertIsNotNone(h.redirect_request(req, None, 302, "", {}, ok))
        for bad in ("http://github.com/a", "https://evil.example/a", "https://github.com.evil.example/a",
                    "https://notgithub.com/a", "file:///etc/passwd"):
            with self.assertRaises(urllib.error.URLError):
                h.redirect_request(req, None, 302, "", {}, bad)

    # -- téléchargement
    # -- download
    def release(self, payload, size=None):
        import hashlib
        return {"asset": {"name": "StreamlinkLauncher-9.9.9.exe", "url": "https://x/y",
                          "size": len(payload) if size is None else size,
                          "sha256": hashlib.sha256(payload).hexdigest()}}

    class Resp:
        def __init__(self, data, fail_after=None):
            self.data, self.pos, self.fail_after = data, 0, fail_after

        def read(self, n):
            if self.fail_after is not None and self.pos >= self.fail_after:
                raise OSError("reset")
            chunk = self.data[self.pos:self.pos + n]
            self.pos += len(chunk)
            return chunk

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def dl(self, payload, release=None, **kw):
        d = Path(tempfile.mkdtemp())
        rel = release or self.release(payload)
        opener = kw.pop("opener", lambda url: self.Resp(payload))
        try:
            return d, updater.download_update(rel, d, opener=opener, **kw)
        except updater.UpdateError as e:
            return d, e

    def test_download_ok(self):
        payload = b"MZ" + b"\0" * 300_000
        seen = []
        d, r = self.dl(payload, progress=lambda a, b: seen.append((a, b)))
        self.assertEqual(r.read_bytes(), payload)
        self.assertEqual(seen[-1], (len(payload), len(payload)))

    def test_download_failures_leave_nothing(self):
        good = b"MZ" + b"\0" * 1000
        cases = {
            "app_err_hash": dict(release=dict(self.release(good), asset=dict(self.release(good)["asset"], sha256="0" * 64))),
            "app_err_download": dict(release=self.release(good, size=len(good) + 5)),
        }
        for key, kw in cases.items():
            d, e = self.dl(good, **kw)
            self.assertIsInstance(e, updater.UpdateError)
            self.assertEqual(e.key, key)
            self.assertEqual(list(d.iterdir()), [])
        d, e = self.dl(good, release=self.release(good, size=10))             # plus gros que annoncé
                                                                              # bigger than announced
        self.assertEqual(e.key, "app_err_hash")
        notpe = b"ZZ" + b"\0" * 1000
        d, e = self.dl(notpe)
        self.assertEqual(e.key, "app_err_hash")
        self.assertEqual(list(d.iterdir()), [])
        d, e = self.dl(good, opener=lambda url: self.Resp(good, fail_after=100))
        self.assertEqual(e.key, "app_err_download")
        self.assertEqual(list(d.iterdir()), [])

    def test_download_network_and_cancel(self):
        def boom(url):
            raise OSError("down")
        d, e = self.dl(b"MZ", opener=boom)
        self.assertEqual(e.key, "app_err_network")
        import threading
        ev = threading.Event()
        ev.set()
        d, e = self.dl(b"MZ" + b"\0" * 100, cancel=ev)
        self.assertEqual(e.key, "app_err_cancelled")
        self.assertEqual(list(d.iterdir()), [])
        with self.assertRaises(updater.UpdateError):
            updater.download_update({"asset": None}, tempfile.mkdtemp())

    # -- signature
    def test_parse_authenticode(self):
        self.assertEqual(updater._parse_authenticode("Valid|CN=SignPath Foundation, O=SignPath\n"),
                         ("Valid", "CN=SignPath Foundation, O=SignPath"))
        self.assertEqual(updater._parse_authenticode("NotSigned|"), ("NotSigned", None))
        self.assertEqual(updater._parse_authenticode(""), ("error", None))

    def test_check_signature(self):
        def run(cur, new):
            return updater.check_signature("c", "n", probe=lambda f: cur if f == "c" else new)
        v = ("Valid", "CN=Me, O=X")
        self.assertIsNone(run(v, ("Valid", "CN=Me, O=Y")))
        self.assertEqual(run(v, ("Valid", "CN=Other")), "app_err_signature")
        self.assertEqual(run(v, ("NotSigned", None)), "app_err_signature")      # pas de retour en arrière
                                                                                # no going back
        self.assertEqual(run(v, ("HashMismatch", "CN=Me")), "app_err_signature")
        self.assertEqual(run(v, ("error", None)), "app_err_signature")
        unsigned = ("NotSigned", None)
        self.assertIsNone(run(unsigned, ("NotSigned", None)))
        self.assertIsNone(run(unsigned, v))
        self.assertIsNone(run(unsigned, ("error", None)))
        self.assertEqual(run(unsigned, ("HashMismatch", "CN=Me")), "app_err_signature")

    # -- installation
    def test_install_update(self):
        d = Path(tempfile.mkdtemp())
        exe, new = d / "app.exe", d / "app.exe.download"
        exe.write_bytes(b"old")
        new.write_bytes(b"new")
        (d / "app.exe.old").write_bytes(b"stale")
        old = updater.install_update(new, exe)
        self.assertEqual(exe.read_bytes(), b"new")
        self.assertEqual(old.read_bytes(), b"old")
        self.assertFalse(new.exists())

    def test_target_exe(self):
        t = updater.target_exe
        self.assertEqual(t("C:/x/StreamlinkLauncher-1.4.1.exe", "1.4.1", "1.4.2"), Path("C:/x/StreamlinkLauncher-1.4.2.exe"))
        self.assertEqual(t("C:/x/slink.exe", "1.4.1", "1.4.2"), Path("C:/x/slink.exe"))
        self.assertEqual(t("C:/x/App-11.4.1.exe", "1.4.1", "1.4.2"), Path("C:/x/App-11.4.1.exe"))
        d = Path(tempfile.mkdtemp())
        (d / "StreamlinkLauncher-1.4.2.exe").write_bytes(b"x")  # déjà pris : on garde le nom actuel
                                                                # already taken: the current name is kept
        cur = d / "StreamlinkLauncher-1.4.1.exe"
        self.assertEqual(t(cur, "1.4.1", "1.4.2"), cur)

    def test_install_update_renamed(self):
        d = Path(tempfile.mkdtemp())
        exe, new, final = d / "app-1.exe", d / "app-1.exe.download", d / "app-2.exe"
        exe.write_bytes(b"old")
        new.write_bytes(b"new")
        old = updater.install_update(new, exe, final)
        self.assertEqual(final.read_bytes(), b"new")
        self.assertFalse(exe.exists())
        self.assertEqual(old, d / "app-1.exe.old")
        self.assertEqual(old.read_bytes(), b"old")

    def test_autostart_command_uses_given_exe(self):
        from launcher import wintray
        with mock.patch.object(sys, "frozen", True, create=True):
            self.assertEqual(wintray.autostart_command("", "", exe="C:/x/new.exe"), '"C:/x/new.exe" --tray')

    def test_install_update_rollback(self):
        d = Path(tempfile.mkdtemp())
        exe = d / "app.exe"
        exe.write_bytes(b"old")
        with self.assertRaises(updater.UpdateError) as cm:
            updater.install_update(d / "missing", exe)
        self.assertEqual(cm.exception.key, "app_err_install")
        self.assertEqual(exe.read_bytes(), b"old")
        self.assertFalse((d / "app.exe.old").exists())

    def test_cleanup(self):
        d = Path(tempfile.mkdtemp())
        exe = d / "StreamlinkLauncher-1.exe"
        exe.write_bytes(b"x")
        (d / (exe.name + ".old")).write_bytes(b"o")
        (d / "StreamlinkLauncher-2.exe.download").write_bytes(b"p")
        (d / "keep.txt").write_bytes(b"k")
        updater.cleanup_update_leftovers(exe)
        self.assertEqual(sorted(p.name for p in d.iterdir()), ["StreamlinkLauncher-1.exe", "keep.txt"])
        self.assertTrue(updater.cleanup_old_executable(exe, tries=1))

    def test_relaunch(self):
        with mock.patch.object(core.subprocess, "Popen") as popen:
            self.assertTrue(updater.relaunch("/x/app.exe", "1.0.0"))
        args, kw = popen.call_args
        self.assertEqual(args[0][0], "/x/app.exe")
        self.assertEqual(args[0][1:3], ["--wait-pid", str(os.getpid())])
        self.assertEqual(args[0][3:], ["--updated-from", "1.0.0"])
        self.assertEqual(kw["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        with mock.patch.object(core.subprocess, "Popen", side_effect=OSError):
            self.assertFalse(updater.relaunch("/x/app.exe"))

    def test_should_auto_update(self):
        res = {"update": True, "release": {"asset": {"name": "a"}}}
        cfg = {"auto_update": True, "update_check": True}
        ok = lambda c=cfg, r=res, u=None, can=True: updater.should_auto_update(c, r, u, can)
        self.assertTrue(ok())
        self.assertFalse(ok(c={**cfg, "auto_update": False}))
        self.assertFalse(ok(c={**cfg, "update_check": False}))
        self.assertFalse(ok(r={**res, "update": False}))
        self.assertFalse(ok(r={"update": True, "release": {"asset": None}}))
        self.assertFalse(ok(r=None))
        self.assertFalse(ok(can=False))
        self.assertFalse(ok(u="1.3.0"))               # vient d'être mis à jour : pas de boucle
                                                      # just updated: no loop
        self.assertFalse(core.DEFAULT_CONFIG["auto_update"])   # désactivé par défaut
                                                               # disabled by default

    def test_platform_colors_setting(self):
        self.assertTrue(core.DEFAULT_CONFIG["platform_colors"])
        self.assertEqual(backup.sanitize_settings({"platform_colors": False}).get("platform_colors"), False)
        self.assertNotIn("platform_colors", backup.sanitize_settings({"platform_colors": 1}))

    def test_auto_update_setting_is_validated(self):
        out = backup.sanitize_settings({"auto_update": True})
        self.assertEqual(out.get("auto_update"), True)
        self.assertNotIn("auto_update", backup.sanitize_settings({"auto_update": "oui"}))

    def test_relaunch_keeps_tray_argument(self):
        with mock.patch.object(core.subprocess, "Popen") as popen:
            updater.relaunch("/x/app.exe", "1.0.0", extra_args=("--tray",))
        self.assertIn("--tray", popen.call_args[0][0])

    def test_arg_value(self):
        self.assertEqual(updater.arg_value("--a", ["p", "--a", "1"]), "1")
        self.assertIsNone(updater.arg_value("--a", ["p", "--a"]))
        self.assertIsNone(updater.arg_value("--b", ["p", "--a", "1"]))

    def test_self_update_needs_frozen_exe(self):
        self.assertFalse(updater.can_self_update())          # lancé depuis les sources
                                                          # started from the sources

    def test_wait_for_pid_off_windows(self):
        from launcher import wintray
        if os.name != "nt":
            self.assertTrue(wintray.wait_for_pid(os.getpid(), timeout=0.1))

    def test_format_size(self):
        for lang, sep in (("en", "."), ("fr", ",")):
            t = core.I18n(lang)
            self.assertIn(f"1{sep}5", t.format_size(1_572_864))


class TestWingetManifest(unittest.TestCase):
    def test_manifests(self):
        sys.path.insert(0, str(ROOT / "packaging" / "winget"))
        import make_manifest
        m = make_manifest.manifests("1.4.0", "https://github.com/x/y/releases/download/v1.4.0/a.exe", "AB" * 32, "2026-10-14")
        self.assertEqual(len(m), 3)
        for text in m.values():
            self.assertIn("PackageIdentifier: Bulls64.StreamlinkLauncher", text)
            self.assertIn("PackageVersion: 1.4.0", text)
        installer = m["Bulls64.StreamlinkLauncher.installer.yaml"]
        self.assertIn("InstallerType: portable", installer)
        self.assertIn("InstallerSha256: " + "AB" * 32, installer)


if __name__ == "__main__":
    unittest.main()
