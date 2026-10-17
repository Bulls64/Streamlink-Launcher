"""Connexion aux comptes, pour écrire dans les chats.

Twitch : « Device Code Flow » (aucune adresse de retour, aucun secret). Il faut un identifiant d'application
  enregistrée sur https://dev.twitch.tv/console (type « Public »).
Kick : OAuth 2.1 avec PKCE et retour sur http://localhost:{port}/callback. Il faut une application Kick
  (https://kick.com/settings/developer) : identifiant + secret, et cette adresse de retour déclarée.
"""
import base64
import hashlib
import logging
import os
import secrets
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .common import HttpError, http

log = logging.getLogger("streamlink_launcher")

TWITCH_DEVICE = "https://id.twitch.tv/oauth2/device"
TWITCH_TOKEN = "https://id.twitch.tv/oauth2/token"
TWITCH_VALIDATE = "https://id.twitch.tv/oauth2/validate"
TWITCH_SCOPES = "chat:read chat:edit"

KICK_AUTHORIZE = "https://id.kick.com/oauth/authorize"
KICK_TOKEN = "https://id.kick.com/oauth/token"
KICK_USER = "https://api.kick.com/public/v1/users"
KICK_SCOPES = "user:read chat:write"
KICK_PORT = 48125
KICK_REDIRECT = f"http://localhost:{KICK_PORT}/callback"


class AuthError(Exception):
    pass


# ---------------------
# Twitch
# ---------------------
def twitch_device_start(client_id, post=http):
    """-> {device_code, user_code, verification_uri, interval, expires_in}"""
    data = post(TWITCH_DEVICE, form={"client_id": client_id, "scopes": TWITCH_SCOPES}, method="POST")
    if not data or "device_code" not in data:
        raise AuthError("device")
    return data


def twitch_device_poll(client_id, device, cancel, post=http, sleep=time.sleep):
    """Attend que l'utilisateur valide le code ; -> {access_token, refresh_token, login, user_id}."""
    interval = max(1, int(device.get("interval") or 5))
    deadline = time.time() + int(device.get("expires_in") or 1800)
    while time.time() < deadline:
        if cancel.is_set():
            raise AuthError("cancelled")
        sleep(interval)
        try:
            tok = post(TWITCH_TOKEN, form={"client_id": client_id, "scopes": TWITCH_SCOPES,
                                           "device_code": device["device_code"],
                                           "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
                       method="POST")
        except HttpError as e:
            if "authorization_pending" in str(e):
                continue
            if "slow_down" in str(e):
                interval += 5
                continue
            raise AuthError("denied" if "denied" in str(e) else "expired" if "expired" in str(e) else str(e)) from None
        info = twitch_validate(tok["access_token"], get=post)
        return {"access_token": tok["access_token"], "refresh_token": tok.get("refresh_token", ""),
                "login": info["login"], "user_id": info["user_id"]}
    raise AuthError("expired")


def twitch_validate(token, get=http):
    data = get(TWITCH_VALIDATE, headers={"Authorization": f"OAuth {token}"})
    if not data or not data.get("login"):
        raise AuthError("invalid")
    return data


def twitch_refresh(client_id, refresh_token, post=http):
    tok = post(TWITCH_TOKEN, form={"client_id": client_id, "grant_type": "refresh_token",
                                   "refresh_token": refresh_token}, method="POST")
    return tok["access_token"], tok.get("refresh_token", refresh_token)


def twitch_ensure(account, post=http):
    """Vérifie le jeton enregistré ; le renouvelle si besoin. Renvoie le compte à jour, ou None."""
    if not account or not account.get("access_token"):
        return None
    try:
        twitch_validate(account["access_token"], get=post)
        return account
    except (HttpError, AuthError):
        pass
    if account.get("refresh_token") and account.get("client_id"):
        try:
            access, refresh = twitch_refresh(account["client_id"], account["refresh_token"], post=post)
            return dict(account, access_token=access, refresh_token=refresh)
        except (HttpError, KeyError):
            return None
    return None


# ---------------------
# Kick
# ---------------------
def pkce_pair():
    verifier = base64.urlsafe_b64encode(os.urandom(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def kick_authorize_url(client_id, challenge, state):
    q = {"response_type": "code", "client_id": client_id, "redirect_uri": KICK_REDIRECT, "scope": KICK_SCOPES,
         "code_challenge": challenge, "code_challenge_method": "S256", "state": state}
    return f"{KICK_AUTHORIZE}?{urllib.parse.urlencode(q)}"


def wait_for_code(state, cancel, port=KICK_PORT, timeout=300, page=b""):
    """Petit serveur local qui reçoit le retour d'autorisation ; -> code."""
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if q.get("state", [""])[0] == state:
                result["code"] = q.get("code", [""])[0]
                result["error"] = q.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page or b"<p>OK</p>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 0.5
    deadline = time.time() + timeout
    try:
        while "code" not in result and time.time() < deadline and not cancel.is_set():
            server.handle_request()
    finally:
        server.server_close()
    if cancel.is_set():
        raise AuthError("cancelled")
    if result.get("error") or not result.get("code"):
        raise AuthError(result.get("error") or "expired")
    return result["code"]


def kick_exchange(client_id, client_secret, code, verifier, post=http):
    tok = post(KICK_TOKEN, form={"grant_type": "authorization_code", "client_id": client_id,
                                 "client_secret": client_secret, "redirect_uri": KICK_REDIRECT,
                                 "code_verifier": verifier, "code": code}, method="POST")
    if not tok or "access_token" not in tok:
        raise AuthError("token")
    return tok


def kick_user(token, get=http):
    data = get(KICK_USER, headers={"Authorization": f"Bearer {token}"}) or {}
    users = data.get("data") or []
    return users[0] if users else {}


def kick_login(client_id, client_secret, open_url, cancel, page=b"", post=http):
    """Parcours complet (hors de l'interface) : ouvre le navigateur, attend le retour, échange le code."""
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(16)
    ready = threading.Event()
    box = {}

    def serve():
        try:
            box["code"] = wait_for_code(state, cancel, page=page)
        except Exception as e:
            box["error"] = e
        ready.set()

    threading.Thread(target=serve, daemon=True).start()
    time.sleep(0.2)
    open_url(kick_authorize_url(client_id, challenge, state))
    ready.wait()
    if "error" in box:
        raise box["error"]
    tok = kick_exchange(client_id, client_secret, box["code"], verifier, post=post)
    user = {}
    try:
        user = kick_user(tok["access_token"], get=post)
    except Exception as e:  # le nom du compte n'est qu'informatif
        log.info("Kick : profil illisible (%s)", e)
    return {"access_token": tok["access_token"], "refresh_token": tok.get("refresh_token", ""),
            "expires_at": time.time() + int(tok.get("expires_in") or 3600),
            "login": user.get("name") or "", "user_id": str(user.get("user_id") or "")}


def kick_refresh(account, post=http):
    tok = post(KICK_TOKEN, form={"grant_type": "refresh_token", "client_id": account["client_id"],
                                 "client_secret": account["client_secret"],
                                 "refresh_token": account["refresh_token"]}, method="POST")
    return dict(account, access_token=tok["access_token"], refresh_token=tok.get("refresh_token",
                                                                                  account["refresh_token"]),
                expires_at=time.time() + int(tok.get("expires_in") or 3600))
