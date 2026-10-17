"""Client WebSocket minimal (RFC 6455), bibliothèque standard uniquement.

Suffisant pour les chats : messages texte, fragmentation, ping/pong, fermeture propre, proxy HTTP(S)
(variables d'environnement / réglages Windows via urllib). Pas d'extension (pas de compression).
"""
import base64
import hashlib
import os
import socket
import ssl
import struct
import threading
import urllib.parse
import urllib.request

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36"
MAX_MESSAGE = 4 * 1024 * 1024  # un message de chat ne dépasse jamais ça


class WebSocketError(Exception):
    pass


class ConnectionClosed(WebSocketError):
    def __init__(self, code=None, reason=""):
        super().__init__(f"connexion fermée ({code}) {reason}".strip())
        self.code, self.reason = code, reason


def _proxy_for(scheme, host):
    """Proxy à utiliser pour cet hôte (même logique que urllib : variables d'environnement, registre Windows)."""
    try:
        if urllib.request.proxy_bypass(host):
            return None
    except Exception:  # proxy_bypass peut échouer sur des configurations Windows exotiques
        return None
    proxies = urllib.request.getproxies()
    url = proxies.get("https" if scheme == "wss" else "http")
    return urllib.parse.urlsplit(url if "://" in (url or "") else f"http://{url}") if url else None


class WebSocket:
    def __init__(self, url, headers=None, origin=None, timeout=15):
        self.url, self.headers, self.origin, self.timeout = url, dict(headers or {}), origin, timeout
        self.sock = None
        self._buf = b""
        self._parts, self._op = [], 0x1
        self._send_lock = threading.Lock()
        self.closed = False

    # --- connexion
    def connect(self):
        u = urllib.parse.urlsplit(self.url)
        if u.scheme not in ("ws", "wss"):
            raise WebSocketError(f"adresse non WebSocket : {self.url}")
        secure = u.scheme == "wss"
        host, port = u.hostname, u.port or (443 if secure else 80)
        proxy = _proxy_for(u.scheme, host)
        if proxy:
            sock = socket.create_connection((proxy.hostname, proxy.port or 8080), timeout=self.timeout)
            self._tunnel(sock, host, port, proxy)
        else:
            sock = socket.create_connection((host, port), timeout=self.timeout)
        if secure:
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        self.sock = sock
        key = base64.b64encode(os.urandom(16)).decode()
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        default_port = 443 if secure else 80
        lines = [f"GET {path} HTTP/1.1", f"Host: {host}" + ("" if port == default_port else f":{port}"),
                 "Upgrade: websocket", "Connection: Upgrade", f"Sec-WebSocket-Key: {key}",
                 "Sec-WebSocket-Version: 13", f"User-Agent: {USER_AGENT}"]
        if self.origin:
            lines.append(f"Origin: {self.origin}")
        lines += [f"{k}: {v}" for k, v in self.headers.items()]
        sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
        status, headers = self._read_http_head()
        if " 101 " not in status + " ":
            raise WebSocketError(f"poignée de main refusée : {status}")
        expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        if headers.get("sec-websocket-accept") != expected:
            raise WebSocketError("poignée de main invalide (Sec-WebSocket-Accept)")
        return self

    def _tunnel(self, sock, host, port, proxy):
        req = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n"
        if proxy.username:
            cred = base64.b64encode(f"{urllib.parse.unquote(proxy.username)}:"
                                    f"{urllib.parse.unquote(proxy.password or '')}".encode()).decode()
            req += f"Proxy-Authorization: Basic {cred}\r\n"
        sock.sendall((req + "\r\n").encode())
        self.sock = sock
        status, _ = self._read_http_head()
        if " 200 " not in status + " ":
            raise WebSocketError(f"proxy : {status}")

    def _read_http_head(self):
        while b"\r\n\r\n" not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketError("connexion fermée pendant la poignée de main")
            self._buf += chunk
            if len(self._buf) > 65536:
                raise WebSocketError("en-têtes trop longs")
        head, self._buf = self._buf.split(b"\r\n\r\n", 1)
        lines = head.decode("latin-1").split("\r\n")
        headers = {}
        for line in lines[1:]:
            k, _, v = line.partition(":")
            headers[k.strip().lower()] = v.strip()
        return lines[0], headers

    # --- trames
    def _read_more(self):
        chunk = self.sock.recv(65536)  # socket.timeout possible : le tampon reste intact
        if not chunk:
            raise ConnectionClosed(1006, "connexion interrompue")
        self._buf += chunk

    def _parse(self):
        """Trame complète en tête du tampon -> (fin, opcode, données), retirée du tampon ; None si incomplète.
        Rien n'est consommé tant que la trame n'est pas entière (un délai d'attente ne la coupe jamais)."""
        buf = self._buf
        if len(buf) < 2:
            return None
        b1, b2 = buf[0], buf[1]
        n, i = b2 & 0x7F, 2
        if n == 126:
            if len(buf) < 4:
                return None
            n, i = struct.unpack("!H", buf[2:4])[0], 4
        elif n == 127:
            if len(buf) < 10:
                return None
            n, i = struct.unpack("!Q", buf[2:10])[0], 10
        if n > MAX_MESSAGE:
            raise WebSocketError("message trop long")
        mask = None
        if b2 & 0x80:
            if len(buf) < i + 4:
                return None
            mask, i = buf[i:i + 4], i + 4
        if len(buf) < i + n:
            return None
        payload = buf[i:i + n]
        self._buf = buf[i + n:]
        if mask:
            payload = bytes(b ^ mask[k % 4] for k, b in enumerate(payload))
        return b1 & 0x80, b1 & 0x0F, payload

    def _send_frame(self, opcode, payload):
        header = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", n)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        with self._send_lock:
            if self.sock is None:
                raise ConnectionClosed(1006, "non connecté")
            self.sock.sendall(header + mask + masked)

    def send(self, text):
        self._send_frame(0x1, text.encode("utf-8"))

    def recv(self):
        """Message texte suivant (str). Répond seul aux pings. Lève ConnectionClosed à la fermeture,
        socket.timeout si rien n'arrive dans le délai (la connexion reste utilisable)."""
        while True:
            frame = self._parse()
            if frame is None:
                self._read_more()
                continue
            fin, op, payload = frame
            if op == 0x9:      # ping -> pong
                self._send_frame(0xA, payload)
                continue
            if op == 0xA:      # pong
                continue
            if op == 0x8:      # fermeture
                code = struct.unpack("!H", payload[:2])[0] if len(payload) >= 2 else None
                try:
                    self._send_frame(0x8, payload[:2])
                except OSError:
                    pass
                self.close()
                raise ConnectionClosed(code, payload[2:].decode("utf-8", "replace"))
            if op in (0x1, 0x2):
                self._op, self._parts = op, [payload]
            elif op == 0x0:
                self._parts.append(payload)
            if fin:
                data, self._parts = b"".join(self._parts), []
                return data.decode("utf-8", "replace") if self._op == 0x1 else data

    def settimeout(self, seconds):
        if self.sock is not None:
            self.sock.settimeout(seconds)

    def close(self):
        self.closed = True
        sock, self.sock = self.sock, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
