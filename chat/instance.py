"""Instance unique de Streamlink Chat : une seconde ouverture transmet ses chats à la fenêtre déjà ouverte
(petit serveur local sur 127.0.0.1, accessible seulement depuis cette machine)."""
import json
import logging
import socket
import threading

log = logging.getLogger("streamlink_launcher")

PORT = 48124
MAGIC = "streamlink-chat/1"
_server = None


def forward(targets, port=PORT, timeout=1.5):
    """Vrai si une instance tourne déjà (elle a reçu les chats à ouvrir)."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.sendall((json.dumps({"magic": MAGIC, "open": [list(t) for t in targets]}) + "\n").encode())
            s.settimeout(timeout)
            return s.recv(16).startswith(b"ok")
    except OSError:
        return False


def serve(on_open, port=PORT):
    global _server
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(4)
    except OSError as e:
        log.info("Instance unique indisponible : %s", e)
        return None
    _server = srv

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            if srv.fileno() == -1:
                conn.close()
                return
            with conn:
                try:
                    conn.settimeout(2)
                    data = b""
                    while not data.endswith(b"\n") and len(data) < 65536:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                    msg = json.loads(data.decode("utf-8"))
                    if msg.get("magic") != MAGIC:
                        continue
                    targets = [tuple(t) for t in msg.get("open") or [] if isinstance(t, list) and len(t) == 2]
                    conn.sendall(b"ok")
                    on_open(targets)
                except (OSError, ValueError):
                    pass
    threading.Thread(target=loop, daemon=True, name="chat-instance").start()
    return srv


def stop(srv=None):
    global _server
    srv = srv or _server
    if srv is not None:
        try:
            srv.shutdown(socket.SHUT_RDWR)  # réveille accept() dans l'autre fil
        except OSError:
            pass
        try:
            srv.close()
        except OSError:
            pass
    if srv is _server:
        _server = None
