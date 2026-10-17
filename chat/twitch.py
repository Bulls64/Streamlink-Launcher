"""Chat Twitch : IRC sur WebSocket (wss://irc-ws.chat.twitch.tv). Lecture anonyme, écriture une fois connecté."""
import random
import re
import socket
import threading
import time

from .common import ChatMessage, Connection, split_words
from .ws import ConnectionClosed, WebSocket

IRC_URL = "wss://irc-ws.chat.twitch.tv:443"
EMOTE_URL = "https://static-cdn.jtvnw.net/emoticons/v2/{id}/default/{theme}/1.0"
LOGIN_RE = re.compile(r"^[a-z0-9_]{1,25}$")

BADGES = {  # identifiant Twitch -> (identifiant interne, libellé court)
    "broadcaster": ("broadcaster", "Streamer"), "moderator": ("moderator", "Mod"), "vip": ("vip", "VIP"),
    "subscriber": ("subscriber", "Sub"), "founder": ("founder", "Fondateur"), "staff": ("staff", "Staff"),
    "partner": ("verified", "✓"), "turbo": ("turbo", "Turbo"), "premium": ("prime", "Prime"),
    "artist-badge": ("artist", "Artiste"),
}

_ESCAPES = {"\\s": " ", "\\:": ";", "\\\\": "\\", "\\r": "\r", "\\n": "\n"}


def unescape_tag(value):
    return re.sub(r"\\[s:\\rn]?", lambda m: _ESCAPES.get(m.group(0), ""), value)


def parse_line(line):
    """Ligne IRC -> (tags, préfixe, commande, paramètres). Le dernier paramètre (après ' :') est inclus."""
    tags, prefix = {}, ""
    if line.startswith("@"):
        raw, _, line = line[1:].partition(" ")
        for item in raw.split(";"):
            k, _, v = item.partition("=")
            tags[k] = unescape_tag(v)
    if line.startswith(":"):
        prefix, _, line = line[1:].partition(" ")
    trailing = None
    if " :" in line:
        line, _, trailing = line.partition(" :")
    elif line.startswith(":"):
        line, trailing = "", line[1:]
    parts = line.split()
    command = parts[0].upper() if parts else ""
    params = parts[1:] + ([trailing] if trailing is not None else [])
    return tags, prefix, command, params


def parse_badges(value):
    out = []
    for item in (value or "").split(","):
        name, _, version = item.partition("/")
        if not name:
            continue
        kind, label = BADGES.get(name, (None, None))
        if kind == "subscriber" and version.isdigit() and int(version) > 0:
            months = int(version) % 1000 if int(version) >= 1000 else int(version)
            label = f"Sub {months}" if months > 1 else "Sub"
        if kind:
            out.append((kind, label))
    return out


def emote_fragments(text, emotes_tag, extra_emotes=None, theme="dark"):
    """Découpe le texte selon le tag emotes (positions en caractères), puis les mots restants."""
    ranges = []
    for item in (emotes_tag or "").split("/"):
        eid, _, positions = item.partition(":")
        for pos in positions.split(","):
            a, _, b = pos.partition("-")
            if a.isdigit() and b.isdigit():
                ranges.append((int(a), int(b), eid))
    ranges.sort()
    frags, cursor = [], 0
    for a, b, eid in ranges:
        if a < cursor or b >= len(text):
            continue
        if a > cursor:
            frags += split_words(text[cursor:a], extra_emotes)
        frags.append(("emote", text[a:b + 1], EMOTE_URL.format(id=eid, theme=theme)))
        cursor = b + 1
    if cursor < len(text):
        frags += split_words(text[cursor:], extra_emotes)
    return frags


class TwitchConnection(Connection):
    platform = "twitch"

    def __init__(self, emit, login=None, token=None, emote_lookup=None, theme="dark"):
        super().__init__(emit)
        self.login, self.token = (login or "").lower(), token
        self.emote_lookup = emote_lookup or (lambda channel: {})
        self.theme = theme
        self.channels = set()
        self.room_ids = {}
        self.ws = None
        self.lock = threading.Lock()
        self.user_state = {}           # salon -> tags USERSTATE (couleur, badges de son propre compte)
        self.authenticated = False
        self.url = IRC_URL

    @property
    def can_send(self):
        return bool(self.token and self.login and self.authenticated)

    # --- commandes depuis l'interface (n'importe quel fil)
    def join(self, channel):
        channel = channel.lower()
        with self.lock:
            self.channels.add(channel)
        self._send_raw(f"JOIN #{channel}")
        self.status(channel, "connecting")

    def part(self, channel):
        channel = channel.lower()
        with self.lock:
            self.channels.discard(channel)
        self._send_raw(f"PART #{channel}")

    def send_message(self, channel, text):
        """Envoie un message ; renvoie le message affiché localement (Twitch ne le renvoie pas)."""
        text = text.replace("\r", " ").replace("\n", " ").strip()
        if not text or not self.can_send:
            return None
        self._send_raw(f"PRIVMSG #{channel.lower()} :{text}")
        state = self.user_state.get(channel.lower(), {})
        action = text.startswith("/me ")
        body = text[4:] if action else text
        if text.startswith("/") and not action:
            return None  # commande (/ban, /mods…) : rien à afficher
        msg = ChatMessage("twitch", channel.lower(), text=body, user=self.login,
                          display_name=state.get("display-name") or self.login, color=state.get("color", ""),
                          badges=parse_badges(state.get("badges")), kind="action" if action else "msg", own=True)
        msg.fragments = split_words(body, self.emote_lookup(channel.lower()))
        return msg

    def _send_raw(self, line):
        ws = self.ws
        if ws is None:
            return False
        try:
            ws.send(line)
            return True
        except OSError:
            return False

    def stop(self):
        super().stop()
        ws = self.ws
        if ws:
            ws.close()

    # --- boucle de connexion
    def run_once(self):
        with self.lock:
            channels = sorted(self.channels)
        for ch in channels:
            self.status(ch, "connecting")
        ws = WebSocket(self.url, timeout=15).connect()
        self.ws = ws
        self.authenticated = False
        with self.lock:
            channels = sorted(self.channels)  # salons ajoutés pendant la connexion compris
        ws.send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        if self.token and self.login:
            ws.send(f"PASS oauth:{self.token}")
            ws.send(f"NICK {self.login}")
        else:
            ws.send(f"NICK justinfan{random.randint(10000, 99999)}")
        for ch in channels:
            ws.send(f"JOIN #{ch}")
        ws.settimeout(1.0)
        last_rx = time.time()
        pinged = False
        try:
            while not self.stop_event.is_set():
                try:
                    data = ws.recv()
                except socket.timeout:
                    idle = time.time() - last_rx
                    if idle > 360 and not pinged:  # Twitch envoie un PING toutes les ~5 min
                        ws.send("PING :tmi.twitch.tv")
                        pinged = True
                    elif idle > 400:
                        raise ConnectionClosed(1006, "plus de réponse du serveur") from None
                    continue
                last_rx, pinged = time.time(), False
                for line in str(data).split("\r\n"):
                    if line and self._handle(ws, line):
                        return  # RECONNECT demandé par Twitch
        finally:
            self.ws = None
            ws.close()

    def on_error(self, error):
        with self.lock:
            channels = sorted(self.channels)
        for ch in channels:
            self.status(ch, "error", str(error))

    def on_retry(self, delay):
        with self.lock:
            channels = sorted(self.channels)
        for ch in channels:
            self.status(ch, "reconnecting", str(delay))

    # --- traitement des lignes
    def _handle(self, ws, line):
        tags, prefix, cmd, params = parse_line(line)
        nick = prefix.split("!")[0]
        channel = params[0][1:].lower() if params and params[0].startswith("#") else ""
        if cmd == "PING":
            ws.send("PONG :" + (params[-1] if params else "tmi.twitch.tv"))
        elif cmd == "RECONNECT":
            return True
        elif cmd == "001":
            self.authenticated = bool(self.token and self.login)
        elif cmd == "PRIVMSG" and channel:
            self.emit(("message", self._privmsg(tags, nick, channel, params[-1])))
        elif cmd == "USERNOTICE" and channel:
            self._usernotice(tags, channel, params[-1] if len(params) > 1 else "")
        elif cmd == "ROOMSTATE" and channel:
            if tags.get("room-id"):
                first = channel not in self.room_ids
                self.room_ids[channel] = tags["room-id"]
                if first:
                    self.emit(("room", "twitch", channel, {"room_id": tags["room-id"]}))
            self.status(channel, "connected", "rw" if self.can_send else "ro")
        elif cmd == "USERSTATE" and channel:
            self.user_state[channel] = tags
        elif cmd == "CLEARCHAT" and channel:
            if len(params) > 1:
                self.emit(("clear_user", "twitch", channel, params[-1].lower()))
            else:
                self.emit(("clear", "twitch", channel))
        elif cmd == "CLEARMSG" and channel:
            self.emit(("delete", "twitch", channel, tags.get("target-msg-id", "")))
        elif cmd == "NOTICE":
            text = params[-1] if params else ""
            if "authentication failed" in text.lower() or "improperly formatted auth" in text.lower():
                self.emit(("auth_failed", "twitch", text))
                raise ConnectionClosed(4000, "authentification refusée")
            target = channel or "*"
            self.emit(("message", ChatMessage("twitch", target, text=text, kind="notice",
                                              fragments=split_words(text))))
        elif cmd == "PART" and channel and nick == self.login:
            pass
        return False

    def _privmsg(self, tags, nick, channel, text):
        kind = "msg"
        if text.startswith("\x01ACTION ") and text.endswith("\x01"):
            text, kind = text[8:-1], "action"
        msg = ChatMessage("twitch", channel, text=text, user=nick.lower(),
                          display_name=tags.get("display-name") or nick, color=tags.get("color", ""),
                          badges=parse_badges(tags.get("badges")), kind=kind, id=tags.get("id", ""),
                          user_id=tags.get("user-id", ""))
        ts = tags.get("tmi-sent-ts", "")
        if ts.isdigit():
            msg.ts = int(ts) / 1000
        msg.reply_to = tags.get("reply-parent-display-name", "")
        if msg.reply_to and text.startswith("@"):
            # Twitch ajoute « @pseudo » en tête des réponses : retiré, la réponse est affichée à part
            head, _, rest = text.partition(" ")
            if head[1:].lower() == msg.reply_to.lower():
                offset = len(head) + 1
                text = rest
                tags = dict(tags, emotes=_shift_emotes(tags.get("emotes", ""), offset))
                msg.text = text
        msg.first = tags.get("first-msg") == "1"
        msg.highlight = tags.get("msg-id") == "highlighted-message"
        msg.fragments = emote_fragments(text, tags.get("emotes"), self.emote_lookup(channel), self.theme)
        return msg

    def _usernotice(self, tags, channel, text):
        system = tags.get("system-msg", "")
        if system:
            ev = ChatMessage("twitch", channel, text=system, kind="event", fragments=split_words(system),
                             id=tags.get("id", "") + ":sys")
            self.emit(("message", ev))
        if text:
            msg = self._privmsg(tags, tags.get("login", ""), channel, text)
            msg.highlight = True
            self.emit(("message", msg))


def _shift_emotes(emotes_tag, offset):
    out = []
    for item in (emotes_tag or "").split("/"):
        eid, _, positions = item.partition(":")
        if not eid:
            continue
        shifted = []
        for pos in positions.split(","):
            a, _, b = pos.partition("-")
            if a.isdigit() and b.isdigit() and int(a) >= offset:
                shifted.append(f"{int(a) - offset}-{int(b) - offset}")
        if shifted:
            out.append(f"{eid}:{','.join(shifted)}")
    return "/".join(out)
