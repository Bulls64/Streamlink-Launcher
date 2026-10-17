"""Emotes tierces (BetterTTV, FrankerFaceZ, 7TV) et chargement des images (PNG / GIF, animées comprises).

Tk ne lit ni le WebP ni l'AVIF : on ne demande que des PNG et des GIF ; une emote sans ces formats reste du texte.
"""
import base64
import hashlib
import logging
import struct
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .common import http

log = logging.getLogger("streamlink_launcher")

BTTV_GLOBAL = "https://api.betterttv.net/3/cached/emotes/global"
BTTV_USER = "https://api.betterttv.net/3/cached/users/twitch/{id}"
BTTV_IMG = "https://cdn.betterttv.net/emote/{id}/1x.{ext}"
FFZ_GLOBAL = "https://api.frankerfacez.com/v1/set/global"
FFZ_ROOM = "https://api.frankerfacez.com/v1/room/id/{id}"
STV_GLOBAL = "https://7tv.io/v3/emote-sets/global"
STV_USER = "https://7tv.io/v3/users/{platform}/{id}"


# ---------------------
# Listes d'emotes
# ---------------------
def bttv_list(items):
    out = {}
    for e in items or []:
        code, eid = e.get("code"), e.get("id")
        if code and eid:
            ext = "gif" if (e.get("imageType") == "gif" or e.get("animated")) else "png"
            out[code] = BTTV_IMG.format(id=eid, ext=ext)
    return out


def ffz_sets(sets):
    out = {}
    for s in (sets or {}).values():
        for e in s.get("emoticons") or []:
            urls = e.get("urls") or {}
            url = urls.get("1") or urls.get(1)
            if e.get("name") and url:
                out[e["name"]] = ("https:" + url) if url.startswith("//") else url
    return out


def stv_list(emotes):
    out = {}
    for e in emotes or []:
        host = ((e.get("data") or {}).get("host") or {})
        base = host.get("url") or ""
        files = {f.get("name"): f for f in host.get("files") or []}
        name = next((n for n in ("1x.gif", "1x.png") if n in files), None)
        if e.get("name") and base and name:
            out[e["name"]] = ("https:" + base if base.startswith("//") else base) + "/" + name
    return out


def fetch_global(providers, get=http):
    emotes = {}
    if "ffz" in providers:
        try:
            data = get(FFZ_GLOBAL) or {}
            default = {str(i) for i in data.get("default_sets") or []}
            sets = {k: v for k, v in (data.get("sets") or {}).items() if not default or k in default}
            emotes.update(ffz_sets(sets))
        except Exception as e:
            log.info("Emotes FFZ globales : %s", e)
    if "bttv" in providers:
        try:
            emotes.update(bttv_list(get(BTTV_GLOBAL)))
        except Exception as e:
            log.info("Emotes BTTV globales : %s", e)
    if "7tv" in providers:
        try:
            emotes.update(stv_list((get(STV_GLOBAL) or {}).get("emotes")))
        except Exception as e:
            log.info("Emotes 7TV globales : %s", e)
    return emotes


def fetch_channel(platform, user_id, providers, get=http):
    """Emotes d'une chaîne (Twitch : identifiant de la chaîne ; Kick : 7TV seulement)."""
    emotes = {}
    if platform == "twitch" and "ffz" in providers:
        try:
            emotes.update(ffz_sets((get(FFZ_ROOM.format(id=user_id)) or {}).get("sets")))
        except Exception as e:
            log.info("Emotes FFZ de %s : %s", user_id, e)
    if platform == "twitch" and "bttv" in providers:
        try:
            data = get(BTTV_USER.format(id=user_id)) or {}
            emotes.update(bttv_list((data.get("channelEmotes") or []) + (data.get("sharedEmotes") or [])))
        except Exception as e:
            log.info("Emotes BTTV de %s : %s", user_id, e)
    if "7tv" in providers and platform in ("twitch", "kick"):
        try:
            data = get(STV_USER.format(platform=platform, id=user_id)) or {}
            emotes.update(stv_list(((data.get("emote_set") or {}).get("emotes"))))
        except Exception as e:
            log.info("Emotes 7TV de %s : %s", user_id, e)
    return emotes


# ---------------------
# Images
# ---------------------
def image_kind(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def gif_frames(data):
    """Nombre d'images et délai de chacune (ms) d'un GIF, sans le décoder."""
    delays, i = [], 13
    if len(data) < 13:
        return []
    flags = data[10]
    if flags & 0x80:
        i += 3 * (2 << (flags & 7))
    delay = 100
    while i < len(data):
        block = data[i]
        if block == 0x21:  # extension
            label = data[i + 1]
            j = i + 2
            if label == 0xF9 and j + 4 < len(data):
                delay = struct.unpack("<H", data[j + 2:j + 4])[0] * 10 or 100
            while j < len(data) and data[j]:
                j += data[j] + 1
            i = j + 1
        elif block == 0x2C:  # image
            delays.append(max(20, delay))
            delay = 100
            if i + 10 > len(data):
                break
            flags = data[i + 9]
            j = i + 10
            if flags & 0x80:
                j += 3 * (2 << (flags & 7))
            j += 1  # taille minimale LZW
            while j < len(data) and data[j]:
                j += data[j] + 1
            i = j + 1
        else:
            break
    return delays


class ImageLoader:
    """Télécharge les images d'emotes en arrière-plan (cache mémoire + disque) ; done(url, octets ou None)."""

    def __init__(self, cache_dir=None, get=http, workers=6):
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.get = get
        self.pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="emote")
        self.pending = set()
        self.lock = threading.Lock()

    def _path(self, url):
        return self.cache_dir / hashlib.sha1(url.encode()).hexdigest() if self.cache_dir else None

    def request(self, url, done):
        with self.lock:
            if url in self.pending:
                return
            self.pending.add(url)
        self.pool.submit(self._load, url, done)

    def _load(self, url, done):
        data = None
        path = self._path(url)
        try:
            if path and path.exists():
                data = path.read_bytes()
            else:
                data = self.get(url, raw=True, headers={"Accept": "image/png,image/gif;q=0.9,*/*;q=0.1"})
                if image_kind(data) and path:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
        except Exception as e:
            log.debug("Emote %s : %s", url, e)
            data = None
        if data is not None and not image_kind(data):
            data = None
        with self.lock:
            self.pending.discard(url)
        done(url, data)

    def shutdown(self):
        self.pool.shutdown(wait=False, cancel_futures=True)


def b64(data):
    return base64.b64encode(data)
