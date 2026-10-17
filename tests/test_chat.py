"""Tests de Streamlink Chat (chat/) : analyse des protocoles et connexions complètes contre de faux serveurs locaux.

Aucun accès à Internet : Twitch (IRC sur WebSocket), Kick (Centrifugo) et Steam (HTTP) sont imités ici.
"""
import base64
import hashlib
import http.server
import json
import os
import queue
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chat import auth, badges, common, config, emotes, instance, kick, steam, twitch, ws  # noqa: E402


# ---------------------
# Faux serveur WebSocket
# ---------------------
class FakeWSServer:
    """Serveur WebSocket minimal : handler(conn) reçoit un objet avec send(text), recv() -> texte ou None."""

    def __init__(self, handler):
        self.handler = handler
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.headers = []
        threading.Thread(target=self._accept, daemon=True).start()

    @property
    def url(self):
        return f"ws://127.0.0.1:{self.port}/chat"

    def _accept(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._serve, args=(c,), daemon=True).start()

    def _serve(self, c):
        data = b""
        while b"\r\n\r\n" not in data:
            data += c.recv(4096)
        head = data.decode()
        self.headers.append(head)
        key = next(line.split(":", 1)[1].strip() for line in head.split("\r\n")
                   if line.lower().startswith("sec-websocket-key"))
        accept = base64.b64encode(hashlib.sha1((key + ws.GUID).encode()).digest()).decode()
        c.sendall(f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                  f"Sec-WebSocket-Accept: {accept}\r\n\r\n".encode())
        conn = _ServerConn(c)
        try:
            self.handler(conn)
        except (OSError, ConnectionError):
            pass
        finally:
            c.close()

    def close(self):
        self.sock.close()


class _ServerConn:
    def __init__(self, sock):
        self.sock, self.buf = sock, b""

    def _exact(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text, opcode=1, fin=True):
        payload = text.encode() if isinstance(text, str) else text
        n = len(payload)
        head = bytes([(0x80 if fin else 0) | opcode])
        if n < 126:
            head += bytes([n])
        elif n < 65536:
            head += bytes([126]) + struct.pack("!H", n)
        else:
            head += bytes([127]) + struct.pack("!Q", n)
        self.sock.sendall(head + payload)

    def recv(self):
        while True:
            b1, b2 = self._exact(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._exact(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._exact(8))[0]
            assert b2 & 0x80, "un client WebSocket doit masquer ses trames"
            mask = self._exact(4)
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(self._exact(n)))
            op = b1 & 0x0F
            if op == 0x8:
                return None
            if op == 0xA:
                self.pongs = getattr(self, "pongs", 0) + 1
                continue
            return payload.decode()


def collect(q, kind, n=1, timeout=5):
    out, deadline = [], time.time() + timeout
    while len(out) < n and time.time() < deadline:
        try:
            ev = q.get(timeout=0.1)
        except queue.Empty:
            continue
        if ev[0] == kind:
            out.append(ev)
    return out


# ---------------------
# WebSocket
# ---------------------
class TestWebSocket(unittest.TestCase):
    def test_roundtrip_fragments_ping_close(self):
        def handler(c):
            msg = c.recv()
            c.send(b"", opcode=0x9)                     # ping : le client doit répondre seul
            c.send("éch", opcode=1, fin=False)            # message fragmenté
            c.send("o:" + msg, opcode=0, fin=True)
            c.send("x" * 70000)                          # longueur sur 8 octets
            time.sleep(0.2)
            c.send(struct.pack("!H", 1000) + b"bye", opcode=0x8)
        srv = FakeWSServer(handler)
        client = ws.WebSocket(srv.url).connect()
        client.send("bonjour")
        self.assertEqual(client.recv(), "écho:bonjour")
        self.assertEqual(len(client.recv()), 70000)
        with self.assertRaises(ws.ConnectionClosed) as cm:
            client.recv()
        self.assertEqual(cm.exception.code, 1000)
        srv.close()

    def test_timeout_mid_frame_keeps_stream_intact(self):
        def handler(c):
            frame = bytes([0x81, 5]) + b"hello"
            c.sock.sendall(frame[:3])          # trame coupée en deux, avec une pause
            time.sleep(0.6)
            c.sock.sendall(frame[3:])
            c.send("next")
            c.recv()
        srv = FakeWSServer(handler)
        client = ws.WebSocket(srv.url).connect()
        client.settimeout(0.2)
        got, deadline = [], time.time() + 5
        while len(got) < 2 and time.time() < deadline:
            try:
                got.append(client.recv())
            except socket.timeout:
                continue
        self.assertEqual(got, ["hello", "next"])
        client.close()
        srv.close()

    def test_origin_header(self):
        srv = FakeWSServer(lambda c: c.recv())
        ws.WebSocket(srv.url, origin="https://kick.com").connect().close()
        time.sleep(0.1)
        self.assertIn("Origin: https://kick.com", srv.headers[0])
        srv.close()

    def test_bad_handshake(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = sock.getsockname()[1]

        def serve():
            c, _ = sock.accept()
            c.recv(4096)
            c.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
            c.close()
        threading.Thread(target=serve, daemon=True).start()
        with self.assertRaises(ws.WebSocketError):
            ws.WebSocket(f"ws://127.0.0.1:{port}/").connect()
        sock.close()


# ---------------------
# Twitch
# ---------------------
class TestTwitchParsing(unittest.TestCase):
    def test_parse_line(self):
        tags, prefix, cmd, params = twitch.parse_line(
            "@badges=moderator/1,subscriber/24;color=#FF0000;display-name=Foo;emotes=25:6-10;id=abc;"
            "system-msg=a\\sb\\:c :foo!foo@foo.tmi.twitch.tv PRIVMSG #chan :hello Kappa :)")
        self.assertEqual(cmd, "PRIVMSG")
        self.assertEqual(params, ["#chan", "hello Kappa :)"])
        self.assertEqual(prefix.split("!")[0], "foo")
        self.assertEqual(tags["system-msg"], "a b;c")
        self.assertEqual(tags["display-name"], "Foo")
        self.assertEqual(twitch.parse_line("PING :tmi.twitch.tv")[2:], ("PING", ["tmi.twitch.tv"]))

    def test_badges(self):
        self.assertEqual(twitch.parse_badges("broadcaster/1,subscriber/3012,unknown/1"),
                         [("broadcaster", "Streamer"), ("subscriber", "Sub 12")])
        self.assertEqual(twitch.parse_badges(""), [])

    def test_emote_fragments(self):
        frags = twitch.emote_fragments("Kappa hi Kappa @bob www.x.com KEKW", "25:0-4,9-13",
                                       {"KEKW": "https://k/1x.png"})
        kinds = [f[0] for f in frags]
        self.assertEqual(kinds, ["emote", "text", "emote", "text", "mention", "text", "link", "text", "emote"])
        self.assertIn("/25/default/dark/1.0", frags[0][2])
        self.assertEqual(frags[-1], ("emote", "KEKW", "https://k/1x.png"))

    def test_emote_positions_with_emoji(self):
        frags = twitch.emote_fragments("🔥 Kappa", "25:2-6")
        self.assertEqual(frags[-1][1], "Kappa")

    def test_reply_prefix_removed(self):
        c = twitch.TwitchConnection(lambda e: None)
        tags = {"display-name": "Ann", "reply-parent-display-name": "Bob", "emotes": "25:5-9"}
        msg = c._privmsg(tags, "ann", "chan", "@Bob Kappa yes")
        self.assertEqual(msg.reply_to, "Bob")
        self.assertEqual(msg.text, "Kappa yes")
        self.assertEqual(msg.fragments[0][:2], ("emote", "Kappa"))

    def test_action_and_first(self):
        c = twitch.TwitchConnection(lambda e: None)
        msg = c._privmsg({"first-msg": "1", "tmi-sent-ts": "1700000000000"}, "x", "c", "\x01ACTION dances\x01")
        self.assertEqual((msg.kind, msg.text, msg.first, msg.ts), ("action", "dances", True, 1700000000.0))

    def test_full_session_against_fake_server(self):
        received = []

        def handler(c):
            while True:
                line = c.recv()
                if line is None:
                    return
                received.append(line)
                if line.startswith("JOIN"):
                    c.send(":tmi.twitch.tv 001 justinfan :Welcome\r\n"
                           "@room-id=1234 :tmi.twitch.tv ROOMSTATE #eslcs\r\n"
                           "@badges=moderator/1;color=#00FF00;display-name=Mod;id=m1;emotes= "
                           ":mod!mod@mod.tmi.twitch.tv PRIVMSG #eslcs :salut @someone\r\n"
                           "@target-msg-id=m1 :tmi.twitch.tv CLEARMSG #eslcs :salut\r\n"
                           ":tmi.twitch.tv CLEARCHAT #eslcs :baduser\r\n"
                           "PING :tmi.twitch.tv")
        srv = FakeWSServer(handler)
        q = queue.Queue()
        conn = twitch.TwitchConnection(q.put)
        conn.url = srv.url
        conn.channels.add("eslcs")
        conn.start()
        msgs = collect(q, "message")
        self.assertEqual(msgs[0][1].display_name, "Mod")
        self.assertEqual(msgs[0][1].badges, [("moderator", "Mod")])
        self.assertEqual(collect(q, "delete")[0][3], "m1")
        self.assertEqual(collect(q, "clear_user")[0][3], "baduser")
        time.sleep(0.3)
        self.assertTrue(any(r.startswith("PONG") for r in received))
        self.assertTrue(any(r.startswith("NICK justinfan") for r in received))
        self.assertIn("CAP REQ :twitch.tv/tags twitch.tv/commands", received)
        self.assertFalse(conn.can_send)  # anonyme
        conn.stop()
        srv.close()

    def test_authenticated_send_echo(self):
        received = []

        def handler(c):
            while True:
                line = c.recv()
                if line is None:
                    return
                received.append(line)
                if line.startswith("NICK"):
                    c.send(":tmi.twitch.tv 001 chris :Welcome")
                if line.startswith("JOIN"):
                    c.send("@color=#1E90FF;display-name=Chris :tmi.twitch.tv USERSTATE #eslcs")
        srv = FakeWSServer(handler)
        q = queue.Queue()
        conn = twitch.TwitchConnection(q.put, login="Chris", token="tok")
        conn.url = srv.url
        conn.start()
        deadline = time.time() + 5
        while not conn.can_send and time.time() < deadline:
            time.sleep(0.05)
        conn.join("eslcs")
        time.sleep(0.3)
        echo = conn.send_message("eslcs", "hello Kappa")
        self.assertEqual((echo.display_name, echo.color, echo.own), ("Chris", "#1E90FF", True))
        self.assertIsNone(conn.send_message("eslcs", "/ban someone"))
        time.sleep(0.3)
        self.assertIn("PASS oauth:tok", received)
        self.assertIn("PRIVMSG #eslcs :hello Kappa", received)
        conn.stop()
        srv.close()


# ---------------------
# Kick
# ---------------------
CHAT_EVENT = {"id": "k1", "chatroom_id": 668, "content": "hi [emote:37226:KEKW] there", "type": "message",
              "sender": {"id": 5, "username": "Foo", "slug": "foo",
                         "identity": {"color": "#FF9D00", "badges": [{"type": "moderator", "text": "Moderator"},
                                                                     {"type": "subscriber", "count": 3}]}}}


class TestKick(unittest.TestCase):
    def test_find_endpoints_and_token(self):
        data = {"data": {"endpoints": [{"provider": "pusher", "app_key": "abc", "cluster": "us2"},
                                       {"provider": "centrifugo", "mode": "websocket", "endpoint": "wss://x"}]}}
        eps = kick.find_endpoints(data)
        self.assertEqual([e["provider"] for e in eps], ["centrifugo", "pusher"])
        self.assertEqual(kick.find_token({"data": {"token": "jwt"}}), "jwt")
        self.assertIsNone(kick.find_token({"data": {}}))

    def test_chat_message(self):
        ch = kick.KickChannel(lambda e: None, "xqc")
        msg = ch.chat_message(CHAT_EVENT)
        self.assertEqual(msg.text, "hi KEKW there")
        self.assertEqual(msg.badges, [("moderator", "Mod"), ("subscriber", "Sub 3")])
        self.assertEqual(msg.fragments[1], ("emote", "KEKW", "https://files.kick.com/emotes/37226/fullsize"))

    def test_publication_string_and_object(self):
        q = queue.Queue()
        ch = kick.KickChannel(q.put, "xqc")
        ch._publication({"event": "App\\Events\\ChatMessageEvent", "data": json.dumps(CHAT_EVENT)})
        ch._publication(json.dumps({"event": "App\\Events\\MessageDeletedEvent", "data": {"message": {"id": "k1"}}}))
        ch._publication({"event": "App\\Events\\UserBannedEvent", "data": {"user": {"username": "Bad"}}})
        kinds = [q.get_nowait()[0] for _ in range(3)]
        self.assertEqual(kinds, ["message", "delete", "clear_user"])

    def test_centrifugo_session_against_fake_server(self):
        frames = []

        def handler(c):
            while True:
                text = c.recv()
                if text is None:
                    return
                for line in text.split("\n"):
                    obj = json.loads(line)
                    frames.append(obj)
                    if "connect" in obj:
                        c.send(json.dumps({"id": obj["id"], "connect": {"client": "c1", "ping": 25, "pong": True}}))
                    elif "subscribe" in obj:
                        c.send(json.dumps({"id": obj["id"], "subscribe": {}}))
                        if obj["subscribe"]["channel"].startswith("chatrooms."):
                            pub = {"push": {"channel": obj["subscribe"]["channel"], "pub": {"data": {
                                "event": "App\\Events\\ChatMessageEvent", "data": CHAT_EVENT}}}}
                            c.send("{}\n" + json.dumps(pub))
                    elif obj == {}:
                        frames.append("pong")
        srv = FakeWSServer(handler)
        q = queue.Queue()
        ch = kick.KickChannel(q.put, "xqc")
        ch.info = {"channel_id": 1, "chatroom_id": 668, "user_id": 5, "name": "xQc"}
        with mock.patch.object(kick, "http") as fake_http:
            fake_http.side_effect = lambda url, **kw: (
                {"data": {"provider": "centrifugo", "endpoint": srv.url}} if "chat/connection" in url
                else {"data": {"token": "jwt-token"}})
            threading.Thread(target=ch.run_once, daemon=True).start()
            msgs = collect(q, "message")
        self.assertEqual(msgs[0][1].display_name, "Foo")
        time.sleep(0.2)
        connect = next(f for f in frames if isinstance(f, dict) and "connect" in f)
        self.assertEqual(connect["connect"], {"name": "js", "token": "jwt-token"})
        subs = [f["subscribe"]["channel"] for f in frames if isinstance(f, dict) and "subscribe" in f]
        self.assertEqual(subs, ["chatrooms.668.v2", "channel.1"])
        self.assertIn("pong", frames)
        self.assertTrue(any("Origin: https://kick.com" in h for h in srv.headers))
        ch.stop()
        srv.close()

    def test_resolve_channel(self):
        payload = {"id": 1, "user_id": 5, "slug": "xqc", "user": {"username": "xQc"}, "chatroom": {"id": 668},
                   "livestream": {"id": 9}}
        with mock.patch.object(kick, "http", return_value=payload):
            info = kick.resolve_channel("xQc")
        self.assertEqual((info["chatroom_id"], info["name"], info["live"]), (668, "xQc", True))
        with mock.patch.object(kick, "http", side_effect=common.HttpError(403)):
            with self.assertRaises(kick.KickError) as cm:
                kick.resolve_channel("xqc")
        self.assertEqual(str(cm.exception), "blocked")

    def test_send_uses_official_api(self):
        mgr = kick.KickManager(lambda e: None, token="tok")
        ch = kick.KickChannel(lambda e: None, "xqc")
        ch.info = {"user_id": "5"}
        mgr.channels["xqc"] = ch
        calls = []
        mgr.send_message("xqc", "salut", http_func=lambda url, **kw: calls.append((url, kw)))
        url, kw = calls[0]
        self.assertEqual(url, kick.SEND_URL)
        self.assertEqual(kw["data"], {"broadcaster_user_id": 5, "content": "salut", "type": "user"})
        self.assertEqual(kw["headers"]["Authorization"], "Bearer tok")


# ---------------------
# Steam
# ---------------------
class TestSteam(unittest.TestCase):
    def test_find_steamid(self):
        page = '<div id="webui_config" data-broadcast="{&quot;steamid&quot;:&quot;76561198000000001&quot;}"></div>'
        self.assertEqual(steam.find_steamid(page), "76561198000000001")
        self.assertIsNone(steam.find_steamid("<html></html>"))

    def test_fragments_and_url(self):
        frags = steam.steam_fragments("gg :steamhappy: ok")
        self.assertEqual(frags[1][:2], ("emote", "steamhappy"))
        self.assertEqual(steam.chat_url("https://h/c?chat_id=%llu&start=%u", 42, 7), "https://h/c?chat_id=42&start=7")

    def test_poll_against_local_server(self):
        state = {"calls": 0}

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                p = self.path
                if p.startswith("/watch"):
                    body, extra = b"<html></html>", [("Set-Cookie", "sessionid=abc; Path=/")]
                elif p.startswith("/mpd"):
                    assert "sessionid=abc" in p
                    body, extra = json.dumps({"success": "ready", "broadcastid": "99", "title": "T"}).encode(), []
                elif p.startswith("/chatinfo"):
                    tpl = f"http://127.0.0.1:{self.server.server_port}/msgs?chat_id=%llu&start=%u"
                    body, extra = json.dumps({"success": 1, "chat_id": "5", "view_url_template": tpl}).encode(), []
                else:
                    state["calls"] += 1
                    body = json.dumps({"messages": [{"type": "chatmessage", "steamid": "1", "persona_name": "Gabe",
                                                     "msg": "hello :steamhappy:"}], "next_request": 10,
                                       "sleep": 2}).encode()
                    extra = []
                self.send_response(200)
                for k, v in extra:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass
        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}"
        q = queue.Queue()
        with mock.patch.multiple(steam, WATCH_URL=base + "/watch/{steamid}", MPD_URL=base + "/mpd",
                                 CHATINFO_URL=base + "/chatinfo"):
            ch = steam.SteamChannel(q.put, "76561198000000001").start()
            msgs = collect(q, "message")
            ch.stop()
        srv.shutdown()
        self.assertEqual(msgs[0][1].display_name, "Gabe")
        self.assertEqual(msgs[0][1].fragments[-1][:2], ("emote", "steamhappy"))


# ---------------------
# Commun, réglages, emotes, comptes
# ---------------------
class TestCommon(unittest.TestCase):
    def test_split_words(self):
        frags = common.split_words("a https://t.co/x, @Bob Pog", {"Pog": "u"})
        self.assertEqual([f[0] for f in frags], ["text", "link", "text", "mention", "text", "emote"])

    def test_mentions(self):
        frags = common.split_words("hey @Chris! ça va")
        self.assertTrue(common.mentions(frags, ["chris"]))
        self.assertTrue(common.mentions(common.split_words("chris tu es là"), ["Chris"]))
        self.assertFalse(common.mentions(common.split_words("christophe"), ["chris"]))
        self.assertTrue(common.mentions(common.split_words("finale ce soir"), [], ["finale"]))

    def test_readable_color(self):
        dark_bg, light_bg = "#1C1D21", "#FFFFFF"
        for color in ("#0000FF", "#000000", "#2E2E8A"):
            self.assertGreaterEqual(common.contrast(common.readable_color(color, dark_bg), dark_bg), 4.0)
        self.assertGreaterEqual(common.contrast(common.readable_color("#FFFF00", light_bg), light_bg), 4.0)
        self.assertIsNone(common.readable_color("", dark_bg))
        self.assertIn(common.default_color("someone"), common.DEFAULT_COLORS)


class TestConfig(unittest.TestCase):
    def test_parse_target(self):
        p = config.parse_target
        self.assertEqual(p("https://www.twitch.tv/ESLCS"), ("twitch", "eslcs"))
        self.assertEqual(p("twitch.tv/popout/eslcs/chat?popout="), ("twitch", "eslcs"))
        self.assertEqual(p("kick.com/xqc"), ("kick", "xqc"))
        self.assertEqual(p("https://steam.tv/dota2"), ("steamtv", "dota2"))
        self.assertEqual(p("https://steamcommunity.com/broadcast/watch/76561198000000001"),
                         ("steamtv", "76561198000000001"))
        self.assertEqual(p("kick:Trainwreckstv"), ("kick", "trainwreckstv"))
        self.assertEqual(p("eslcs", "kick"), ("kick", "eslcs"))
        self.assertEqual(p("#shroud"), ("twitch", "shroud"))
        self.assertIsNone(p("https://youtube.com/watch?v=x"))
        self.assertIsNone(p("twitch.tv/directory"))
        self.assertIsNone(p("bad name!"))
        self.assertIsNone(p(""))

    def test_load_sanitizes(self):
        d = Path(tempfile.mkdtemp())
        f = d / "chat.json"
        f.write_text(json.dumps({"tabs": [{"platform": "twitch", "channel": "a"}, {"platform": "x", "channel": "b"},
                                          "junk"], "font_size": 99, "accounts": {"twitch": "bad"}}), encoding="utf-8")
        with mock.patch.object(config, "CONFIG_FILE", f):
            cfg = config.load()
        self.assertEqual(cfg["tabs"], [{"platform": "twitch", "channel": "a"}])
        self.assertEqual(cfg["font_size"], 14)
        self.assertEqual(cfg["accounts"]["twitch"], {})


class TestEmotes(unittest.TestCase):
    def test_providers(self):
        self.assertEqual(emotes.bttv_list([{"id": "a", "code": "catJAM", "imageType": "gif"},
                                           {"id": "b", "code": "OMEGALUL", "imageType": "png"}]),
                         {"catJAM": "https://cdn.betterttv.net/emote/a/1x.gif",
                          "OMEGALUL": "https://cdn.betterttv.net/emote/b/1x.png"})
        self.assertEqual(emotes.ffz_sets({"3": {"emoticons": [{"name": "LUL", "urls": {"1": "//cdn.ffz/1"}}]}}),
                         {"LUL": "https://cdn.ffz/1"})
        stv = [{"name": "peepoHey", "data": {"host": {"url": "//cdn.7tv.app/emote/x",
                                                      "files": [{"name": "1x.webp"}, {"name": "1x.png"}]}}},
               {"name": "webpOnly", "data": {"host": {"url": "//cdn", "files": [{"name": "1x.webp"}]}}}]
        self.assertEqual(emotes.stv_list(stv), {"peepoHey": "https://cdn.7tv.app/emote/x/1x.png"})

    def test_fetch_tolerates_errors(self):
        def get(url, **kw):
            if "betterttv" in url:
                raise OSError("down")
            if "frankerfacez" in url:
                return {"default_sets": [3], "sets": {"3": {"emoticons": [{"name": "LUL", "urls": {"1": "u"}}]},
                                                      "4": {"emoticons": [{"name": "X", "urls": {"1": "v"}}]}}}
            return {"emotes": []}
        self.assertEqual(emotes.fetch_global(("bttv", "ffz", "7tv"), get=get), {"LUL": "u"})

    def test_image_kind_and_loader_cache(self):
        png = badges.badge_png("vip", 8)
        self.assertEqual(emotes.image_kind(png), "png")
        self.assertIsNone(emotes.image_kind(b"RIFF....WEBP"))
        d = Path(tempfile.mkdtemp())
        calls = []

        def get(url, **kw):
            calls.append(url)
            return png
        loader = emotes.ImageLoader(d, get=get)
        done = queue.Queue()
        loader.request("https://e/1", lambda u, data: done.put(data))
        self.assertEqual(done.get(timeout=5), png)
        loader.request("https://e/1", lambda u, data: done.put(data))
        self.assertEqual(done.get(timeout=5), png)
        self.assertEqual(len(calls), 1)  # deuxième fois : cache disque
        loader.shutdown()


class TestBadges(unittest.TestCase):
    def test_png(self):
        data = badges.badge_png("moderator", 18)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", data[16:24]), (18, 18))


class TestAuth(unittest.TestCase):
    def test_pkce(self):
        verifier, challenge = auth.pkce_pair()
        expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        self.assertEqual(challenge, expected)
        url = auth.kick_authorize_url("cid", challenge, "st")
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("redirect_uri=http%3A%2F%2Flocalhost%3A48125%2Fcallback", url)

    def test_twitch_device_poll(self):
        answers = [common.HttpError(400, '{"message":"authorization_pending"}'),
                   {"access_token": "at", "refresh_token": "rt"}, {"login": "chris", "user_id": "1"}]

        def post(url, **kw):
            a = answers.pop(0)
            if isinstance(a, Exception):
                raise a
            return a
        result = auth.twitch_device_poll("cid", {"device_code": "d", "interval": 1}, threading.Event(), post=post,
                                         sleep=lambda s: None)
        self.assertEqual(result, {"access_token": "at", "refresh_token": "rt", "login": "chris", "user_id": "1"})

    def test_local_redirect_server(self):
        cancel = threading.Event()
        port = _free_port()
        box = {}
        t = threading.Thread(target=lambda: box.update(code=auth.wait_for_code("st", cancel, port=port, timeout=5)))
        t.start()
        time.sleep(0.3)
        import urllib.request
        urllib.request.urlopen(f"http://127.0.0.1:{port}/callback?code=abc&state=st", timeout=5).read()
        t.join(5)
        self.assertEqual(box["code"], "abc")


class TestInstance(unittest.TestCase):
    def test_forward(self):
        port = _free_port()
        got = queue.Queue()
        srv = instance.serve(got.put, port=port)
        self.assertTrue(instance.forward([("twitch", "eslcs")], port=port))
        self.assertEqual(got.get(timeout=3), [("twitch", "eslcs")])
        instance.stop(srv)
        time.sleep(0.1)
        self.assertFalse(instance.forward([], port=port))


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    unittest.main()
