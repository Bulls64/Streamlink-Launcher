"""Protection des jetons enregistrés dans chat.json.

Sous Windows, chiffrés avec DPAPI (CryptProtectData) : lisibles seulement par ce compte Windows, sur ce PC.
Ailleurs, gardés tels quels (le fichier est dans le dossier personnel de l'utilisateur).
"""
import base64
import ctypes
import logging
import os

log = logging.getLogger("streamlink_launcher")

PREFIX = "dpapi:"
SECRET_KEYS = ("access_token", "refresh_token", "client_secret")


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _call(func, data):
    blob_in = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
    blob_out = _Blob()
    if not func(ctypes.byref(blob_in), None, None, None, None, 0x1, ctypes.byref(blob_out)):  # UI_FORBIDDEN
        raise OSError("DPAPI")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def protect(value):
    if os.name != "nt" or not value or value.startswith(PREFIX):
        return value
    try:
        return PREFIX + base64.b64encode(_call(ctypes.windll.crypt32.CryptProtectData, value.encode())).decode()
    except (OSError, AttributeError) as e:
        log.info("DPAPI indisponible : %s", e)
        return value


def unprotect(value):
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return value
    if os.name != "nt":
        return ""
    try:
        return _call(ctypes.windll.crypt32.CryptUnprotectData, base64.b64decode(value[len(PREFIX):])).decode()
    except (OSError, ValueError, AttributeError) as e:
        log.info("Jeton illisible (autre PC ou autre compte ?) : %s", e)
        return ""


def seal(accounts):
    return {p: {k: (protect(v) if k in SECRET_KEYS and isinstance(v, str) else v) for k, v in acc.items()}
            for p, acc in accounts.items()}


def unseal(accounts):
    return {p: {k: (unprotect(v) if k in SECRET_KEYS else v) for k, v in acc.items()}
            for p, acc in accounts.items() if isinstance(acc, dict)}
