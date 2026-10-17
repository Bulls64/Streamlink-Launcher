"""Chat des diffusions Steam (steam.tv et steamcommunity.com/broadcast/watch/…), en lecture seule.

API web interne de Steam (non officielle) :
  getbroadcastmpd?steamid=…  -> identifiant de la diffusion en cours (broadcastid)
  getchatinfo?steamid=…&broadcastid=…  -> chat_id + modèle d'adresse des messages (view_url_template)
  modèle (%llu = chat_id, %u = horodatage de départ) -> {messages: […], next_request: …}, interrogé en boucle.
"""
import html
import json
import logging
import re
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

from .common import ChatMessage, Connection, HttpError, http, split_words

log = logging.getLogger("streamlink_launcher")

WATCH_URL = "https://steamcommunity.com/broadcast/watch/{steamid}"
MPD_URL = "https://steamcommunity.com/broadcast/getbroadcastmpd/"
CHATINFO_URL = "https://steamcommunity.com/broadcast/getchatinfo"
STEAMTV_URL = "https://steam.tv/{name}"
EMOTICON_URL = "https://community.cloudflare.steamstatic.com/economy/emoticon/{name}"
STEAMID_RE = re.compile(r"^7656119\d{10}$")
EMOTICON_RE = re.compile(r"[:ː]([A-Za-z0-9_]{2,40})[:ː]")


class SteamError(Exception):
    pass


def find_steamid(page):
    """steamid du diffuseur dans une page steam.tv (attribut data-broadcast de #webui_config)."""
    m = re.search(r'data-broadcast="([^"]*)"', page)
    if m:
        try:
            sid = str(json.loads(html.unescape(m.group(1))).get("steamid", ""))
            if STEAMID_RE.match(sid):
                return sid
        except ValueError:
            pass
    m = re.search(r'"steamid"\s*:\s*"(7656119\d{10})"', html.unescape(page))
    return m.group(1) if m else None


def steam_fragments(text):
    """Texte -> fragments, avec les émoticônes Steam (:nom: ou ːnomː) en images."""
    frags, cursor = [], 0
    for m in EMOTICON_RE.finditer(text):
        if m.start() > cursor:
            frags += split_words(text[cursor:m.start()])
        frags.append(("emote", m.group(1), EMOTICON_URL.format(name=m.group(1))))
        cursor = m.end()
    if cursor < len(text):
        frags += split_words(text[cursor:])
    return frags


def chat_url(template, chat_id, start):
    return template.replace("%llu", str(chat_id)).replace("%u", str(start))


class SteamChannel(Connection):
    platform = "steamtv"

    def __init__(self, emit, name):
        super().__init__(emit)
        self.name = name
        self.steamid = name if STEAMID_RE.match(name) else None
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def _get(self, url, **kw):
        return http(url, opener=self.opener, **kw)

    def resolve(self):
        if not self.steamid:
            page = self._get(STEAMTV_URL.format(name=self.name), raw=True).decode("utf-8", "replace")
            self.steamid = find_steamid(page)
            if not self.steamid:
                raise SteamError("not_found")
        # La page de visionnage pose le cookie sessionid demandé par getbroadcastmpd
        self._get(WATCH_URL.format(steamid=self.steamid), raw=True)
        session = next((c.value for c in self.jar if c.name == "sessionid"), "")
        q = urllib.parse.urlencode({"steamid": self.steamid, "broadcastid": 0, "viewertoken": 0,
                                    "watchlocation": 5, "sessionid": session})
        mpd = self._get(f"{MPD_URL}?{q}") or {}
        broadcastid = str(mpd.get("broadcastid") or "0")
        if mpd.get("success") not in ("ready", "waiting", 1, True) and broadcastid == "0":
            raise SteamError("offline")
        q = urllib.parse.urlencode({"steamid": self.steamid, "broadcastid": broadcastid})
        info = self._get(f"{CHATINFO_URL}?{q}") or {}
        if str(info.get("success")) != "1" or not info.get("view_url_template"):
            raise SteamError("offline")
        title = mpd.get("title") or ""
        self.emit(("room", "steamtv", self.name, {"steamid": self.steamid, "broadcastid": broadcastid,
                                                 "title": title}))
        return str(info.get("chat_id", "")), info["view_url_template"]

    def run_once(self):
        self.status(self.name, "connecting")
        chat_id, template = self.resolve()
        self.status(self.name, "connected", "ro")
        start = 0
        seen = set()
        while not self.stop_event.is_set():
            try:
                data = self._get(chat_url(template, chat_id, start)) or {}
            except HttpError as e:
                if e.status in (404, 410):
                    raise SteamError("offline") from None
                raise
            for m in data.get("messages") or []:
                msg = self.parse_message(m)
                if msg is None:
                    continue
                # Normalement, start=next_request ne renvoie que les nouveaux messages ; si Steam renvoie
                # l'horodatage des messages, il sert en plus à écarter un éventuel doublon.
                key = (msg.user_id, msg.text, m.get("time")) if m.get("time") else None
                if key is None or key not in seen:
                    if key:
                        seen.add(key)
                    self.emit(("message", msg))
            if len(seen) > 2000:
                seen.clear()
            start = data.get("next_request") or start
            sleep = data.get("sleep") or data.get("sleep_seconds") or 5
            self.stop_event.wait(max(2, min(float(sleep), 15)))

    def parse_message(self, m):
        kind = m.get("type", "chatmessage")
        if kind not in ("chatmessage", "chat"):
            return None
        text = m.get("msg") or m.get("message") or ""
        name = m.get("persona_name") or m.get("name") or "?"
        msg = ChatMessage("steamtv", self.name, text=text, user=name.lower(), display_name=name,
                          user_id=str(m.get("steamid", "")), fragments=steam_fragments(text))
        if m.get("time"):
            try:
                msg.ts = float(m["time"])
            except (TypeError, ValueError):
                pass
        return msg

    def on_error(self, error):
        self.status(self.name, "error", str(error)[:200])

    def on_retry(self, delay):
        # Hors ligne : on revérifie toutes les 30 s
        self.status(self.name, "reconnecting", str(delay))


class SteamManager:
    platform = "steamtv"
    can_send = False

    def __init__(self, emit):
        self.emit = emit
        self.channels = {}

    def start(self):
        return self

    def join(self, name):
        if name not in self.channels:
            self.channels[name] = SteamChannel(self.emit, name).start()

    def part(self, name):
        ch = self.channels.pop(name, None)
        if ch:
            ch.stop()

    def stop(self):
        for ch in self.channels.values():
            ch.stop()
        self.channels = {}

    def send_message(self, name, text):
        return None

