"""Sauvegarde : export et import des réglages et des favoris (fichier JSON vérifié).

Backup: export and import of the settings and favorites (checked JSON file)."""
import json
import re
from pathlib import Path

from .core import DEFAULT_CONFIG, LIVE_INTERVALS, PLAYER_NAMES, now_str, target_key
from .inputs import QUALITY_RE

# --- Sauvegarde : export / import des réglages et des favoris ----------------
# --- Backup: export / import of the settings and favorites ----------------
BACKUP_FORMAT = "streamlink-launcher-backup"
BACKUP_MAX_BYTES = 1024 * 1024
# Propres à l'ordinateur d'origine : jamais exportés, jamais importés. Surtout les chemins :
# un fichier reçu d'ailleurs ne doit pas pouvoir désigner un programme à lancer.
# Specific to the original computer: never exported, never imported. Above all the paths:
# a file received from elsewhere must not be able to designate a program to run.
MACHINE_KEYS = ("streamlink_path", "player_path", "scripts_folder", "geometry", "tray_hint_shown")
PLAYER_CHOICES = ("default", "custom", *PLAYER_NAMES)
FAVORITES_MAX = 1000


class BackupError(Exception):
    """key : clé de traduction du message d'erreur.

    key: translation key of the error message."""

    def __init__(self, key):
        super().__init__(key)
        self.key = key


def make_backup(cfg, favorites, version):
    """Contenu du fichier d'export : réglages (sans les chemins de cet ordinateur) + favoris.

    Content of the export file: settings (without this computer's paths) + favorites."""
    return {
        "format": BACKUP_FORMAT,
        "app_version": version,
        "exported": now_str(),
        "settings": {k: v for k, v in cfg.items() if k in DEFAULT_CONFIG and k not in MACHINE_KEYS},
        "favorites": [dict(f) for f in favorites],
    }


def _short_text(value, limit):
    return isinstance(value, str) and len(value) <= limit and not re.search(r"[\x00-\x1f]", value)


def sanitize_settings(raw, languages=(), hotkeys=()):
    """Ne garde que les réglages connus, du bon type et dans les valeurs permises.

    Keeps only the known settings, of the right type and within the allowed values."""
    out = {}
    if not isinstance(raw, dict):
        return out
    for key, default in DEFAULT_CONFIG.items():
        if key in MACHINE_KEYS or key not in raw:
            continue
        value = raw[key]
        if key == "language":
            ok = value in languages
        elif key == "theme":
            ok = value in ("auto", "light", "dark")
        elif key == "live_interval":
            ok = value in LIVE_INTERVALS and not isinstance(value, bool)
        elif key == "player":
            ok = value in PLAYER_CHOICES
        elif key == "hotkey_combo":
            ok = value in hotkeys
        elif key == "qualities":
            ok = isinstance(value, dict) and len(value) <= 100 and all(
                _short_text(k, 50) and isinstance(v, str) and QUALITY_RE.match(v) for k, v in value.items())
        elif key == "last_platform":
            ok = _short_text(value, 50) and bool(value)
        elif key == "player_args":
            ok = _short_text(value, 300)
        elif isinstance(default, bool):
            ok = isinstance(value, bool)
        else:
            ok = False
        if ok:
            out[key] = dict(value) if isinstance(value, dict) else value
    return out


def sanitize_favorites(raw):
    out = []
    for f in raw if isinstance(raw, list) else []:
        if not isinstance(f, dict):
            continue
        entry = {k: f[k] for k in ("channel", "platform", "script", "added")
                 if k in f and _short_text(f[k], 300)}
        if entry.get("platform") or entry.get("script"):
            out.append(entry)
        if len(out) >= FAVORITES_MAX:
            break
    return out


def parse_backup(data, languages=(), hotkeys=()):
    """Contenu d'un fichier JSON -> (réglages, favoris). Accepte une sauvegarde complète, un config.json
    ou un favorites.json. Lève BackupError('err_backup_invalid') si rien n'est reconnu.

    Content of a JSON file -> (settings, favorites). Accepts a full backup, a config.json
    or a favorites.json. Raises BackupError('err_backup_invalid') if nothing is recognized."""
    if not isinstance(data, dict):
        raise BackupError("err_backup_invalid")
    if data.get("format") == BACKUP_FORMAT:
        raw_settings, raw_favorites = data.get("settings"), data.get("favorites")
    else:
        raw_settings, raw_favorites = data, data.get("favorites")
    settings = sanitize_settings(raw_settings, languages, hotkeys)
    favorites = sanitize_favorites(raw_favorites)
    if not settings and not favorites:
        raise BackupError("err_backup_invalid")
    return settings, favorites


def read_backup(path, languages=(), hotkeys=()):
    try:
        if Path(path).stat().st_size > BACKUP_MAX_BYTES:
            raise BackupError("err_backup_read")
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise BackupError("err_backup_read") from None
    return parse_backup(data, languages, hotkeys)


def merge_favorites(current, incoming):
    """Favoris actuels d'abord, puis ceux du fichier qui n'y sont pas déjà -> (liste, nombre ajouté).

    Current favorites first, then those of the file that are not already there -> (list, number added)."""
    merged = list(current)
    seen = {(f.get("channel"), target_key(f)) for f in merged}
    added = 0
    for f in incoming:
        key = (f.get("channel"), target_key(f))
        if key not in seen:
            seen.add(key)
            merged.append(f)
            added += 1
    return merged, added
