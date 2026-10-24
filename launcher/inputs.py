"""Validation des saisies (chaînes, liens, qualité, arguments) et repérage des liens collés, copiés ou glissés.

Input validation (channels, links, quality, arguments) and detection of pasted, copied or dropped links."""
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


# ---------------------
# Validation des entrées
# Input validation
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
    """Transforme 'twitch.tv/xxx' en URL complète ; renvoie None si ce n'est pas une URL.

    Turns 'twitch.tv/xxx' into a full URL; returns None if it is not a URL."""
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
    Lève InputError si la saisie est vide ou invalide.

    Returns (URL to give to Streamlink, value to keep in the history).
    Raises InputError if the input is empty or invalid."""
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
    """Si le texte est un lien, renvoie l'id de la plateforme correspondante (ou du lien direct).

    If the text is a link, returns the id of the matching platform (or of the direct link)."""
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
# --- Links pasted, copied or dragged into the application ------------------------
CLIPBOARD_MAX = 2000   # au-delà, le contenu du presse-papiers est ignoré (texte énorme)
                       # beyond this, the clipboard content is ignored (huge text)
_URL_IN_TEXT = re.compile(r"https?://[^\s\"'<>]{3,2000}", re.IGNORECASE)


def link_in_text(platforms, text):
    """Premier lien reconnu dans un texte -> (id de plateforme, lien) ou None.

    Les liens des plateformes connues passent avant un lien quelconque, et un texte sans
    lien (un simple mot, une phrase) ne donne rien : le presse-papiers n'est pas fouillé
    pour autre chose que des adresses.

    First link recognized in a text -> (platform id, link) or None.

    Links of known platforms come before any other link, and a text without a
    link (a single word, a sentence) gives nothing: the clipboard is not searched
    for anything other than addresses.
    """
    text = (text or "").strip()
    if not text or len(text) > CLIPBOARD_MAX:
        return None
    candidates = _URL_IN_TEXT.findall(text)
    if not candidates and " " not in text and "\n" not in text:
        candidates = [text]          # « twitch.tv/zerator » sans https://
                                     # "twitch.tv/zerator" without https://
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
    """Adresse contenue dans un raccourci Internet .url (INI) ou .webloc simple, sinon None.

    Address contained in a .url Internet shortcut (INI) or a simple .webloc, otherwise None."""
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
    """Fichiers déposés (.url, .txt) -> premier lien reconnu, ou None.

    Dropped files (.url, .txt) -> first recognized link, or None."""
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
    """Numéro de séquence du presse-papiers Windows (change à chaque copie), 0 ailleurs.

    Windows clipboard sequence number (changes with each copy), 0 elsewhere."""
    if os.name != "nt":
        return 0
    try:
        import ctypes
        return int(ctypes.windll.user32.GetClipboardSequenceNumber())
    except Exception:
        return 0
