"""Statut en direct (Twitch, Streamlink) et aperçus des lives.

Live status (Twitch, Streamlink) and live previews."""
import json
import os
import re
import subprocess
import time

from .core import LIVE_METHODS, find_streamlink, log
from .inputs import resolve_target

# ---------------------
# Qui est en direct ?
# Who is live?
# ---------------------
TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # identifiant public du site web Twitch (utilisé aussi par Streamlink)
                                                     # public client id of the Twitch website (also used by Streamlink)
TWITCH_LOGIN_RE = re.compile(r"^[A-Za-z0-9_]{1,25}$")
PREVIEW_SIZE = (640, 360)  # taille demandée à Twitch ; réduite ensuite à la taille de la carte
                           # size requested from Twitch; then reduced to the card's size
PREVIEW_MAX_BYTES = 2 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) StreamlinkLauncher"


def live_method(platform):
    """'twitch', 'streamlink' ou 'none'.

    'twitch', 'streamlink' or 'none'."""
    method = platform.get("live_check") or LIVE_METHODS.get(platform["id"], "none")
    return method if method in ("twitch", "streamlink") else "none"


def _http_json(url, payload, headers, timeout):
    import urllib.request  # chargé seulement au besoin (économise la mémoire au démarrage)
                           # loaded only when needed (saves memory at start-up)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _offline():
    return {"live": False, "title": None, "game": None, "viewers": None, "preview": None}


def twitch_live(logins, timeout=8):
    """Une seule requête pour toutes les chaînes Twitch : {login: info}.

    A single request for all the Twitch channels: {login: info}."""
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
    """Vérifie via 'streamlink --json URL'. Renvoie info, ou None si inconnu (plugin absent, erreur réseau…).

    Checks via 'streamlink --json URL'. Returns info, or None if unknown (missing plugin, network error…)."""
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
    """entries : [(chaîne, id_plateforme)]. Renvoie {(chaîne en minuscules, id): info ou None}.

    entries: [(channel, platform_id)]. Returns {(lowercase channel, id): info or None}."""
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
    le CDN de Twitch garde sinon longtemps la même image en cache. None si l'URL ne convient pas.

    Safe preview URL (https only), with a parameter that changes every 5 minutes:
    otherwise Twitch's CDN keeps the same image cached for a long time. None if the URL is not suitable."""
    if not isinstance(url, str) or not url.startswith("https://") or len(url) > 500:
        return None
    stamp = int((now if now is not None else time.time()) // 300)
    return f"{url}{'&' if '?' in url else '?'}t={stamp}"


def fetch_image(url, timeout=8):
    """Télécharge une image (JPEG/PNG, 2 Mo maximum). Renvoie les octets, ou None.

    Downloads an image (JPEG/PNG, 2 MB maximum). Returns the bytes, or None."""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read(PREVIEW_MAX_BYTES + 1)
    if len(data) > PREVIEW_MAX_BYTES or not data.startswith((b"\xff\xd8", b"\x89PNG")):
        return None
    return data


def fetch_previews(urls):
    """{clé: url} -> {clé: octets ou None}. Une erreur sur une image n'empêche pas les autres.

    {key: url} -> {key: bytes or None}. An error on one image does not prevent the others."""
    out = {}
    for key, url in urls.items():
        try:
            out[key] = fetch_image(url)
        except Exception as e:
            log.info("Aperçu indisponible (%s) : %s", key, e)
            out[key] = None
    return out
