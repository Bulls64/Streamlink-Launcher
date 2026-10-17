"""Badges dessinés (petites icônes PNG générées, sans fichier ni dépendance) : un carré arrondi coloré et un
pictogramme blanc, comme dans les chats des plateformes."""
import base64
import math
import struct
import zlib

COLORS = {
    "broadcaster": "#E91916", "moderator": "#00AD03", "vip": "#E005B9", "founder": "#8C43F6",
    "verified": "#9147FF", "staff": "#4B4B4B", "prime": "#0E9DD9", "turbo": "#59399A", "artist": "#1E69FF",
    "og": "#D79B00", "gifter": "#C4314B",
}


def _star(cx, cy, r1, r2, n=5, rot=-math.pi / 2):
    return [(cx + math.cos(rot + k * math.pi / n) * (r1 if k % 2 == 0 else r2),
             cy + math.sin(rot + k * math.pi / n) * (r1 if k % 2 == 0 else r2)) for k in range(2 * n)]


def _thick_line(x0, y0, x1, y1, w):
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1
    ox, oy = -dy / n * w / 2, dx / n * w / 2
    return [(x0 + ox, y0 + oy), (x1 + ox, y1 + oy), (x1 - ox, y1 - oy), (x0 - ox, y0 - oy)]


# Pictogrammes en coordonnées 0..1 : liste de polygones
GLYPHS = {
    "broadcaster": [[(0.2, 0.32), (0.62, 0.32), (0.62, 0.68), (0.2, 0.68)], [(0.62, 0.5), (0.82, 0.34), (0.82, 0.66)]],
    "moderator": [_thick_line(0.28, 0.72, 0.74, 0.26, 0.13), _thick_line(0.22, 0.56, 0.44, 0.78, 0.11)],
    "vip": [[(0.5, 0.2), (0.8, 0.46), (0.5, 0.8), (0.2, 0.46)]],
    "subscriber": [_star(0.5, 0.53, 0.33, 0.14)],
    "founder": [_star(0.5, 0.53, 0.33, 0.14)],
    "verified": [_thick_line(0.24, 0.52, 0.42, 0.7, 0.13), _thick_line(0.38, 0.7, 0.76, 0.3, 0.13)],
    "staff": [[(0.5, 0.18), (0.78, 0.3), (0.74, 0.6), (0.5, 0.82), (0.26, 0.6), (0.22, 0.3)]],
    "prime": [[(0.2, 0.7), (0.22, 0.32), (0.38, 0.48), (0.5, 0.26), (0.62, 0.48), (0.78, 0.32), (0.8, 0.7)]],
    "og": [[(0.2, 0.7), (0.22, 0.32), (0.38, 0.48), (0.5, 0.26), (0.62, 0.48), (0.78, 0.32), (0.8, 0.7)]],
    "turbo": [[(0.56, 0.16), (0.26, 0.56), (0.46, 0.56), (0.4, 0.84), (0.74, 0.42), (0.54, 0.42)]],
    "artist": [_thick_line(0.3, 0.72, 0.72, 0.3, 0.16)],
    "gifter": [[(0.22, 0.42), (0.78, 0.42), (0.78, 0.78), (0.22, 0.78)], [(0.18, 0.3), (0.82, 0.3), (0.82, 0.42),
                                                                         (0.18, 0.42)]],
}


def _inside(poly, x, y):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _png(w, h, rows):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def badge_png(kind, size, color=None, fg="#FFFFFF"):
    """PNG RGBA (octets) du badge, size x size pixels."""
    color = color or COLORS.get(kind, "#6B7280")
    br, bgc, bb = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    fr, fgc, fb = (int(fg[i:i + 2], 16) for i in (1, 3, 5))
    polys = GLYPHS.get(kind, [[(0.35, 0.35), (0.65, 0.35), (0.65, 0.65), (0.35, 0.65)]])
    rad = 0.22
    samples = [(i + 0.5) / 4 for i in range(4)]
    rows = []
    for py in range(size):
        row = []
        for px_ in range(size):
            cover = glyph = 0
            for sy in samples:
                for sx in samples:
                    x, y = (px_ + sx) / size, (py + sy) / size
                    # carré arrondi
                    dx = max(rad - x, 0, x - (1 - rad))
                    dy = max(rad - y, 0, y - (1 - rad))
                    if dx * dx + dy * dy <= rad * rad:
                        cover += 1
                        if any(_inside(p, x, y) for p in polys):
                            glyph += 1
            a = cover / 16
            t = glyph / cover if cover else 0
            row += [round(br + (fr - br) * t), round(bgc + (fgc - bgc) * t), round(bb + (fb - bb) * t), round(255 * a)]
        rows.append(row)
    return _png(size, size, rows)


def badge_b64(kind, size, color=None, fg="#FFFFFF"):
    return base64.b64encode(badge_png(kind, size, color, fg))
