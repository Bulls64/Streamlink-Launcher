"""Éléments partagés par les plateformes : message de chat, découpage du texte, couleurs, requêtes HTTP."""
import gzip
import hashlib
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field

from .ws import USER_AGENT

log = logging.getLogger("streamlink_launcher")

URL_RE = re.compile(r"(?i)\b((?:https?://|www\.)[^\s<>\"']+[^\s<>\"'.,;:!?)\]}])")


@dataclass
class ChatMessage:
    """Une ligne de chat, quelle que soit la plateforme.

    fragments : liste de tuples ("text", s) | ("emote", nom, url) | ("link", url) | ("mention", s)
    badges : liste de (identifiant, libellé) ; kind : msg, action (/me), system, notice, event (abonnement…)
    """
    platform: str
    channel: str
    text: str = ""
    user: str = ""                 # identifiant de connexion (minuscules)
    display_name: str = ""
    color: str = ""
    badges: list = field(default_factory=list)
    fragments: list = field(default_factory=list)
    kind: str = "msg"
    id: str = ""
    user_id: str = ""
    ts: float = field(default_factory=time.time)
    reply_to: str = ""             # pseudo auquel le message répond
    first: bool = False            # premier message de cette personne dans ce chat
    highlight: bool = False        # message mis en avant (points de chaîne, etc.)
    own: bool = False              # envoyé depuis cette application
    deleted: bool = False


# ---------------------
# Découpage du texte
# ---------------------
def split_words(text, emotes=None, own_name=""):
    """Texte -> fragments : emotes (dictionnaire nom -> url), liens, mentions @pseudo."""
    emotes = emotes or {}
    out = []
    buf = []

    def flush():
        if buf:
            out.append(("text", "".join(buf)))
            buf.clear()

    for token in re.split(r"(\s+)", text):
        if not token:
            continue
        if token.isspace():
            buf.append(token)
            continue
        url = emotes.get(token)
        if url:
            flush()
            out.append(("emote", token, url))
        elif URL_RE.match(token) and not token[URL_RE.match(token).end():].strip(".,;:!?)]}\"'"):
            end = URL_RE.match(token).end()
            flush()
            out.append(("link", token[:end]))
            if token[end:]:
                buf.append(token[end:])  # ponctuation après le lien
        elif token.startswith("@") and len(token) > 1:
            flush()
            out.append(("mention", token))
        else:
            buf.append(token)
    flush()
    return out


def mentions(fragments, names, words=()):
    """Vrai si le message cite l'un des noms (avec ou sans @) ou l'un des mots surveillés."""
    names = {n.lower().lstrip("@") for n in names if n}
    words = [w.lower() for w in words if w]
    for frag in fragments:
        if frag[0] == "mention" and frag[1].lstrip("@").rstrip(",.:!?").lower() in names:
            return True
        if frag[0] in ("text", "mention"):
            low = frag[1].lower()
            if any(re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", low) for n in names):
                return True
            if any(w in low for w in words):
                return True
    return False


# ---------------------
# Couleurs des pseudos
# ---------------------
# Couleurs par défaut de Twitch, quand la personne n'en a pas choisi
DEFAULT_COLORS = ["#FF0000", "#0000FF", "#008000", "#B22222", "#FF7F50", "#9ACD32", "#FF4500", "#2E8B57",
                  "#DAA520", "#D2691E", "#5F9EA0", "#1E90FF", "#FF69B4", "#8A2BE2", "#00FF7F"]


def default_color(name):
    h = int(hashlib.md5((name or "").lower().encode()).hexdigest(), 16)
    return DEFAULT_COLORS[h % len(DEFAULT_COLORS)]


def _lum(rgb):
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def contrast(a, b):
    la, lb = _lum(_rgb(a)), _lum(_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def readable_color(color, bg, minimum=4.0):
    """Éclaircit ou assombrit la couleur d'un pseudo jusqu'à ce qu'elle se lise sur le fond (comme Chatterino)."""
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", color or ""):
        return None
    target = "#FFFFFF" if _lum(_rgb(bg)) < 0.4 else "#000000"
    c = color.upper()
    rgb0, rgb1 = _rgb(c), _rgb(target)
    for step in range(11):
        t = step / 10
        mixed = "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(rgb0, rgb1))
        if contrast(mixed, bg) >= minimum:
            return mixed
    return target


# ---------------------
# HTTP
# ---------------------
class HttpError(Exception):
    def __init__(self, status, message=""):
        super().__init__(f"HTTP {status} {message}".strip())
        self.status = status


def http(url, data=None, headers=None, method=None, timeout=12, form=None, opener=None, raw=False):
    """Requête HTTP(S) ; renvoie le JSON décodé (ou les octets si raw). data = objet JSON à envoyer,
    form = dictionnaire encodé en application/x-www-form-urlencoded."""
    h = {"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*", "Accept-Encoding": "gzip, deflate"}
    h.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        h.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urllib.parse.urlencode(form).encode()
        h.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with (opener or urllib.request.build_opener()).open(req, timeout=timeout) as resp:
            payload = resp.read(8 * 1024 * 1024)
            enc = (resp.headers.get("Content-Encoding") or "").lower()
    except urllib.error.HTTPError as e:
        try:
            detail = e.read(2000).decode("utf-8", "replace")
        except Exception:
            detail = ""
        raise HttpError(e.code, detail[:300]) from None
    if enc == "gzip":
        payload = gzip.decompress(payload)
    elif enc == "deflate":
        payload = zlib.decompress(payload)
    if raw:
        return payload
    text = payload.decode("utf-8", "replace")
    return json.loads(text) if text.strip() else None



# ---------------------
# Base des connexions
# ---------------------
class Connection:
    """Connexion à une plateforme dans un fil d'exécution à part.

    Les événements partent vers l'interface par emit(...) (une file lue par la boucle Tk) :
      ("message", ChatMessage) · ("status", platform, channel, état, détail) · ("delete", platform, channel, id)
      ("clear_user", platform, channel, user) · ("clear", platform, channel) · ("room", platform, channel, infos)
    états : connecting, connected (lecture seule ou non), reconnecting, error, closed
    """

    platform = ""

    def __init__(self, emit):
        self.emit = emit
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self._run_forever, daemon=True, name=f"chat-{self.platform}")
        self.thread.start()
        return self

    def stop(self):
        self.stop_event.set()

    def status(self, channel, state, detail=""):
        self.emit(("status", self.platform, channel, state, detail))

    def _run_forever(self):
        delay = 1
        while not self.stop_event.is_set():
            started = time.time()
            try:
                self.run_once()
            except Exception as e:  # réseau, protocole : on retente plus tard
                log.info("Chat %s : %s", self.platform, e)
                self.on_error(e)
            if self.stop_event.is_set():
                break
            delay = 1 if time.time() - started > 60 else min(delay * 2, 30)
            self.on_retry(delay)
            self.stop_event.wait(delay)

    def run_once(self):
        raise NotImplementedError

    def on_error(self, error):
        pass

    def on_retry(self, delay):
        pass
