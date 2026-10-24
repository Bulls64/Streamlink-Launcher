"""Logique sans interface : chemins, configuration, langues, plateformes, historique, favoris, lancement.
Le reste est dans inputs (saisies et liens), backup (export / import), updater (mises à jour) et live (lives).

Logic without interface: paths, configuration, languages, platforms, history, favorites, launch.
The rest is in inputs (input and links), backup (export / import), updater (updates) and live (live status)."""
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
from datetime import datetime
from pathlib import Path

# ---------------------
# Chemins (tout est relatif au dossier du lanceur)
# Paths (everything is relative to the launcher's folder)
# ---------------------
# Version empaquetée (.exe) : les données restent à côté de l'exécutable, les ressources sont embarquées.
# Packaged version (.exe): the data stays next to the executable, the resources are embedded.
FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
RES_DIR = Path(getattr(sys, "_MEIPASS", BASE_DIR))


def _is_writable(folder):
    """Vrai si l'on peut créer un fichier dans ce dossier (faux p. ex. dans C:\\Program Files).

    True if a file can be created in this folder (false e.g. in C:\\Program Files)."""
    probe = Path(folder) / f".write_test_{os.getpid()}"
    try:
        probe.write_bytes(b"")
        probe.unlink()
        return True
    except OSError:
        return False


def _user_data_dir():
    """Dossier de repli pour les données quand le dossier du lanceur est protégé en écriture.

    Fallback folder for the data when the launcher's folder is write-protected."""
    if os.name == "nt":
        root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(root) / "Streamlink Launcher"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "streamlink-launcher"


# Version portable par défaut : les données restent à côté du lanceur. Si ce dossier est en lecture seule,
# elles vont dans %APPDATA%\Streamlink Launcher (au lieu de planter au démarrage).
# AppImage (Linux) : le dossier de l'application est en lecture seule, ou extrait dans un dossier temporaire
# (--appimage-extract-and-run) effacé à la fermeture : les données vont toujours dans ~/.config.
# Portable version by default: the data stays next to the launcher. If this folder is read-only,
# it goes to %APPDATA%\Streamlink Launcher (instead of crashing at start-up).
# AppImage (Linux): the application folder is read-only, or extracted to a temporary folder
# (--appimage-extract-and-run) deleted on exit: the data always goes to ~/.config.
APPIMAGE = bool(os.environ.get("APPIMAGE")) and not FROZEN and os.name != "nt"
PORTABLE = not APPIMAGE and _is_writable(BASE_DIR)
DATA_ROOT = BASE_DIR if PORTABLE else _user_data_dir()
CONFIG_FILE = DATA_ROOT / "config.json"
# platforms.json livré à côté du lanceur reste prioritaire, même en lecture seule (sauf dans l'AppImage,
# où il doit rester modifiable : il est créé dans le dossier des données)
# platforms.json shipped next to the launcher takes priority, even read-only (except in the AppImage,
# where it must stay editable: it is created in the data folder)
PLATFORMS_FILE = BASE_DIR / "platforms.json" if not APPIMAGE and (PORTABLE or (BASE_DIR / "platforms.json").exists()) \
    else DATA_ROOT / "platforms.json"
LOG_FILE = DATA_ROOT / "launcher.log"
LANG_DIR = BASE_DIR / "lang" if (BASE_DIR / "lang").is_dir() else RES_DIR / "lang"  # dossier lang/ modifiable prioritaire
                                                                                    # editable lang/ folder takes priority
DEFAULT_FOLDER = DATA_ROOT / "streams"
DATA_FOLDER = DEFAULT_FOLDER
HISTORY_FILE = DATA_FOLDER / "history.json"
FAV_FILE = DATA_FOLDER / "favorites.json"

SCRIPT_EXTENSIONS = (".bat", ".cmd", ".ps1", ".exe", ".py", ".lnk")
STREAMLINK_INSTALL_URL = "https://streamlink.github.io/install.html"
HISTORY_LIMIT = 200

DEFAULT_CONFIG = {
    "language": None,          # None = langue du système
                               # None = system language
    "theme": "auto",           # auto, light, dark
    "streamlink_path": "",     # vide = détection automatique
                               # empty = automatic detection
    "player": "default",       # default, vlc, mpv, potplayer, custom
    "player_path": "",
    "player_args": "",
    "show_scripts": False,
    "scripts_folder": str(DEFAULT_FOLDER),
    "qualities": {},
    "last_platform": "twitch",
    "geometry": "",
    "live_check": True,        # vérifier qui est en direct parmi les favoris
                               # check who is live among the favorites
    "live_interval": 5,        # minutes
    "live_notify": True,       # notification Windows au début d'un live
                               # Windows notification when a live starts
    "platform_colors": True,   # cartes de favoris teintées aux couleurs de leur plateforme
                               # favorite cards tinted with the colors of their platform
    "live_previews": True,     # aperçu, titre et spectateurs des favoris en direct (Twitch)
                               # preview, title and viewers of live favorites (Twitch)
    "tray": True,              # fermer la fenêtre = réduire dans la zone de notification (Windows)
                               # closing the window = minimize to the notification area (Windows)
    "hotkey": True,            # raccourci global qui ouvre le mode mini (Windows)
                               # global shortcut that opens the mini mode (Windows)
    "hotkey_combo": "ctrl+alt+s",
    "autostart": False,        # lancer au démarrage de Windows, réduit
                               # start with Windows, minimized
    "tray_hint_shown": False,
    "update_check": True,      # vérifier au démarrage si Streamlink et le lanceur sont à jour
                               # check at start-up whether Streamlink and the launcher are up to date
    "auto_update": False,      # installer seul, au démarrage, la mise à jour du lanceur (exécutable Windows)
                               # install the launcher update by itself at start-up (Windows executable)
    "clipboard_watch": True,   # proposer un lien de stream copié dans le presse-papiers
                               # offer a stream link copied to the clipboard
}

LIVE_INTERVALS = [2, 5, 10, 15, 30]
# Méthode de vérification par défaut (si platforms.json ne précise pas "live_check")
# Default check method (if platforms.json does not set "live_check")
LIVE_METHODS = {"twitch": "twitch", "kick": "streamlink"}

# Couleurs par défaut (utilisées si platforms.json n'en donne pas)
# Default colors (used if platforms.json does not give any)
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
# Error log (launcher.log, next to the data; 2 × 512 KB maximum)
# ---------------------
log = logging.getLogger("streamlink_launcher")
log.addHandler(logging.NullHandler())
_log_ready = False


def setup_logging():
    """Active l'écriture de launcher.log. Appelé une fois au démarrage ; sans effet si le dossier est inaccessible.

    Enables writing launcher.log. Called once at start-up; no effect if the folder is not accessible."""
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
# File problems to report to the interface: [(translation key, {variables})]
DATA_ISSUES = []
_issue_handler = None


def set_issue_handler(handler):
    """L'interface s'inscrit ici pour être prévenue d'un nouveau problème (appelé dans le thread de Tk).

    The interface registers here to be told about a new problem (called in the Tk thread)."""
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
    est signalé (DATA_ISSUES) au lieu d'être écrasé en silence au prochain enregistrement.

    Reads a JSON file. Missing or unreadable: returns default.
    With recover=True (config, favorites, history), an unreadable file (truncated file, power cut…):
    the file is set aside as .corrupt, the .bak backup is used if it exists, and the problem
    is reported (DATA_ISSUES) instead of being silently overwritten at the next save."""
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except OSError as e:  # fichier verrouillé, droits… : on ne touche pas au fichier
                          # locked file, permissions…: the file is left untouched
        log.warning("Lecture impossible de %s : %s", path, e)
        return default
    except ValueError as e:  # JSON invalide ou tronqué (UnicodeDecodeError compris)
                             # invalid or truncated JSON (UnicodeDecodeError included)
        log.warning("Fichier illisible %s : %s", path, e)
        if not recover:
            return default
    # Fichier de données présent mais illisible
    # Data file present but unreadable
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
    Renvoie True si l'écriture a réussi.

    Atomic write: temporary file, then replacement. The previous version is kept as .bak.
    Returns True if the write succeeded."""
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
# Languages
# ---------------------
def detect_system_language():
    try:
        name = locale.getlocale()[0] or ""
        if os.name != "nt":  # Linux : la langue d'affichage, même si la locale n'est pas générée sur la machine
                             # Linux: the display language, even if the locale is not generated on the machine
            name = next((os.environ[v] for v in ("LC_ALL", "LC_MESSAGES", "LANG")
                         if os.environ.get(v) and os.environ[v] not in ("C", "POSIX")), name)
        if os.name == "nt":
            import ctypes
            name = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), name)
        code = name.lower()[:2]
        return code if code in ("fr", "es", "de", "it") else "en"
    except Exception:
        return "fr"


def available_languages():
    """{code: nom affiché} d'après les fichiers présents dans lang/.

    {code: displayed name} from the files present in lang/."""
    langs = {}
    for f in sorted(LANG_DIR.glob("*.json")):
        langs[f.stem] = load_json(f, {}).get("_language_name", f.stem)
    return langs or {"fr": "Français"}


@functools.lru_cache(maxsize=2048)
def _parse_date(value):
    """Date de l'historique -> datetime (None si illisible). Mise en cache : les mêmes dates sont relues
    à chaque affichage de l'historique, des récents et des suggestions, et strptime est lent.

    History date -> datetime (None if unreadable). Cached: the same dates are read again
    each time the history, the recent items and the suggestions are shown, and strptime is slow."""
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
                                           # "/": a {key} variable remains possible in the texts
        text = self.strings.get(key) or self.fallback.get(key) or key
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    def format_date(self, value, now=None):
        """'2026-06-20 22:35:26' -> 'Aujourd'hui, 22:35' / '20 juin, 22:35' / '20 oct. 2025'.

        '2026-06-20 22:35:26' -> 'Today, 22:35' / '20 June, 22:35' / '20 Oct 2025'."""
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
        """12 -> '12', 1234 -> '1,2 k', 123456 -> '123 k', 2500000 -> '2,5 M' (arrondi vers le bas, selon la langue).

        12 -> '12', 1234 -> '1.2K', 123456 -> '123K', 2500000 -> '2.5M' (rounded down, according to the language)."""
        n = max(0, int(n))
        for div, key in ((1_000_000, "num_millions"), (1000, "num_thousands")):
            if n >= div:
                tenths = n * 10 // div
                text = str(tenths // 10) if tenths >= 1000 or tenths % 10 == 0 else f"{tenths // 10}.{tenths % 10}"
                return self(key, n=text.replace(".", self.get("decimal_sep") or ","))
        return str(n)

    def format_size(self, nbytes):
        """13790309 -> '13,2 Mo' (séparateur décimal et unité selon la langue).

        13790309 -> '13.2 MB' (decimal separator and unit according to the language)."""
        return self("size_mb", size=f"{max(0, nbytes) / 1048576:.1f}".replace(".", self.get("decimal_sep") or ","))

    def viewers(self, n):
        """'1 spectateur', '12,3 k spectateurs'…

        '1 viewer', '12.3K viewers'…"""
        return self("viewers_one" if n == 1 else "viewers", count=self.format_number(n))


# ---------------------
# Plateformes
# Platforms
# ---------------------
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_platforms():
    """Renvoie (liste des plateformes, message d'erreur éventuel).

    Returns (list of platforms, error message if any)."""
    error = None
    if PLATFORMS_FILE.exists():
        try:
            with open(PLATFORMS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f).get("platforms", [])
        except Exception as e:
            raw, error = [], str(e)
    else:
        raw = DEFAULT_PLATFORMS
        bundled = BASE_DIR / "platforms.json"  # AppImage : copie modifiable du fichier livré (avec son aide)
                                               # AppImage: editable copy of the shipped file (with its help)
        try:
            data = json.loads(bundled.read_text(encoding="utf-8")) if bundled != PLATFORMS_FILE else None
            if isinstance(data, dict) and isinstance(data.get("platforms"), list):
                raw = data["platforms"]
        except (OSError, ValueError):
            data = None
        save_json(PLATFORMS_FILE, data if raw is not DEFAULT_PLATFORMS else {"platforms": DEFAULT_PLATFORMS})

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
    """Ancien format (avant le lot 2) : retrouve la plateforme d'après le nom du .bat.

    Old format (before batch 2): finds the platform from the name of the .bat."""
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


def build_script_command(path, arg):
    """Commande pour un script personnalisé (liste, sans shell=True).

    Command for a custom script (list, without shell=True)."""
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
                 # .lnk: opened via os.startfile, without arguments


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
    """Options --player / --player-args. Renvoie (options, joueur introuvable ou None).

    --player / --player-args options. Returns (options, player not found or None)."""
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
# History and favorites
# ---------------------
def target_key(entry):
    """Clé de plateforme (ou de script) d'une entrée d'historique/favori.

    Platform (or script) key of a history/favorite entry."""
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
                              # folder not accessible: start anyway, saving will report it
            log.error("Dossier de données inaccessible %s : %s", DATA_FOLDER, e)
        h = load_json(HISTORY_FILE, {"history": []}, recover=True)
        f = load_json(FAV_FILE, {"favorites": []}, recover=True)
        self.history = [e for e in (h.get("history") if isinstance(h, dict) else []) or [] if isinstance(e, dict)]
        self.favorites = [e for e in (f.get("favorites") if isinstance(f, dict) else []) or [] if isinstance(e, dict)]
        self._migrate_favorites()

    def _migrate_favorites(self):
        """Anciens favoris sans plateforme : on la retrouve dans l'historique, sinon Twitch (comportement d'avant).

        Old favorites without a platform: it is found in the history, otherwise Twitch (previous behavior)."""
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
        """Dernières entrées, sans doublon (même chaîne sur la même plateforme).

        Latest entries, without duplicates (same channel on the same platform)."""
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
        """Favoris puis historique dont le nom contient le texte (le début d'abord).

        Favorites, then history, whose name contains the text (those starting with it first)."""
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
# Streams en cours
# Running streams
# ---------------------
class StreamManager:
    """Lance Streamlink, lit sa sortie dans des threads et la transmet via une file.

    Starts Streamlink, reads its output in threads and passes it on through a queue."""

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
