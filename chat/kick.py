"""Chat Kick.

Depuis le 13 octobre 2026, le site de Kick passe par une connexion « temps réel » négociée :
  1. POST https://web.kick.com/api/v1/realtime/channels/{id}/chat/connection -> point d'accès (Centrifugo, ou Pusher)
  2. POST https://web.kick.com/api/v1/realtime/auth/connection -> jeton de connexion Centrifugo
  3. WebSocket Centrifugo (protocole JSON) : connect, puis subscribe sur chatrooms.{salon}.v2 et channel.{id}
Les publications gardent l'ancien format (App\\Events\\ChatMessageEvent…). Ce protocole n'est pas documenté
par Kick : tout est lu avec tolérance, et l'ancienne connexion Pusher reste un dernier recours.
L'envoi de messages passe par l'API officielle (https://api.kick.com/public/v1/chat, jeton OAuth).
"""
import json
import logging
import re
import socket
import threading
import time
import uuid

from .common import ChatMessage, Connection, HttpError, http, split_words
from .ws import WebSocket

log = logging.getLogger("streamlink_launcher")

CHANNEL_URLS = ["https://kick.com/api/v2/channels/{slug}", "https://kick.com/api/v1/channels/{slug}"]
NEGOTIATE_URL = "https://web.kick.com/api/v1/realtime/channels/{channel_id}/chat/connection"
NEGOTIATE_FALLBACK_URL = "https://web.kick.com/api/v1/realtime/connection"
AUTH_URL = "https://web.kick.com/api/v1/realtime/auth/connection"
DEFAULT_CENTRIFUGO = "wss://realtime.us-east-1.platform.kick.com/connection/websocket"
LEGACY_PUSHER = {"provider": "pusher", "app_key": "32cbd69e4b950bf97679", "cluster": "us2"}
PUSHER_URL = "wss://ws-{cluster}.pusher.com/app/{key}?protocol=7&client=js&version=8.4.0&flash=false"
SEND_URL = "https://api.kick.com/public/v1/chat"
EMOTE_URL = "https://files.kick.com/emotes/{id}/fullsize"
ORIGIN = "https://kick.com"
HEADERS = {"Origin": ORIGIN, "Referer": "https://kick.com/"}
SLUG_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
EMOTE_RE = re.compile(r"\[emote:(\d+):([^\]]*)\]")

BADGES = {"broadcaster": ("broadcaster", "Streamer"), "moderator": ("moderator", "Mod"), "vip": ("vip", "VIP"),
          "og": ("og", "OG"), "founder": ("founder", "Fondateur"), "verified": ("verified", "✓"),
          "staff": ("staff", "Staff"), "sub_gifter": ("gifter", "Gift")}


class KickError(Exception):
    pass


def resolve_channel(slug):
    """Nom de chaîne -> {channel_id, chatroom_id, user_id, name, live}."""
    last = None
    for tpl in CHANNEL_URLS:
        try:
            data = http(tpl.format(slug=slug.lower()), headers=HEADERS)
        except HttpError as e:
            last = e
            if e.status == 404:
                raise KickError("not_found") from None
            continue
        except OSError as e:
            last = e
            continue
        if isinstance(data, dict) and (data.get("chatroom") or {}).get("id"):
            user = data.get("user") or {}
            return {"channel_id": data.get("id"), "chatroom_id": data["chatroom"]["id"],
                    "user_id": data.get("user_id") or user.get("id"), "slug": data.get("slug") or slug.lower(),
                    "name": user.get("username") or slug, "live": bool(data.get("livestream"))}
    if isinstance(last, HttpError) and last.status in (403, 429, 503):
        raise KickError("blocked")
    raise KickError(f"lookup: {last}")


def find_endpoints(data):
    """Points d'accès dans la réponse de négociation, quelle que soit son enveloppe ({data: …}, liste…)."""
    found = []

    def walk(node):
        if isinstance(node, dict):
            if "provider" in node and any(k in node for k in ("endpoint", "url", "app_key", "host")):
                found.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(data)
    order = {"centrifugo": 0, "pusher": 1}
    return sorted(found, key=lambda e: order.get(str(e.get("provider")).lower(), 9))


def find_token(data):
    if isinstance(data, dict):
        for k in ("token", "connection_token", "jwt"):
            if isinstance(data.get(k), str) and data[k]:
                return data[k]
        for v in data.values():
            t = find_token(v)
            if t:
                return t
    elif isinstance(data, list):
        for v in data:
            t = find_token(v)
            if t:
                return t
    return None


def parse_badges(identity):
    out = []
    for b in (identity or {}).get("badges") or []:
        kind = b.get("type", "")
        if kind == "subscriber":
            months = b.get("count") or 0
            out.append(("subscriber", f"Sub {months}" if months and months > 1 else "Sub"))
        elif kind in BADGES:
            out.append(BADGES[kind])
    return out


def content_fragments(content, extra_emotes=None):
    frags, cursor = [], 0
    for m in EMOTE_RE.finditer(content):
        if m.start() > cursor:
            frags += split_words(content[cursor:m.start()], extra_emotes)
        frags.append(("emote", m.group(2) or "emote", EMOTE_URL.format(id=m.group(1))))
        cursor = m.end()
    if cursor < len(content):
        frags += split_words(content[cursor:], extra_emotes)
    return frags


def plain_text(content):
    return EMOTE_RE.sub(lambda m: m.group(2), content)


class KickChannel(Connection):
    """Une connexion par chaîne Kick (la négociation se fait par chaîne)."""

    platform = "kick"

    def __init__(self, emit, slug, emote_lookup=None):
        super().__init__(emit)
        self.slug = slug.lower()
        self.info = None
        self.emote_lookup = emote_lookup or (lambda channel: {})
        self.client_id = str(uuid.uuid4())
        self.ws = None

    def stop(self):
        super().stop()
        if self.ws:
            self.ws.close()

    def run_once(self):
        self.status(self.slug, "connecting")
        if self.info is None:
            self.info = resolve_channel(self.slug)
            self.emit(("room", "kick", self.slug, dict(self.info)))
        endpoints = self._negotiate()
        errors = []
        for ep in endpoints:
            if self.stop_event.is_set():
                return
            provider = str(ep.get("provider", "")).lower()
            try:
                if provider == "centrifugo":
                    self._run_centrifugo(ep)
                elif provider == "pusher":
                    self._run_pusher(ep)
                else:
                    continue
                return
            except Exception as e:  # on essaie le point d'accès suivant
                log.info("Kick %s via %s : %s", self.slug, provider, e)
                errors.append(f"{provider}: {e}")
        raise KickError("; ".join(errors) or "no_endpoint")

    def on_error(self, error):
        code = str(error)
        self.status(self.slug, "error", code if code in ("blocked", "not_found") else code[:200])
        if code == "not_found":
            self.stop_event.set()  # inutile de réessayer

    def on_retry(self, delay):
        self.status(self.slug, "reconnecting", str(delay))

    # --- négociation
    def _negotiate(self):
        body = {"client": {"type": "web", "id": self.client_id}, "accepted_providers": ["pusher", "centrifugo"]}
        for url in (NEGOTIATE_URL.format(channel_id=self.info["channel_id"]), NEGOTIATE_FALLBACK_URL):
            try:
                found = find_endpoints(http(url, data=body, headers=HEADERS, method="POST"))
                if found:
                    return found + [{"provider": "centrifugo", "endpoint": DEFAULT_CENTRIFUGO}, LEGACY_PUSHER]
            except (HttpError, OSError, ValueError) as e:
                log.info("Kick : négociation %s : %s", url, e)
        return [{"provider": "centrifugo", "endpoint": DEFAULT_CENTRIFUGO}, LEGACY_PUSHER]

    def _token(self):
        body = {"client": {"type": "web", "id": self.client_id}}
        try:
            return find_token(http(AUTH_URL, data=body, headers=HEADERS, method="POST"))
        except (HttpError, OSError, ValueError) as e:
            log.info("Kick : jeton temps réel : %s", e)
            return None

    def _channels(self):
        return [f"chatrooms.{self.info['chatroom_id']}.v2", f"channel.{self.info['channel_id']}"]

    # --- Centrifugo (protocole JSON)
    def _run_centrifugo(self, ep):
        url = ep.get("endpoint") or ep.get("url") or DEFAULT_CENTRIFUGO
        token = ep.get("token") or self._token()
        ws = WebSocket(url, origin=ORIGIN, timeout=15).connect()
        self.ws = ws
        try:
            connect = {"name": "js"}
            if token:
                connect["token"] = token
            ws.send(json.dumps({"id": 1, "connect": connect}))
            ws.settimeout(15)
            reply = self._centrifugo_reply(ws, 1)
            ping = int((reply.get("connect") or {}).get("ping") or ep.get("ping") or 25)
            for i, ch in enumerate(self._channels(), start=2):
                ws.send(json.dumps({"id": i, "subscribe": {"channel": ch, "flag": 1}}))
            ws.settimeout(1.0)
            last = time.time()
            joined = False
            while not self.stop_event.is_set():
                try:
                    data = ws.recv()
                except socket.timeout:
                    if time.time() - last > ping + 15:
                        raise KickError("timeout") from None
                    continue
                last = time.time()
                for line in str(data).split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if line == "{}":
                        ws.send("{}")  # ping -> pong
                        continue
                    obj = json.loads(line)
                    if "error" in obj:
                        raise KickError(f"centrifugo {obj['error']}")
                    if obj.get("id") == 2 and "subscribe" in obj and not joined:
                        joined = True
                        self.status(self.slug, "connected", "ro")
                    push = obj.get("push") or {}
                    if "disconnect" in push:
                        raise KickError(f"disconnect {push['disconnect']}")
                    pub = push.get("pub")
                    if pub is not None:
                        self._publication(pub.get("data"))
        finally:
            self.ws = None
            ws.close()

    def _centrifugo_reply(self, ws, wanted):
        deadline = time.time() + 15
        while time.time() < deadline:
            for line in str(ws.recv()).split("\n"):
                line = line.strip()
                if not line or line == "{}":
                    continue
                obj = json.loads(line)
                if obj.get("id") == wanted:
                    if "error" in obj:
                        raise KickError(f"centrifugo {obj['error']}")
                    return obj
        raise KickError("centrifugo: no connect reply")

    # --- Pusher (ancien protocole, gardé en dernier recours)
    def _run_pusher(self, ep):
        key, cluster = ep.get("app_key") or ep.get("key"), ep.get("cluster") or "us2"
        url = ep.get("endpoint") or ep.get("url") or PUSHER_URL.format(cluster=cluster, key=key)
        ws = WebSocket(url, origin=ORIGIN, timeout=15).connect()
        self.ws = ws
        try:
            ws.settimeout(1.0)
            last = time.time()
            while not self.stop_event.is_set():
                try:
                    data = ws.recv()
                except socket.timeout:
                    idle = time.time() - last
                    if idle > 120:
                        raise KickError("timeout") from None
                    if int(idle) == 60:
                        ws.send(json.dumps({"event": "pusher:ping", "data": {}}))
                    continue
                last = time.time()
                obj = json.loads(data)
                event = obj.get("event", "")
                if event == "pusher:connection_established":
                    for ch in self._channels():
                        ws.send(json.dumps({"event": "pusher:subscribe", "data": {"auth": "", "channel": ch}}))
                elif event == "pusher:ping":
                    ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                elif event == "pusher:error":
                    raise KickError(f"pusher {obj.get('data')}")
                elif event == "pusher_internal:subscription_succeeded":
                    self.status(self.slug, "connected", "ro")
                elif not event.startswith("pusher"):
                    self._publication({"event": event, "data": obj.get("data")})
        finally:
            self.ws = None
            ws.close()

    # --- événements (identiques quelle que soit la connexion)
    def _publication(self, pub):
        if isinstance(pub, str):
            try:
                pub = json.loads(pub)
            except ValueError:
                return
        if not isinstance(pub, dict):
            return
        event = str(pub.get("event") or pub.get("name") or "")
        data = pub.get("data", pub)
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except ValueError:
                return
        if not isinstance(data, dict):
            return
        name = event.rsplit("\\", 1)[-1]
        if name == "ChatMessageEvent" or (not event and "content" in data and "sender" in data):
            self.emit(("message", self.chat_message(data)))
        elif name == "MessageDeletedEvent":
            mid = (data.get("message") or {}).get("id") or data.get("id")
            self.emit(("delete", "kick", self.slug, str(mid)))
        elif name == "UserBannedEvent":
            user = (data.get("user") or {}).get("username", "")
            self.emit(("clear_user", "kick", self.slug, user.lower()))
        elif name == "ChatroomClearEvent":
            self.emit(("clear", "kick", self.slug))
        elif name == "SubscriptionEvent":
            who, months = data.get("username", "?"), data.get("months") or 1
            self._event(f"{who} s'est abonné ({months} mois)", "sub")
        elif name == "GiftedSubscriptionsEvent":
            who = data.get("gifter_username", "?")
            n = len(data.get("gifted_usernames") or []) or 1
            self._event(f"{who} a offert {n} abonnement(s)", "gift")
        elif name == "StreamHostEvent":
            self._event(f"{data.get('host_username', '?')} héberge la chaîne ({data.get('number_viewers', 0)})",
                        "host")

    def _event(self, text, kind):
        self.emit(("message", ChatMessage("kick", self.slug, text=text, kind="event", id=f"{kind}:{time.time()}",
                                          fragments=split_words(text))))

    def chat_message(self, data):
        sender = data.get("sender") or {}
        identity = sender.get("identity") or {}
        content = data.get("content") or ""
        msg = ChatMessage("kick", self.slug, text=plain_text(content), user=(sender.get("slug") or "").lower(),
                          display_name=sender.get("username") or sender.get("slug") or "?",
                          color=identity.get("color") or "", badges=parse_badges(identity), id=str(data.get("id", "")),
                          user_id=str(sender.get("id", "")))
        if data.get("type") == "reply":
            original = ((data.get("metadata") or {}).get("original_sender") or {})
            msg.reply_to = original.get("username", "")
        msg.fragments = content_fragments(content, self.emote_lookup(self.slug))
        return msg


class KickManager:
    """Même interface que TwitchConnection : join, part, send_message, stop."""

    platform = "kick"

    def __init__(self, emit, token=None, emote_lookup=None):
        self.emit, self.token = emit, token
        self.emote_lookup = emote_lookup
        self.channels = {}
        self.lock = threading.Lock()

    @property
    def can_send(self):
        return bool(self.token)

    def start(self):
        return self

    def join(self, slug):
        slug = slug.lower()
        with self.lock:
            if slug in self.channels:
                return
            self.channels[slug] = KickChannel(self.emit, slug, self.emote_lookup).start()

    def part(self, slug):
        with self.lock:
            ch = self.channels.pop(slug.lower(), None)
        if ch:
            ch.stop()

    def stop(self):
        with self.lock:
            chans, self.channels = list(self.channels.values()), {}
        for ch in chans:
            ch.stop()

    def send_message(self, slug, text, http_func=None):
        """Envoi par l'API officielle (appelé hors de l'interface). Kick renvoie le message dans le chat."""
        ch = self.channels.get(slug.lower())
        if not self.token or ch is None or not ch.info:
            raise KickError("not_ready")
        (http_func or http)(SEND_URL, data={"broadcaster_user_id": int(ch.info["user_id"]), "content": text, "type": "user"},
                  headers={"Authorization": f"Bearer {self.token}"}, method="POST")
        return None
