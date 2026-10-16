"""Logique sans interface : configuration, plateformes, saisie, historique, favoris, lancement."""
import functools
import json
import locale
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# ---------------------
# Chemins (tout est relatif au dossier du lanceur)
# ---------------------
# Version empaquetée (.exe) : les données restent à côté de l'exécutable, les ressources sont embarquées.
FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
RES_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))


def _is_writable(folder):
    """Vrai si l'on peut créer un fichier dans ce dossier (faux p. ex. dans C:\\Program Files)."""
    probe = Path(folder) / f".write_test_{os.getpid()}"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def _user_data_dir():
    """Dossier de repli pour les données quand le dossier du lanceur est protégé en écriture."""
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / "Streamlink Launcher"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "streamlink-launcher"


# Version portable par défaut : les données restent à côté du lanceur. Si ce dossier est en lecture seule,
# elles vont dans %APPDATA%\Streamlink Launcher (au lieu de planter au démarrage).
PORTABLE = _is_writable(BASE_DIR)
DATA_ROOT = BASE_DIR if PORTABLE else _user_data_dir()
CONFIG_FILE = DATA_ROOT / "config.json"
# platforms.json livré à côté du lanceur reste prioritaire, même en lecture seule
PLATFORMS_FILE = BASE_DIR / "platforms.json" if PORTABLE or (BASE_DIR / "platforms.json").exists() \
    else DATA_ROOT / "platforms.json"
LOG_FILE = DATA_ROOT / "launcher.log"
LANG_DIR = BASE_DIR / "lang" if (BASE_DIR / "lang").is_dir() else RES_DIR / "lang"  # dossier lang/ modifiable prioritaire
DEFAULT_FOLDER = DATA_ROOT / "streams"
DATA_FOLDER = DEFAULT_FOLDER
HISTORY_FILE = DATA_FOLDER / "history.json"
FAV_FILE = DATA_FOLDER / "favorites.json"

SCRIPT_EXTENSIONS = (".bat", ".cmd", ".ps1", ".exe", ".py", ".lnk")
STREAMLINK_INSTALL_URL = "https://streamlink.github.io/install.html"
HISTORY_LIMIT = 200

DEFAULT_CONFIG = {
    "language": None,          # None = langue du système
    "theme": "auto",           # auto, light, dark
    "streamlink_path": "",     # vide = détection automatique
    "player": "default",       # default, vlc, mpv, potplayer, custom
    "player_path": "",
    "player_args": "",
    "show_scripts": False,
    "scripts_folder": str(DEFAULT_FOLDER),
    "qualities": {},
    "last_platform": "twitch",
    "geometry": "",
    "live_check": True,        # vérifier qui est en direct parmi les favoris
    "live_interval": 5,        # minutes
    "live_notify": True,       # notification Windows au début d'un live
    "platform_colors": True,   # cartes de favoris teintées aux couleurs de leur plateforme
    "live_previews": True,     # aperçu, titre et spectateurs des favoris en direct (Twitch)
    "tray": True,              # fermer la fenêtre = réduire dans la zone de notification (Windows)
    "hotkey": True,            # raccourci global qui ouvre le mode mini (Windows)
    "hotkey_combo": "ctrl+alt+s",
    "autostart": False,        # lancer au démarrage de Windows, réduit
    "tray_hint_shown": False,
    "update_check": True,      # vérifier au démarrage si Streamlink et le lanceur sont à jour
    "auto_update": False,      # installer seul, au démarrage, la mise à jour du lanceur (exécutable Windows)
    "clipboard_watch": True,   # proposer un lien de stream copié dans le presse-papiers
}

LIVE_INTERVALS = [2, 5, 10, 15, 30]
# Méthode de vérification par défaut (si platforms.json ne précise pas "live_check")
LIVE_METHODS = {"twitch": "twitch", "kick": "streamlink"}

# Couleurs par défaut (utilisées si platforms.json n'en donne pas)
PLATFORM_STYLE = {
    "twitch": {"color": "#9146FF", "text_color": "#FFFFFF"},
    "kick": {"color": "#53FC18", "text_color": "#0B0D0A"},
    "youtube": {"color": "#D91A1A", "text_color": "#FFFFFF"},
    "dailymotion": {"color": "#0A6CFF", "text_color": "#FFFFFF"},
    "steamtv": {"color": "#66C0F4", "text_color": "#0B1A26"},
    "url": {"color": "#6B7180", "text_color": "#FFFFFF", "name_key": "platform_url"},
}
NEUTRAL_STYLE = {"color": "#6B7180", "text_color": "#FFFFFF"}

DEFAULT_PLATFORMS = [
    {"id": "twitch", "name": "Twitch", "input": "channel", "url": "https://www.twitch.tv/{arg}",
     "hosts": ["twitch.tv"], "args": ["--twitch-disable-ads"],
     "qualities": ["best", "1080p60", "720p60", "720p", "480p", "360p", "160p", "audio_only", "worst"],
     "default_quality": "best", "color": "#9146FF", "text_color": "#FFFFFF"},
    {"id": "kick", "name": "Kick", "input": "channel", "url": "https://kick.com/{arg}",
     "hosts": ["kick.com"], "args": [],
     "qualities": ["best", "1080p60", "720p60", "480p30", "360p30", "160p30", "worst"],
     "default_quality": "best", "color": "#53FC18", "text_color": "#0B0D0A"},
    {"id": "youtube", "name": "YouTube", "input": "youtube", "url": "https://www.youtube.com/watch?v={arg}",
     "hosts": ["youtube.com", "youtu.be"], "args": [],
     "qualities": ["best", "1080p", "720p", "480p", "360p", "worst"], "default_quality": "1080p",
     "color": "#D91A1A", "text_color": "#FFFFFF"},
    {"id": "dailymotion", "name": "Dailymotion", "input": "video", "url": "https://www.dailymotion.com/video/{arg}",
     "hosts": ["dailymotion.com", "dai.ly"], "args": [],
     "qualities": ["best", "1080p", "720p", "480p", "380p", "240p", "worst"], "default_quality": "best",
     "color": "#0A6CFF", "text_color": "#FFFFFF"},
    {"id": "steamtv", "name": "Steam TV", "input": "none", "url": "https://steam.tv", "history_name": "steam.tv",
     "hosts": ["steam.tv"], "args": [], "qualities": ["best", "worst"], "default_quality": "best",
     "color": "#66C0F4", "text_color": "#0B1A26"},
    {"id": "url", "name": "Direct link", "name_key": "platform_url", "input": "url", "url": "{arg}",
     "hosts": [], "args": [], "qualities": ["best", "1080p", "720p", "480p", "worst", "audio_only"],
     "default_quality": "best", "color": "#6B7180", "text_color": "#FFFFFF"},
]

PLAYERS = ["default", "mpv", "vlc", "potplayer", "custom"]
PLAYER_NAMES = {"vlc": "VLC", "mpv": "mpv", "potplayer": "PotPlayer"}
PLAYER_CANDIDATES = {
    "vlc": ["vlc", r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"],
    "mpv": ["mpv", r"C:\Program Files\mpv\mpv.exe"],
    "potplayer": ["PotPlayerMini64", r"C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe",
                  r"C:\Program Files (x86)\DAUM\PotPlayer\PotPlayerMini.exe"],
}
STREAMLINK_CANDIDATES = [
    "streamlink",
    r"C:\Program Files\Streamlink\bin\streamlink.exe",
    r"C:\Program Files (x86)\Streamlink\bin\streamlink.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Streamlink\bin\streamlink.exe"),
]


# ---------------------
# JSON
# ---------------------
# ---------------------
# Journal des erreurs (launcher.log, à côté des données ; 2 × 512 Ko maximum)
# ---------------------
log = logging.getLogger("streamlink_launcher")
log.addHandler(logging.NullHandler())
_log_ready = False


def setup_logging():
    """Active l'écriture de launcher.log. Appelé une fois au démarrage ; sans effet si le dossier est inaccessible."""
    global _log_ready
    if _log_ready:
        return
    _log_ready = True
    try:
        from logging.handlers import RotatingFileHandler
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
    except OSError:
        pass


# Problèmes de fichiers à signaler à l'interface : [(clé de traduction, {variables})]
DATA_ISSUES = []
_issue_handler = None


def set_issue_handler(handler):
    """L'interface s'inscrit ici pour être prévenue d'un nouveau problème (appelé dans le thread de Tk)."""
    global _issue_handler
    _issue_handler = handler


def _add_issue(key, **kwargs):
    issue = (key, kwargs)
    if issue not in DATA_ISSUES:
        DATA_ISSUES.append(issue)
    if _issue_handler:
        _issue_handler()


# ---------------------
# JSON
# ---------------------
def load_json(path, default, recover=False):
    """Lit un fichier JSON. Absent ou illisible : renvoie default.
    Avec recover=True (config, favoris, historique), un fichier illisible (fichier tronqué, coupure de courant…) :
    le fichier est mis de côté en .corrupt, la sauvegarde .bak est utilisée si elle existe, et le problème
    est signalé (DATA_ISSUES) au lieu d'être écrasé en silence au prochain enregistrement."""
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except OSError as e:  # fichier verrouillé, droits… : on ne touche pas au fichier
        log.warning("Lecture impossible de %s : %s", path, e)
        return default
    except ValueError as e:  # JSON invalide ou tronqué (UnicodeDecodeError compris)
        log.warning("Fichier illisible %s : %s", path, e)
        if not recover:
            return default
    # Fichier de données présent mais illisible
    backup = path.with_name(path.name + ".bak")
    corrupt = path.with_name(f"{path.name}.{datetime.now():%Y%m%d-%H%M%S}.corrupt")
    try:
        os.replace(path, corrupt)
    except OSError as e:
        log.warning("Impossible de mettre %s de côté : %s", path, e)
        corrupt = None
    try:
        with open(backup, "r", encoding="utf-8") as f:
            data = json.load(f)
        _add_issue("data_restored", file=path.name)
        log.warning("%s restauré depuis %s", path.name, backup.name)
        save_json(path, data)
        return data
    except (OSError, ValueError):
        _add_issue("data_unreadable", file=path.name, saved=corrupt.name if corrupt else "-")
        return default


def save_json(path, data):
    """Écriture atomique : fichier temporaire puis remplacement. La version précédente est gardée en .bak.
    Renvoie True si l'écriture a réussi."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            try:
                shutil.copy2(path, path.with_name(path.name + ".bak"))
            except OSError as e:
                log.warning("Sauvegarde .bak impossible pour %s : %s", path.name, e)
        os.replace(tmp, path)
        return True
    except (OSError, TypeError, ValueError) as e:
        log.error("Enregistrement impossible de %s : %s", path, e)
        _add_issue("save_failed", file=path.name)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    saved = load_json(CONFIG_FILE, {}, recover=True)
    if isinstance(saved, dict):
        cfg.update(saved)
    cfg["qualities"] = dict(cfg.get("qualities") or {})
    if cfg.get("theme") not in ("auto", "light", "dark"):
        cfg["theme"] = "auto"
    if cfg.get("live_interval") not in LIVE_INTERVALS:
        cfg["live_interval"] = DEFAULT_CONFIG["live_interval"]
    return cfg


def save_config(cfg):
    save_json(CONFIG_FILE, cfg)


# ---------------------
# Langues
# ---------------------
def detect_system_language():
    try:
        name = locale.getlocale()[0] or ""
        if os.name == "nt":
            import ctypes
            name = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), name)
        code = name.lower()[:2]
        return code if code in ("fr", "es", "de", "it") else "en"
    except Exception:
        return "fr"


def available_languages():
    """{code: nom affiché} d'après les fichiers présents dans lang/."""
    langs = {}
    for f in sorted(LANG_DIR.glob("*.json")):
        langs[f.stem] = load_json(f, {}).get("_language_name", f.stem)
    return langs or {"fr": "Français"}


@functools.lru_cache(maxsize=2048)
def _parse_date(value):
    """Date de l'historique -> datetime (None si illisible). Mise en cache : les mêmes dates sont relues
    à chaque affichage de l'historique, des récents et des suggestions, et strptime est lent."""
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


class I18n:
    def __init__(self, lang):
        self.set(lang)

    def set(self, lang):
        self.lang = lang
        self.strings = load_json(LANG_DIR / f"{lang}.json", {})
        self.fallback = load_json(LANG_DIR / "fr.json", {}) if lang != "fr" else {}

    def get(self, key, default=None):
        return self.strings.get(key, self.fallback.get(key, default))

    def __call__(self, key, /, **kwargs):  # « / » : une variable {key} reste possible dans les textes
        text = self.strings.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    def format_date(self, value, now=None):
        """'2026-06-20 22:35:26' -> 'Aujourd'hui, 22:35' / '20 juin, 22:35' / '20 oct. 2025'."""
        d = _parse_date(value) if isinstance(value, str) else None
        if d is None:
            return value or ""
        now = now or datetime.now()
        months = self.get("months_short") or ["jan.", "fév.", "mars", "avr.", "mai", "juin",
                                               "juil.", "août", "sept.", "oct.", "nov.", "déc."]
        hm = d.strftime("%H:%M")
        delta = (now.date() - d.date()).days
        if delta == 0:
            return self("date_today", time=hm)
        if delta == 1:
            return self("date_yesterday", time=hm)
        if d.year == now.year:
            return self("date_same_year", day=d.day, month=months[d.month - 1], time=hm)
        return self("date_other_year", day=d.day, month=months[d.month - 1], year=d.year)

    def format_number(self, n):
        """12 -> '12', 1234 -> '1,2 k', 123456 -> '123 k', 2500000 -> '2,5 M' (arrondi vers le bas, selon la langue)."""
        n = max(0, int(n))
        for div, key in ((1_000_000, "num_millions"), (1000, "num_thousands")):
            if n >= div:
                tenths = n * 10 // div
                text = str(tenths // 10) if tenths >= 1000 or tenths % 10 == 0 else f"{tenths // 10}.{tenths % 10}"
                return self(key, n=text.replace(".", self.get("decimal_sep") or ","))
        return str(n)

    def format_size(self, nbytes):
        """13790309 -> '13,2 Mo' (séparateur décimal et unité selon la langue)."""
        return self("size_mb", size=f"{max(0, nbytes) / 1048576:.1f}".replace(".", self.get("decimal_sep") or ","))

    def viewers(self, n):
        """'1 spectateur', '12,3 k spectateurs'…"""
        return self("viewers_one" if n == 1 else "viewers", count=self.format_number(n))


# ---------------------
# Plateformes
# ---------------------
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_platforms():
    """Renvoie (liste des plateformes, message d'erreur éventuel)."""
    error = None
    if PLATFORMS_FILE.exists():
        try:
            with open(PLATFORMS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f).get("platforms", [])
        except Exception as e:
            raw, error = [], str(e)
    else:
        raw = DEFAULT_PLATFORMS
        save_json(PLATFORMS_FILE, {"platforms": DEFAULT_PLATFORMS})

    platforms, seen = [], set()
    for p in raw:
        if not isinstance(p, dict) or not p.get("id") or not p.get("name") or not p.get("url") or p["id"] in seen:
            continue
        p = dict(p)
        style = PLATFORM_STYLE.get(p["id"], NEUTRAL_STYLE)
        p.setdefault("input", "channel")
        p.setdefault("hosts", [])
        p.setdefault("args", [])
        p["qualities"] = p.get("qualities") or ["best", "worst"]
        p.setdefault("default_quality", p["qualities"][0])
        for key in ("color", "text_color"):
            if not HEX_RE.match(str(p.get(key, ""))):
                p[key] = style[key]
        if "name_key" in style:
            p.setdefault("name_key", style["name_key"])
        seen.add(p["id"])
        platforms.append(p)
    if not platforms:
        platforms = [dict(p) for p in DEFAULT_PLATFORMS]
    return platforms, error


def platform_from_script(script_name):
    """Ancien format (avant le lot 2) : retrouve la plateforme d'après le nom du .bat."""
    stem = Path(script_name or "").stem.lower()
    for prefix, pid in (("twitch", "twitch"), ("kick", "kick"), ("youtube", "youtube"), ("yt", "youtube"),
                        ("steam", "steamtv"), ("dailymotion", "dailymotion")):
        if stem.startswith(prefix):
            return pid
    return None


def list_scripts(folder):
    try:
        return sorted((f for f in os.listdir(folder) if f.lower().endswith(SCRIPT_EXTENSIONS)), key=str.lower)
    except OSError:
        return []


# ---------------------
# Validation des entrées
# ---------------------
class InputError(Exception):
    def __init__(self, key):
        super().__init__(key)
        self.key = key


CHANNEL_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")
URL_RE = re.compile(r"^https?://[^\s\"'<>]{3,2000}$", re.IGNORECASE)
QUALITY_RE = re.compile(r"^[A-Za-z0-9_+,-]{1,100}$")
SCRIPT_ARG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,200}$")


def _host_matches(url, hosts):
    host = urlparse(url).netloc.lower().split(":")[0]
    return any(host == h or host.endswith("." + h) for h in hosts)


def _as_url(text, hosts):
    """Transforme 'twitch.tv/xxx' en URL complète ; renvoie None si ce n'est pas une URL."""
    if "://" in text:
        return text
    low = text.lower()
    if any(low.startswith(h) or low.startswith("www." + h) or low.startswith("m." + h) for h in hosts):
        return "https://" + text
    return None


def _youtube_id(url):
    parsed = urlparse(url)
    if parsed.netloc.lower().endswith("youtu.be"):
        return parsed.path.strip("/").split("/")[0]
    query = parse_qs(parsed.query)
    if "v" in query:
        return query["v"][0]
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] in ("shorts", "live", "embed"):
        return parts[1]
    return ""


def resolve_target(platform, raw):
    """Renvoie (url à donner à Streamlink, valeur à garder dans l'historique).
    Lève InputError si la saisie est vide ou invalide."""
    kind = platform["input"]
    hosts = platform.get("hosts", [])
    text = (raw or "").strip()

    if kind == "none":
        return platform["url"], platform.get("history_name") or platform["name"]
    if not text:
        raise InputError("err_empty")
    if kind == "url":
        if not URL_RE.match(text):
            raise InputError("err_url")
        return text, text

    full = _as_url(text, hosts)
    if full and not URL_RE.match(full):
        raise InputError("err_url")

    if kind == "youtube":
        arg = _youtube_id(full) if full else re.split(r"[&?#]", text, maxsplit=1)[0]
        valid = bool(YOUTUBE_ID_RE.match(arg))
        error = "err_youtube"
    elif kind == "video":
        if full:
            parts = [p for p in urlparse(full).path.split("/") if p]
            arg = parts[parts.index("video") + 1] if "video" in parts[:-1] else (parts[-1] if parts else "")
        else:
            arg = text
        valid = bool(VIDEO_ID_RE.match(arg))
        error = "err_video"
    else:  # channel
        parts = [p for p in urlparse(full).path.split("/") if p] if full else [text]
        arg = parts[0] if len(parts) == 1 else ""
        valid = bool(CHANNEL_RE.match(arg))
        error = "err_channel"

    if valid:
        return platform["url"].replace("{arg}", arg), arg
    if full and _host_matches(full, hosts) and urlparse(full).path.strip("/"):
        return full, full
    raise InputError(error)


def detect_platform_in_text(platforms, text):
    """Si le texte est un lien, renvoie l'id de la plateforme correspondante (ou du lien direct)."""
    text = (text or "").strip()
    if not text:
        return None
    for p in platforms:
        hosts = p.get("hosts") or []
        if p["input"] == "url" or not hosts:
            continue
        full = _as_url(text, hosts)
        if full and _host_matches(full, hosts):
            return p["id"]
    if URL_RE.match(text):
        generic = next((p for p in platforms if p["input"] == "url"), None)
        return generic["id"] if generic else None
    return None


# --- Liens collés, copiés ou glissés dans l'application ------------------------
CLIPBOARD_MAX = 2000   # au-delà, le contenu du presse-papiers est ignoré (texte énorme)
_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>]{3,2000}", re.IGNORECASE)


def link_in_text(platforms, text):
    """Premier lien reconnu dans un texte -> (id de plateforme, lien) ou None.

    Les liens des plateformes connues passent avant un lien quelconque, et un texte sans
    lien (un simple mot, une phrase) ne donne rien : le presse-papiers n'est pas fouillé
    pour autre chose que des adresses.
    """
    text = (text or "").strip()
    if not text or len(text) > CLIPBOARD_MAX:
        return None
    candidates = _URL_IN_TEXT.findall(text)
    if not candidates and " " not in text and "\n" not in text:
        candidates = [text]          # « twitch.tv/zerator » sans https://
    generic = None
    for c in candidates:
        c = c.rstrip(".,;)]}")
        pid = detect_platform_in_text(platforms, c)
        if not pid:
            continue
        if any(p["id"] == pid and p["input"] != "url" for p in platforms):
            return pid, c
        generic = generic or (pid, c)
    return generic


def link_from_url_file(path):
    """Adresse contenue dans un raccourci Internet .url (INI) ou .webloc simple, sinon None."""
    try:
        if Path(path).stat().st_size > 64 * 1024:
            return None
        raw = Path(path).read_bytes()
    except OSError:
        return None
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeError:
            continue
    else:
        return None
    m = re.search(r"^\s*URL\s*=\s*(\S+)", text, re.IGNORECASE | re.MULTILINE)
    if not m:
        m = re.search(r"<string>\s*(https?://[^<\s]+)\s*</string>", text, re.IGNORECASE)
    return m.group(1) if m and URL_RE.match(m.group(1)) else None


def links_from_paths(platforms, paths):
    """Fichiers déposés (.url, .txt) -> premier lien reconnu, ou None."""
    for path in paths:
        suffix = Path(path).suffix.lower()
        if suffix == ".url":
            found = link_from_url_file(path)
        elif suffix in (".txt", ".webloc"):
            try:
                found = Path(path).read_text(encoding="utf-8", errors="ignore")[:CLIPBOARD_MAX]
            except OSError:
                found = None
        else:
            found = None
        hit = link_in_text(platforms, found) if found else None
        if hit:
            return hit
    return None


def clipboard_sequence():
    """Numéro de séquence du presse-papiers Windows (change à chaque copie), 0 ailleurs."""
    if os.name != "nt":
        return 0
    try:
        import ctypes
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except Exception:
        return 0


# --- Sauvegarde : export / import des réglages et des favoris ----------------
BACKUP_FORMAT = "streamlink-launcher-backup"
BACKUP_MAX_BYTES = 1024 * 1024
# Propres à l'ordinateur d'origine : jamais exportés, jamais importés. Surtout les chemins :
# un fichier reçu d'ailleurs ne doit pas pouvoir désigner un programme à lancer.
MACHINE_KEYS = ("streamlink_path", "player_path", "scripts_folder", "geometry", "tray_hint_shown")
PLAYER_CHOICES = ("default", "custom", *PLAYER_NAMES)
FAVORITES_MAX = 1000


class BackupError(Exception):
    """key : clé de traduction du message d'erreur."""

    def __init__(self, key):
        super().__init__(key)
        self.key = key


def make_backup(cfg, favorites, version):
    """Contenu du fichier d'export : réglages (sans les chemins de cet ordinateur) + favoris."""
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
    """Ne garde que les réglages connus, du bon type et dans les valeurs permises."""
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
    ou un favorites.json. Lève BackupError('err_backup_invalid') si rien n'est reconnu."""
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
    """Favoris actuels d'abord, puis ceux du fichier qui n'y sont pas déjà -> (liste, nombre ajouté)."""
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


def build_script_command(path, arg):
    """Commande pour un script personnalisé (liste, sans shell=True)."""
    path = str(path)
    args = [arg] if arg else []
    ext = Path(path).suffix.lower()
    if ext in (".bat", ".cmd"):
        return ["cmd", "/c", path, *args]
    if ext == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path, *args]
    if ext == ".py":
        python = (shutil.which("py") or shutil.which("python")) if FROZEN else sys.executable
        return [python, path, *args] if python else None
    if ext == ".exe":
        return [path, *args]
    return None  # .lnk : ouvert via os.startfile, sans argument


def find_executable(candidates):
    for c in candidates:
        if not c:
            continue
        found = shutil.which(c)
        if found:
            return found
        if os.path.isfile(c):
            return c
    return None


def find_streamlink(configured=""):
    if configured:
        return configured if os.path.isfile(configured) or shutil.which(configured) else None
    return find_executable(STREAMLINK_CANDIDATES)


def find_player(player):
    return find_executable(PLAYER_CANDIDATES.get(player, []))


def player_options(cfg):
    """Options --player / --player-args. Renvoie (options, joueur introuvable ou None)."""
    opts, missing = [], None
    player = cfg.get("player", "default")
    if player != "default":
        path = cfg.get("player_path") or find_player(player)
        if path:
            opts += ["--player", path]
        else:
            missing = player
    args = (cfg.get("player_args") or "").strip()
    if args:
        opts += ["--player-args", args]
    return opts, missing


# ---------------------
# Historique et favoris
# ---------------------
def target_key(entry):
    """Clé de plateforme (ou de script) d'une entrée d'historique/favori."""
    if entry.get("platform"):
        return entry["platform"]
    script = entry.get("script")
    if script:
        return platform_from_script(script) or ("script:" + script.lower())
    return None


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self):
        try:
            DATA_FOLDER.mkdir(parents=True, exist_ok=True)
        except OSError as e:  # dossier inaccessible : on démarre quand même, l'enregistrement le signalera
            log.error("Dossier de données inaccessible %s : %s", DATA_FOLDER, e)
        h = load_json(HISTORY_FILE, {"history": []}, recover=True)
        f = load_json(FAV_FILE, {"favorites": []}, recover=True)
        self.history = [e for e in (h.get("history") if isinstance(h, dict) else []) or [] if isinstance(e, dict)]
        self.favorites = [e for e in (f.get("favorites") if isinstance(f, dict) else []) or [] if isinstance(e, dict)]
        self._migrate_favorites()

    def _migrate_favorites(self):
        """Anciens favoris sans plateforme : on la retrouve dans l'historique, sinon Twitch (comportement d'avant)."""
        changed = False
        for fav in self.favorites:
            if fav.get("platform") or fav.get("script"):
                continue
            key = next((target_key(e) for e in self.history
                        if e.get("channel") == fav.get("channel") and target_key(e)
                        and not target_key(e).startswith("script:")), None)
            fav["platform"] = key or "twitch"
            changed = True
        if changed:
            self.save_favorites()

    def save_history(self):
        save_json(HISTORY_FILE, {"history": self.history})

    def save_favorites(self):
        save_json(FAV_FILE, {"favorites": self.favorites})

    def add_history(self, entry):
        entry = dict(entry, date=now_str())
        self.history.insert(0, entry)
        del self.history[HISTORY_LIMIT:]
        self.save_history()
        return entry

    def remove_history(self, entry):
        if entry in self.history:
            self.history.remove(entry)
            self.save_history()

    def clear_history(self):
        self.history = []
        self.save_history()

    def recents(self, count):
        """Dernières entrées, sans doublon (même chaîne sur la même plateforme)."""
        seen, out = set(), []
        for e in self.history:
            key = (e.get("channel", ""), target_key(e))
            if key in seen:
                continue
            seen.add(key)
            out.append(e)
            if len(out) >= count:
                break
        return out

    def is_favorite(self, entry):
        key = (entry.get("channel"), target_key(entry))
        return any((f.get("channel"), target_key(f)) == key for f in self.favorites)

    def add_favorite(self, entry):
        if self.is_favorite(entry):
            return None
        entry = dict(entry, added=now_str())
        self.favorites.insert(0, entry)
        self.save_favorites()
        return entry

    def remove_favorite(self, entry):
        if entry in self.favorites:
            index = self.favorites.index(entry)
            self.favorites.remove(entry)
            self.save_favorites()
            return index
        return None

    def restore_favorite(self, entry, index):
        self.favorites.insert(max(0, min(index, len(self.favorites))), entry)
        self.save_favorites()

    def suggestions(self, text, limit=5):
        """Favoris puis historique dont le nom contient le texte (le début d'abord)."""
        q = (text or "").strip().lower()
        if not q:
            return []
        out, seen = [], set()
        for source, items in (("favorite", self.favorites), ("history", self.history)):
            ranked = sorted((e for e in items if q in (e.get("channel") or "").lower()),
                            key=lambda e: not (e.get("channel") or "").lower().startswith(q))
            for e in ranked:
                key = (e.get("channel"), target_key(e))
                if key in seen or (e.get("channel") or "").lower() == q:
                    continue
                seen.add(key)
                out.append((source, e))
                if len(out) >= limit:
                    return out
        return out


# ---------------------
# Streamlink est-il à jour ?
# ---------------------
PYPI_URL = "https://pypi.org/pypi/streamlink/json"
WINDOWS_BUILDS_URL = "https://github.com/streamlink/windows-builds/releases/latest"
PIP_UPGRADE_CMD = "python -m pip install --upgrade streamlink"
VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def parse_version(text):
    """'streamlink 7.1.3' / '7.1.3-1' / '8.0.0+12.gabc' -> (7, 1, 3). None si introuvable."""
    m = VERSION_RE.search(text or "")
    if not m:
        return None
    return tuple(int(x or 0) for x in m.groups())


def version_text(text):
    v = parse_version(text)
    return ".".join(map(str, v)) if v else None


def streamlink_version(path, timeout=20):
    """Version installée (ex. '7.1.3'), ou None si Streamlink ne répond pas."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    out = subprocess.run([path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=timeout, creationflags=flags,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    return version_text((out.stdout or "") + " " + (out.stderr or ""))


def _http_get_json(url, timeout):
    import urllib.request  # chargé seulement au besoin
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_streamlink_version(timeout=8):
    """Dernière version stable publiée (PyPI, source officielle des versions de Streamlink)."""
    data = _http_get_json(PYPI_URL, timeout)
    return version_text(((data or {}).get("info") or {}).get("version"))


def install_kind(path):
    """'windows' pour l'installateur officiel (…\\Streamlink\\bin\\streamlink.exe), sinon 'pip'."""
    p = (path or "").replace("/", "\\").lower()
    return "windows" if "\\streamlink\\bin\\" in p or p.endswith("\\streamlink\\bin") else "pip"


def check_streamlink_update(streamlink_path=""):
    """Renvoie {path, installed, latest, update, kind, error} ; 'update' vaut None si on ne peut pas conclure."""
    path = find_streamlink(streamlink_path)
    result = {"path": path, "installed": None, "latest": None, "update": None, "kind": install_kind(path),
              "error": None}
    if not path:
        result["error"] = "missing"
        return result
    try:
        result["installed"] = streamlink_version(path)
    except Exception:
        result["installed"] = None
    try:
        result["latest"] = latest_streamlink_version()
    except Exception as e:
        log.warning("Vérification de mise à jour impossible : %s", e)
        result["error"] = "network"
    if result["installed"] and result["latest"]:
        result["update"] = parse_version(result["latest"]) > parse_version(result["installed"])
    elif not result["error"]:
        result["error"] = "version"
    return result


# ---------------------
# Mise à jour du lanceur (releases GitHub)
# ---------------------
REPO = "Bulls64/Streamlink-Launcher"
REPO_URL = f"https://github.com/{REPO}"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
UPDATE_TAG_RE = re.compile(r"^v(\d+\.\d+\.\d+)$")
SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")
UPDATE_MIN_BYTES, UPDATE_MAX_BYTES = 1_000_000, 100 * 1024 * 1024
OLD_SUFFIX = ".old"      # ancien exécutable, gardé le temps du redémarrage puis supprimé


class UpdateError(Exception):
    """Échec de mise à jour ; .key est la clé de traduction du message à afficher."""

    def __init__(self, key):
        super().__init__(key)
        self.key = key


def parse_release(data):
    """Réponse de l'API GitHub -> {version, tag, page, asset} ou None si elle ne convient pas.
    asset = {name, url, size, sha256} ou None quand la version n'a pas d'exécutable téléchargeable.
    Tout est contrôlé : seules une release publiée (ni brouillon ni préversion) et une adresse de
    téléchargement qui est exactement celle attendue sur ce dépôt sont acceptées."""
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    m = UPDATE_TAG_RE.match(tag)
    if not m:
        return None
    version = m.group(1)
    release = {"version": version, "tag": tag, "page": f"{REPO_URL}/releases/tag/{tag}", "asset": None}
    name = f"StreamlinkLauncher-{version}.exe"
    url = f"{REPO_URL}/releases/download/{tag}/{name}"
    for a in data.get("assets") or []:
        if not isinstance(a, dict) or a.get("name") != name:
            continue
        size, digest = a.get("size"), SHA256_RE.match(str(a.get("digest") or ""))
        if (a.get("browser_download_url") == url and digest and isinstance(size, int) and not isinstance(size, bool)
                and UPDATE_MIN_BYTES <= size <= UPDATE_MAX_BYTES):
            release["asset"] = {"name": name, "url": url, "size": size, "sha256": digest.group(1)}
    return release


def check_app_update(current=None):
    """Compare la version du lanceur à la dernière release publiée.
    Renvoie {current, latest, update, release, error} ; 'update' vaut None si on ne peut pas conclure."""
    if current is None:
        from . import __version__ as current
    result = {"current": current, "latest": None, "update": None, "release": None, "error": None}
    try:
        data = _http_get_json(RELEASES_API, 10)
    except Exception as e:
        log.warning("Recherche de mise à jour du lanceur impossible : %s", e)
        result["error"] = "release" if getattr(e, "code", None) == 404 else "network"
        return result
    release = parse_release(data)
    if release is None:
        result["error"] = "release"
        return result
    result.update(latest=release["version"], release=release,
                  update=parse_version(release["version"]) > parse_version(current))
    return result


def should_auto_update(cfg, result, updated_from=None, can_update=None):
    """Faut-il installer sans demander la mise à jour trouvée au démarrage ? Oui si l'option est active (avec la
    vérification au démarrage), si une version plus récente existe avec un fichier téléchargeable, si cet exécutable
    peut se remplacer, et si le lanceur ne vient pas lui-même d'être mis à jour (pas de boucle de mises à jour)."""
    if can_update is None:
        can_update = can_self_update()
    release = (result or {}).get("release") or {}
    return bool(cfg.get("auto_update") and cfg.get("update_check") and (result or {}).get("update")
                and release.get("asset") and can_update and not updated_from)


def can_self_update():
    """Vrai pour l'exécutable Windows dont le dossier est modifiable ; sinon, la page de la release s'ouvre."""
    if not (FROZEN and os.name == "nt"):
        return False
    exe = Path(sys.executable)
    return os.access(exe.parent, os.W_OK) and os.access(exe, os.W_OK)


def _safe_opener():
    """Ouvreur d'adresses qui refuse toute redirection hors de GitHub ou en clair (http)."""
    import urllib.error
    import urllib.request

    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            u = urlparse(newurl)
            host = (u.hostname or "").lower()
            if u.scheme != "https" or not (host == "github.com" or host.endswith((".github.com", ".githubusercontent.com"))):
                raise urllib.error.URLError(f"redirection refusée : {u.scheme}://{host}")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    return urllib.request.build_opener(Redirect)


def _open_download(url, timeout=20):
    import urllib.request
    return _safe_opener().open(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def download_update(release, dest_dir, progress=None, cancel=None, opener=None):
    """Télécharge l'exécutable de la release dans dest_dir et le contrôle : taille annoncée, empreinte SHA-256
    publiée par GitHub, en-tête d'exécutable Windows. Renvoie son chemin. Lève UpdateError, et le fichier
    partiel est alors supprimé. progress(octets_reçus, total) ; cancel : threading.Event."""
    import hashlib
    asset = (release or {}).get("asset")
    if not asset:
        raise UpdateError("app_err_release")
    dest = Path(dest_dir) / (asset["name"] + ".download")
    digest, done, ok = hashlib.sha256(), 0, False
    try:
        try:
            resp = (opener or _open_download)(asset["url"])
        except Exception as e:
            log.warning("Téléchargement impossible : %s", e)
            raise UpdateError("app_err_network") from e
        try:
            with resp, open(dest, "wb") as out:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise UpdateError("app_err_cancelled")
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > asset["size"]:
                        raise UpdateError("app_err_hash")
                    digest.update(chunk)
                    out.write(chunk)
                    if progress:
                        progress(done, asset["size"])
        except UpdateError:
            raise
        except Exception as e:
            log.warning("Téléchargement interrompu : %s", e)
            raise UpdateError("app_err_download") from e
        if done != asset["size"]:
            raise UpdateError("app_err_download")
        if digest.hexdigest() != asset["sha256"]:
            raise UpdateError("app_err_hash")
        with open(dest, "rb") as f:
            if f.read(2) != b"MZ":
                raise UpdateError("app_err_hash")
        ok = True
        return dest
    finally:
        if not ok:
            try:
                dest.unlink()
            except OSError:
                pass


def _parse_authenticode(text):
    """'Valid|CN=Nom, O=…' -> ('Valid', 'CN=Nom, O=…') ; sortie vide ou illisible -> ('error', None)."""
    lines = (text or "").strip().splitlines()
    status, _, subject = (lines[-1] if lines else "").partition("|")
    return (status.strip(), subject.strip() or None) if status.strip() else ("error", None)


def authenticode(path, timeout=40):
    """Signature d'un exécutable Windows : (statut, signataire). Statut : 'Valid', 'NotSigned', 'HashMismatch',
    'NotTrusted'… ou 'error' si PowerShell est indisponible."""
    if os.name != "nt":
        return "error", None
    try:
        script = "$s = Get-AuthenticodeSignature -LiteralPath $env:SL_FILE; '{0}|{1}' -f $s.Status, $s.SignerCertificate.Subject"
        out = subprocess.run([shutil.which("powershell") or "powershell", "-NoProfile", "-NonInteractive",
                              "-ExecutionPolicy", "Bypass", "-Command", script],
                             capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             env=dict(os.environ, SL_FILE=str(path)))
        return _parse_authenticode(out.stdout)
    except Exception as e:
        log.warning("Lecture de la signature impossible : %s", e)
        return "error", None


def _common_name(subject):
    m = re.search(r"CN=([^,]+)", subject or "")
    return (m.group(1) if m else subject or "").strip()


def check_signature(current_file, new_file, probe=None):
    """None si la nouvelle version peut être installée, sinon la clé du message d'erreur.
    Si l'application actuelle est signée (signature valide), la nouvelle doit l'être aussi, par le même
    signataire : impossible de revenir à une version non signée. Sinon, on refuse seulement une signature
    présente mais invalide (fichier modifié)."""
    probe = probe or authenticode
    cur_status, cur_subject = probe(current_file)
    new_status, new_subject = probe(new_file)
    if cur_status == "Valid":
        same = new_status == "Valid" and _common_name(new_subject) == _common_name(cur_subject)
        return None if same else "app_err_signature"
    return None if new_status in ("Valid", "NotSigned", "error") else "app_err_signature"


def target_exe(exe, old_version, new_version):
    """Chemin sous lequel installer la nouvelle version : si le nom de fichier contient l'ancien numéro
    (StreamlinkLauncher-1.4.1.exe), il prend le nouveau, pour que le nom ne mente pas. Sinon, inchangé."""
    exe = Path(exe)
    if not old_version or not new_version or old_version == new_version:
        return exe
    renamed = re.sub(r"(?<![\d.])" + re.escape(str(old_version)) + r"(?!\.?\d)", str(new_version), exe.name)
    target = exe.with_name(renamed)
    return target if renamed != exe.name and not target.exists() else exe


def install_update(new_file, exe=None, final=None):
    """Remplace l'exécutable : l'ancien est renommé en .old (Windows permet de renommer un exécutable en
    cours d'exécution, pas de l'écraser), le nouveau prend sa place (sous le nom `final` si donné, sinon
    celui de l'ancien). En cas d'échec, l'ancien est remis."""
    exe, new_file = Path(exe or sys.executable), Path(new_file)
    final = Path(final) if final else exe
    old = exe.with_name(exe.name + OLD_SUFFIX)
    try:
        old.unlink(missing_ok=True)
        os.replace(exe, old)
    except OSError as e:
        log.warning("Remplacement impossible : %s", e)
        raise UpdateError("app_err_install") from e
    try:
        os.replace(new_file, final)
    except OSError as e:
        log.warning("Remplacement impossible : %s", e)
        try:
            os.replace(old, exe)
        except OSError:
            log.error("L'ancien exécutable n'a pas pu être remis en place (%s)", old)
        raise UpdateError("app_err_install") from e
    return old


def cleanup_old_executable(exe=None, tries=30, delay=1.0):
    """Supprime l'ancien exécutable laissé par une mise à jour (réessaie : l'ancienne instance peut
    mettre quelques secondes à se fermer). Renvoie True si rien ne reste."""
    exe = Path(exe or sys.executable)
    old = exe.with_name(exe.name + OLD_SUFFIX)
    for _i in range(tries):
        if not old.exists():
            return True
        try:
            old.unlink()
            return True
        except OSError:
            time.sleep(delay)
    return False


def cleanup_update_leftovers(exe=None):
    """Au démarrage : ancien exécutable d'une mise à jour, et téléchargements interrompus."""
    exe = Path(exe or sys.executable)
    cleanup_old_executable(exe)
    for f in [*exe.parent.glob("StreamlinkLauncher-*.exe.download"),
              *exe.parent.glob("StreamlinkLauncher-*.exe" + OLD_SUFFIX)]:  # .old d'avant un renommage
        try:
            f.unlink()
        except OSError:
            pass


def relaunch(exe=None, old_version=None, extra_args=()):
    """Démarre la nouvelle version, détachée de ce processus ; elle attend sa fermeture (--wait-pid) avant de
    prendre le verrou d'instance unique. PYINSTALLER_RESET_ENVIRONMENT : sans cela, un exécutable
    PyInstaller lancé par lui-même réutiliserait le dossier temporaire de l'ancien, supprimé à sa fermeture."""
    exe = str(exe or sys.executable)
    args = [exe, "--wait-pid", str(os.getpid()), *extra_args]
    if old_version:
        args += ["--updated-from", str(old_version)]
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(args, cwd=os.path.dirname(exe), close_fds=True, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
        return True
    except OSError as e:
        log.error("Redémarrage impossible : %s", e)
        return False


def arg_value(name, argv=None):
    """Valeur qui suit l'option `name` sur la ligne de commande, ou None."""
    argv = sys.argv if argv is None else argv
    for i, a in enumerate(argv[:-1]):
        if a == name:
            return argv[i + 1]
    return None


# ---------------------
# Qui est en direct ?
# ---------------------
TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # identifiant public du site web Twitch (utilisé aussi par Streamlink)
TWITCH_LOGIN_RE = re.compile(r"^[A-Za-z0-9_]{1,25}$")
PREVIEW_SIZE = (640, 360)  # taille demandée à Twitch ; réduite ensuite à la taille de la carte
PREVIEW_MAX_BYTES = 2 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StreamlinkLauncher"


def live_method(platform):
    """'twitch', 'streamlink' ou 'none'."""
    method = platform.get("live_check") or LIVE_METHODS.get(platform["id"], "none")
    return method if method in ("twitch", "streamlink") else "none"


def _http_json(url, payload, headers, timeout):
    import urllib.request  # chargé seulement au besoin (économise la mémoire au démarrage)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _offline():
    return {"live": False, "title": None, "game": None, "viewers": None, "preview": None}


def twitch_live(logins, timeout=8):
    """Une seule requête pour toutes les chaînes Twitch : {login: info}."""
    logins = sorted({n.lower() for n in logins if TWITCH_LOGIN_RE.match(n or "")})
    result = {}
    query = ("query($logins:[String!]){users(logins:$logins){login stream{title viewersCount "
             "previewImageURL(width:%d,height:%d) game{displayName}}}}" % PREVIEW_SIZE)
    for i in range(0, len(logins), 100):
        chunk = logins[i:i + 100]
        data = _http_json(TWITCH_GQL_URL, {"query": query, "variables": {"logins": chunk}},
                          {"Client-ID": TWITCH_CLIENT_ID, "Content-Type": "application/json",
                           "User-Agent": USER_AGENT}, timeout)
        users = ((data or {}).get("data") or {}).get("users")
        if users is None:
            raise ValueError("réponse Twitch inattendue")
        found = {}
        for u in users:
            if u and u.get("login"):
                s = u.get("stream")
                found[u["login"].lower()] = {
                    "live": bool(s),
                    "title": (s or {}).get("title"),
                    "game": ((s or {}).get("game") or {}).get("displayName"),
                    "viewers": (s or {}).get("viewersCount"),
                    "preview": (s or {}).get("previewImageURL"),
                }
        for login in chunk:
            result[login] = found.get(login, _offline())
    return result


def streamlink_live(streamlink, url, timeout=30):
    """Vérifie via 'streamlink --json URL'. Renvoie info, ou None si inconnu (plugin absent, erreur réseau…)."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    out = subprocess.run([streamlink, "--json", url], capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=timeout, creationflags=flags,
                         env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    try:
        data = json.loads(out.stdout or "{}")
    except ValueError:
        return None
    if data.get("streams"):
        meta = data.get("metadata") or {}
        return {"live": True, "title": meta.get("title"), "game": meta.get("category"), "viewers": None,
                "preview": None}
    error = (data.get("error") or "").lower()
    if "no playable streams" in error:
        return _offline()
    return None


def check_live(entries, platforms, streamlink_path=""):
    """entries : [(chaîne, id_plateforme)]. Renvoie {(chaîne en minuscules, id): info ou None}."""
    by_id = {p["id"]: p for p in platforms}
    results = {}
    twitch = [(ch, pid) for ch, pid in entries if pid in by_id and live_method(by_id[pid]) == "twitch"]
    if twitch:
        try:
            states = twitch_live([ch for ch, _ in twitch])
            for ch, pid in twitch:
                results[(ch.lower(), pid)] = states.get(ch.lower())
        except Exception as e:
            log.warning("Statut Twitch indisponible : %s", e)
            for ch, pid in twitch:
                results[(ch.lower(), pid)] = None
    others = [(ch, pid) for ch, pid in entries if pid in by_id and live_method(by_id[pid]) == "streamlink"]
    streamlink = find_streamlink(streamlink_path) if others else None
    for ch, pid in others:
        info = None
        if streamlink:
            try:
                url, _ = resolve_target(by_id[pid], ch)
                info = streamlink_live(streamlink, url)
            except Exception as e:
                log.warning("Statut de %s (%s) indisponible : %s", ch, pid, e)
                info = None
        results[(ch.lower(), pid)] = info
    return results


def preview_url(url, now=None):
    """URL d'aperçu sûre (https uniquement), avec un paramètre qui change toutes les 5 minutes :
    le CDN de Twitch garde sinon longtemps la même image en cache. None si l'URL ne convient pas."""
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 500:
        return None
    stamp = int((now if now is not None else time.time()) // 300)
    return f"{url}{'&' if '?' in url else '?'}t={stamp}"


def fetch_image(url, timeout=8):
    """Télécharge une image (JPEG/PNG, 2 Mo maximum). Renvoie les octets, ou None."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(PREVIEW_MAX_BYTES + 1)
    if len(data) > PREVIEW_MAX_BYTES or not data.startswith((b"\xff\xd8", b"\x89PNG")):
        return None
    return data


def fetch_previews(urls):
    """{clé: url} -> {clé: octets ou None}. Une erreur sur une image n'empêche pas les autres."""
    out = {}
    for key, url in urls.items():
        try:
            out[key] = fetch_image(url)
        except Exception as e:
            log.info("Aperçu indisponible (%s) : %s", key, e)
            out[key] = None
    return out


# ---------------------
# Streams en cours
# ---------------------
class StreamManager:
    """Lance Streamlink, lit sa sortie dans des threads et la transmet via une file."""

    def __init__(self):
        self.streams = []
        self.events = queue.Queue()

    def start(self, command, info):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                env=env, creationflags=flags)
        stream = dict(info, proc=proc, started=datetime.now())
        self.streams.append(stream)
        threading.Thread(target=self._read, args=(stream,), daemon=True).start()
        return stream

    def _read(self, stream):
        proc = stream["proc"]
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.events.put(("line", stream, line))
        except Exception as e:
            log.warning("Lecture de la sortie de Streamlink interrompue : %s", e)
        self.events.put(("end", stream, proc.wait()))

    def poll(self):
        out = []
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "end" and event[1] in self.streams:
                    self.streams.remove(event[1])
                out.append(event)
        except queue.Empty:
            pass
        return out

    def running(self):
        return [s for s in self.streams if s["proc"].poll() is None]

    def busy(self):
        return bool(self.streams) or not self.events.empty()

    def stop(self, stream):
        try:
            stream["proc"].terminate()
        except Exception as e:
            log.warning("Arrêt du stream impossible : %s", e)

    def stop_all(self):
        for s in list(self.streams):
            self.stop(s)
