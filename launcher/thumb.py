"""Aperçus des streams en direct : image JPEG téléchargée -> PNG mis à l'échelle et arrondi,
prêt pour tk.PhotoImage (Tk 8.6 ne lit ni JPEG ni ne redimensionne proprement).

Le décodage passe par GDI+ (inclus dans Windows, appelé via ctypes : aucune dépendance).
Ailleurs, decode_scaled() renvoie None et la carte affiche un aperçu de remplacement.
Tout ici peut tourner hors de l'interface (thread) : seul PhotoImage(data=...) se fait dans Tk.
"""
import logging
import os
import struct
import threading
import zlib

log = logging.getLogger("streamlink_launcher")

_SAMPLES = (0.125, 0.375, 0.625, 0.875)  # suréchantillonnage 4x4 des pixels des coins


# ---------------------
# PNG et coins arrondis (pur Python)
# ---------------------
def png_rgba(width, height, rgba):
    """Encode des pixels RGBA (octets, ligne par ligne) en PNG."""
    row = width * 4
    raw = b"".join(b"\0" + bytes(rgba[y * row:(y + 1) * row]) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _coverage(r):
    """Part de chaque pixel d'un coin (r x r, coin haut-gauche) située dans l'arrondi : 0..16."""
    table = []
    for j in range(r):
        line = []
        for i in range(r):
            n = 0
            for sy in _SAMPLES:
                dy = r - (j + sy)
                for sx in _SAMPLES:
                    dx = r - (i + sx)
                    if dx <= 0 or dy <= 0 or dx * dx + dy * dy <= r * r:
                        n += 1
            line.append(n)
        table.append(line)
    return table


def round_corners(rgba, width, height, radius):
    """Rend les quatre coins transparents (bord lissé). Modifie le bytearray `rgba` sur place."""
    r = min(int(radius), width // 2, height // 2)
    if r <= 0:
        return rgba
    cov = _coverage(r)
    for j in range(r):
        for i in range(r):
            n = cov[j][i]
            if n == 16:
                continue
            for x, y in ((i, j), (width - 1 - i, j), (i, height - 1 - j), (width - 1 - i, height - 1 - j)):
                k = (y * width + x) * 4 + 3
                rgba[k] = rgba[k] * n // 16
    return rgba


def bgra_to_rgba(buf, width, height, stride):
    """Pixels GDI+ (B, G, R, A par pixel, `stride` octets par ligne) -> RGBA compact."""
    row = width * 4
    if stride != row:
        buf = b"".join(buf[y * stride:y * stride + row] for y in range(height))
    out = bytearray(buf)
    out[0::4], out[2::4] = buf[2::4], buf[0::4]
    return out


def cover_box(src_w, src_h, dst_w, dst_h):
    """Zone de l'image source à garder pour remplir dst sans déformer (recadrage centré)."""
    if src_w * dst_h > dst_w * src_h:              # source plus large : on rogne les côtés
        w = max(1, round(src_h * dst_w / dst_h))
        return (src_w - w) // 2, 0, w, src_h
    h = max(1, round(src_w * dst_h / dst_w))       # source plus haute : on rogne en haut et en bas
    return 0, (src_h - h) // 2, src_w, h


def render(data, width, height, radius):
    """JPEG/PNG (octets) -> PNG RGBA de width x height aux coins arrondis, ou None si illisible."""
    if not data or width < 8 or height < 8:
        return None
    try:
        rgba = decode_scaled(data, width, height)
    except OSError as e:          # image abîmée ou format inconnu : la carte garde son fond de remplacement
        log.info("Aperçu illisible : %s", e)
        return None
    except Exception:
        log.exception("Aperçu illisible")
        return None
    if rgba is None or len(rgba) != width * height * 4:
        return None
    return png_rgba(width, height, round_corners(bytearray(rgba), width, height, radius))


# ---------------------
# Décodage (GDI+ sous Windows)
# ---------------------
if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _VP = ctypes.c_void_p
    PixelFormat32bppARGB = 0x26200A
    UnitPixel = 2
    InterpolationModeHighQualityBicubic = 7
    PixelOffsetModeHighQuality = 2
    WrapModeTileFlipXY = 3
    ImageLockModeRead = 1

    class _StartupInput(ctypes.Structure):
        _fields_ = [("GdiplusVersion", ctypes.c_uint32), ("DebugEventCallback", _VP),
                    ("SuppressBackgroundThread", wintypes.BOOL), ("SuppressExternalCodecs", wintypes.BOOL)]

    class _Rect(ctypes.Structure):
        _fields_ = [("X", ctypes.c_int), ("Y", ctypes.c_int), ("Width", ctypes.c_int), ("Height", ctypes.c_int)]

    class _BitmapData(ctypes.Structure):
        _fields_ = [("Width", ctypes.c_uint), ("Height", ctypes.c_uint), ("Stride", ctypes.c_int),
                    ("PixelFormat", ctypes.c_int), ("Scan0", _VP), ("Reserved", ctypes.c_size_t)]

    _gdip = ctypes.WinDLL("gdiplus")
    _shlwapi = ctypes.WinDLL("shlwapi")
    _shlwapi.SHCreateMemStream.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    _shlwapi.SHCreateMemStream.restype = _VP
    _P = ctypes.POINTER
    for _name, _args in {
        "GdiplusStartup": [_P(ctypes.c_size_t), _P(_StartupInput), _VP],
        "GdipCreateBitmapFromStream": [_VP, _P(_VP)],
        "GdipGetImageWidth": [_VP, _P(ctypes.c_uint)],
        "GdipGetImageHeight": [_VP, _P(ctypes.c_uint)],
        "GdipCreateBitmapFromScan0": [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, _VP, _P(_VP)],
        "GdipGetImageGraphicsContext": [_VP, _P(_VP)],
        "GdipSetInterpolationMode": [_VP, ctypes.c_int],
        "GdipSetPixelOffsetMode": [_VP, ctypes.c_int],
        "GdipCreateImageAttributes": [_P(_VP)],
        "GdipSetImageAttributesWrapMode": [_VP, ctypes.c_int, ctypes.c_uint32, wintypes.BOOL],
        "GdipDrawImageRectRectI": [_VP, _VP] + [ctypes.c_int] * 9 + [_VP, _VP, _VP],
        "GdipBitmapLockBits": [_VP, _P(_Rect), ctypes.c_uint, ctypes.c_int, _P(_BitmapData)],
        "GdipBitmapUnlockBits": [_VP, _P(_BitmapData)],
        "GdipDeleteGraphics": [_VP],
        "GdipDisposeImage": [_VP],
        "GdipDisposeImageAttributes": [_VP],
    }.items():
        _fn = getattr(_gdip, _name)
        _fn.argtypes, _fn.restype = _args, ctypes.c_int

    _lock = threading.Lock()
    _token = ctypes.c_size_t(0)

    def _check(status, what):
        if status != 0:
            raise OSError(f"{what}: GDI+ {status}")

    def _release(com):
        vtbl = ctypes.cast(com, _P(_P(_VP)))[0]
        ctypes.WINFUNCTYPE(ctypes.c_ulong, _VP)(vtbl[2])(com)

    def decode_scaled(data, width, height):
        """Décode l'image, la recadre et la met à l'échelle (bicubique) : pixels RGBA, ou None."""
        with _lock:
            if not _token.value:
                _check(_gdip.GdiplusStartup(ctypes.byref(_token), ctypes.byref(_StartupInput(1)), None), "startup")
            stream = _shlwapi.SHCreateMemStream(data, len(data))
            if not stream:
                return None
            src, dst, gfx, attrs = _VP(), _VP(), _VP(), _VP()
            try:
                _check(_gdip.GdipCreateBitmapFromStream(stream, ctypes.byref(src)), "stream")
                sw, sh = ctypes.c_uint(), ctypes.c_uint()
                _gdip.GdipGetImageWidth(src, ctypes.byref(sw))
                _gdip.GdipGetImageHeight(src, ctypes.byref(sh))
                if not sw.value or not sh.value:
                    return None
                sx, sy, cw, ch = cover_box(sw.value, sh.value, width, height)
                _check(_gdip.GdipCreateBitmapFromScan0(width, height, 0, PixelFormat32bppARGB, None,
                                                       ctypes.byref(dst)), "bitmap")
                _check(_gdip.GdipGetImageGraphicsContext(dst, ctypes.byref(gfx)), "graphics")
                _gdip.GdipSetInterpolationMode(gfx, InterpolationModeHighQualityBicubic)
                _gdip.GdipSetPixelOffsetMode(gfx, PixelOffsetModeHighQuality)
                _check(_gdip.GdipCreateImageAttributes(ctypes.byref(attrs)), "attributes")
                _gdip.GdipSetImageAttributesWrapMode(attrs, WrapModeTileFlipXY, 0, False)  # pas de halo au bord
                _check(_gdip.GdipDrawImageRectRectI(gfx, src, 0, 0, width, height, sx, sy, cw, ch, UnitPixel,
                                                    attrs, None, None), "draw")
                bd = _BitmapData()
                _check(_gdip.GdipBitmapLockBits(dst, ctypes.byref(_Rect(0, 0, width, height)), ImageLockModeRead,
                                                PixelFormat32bppARGB, ctypes.byref(bd)), "lock")
                try:
                    raw = ctypes.string_at(bd.Scan0, bd.Stride * height)
                    stride = bd.Stride
                finally:
                    _gdip.GdipBitmapUnlockBits(dst, ctypes.byref(bd))
                return bgra_to_rgba(raw, width, height, stride)
            finally:
                if attrs:
                    _gdip.GdipDisposeImageAttributes(attrs)
                if gfx:
                    _gdip.GdipDeleteGraphics(gfx)
                for img in (dst, src):
                    if img:
                        _gdip.GdipDisposeImage(img)
                _release(stream)

else:
    def decode_scaled(data, width, height):
        return None
